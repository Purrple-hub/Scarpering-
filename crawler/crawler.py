from __future__ import annotations

import asyncio
import gc
import hashlib
import io
import os
import re
import time
import zipfile
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

import psutil
from curl_cffi.requests import AsyncSession
from selectolax.parser import HTMLParser

from crawler.dedup import SmartDeduplicator
from crawler.discovery import extract_links_from_html, parse_sitemap
from crawler.domain_health import DomainHealthManager
from crawler.proxy import ProxyFetcher, ProxyManager
from crawler.quality import QualityScorer
from crawler.rate_limiter import AdaptiveRateLimiter
from crawler.storage import FileManager


class RequestError(Exception):
    pass


@dataclass
class CrawlStats:
    processed: int = 0
    errors: int = 0
    duplicates: int = 0
    queue_size: int = 0
    active_requests: int = 0
    start_time: float = 0.0

    def speed(self) -> float:
        elapsed = time.monotonic() - self.start_time
        return self.processed / elapsed if elapsed > 0 else 0.0


class UnifiedAsyncCrawler:
    def __init__(self, settings, bridge=None) -> None:
        self.settings = settings
        self.bridge = bridge
        self.stop_event = asyncio.Event()
        self.queue: asyncio.PriorityQueue[tuple[int, int, str]] = asyncio.PriorityQueue()
        self.sessions: dict[str, AsyncSession] = {}
        self.domain_health = DomainHealthManager()
        self.rate_limiter = AdaptiveRateLimiter(settings.base_delay, settings.memory_limit_mb)
        self.dedup = SmartDeduplicator(settings)
        self.quality = QualityScorer()
        self.storage = FileManager(settings)
        self.proxy_manager = None
        self.stats = CrawlStats(start_time=time.monotonic())
        self.active_requests = 0
        self.worker_tasks: list[asyncio.Task] = []
        self.monitor_task: asyncio.Task | None = None
        self.base_workers = settings.concurrency or max(4, (os.cpu_count() or 4) * 2)
        self.target_workers = self.base_workers
        self.sequence = 0

    def log(self, level: str, message: str) -> None:
        if self.bridge:
            self.bridge.console.emit(level, message)

    def emit_stats(self) -> None:
        if not self.bridge:
            return
        mem = psutil.virtual_memory()
        data = {
            "processed": self.stats.processed,
            "errors": self.stats.errors,
            "duplicates": self.stats.duplicates,
            "queue_size": self.queue.qsize(),
            "active_requests": self.active_requests,
            "speed": round(self.stats.speed(), 2),
            "memory_used_mb": round(mem.used / 1024 / 1024, 1),
            "memory_percent": mem.percent,
            "workers": len(self.worker_tasks),
        }
        self.bridge.stats.emit(data)

    def emit_page(self, page: dict) -> None:
        if self.bridge:
            self.bridge.page.emit(page)

    async def _init(self) -> None:
        await self.storage.init_sqlite()
        if self.settings.use_proxy:
            fetcher = ProxyFetcher(self.settings.proxy_sources, self.settings.timeout)
            self.proxy_manager = ProxyManager(fetcher)

    def _get_domain(self, url: str) -> str:
        return urlparse(url).netloc.lower()

    def normalize_url(self, url: str) -> str:
        url = url.strip()
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        parsed = urlparse(url)
        return parsed.geturl()

    async def get_session(self, domain: str) -> AsyncSession:
        if domain not in self.sessions:
            self.sessions[domain] = AsyncSession(
                impersonate="chrome124",
                verify=self.settings.ssl_verify,
                timeout=self.settings.timeout,
            )
        return self.sessions[domain]

    async def _fetch_text(self, url: str) -> str:
        domain = self._get_domain(url)
        session = await self.get_session(domain)
        resp = await session.get(
            url,
            timeout=self.settings.timeout,
            verify=self.settings.ssl_verify,
        )
        if resp.status_code >= 400:
            raise RequestError(f"HTTP {resp.status_code}")
        return resp.content.decode("utf-8", errors="ignore")

    def _is_allowed_domain(self, url: str) -> bool:
        if self.settings.follow_external:
            return True
        seed_domains = {self._get_domain(u) for u in self.settings.seed_urls}
        return self._get_domain(url) in seed_domains

    async def _fetch_sitemap_recursive(
        self,
        url: str,
        discovered: set[str],
        visited: set[str],
        depth: int = 0,
    ) -> None:
        if depth > 3 or url in visited:
            return
        visited.add(url)
        try:
            text = await self._fetch_text(url)
            page_urls, nested = parse_sitemap(text)
            for u in page_urls:
                if self._is_allowed_domain(u):
                    discovered.add(u)
            for nested_url in nested:
                await self._fetch_sitemap_recursive(
                    nested_url, discovered, visited, depth + 1
                )
        except Exception:
            # Non-fatal: skip broken sitemap and continue
            return

    async def _discover_sitemap_urls(self) -> set[str]:
        discovered: set[str] = set()
        visited: set[str] = set()

        for seed in self.settings.seed_urls:
            domain = self._get_domain(seed)
            sitemap_urls: list[str] = []

            # Try robots.txt first
            robots_url = f"https://{domain}/robots.txt"
            try:
                robots_text = await self._fetch_text(robots_url)
                sitemap_urls = re.findall(
                    r"(?im)^\s*Sitemap:\s*(\S+)", robots_text
                )
            except Exception:
                sitemap_urls = []

            # If robots.txt didn't expose any sitemap, try common location
            if not sitemap_urls:
                sitemap_urls = [f"https://{domain}/sitemap.xml"]

            for sm_url in sitemap_urls:
                await self._fetch_sitemap_recursive(
                    sm_url, discovered, visited
                )

        return discovered

    async def _fetch(self, url: str, domain: str) -> tuple[bytes, str]:
        proxy = None
        if self.settings.use_proxy and self.proxy_manager:
            proxy = await self.proxy_manager.get_proxy()
        last_error = None
        for attempt in range(self.settings.retries + 1):
            start = time.monotonic()
            try:
                session = await self.get_session(domain)
                kwargs = {"timeout": self.settings.timeout, "verify": self.settings.ssl_verify}
                if proxy:
                    kwargs["proxy"] = f"http://{proxy}"
                resp = await session.get(url, **kwargs)
                latency = time.monotonic() - start
                status = resp.status_code
                if status in (403, 429, 503):
                    self.domain_health.record_failure(domain, status)
                    raise RequestError(f"Blocked status {status}")
                if status >= 400:
                    raise RequestError(f"HTTP {status}")
                content = resp.content
                if len(content) > self.settings.max_page_size:
                    raise RequestError("Page too large")
                self.domain_health.record_success(domain)
                self.rate_limiter.record(domain, True, latency)
                if proxy and self.proxy_manager:
                    self.proxy_manager.report_success(proxy)
                content_type = resp.headers.get("content-type", "")
                return content, content_type
            except Exception as exc:
                last_error = exc
                if proxy and self.proxy_manager:
                    self.proxy_manager.report_failure(proxy)
                    proxy = None
                self.rate_limiter.record(domain, False, self.settings.timeout)
                if attempt < self.settings.retries:
                    await asyncio.sleep(self.settings.backoff_factor * (2 ** attempt))
                    continue
                self.domain_health.record_failure(domain, 0)
        raise RequestError(str(last_error or "Request failed"))

    def _parse_html(self, url: str, html: bytes, depth: int) -> dict | None:
        parser = HTMLParser(html)
        body = parser.body
        text = body.text(separator=" ", strip=True) if body else ""
        title_el = parser.css_first("title")
        title = title_el.text(strip=True) if title_el else ""
        headers = [h.text(strip=True) for h in parser.css("h1,h2,h3")]

        links = list(extract_links_from_html(parser, url))

        quality_score = self.quality.score(title, text, headers, len(links))
        content_hash = hashlib.sha256(html).hexdigest()
        domain = self._get_domain(url)
        return {
            "url": url,
            "title": title,
            "content": text[:5000],
            "quality_score": quality_score,
            "depth": depth,
            "domain": domain,
            "content_hash": content_hash,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "links": links,
        }

    async def _process_url(self, url: str, depth: int) -> None:
        domain = self._get_domain(url)
        if not self.domain_health.can_request(domain):
            self.stats.duplicates += 1
            return
        await self.rate_limiter.wait(domain)
        content, content_type = await self._fetch(url, domain)
        if url.lower().endswith(".zip") or "zip" in content_type:
            if self.settings.zip_extract:
                await self._process_zip(url, content, depth)
            return
        page = self._parse_html(url, content, depth)
        if page is None:
            return
        is_dup, reason = self.dedup.is_duplicate(url, page["content"], content.decode(errors="ignore"))
        if is_dup:
            self.stats.duplicates += 1
            return
        links = page.pop("links")
        await self.storage.add_page(page)
        self.stats.processed += 1
        self.emit_page(page)
        self.emit_stats()
        self.log("info", f"Crawled {url} depth={depth} quality={page['quality_score']}")
        self._enqueue_links(links, depth)

    async def _process_zip(self, url: str, content: bytes, depth: int) -> None:
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as zf:
                for name in zf.namelist():
                    if name.lower().endswith((".html", ".htm")):
                        html = zf.read(name)
                        fake_url = f"zip:{url}!{name}"
                        page = self._parse_html(fake_url, html, depth)
                        if page:
                            is_dup, _ = self.dedup.is_duplicate(fake_url, page["content"], html.decode(errors="ignore"))
                            if not is_dup:
                                links = page.pop("links")
                                await self.storage.add_page(page)
                                self.stats.processed += 1
                                self.emit_page(page)
                                self._enqueue_links(links, depth)
        except zipfile.BadZipFile:
            self.log("error", f"Bad zip from {url}")

    def _enqueue_links(self, links: list[str], current_depth: int) -> None:
        if current_depth >= self.settings.max_depth:
            return
        for link in links:
            domain = self._get_domain(link)
            if not self.settings.follow_external:
                seed_domains = {self._get_domain(u) for u in self.settings.seed_urls}
                if domain not in seed_domains:
                    continue
            if self.stop_event.is_set():
                break
            self.sequence += 1
            self.queue.put_nowait((current_depth + 1, self.sequence, link))

    async def _worker(self) -> None:
        while not self.stop_event.is_set():
            try:
                depth, _, url = await asyncio.wait_for(self.queue.get(), timeout=0.5)
            except asyncio.TimeoutError:
                continue
            self.active_requests += 1
            try:
                await self._process_url(url, depth)
            except Exception as exc:
                self.stats.errors += 1
                self.log("error", f"Error on {url}: {exc}")
            finally:
                self.active_requests -= 1
                self.queue.task_done()
                self.emit_stats()

    async def _monitor_workers(self) -> None:
        while not self.stop_event.is_set():
            await asyncio.sleep(5)
            qsize = self.queue.qsize()
            mem = psutil.virtual_memory().percent
            current = len(self.worker_tasks)
            if qsize > current * 5 and current < self.base_workers * 3 and mem < 85:
                additional = min(self.base_workers, max(1, qsize // 5))
                for _ in range(additional):
                    if current >= self.base_workers * 3:
                        break
                    task = asyncio.create_task(self._worker())
                    self.worker_tasks.append(task)
                    current += 1
                self.log("info", f"Scaled workers up to {current}")
            elif qsize < current and current > self.base_workers:
                remove = min(current - self.base_workers, 2)
                for _ in range(remove):
                    if not self.worker_tasks:
                        break
                    task = self.worker_tasks.pop()
                    task.cancel()
                self.log("info", f"Scaled workers down to {len(self.worker_tasks)}")
            self.emit_stats()

    async def crawl(self) -> None:
        self.stats.start_time = time.monotonic()
        await self._init()

        seed_urls = set(self.settings.seed_urls)
        if self.settings.use_sitemap:
            try:
                extra = await self._discover_sitemap_urls()
                seed_urls.update(extra)
                self.log(
                    "info",
                    f"Sitemap discovery found {len(extra)} additional URLs",
                )
            except Exception as exc:
                self.log("warning", f"Sitemap discovery failed: {exc}")

        for url in seed_urls:
            url = self.normalize_url(url)
            self.sequence += 1
            self.queue.put_nowait((0, self.sequence, url))

        self.worker_tasks = [
            asyncio.create_task(self._worker()) for _ in range(self.base_workers)
        ]
        self.monitor_task = asyncio.create_task(self._monitor_workers())
        self.log("info", f"Starting crawl with {self.base_workers} workers")
        try:
            while not self.stop_event.is_set():
                await asyncio.sleep(1)
                self.rate_limiter.set_queue_size(self.queue.qsize())
                if self.stats.processed >= self.settings.max_pages:
                    self.log("info", "Max pages reached, stopping")
                    self.stop_event.set()
                    break
                if self.queue.empty() and self.active_requests == 0:
                    await asyncio.sleep(2)
                    if self.queue.empty() and self.active_requests == 0:
                        self.log("info", "Queue drained, stopping")
                        self.stop_event.set()
                        break
                if self.stats.processed % self.settings.gc_interval == 0:
                    gc.collect()
                    if hasattr(gc, "freeze"):
                        pass
        finally:
            await self.queue.join()
            for task in self.worker_tasks:
                task.cancel()
            if self.monitor_task:
                self.monitor_task.cancel()
            await asyncio.gather(*self.worker_tasks, self.monitor_task, return_exceptions=True)
            await self.storage.flush_batch()
            for session in self.sessions.values():
                try:
                    await session.close()
                except Exception:
                    pass
            self.log("info", f"Crawl finished. Processed {self.stats.processed}, errors {self.stats.errors}")
            if self.bridge:
                self.bridge.finished.emit({"processed": self.stats.processed, "errors": self.stats.errors})