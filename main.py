#!/usr/bin/env python3
"""
Scarpering - Main entry point.
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

# Add this to ensure the current directory is on the path (if running from source)
# But the proper way is to install the package.
from crawler.crawler import UnifiedAsyncCrawler
from crawler.settings import Settings
from crawler.storage import StorageManager

# If you have GUI code:
try:
    from gui.main_window import MainWindow
    from PyQt6.QtWidgets import QApplication
    GUI_AVAILABLE = True
except ImportError:
    GUI_AVAILABLE = False


def main():
    """Parse arguments and run the crawler."""
    parser = argparse.ArgumentParser(description="Scarpering Web Crawler")
    parser.add_argument("--config", "-c", type=str, help="Path to JSON config file")
    parser.add_argument("--headless", "-H", action="store_true", help="Run in headless (CLI) mode")
    parser.add_argument("--gui", "-g", action="store_true", help="Launch GUI (if available)")
    parser.add_argument("--url", "-u", type=str, help="Seed URL to start crawling")
    parser.add_argument("--output", "-o", type=str, default="./output", help="Output directory")
    args = parser.parse_args()

    if args.gui and GUI_AVAILABLE:
        app = QApplication(sys.argv)
        window = MainWindow()
        window.show()
        sys.exit(app.exec())
    elif args.headless or args.url:
        settings = Settings()
        if args.config and Path(args.config).exists():
            with open(args.config) as f:
                config_data = json.load(f)
                settings = Settings.from_dict(config_data)  # you'd implement this in settings.py
        
        if args.url:
            settings.seed_urls = [args.url]
        if args.output:
            settings.output_dir = args.output

        async def run():
            crawler = UnifiedAsyncCrawler(settings)
            await crawler.start()
        asyncio.run(run())
    else:
        # Default: try GUI if available, else headless help
        if GUI_AVAILABLE:
            app = QApplication(sys.argv)
            window = MainWindow()
            window.show()
            sys.exit(app.exec())
        else:
            parser.print_help()


if __name__ == "__main__":
    main()
