from __future__ import annotations

import json
import os
from dataclasses import dataclass, field


@dataclass
class Settings:
    seed_urls: list[str] = field(default_factory=list)
    max_depth: int = 3
    max_pages: int = 1000
    concurrency: int = 0
    timeout: float = 15.0
    retries: int = 3
    backoff_factor: float = 0.5
    base_delay: float = 0.1
    output_dir: str = "crawled_data"
    output_formats: list[str] = field(default_factory=lambda: ["jsonl", "sqlite"])
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
    follow_external: bool = False
    max_page_size: int = 5 * 1024 * 1024
    enable_dedup: bool = True
    near_dup_threshold: float = 0.85
    simhash_bits: int = 64
    minhash_perms: int = 128
    minhash_bands: int = 16
    lsh_max_docs: int = 5000
    use_proxy: bool = False
    proxy_sources: list[str] = field(default_factory=list)
    ssl_verify: bool = False
    batch_size: int = 50
    gc_interval: int = 100
    memory_limit_mb: int = 1024
    zip_extract: bool = True
    log_file: str = "crawler.log"
    headless: bool = False
    use_sitemap: bool = True   # <-- new

    @classmethod
    def from_config(cls, config_path: str | None = None) -> "Settings":
        s = cls()
        if config_path and os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for k, v in data.items():
                if hasattr(s, k):
                    setattr(s, k, v)
        for k, v in os.environ.items():
            if k.startswith("CRAWLER_"):
                key = k[8:].lower()
                if hasattr(s, key):
                    current = getattr(s, key)
                    if isinstance(current, bool):
                        setattr(s, key, v.lower() in ("1", "true", "yes"))
                    elif isinstance(current, int):
                        setattr(s, key, int(v))
                    elif isinstance(current, float):
                        setattr(s, key, float(v))
                    elif isinstance(current, list):
                        setattr(s, key, v.split(","))
                    else:
                        setattr(s, key, v)
        return s

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}