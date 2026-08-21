from __future__ import annotations

import asyncio
import re

from curl_cffi.requests import AsyncSession


class ProxyFetcher:
    def __init__(self, sources: list[str], timeout: float = 5.0) -> None:
        self.sources = sources
        self.timeout = timeout

    async def fetch(self) -> list[str]:
        proxies: set[str] = set()
        async with AsyncSession(verify=False) as session:
            for src in self.sources:
                try:
                    resp = await session.get(src, timeout=self.timeout)
                    text = resp.text
                    proxies.update(re.findall(r"\d{1,3}(?:\.\d{1,3}){3}:\d{2,5}", text))
                except Exception:
                    continue
        return list(proxies)

    async def validate(self, proxy: str, test_url: str = "http://example.com") -> bool:
        try:
            async with AsyncSession(proxy=f"http://{proxy}", timeout=self.timeout, verify=False) as session:
                resp = await session.get(test_url)
                return resp.status_code < 400
        except Exception:
            return False


class ProxyManager:
    def __init__(self, fetcher: ProxyFetcher) -> None:
        self.fetcher = fetcher
        self.proxies: list[str] = []
        self.blacklist: set[str] = set()
        self.index = 0
        self.lock = asyncio.Lock()

    async def fetch_and_validate(self, limit: int = 10) -> None:
        raw = await self.fetcher.fetch()
        valid = []
        for proxy in raw:
            if len(valid) >= limit:
                break
            if proxy in self.blacklist:
                continue
            if await self.fetcher.validate(proxy):
                valid.append(proxy)
        self.proxies = valid
        self.index = 0

    async def get_proxy(self) -> str | None:
        async with self.lock:
            if not self.proxies:
                await self.fetch_and_validate()
            if not self.proxies:
                return None
            proxy = self.proxies[self.index % len(self.proxies)]
            self.index += 1
            return proxy

    def report_failure(self, proxy: str) -> None:
        self.blacklist.add(proxy)
        if proxy in self.proxies:
            self.proxies.remove(proxy)

    def report_success(self, proxy: str) -> None:
        pass