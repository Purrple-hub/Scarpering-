"""
Scarpering - Adaptive Web Crawler Package
"""

from .crawler import UnifiedAsyncCrawler
from .settings import Settings
from .dedup import Deduplicator
from .storage import StorageManager
from .rate_limiter import AdaptiveRateLimiter
from .proxy import ProxyManager

__version__ = "1.0.0"
__all__ = [
    "UnifiedAsyncCrawler",
    "Settings",
    "Deduplicator",
    "StorageManager",
    "AdaptiveRateLimiter",
    "ProxyManager",
]
