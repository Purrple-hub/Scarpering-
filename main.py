from __future__ import annotations

import argparse
import asyncio
import sys

from crawler.package_manager import ensure_dependencies

ensure_dependencies()

from crawler.settings import Settings  # noqa: E402
from crawler.signals import SignalBridge  # noqa: E402


def run_headless(settings: Settings) -> None:
    from crawler.crawler import UnifiedAsyncCrawler

    bridge = SignalBridge()
    crawler = UnifiedAsyncCrawler(settings, bridge)
    asyncio.run(crawler.crawl())


def run_gui(settings: Settings) -> None:
    from PyQt6.QtWidgets import QApplication

    from gui.main_window import MainWindow

    app = QApplication(sys.argv)
    window = MainWindow()
    window.settings = settings
    window.show()
    sys.exit(app.exec())


def main() -> None:
    parser = argparse.ArgumentParser(description="Advanced async web crawler")
    parser.add_argument("--headless", action="store_true", help="Run without GUI")
    parser.add_argument("--config", type=str, help="Path to JSON config file")
    parser.add_argument("--url", nargs="+", help="Seed URL(s)")
    parser.add_argument("--max-pages", type=int, help="Max pages to crawl")
    parser.add_argument("--output-dir", type=str, help="Output directory")
    args = parser.parse_args()

    settings = Settings.from_config(args.config)
    if args.url:
        settings.seed_urls = args.url
    if args.max_pages:
        settings.max_pages = args.max_pages
    if args.output_dir:
        settings.output_dir = args.output_dir

    if args.headless or args.url:
        if not settings.seed_urls:
            parser.error("--url is required in headless mode or when URLs are provided")
        run_headless(settings)
    else:
        run_gui(settings)


if __name__ == "__main__":
    main()