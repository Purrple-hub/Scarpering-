from __future__ import annotations

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from crawler.proxy import ProxyFetcher, ProxyManager


class TestProxyFetcher(unittest.TestCase):
    @patch("crawler.proxy.AsyncSession")
    def test_fetch_regex(self, mock_session_cls):
        mock_session = AsyncMock()
        mock_session_cls.return_value.__aenter__.return_value = mock_session
        mock_response = MagicMock()
        mock_response.text = "192.168.1.1:8080\n10.0.0.1:9999\ninvalid"
        mock_session.get = AsyncMock(return_value=mock_response)

        async def run():
            fetcher = ProxyFetcher(["http://proxylist"])
            proxies = await fetcher.fetch()
            return proxies

        proxies = asyncio.run(run())
        self.assertEqual(len(proxies), 2)
        self.assertIn("192.168.1.1:8080", proxies)


class TestProxyManager(unittest.IsolatedAsyncioTestCase):
    async def test_rotation_and_blacklist(self):
        fetcher = ProxyFetcher(["dummy"])
        manager = ProxyManager(fetcher)
        manager.proxies = ["1.1.1.1:80", "2.2.2.2:80"]
        p1 = await manager.get_proxy()
        p2 = await manager.get_proxy()
        self.assertNotEqual(p1, p2)

        manager.report_failure("1.1.1.1:80")
        self.assertNotIn("1.1.1.1:80", manager.proxies)
        p3 = await manager.get_proxy()
        self.assertEqual(p3, "2.2.2.2:80")


if __name__ == "__main__":
    unittest.main()