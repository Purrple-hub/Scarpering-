import asyncio

from PyQt6.QtCore import QThread

from crawler.crawler import UnifiedAsyncCrawler


class CrawlerWorker(QThread):
    def __init__(self, settings, bridge) -> None:
        super().__init__()
        self.settings = settings
        self.bridge = bridge
        self.crawler = None

    def run(self) -> None:
        try:
            self.crawler = UnifiedAsyncCrawler(self.settings, self.bridge)
            asyncio.run(self.crawler.crawl())
        except Exception as exc:
            self.bridge.console.emit("error", str(exc))
        finally:
            self.bridge.finished.emit({})

    def stop(self) -> None:
        if self.crawler:
            self.crawler.stop_event.set()