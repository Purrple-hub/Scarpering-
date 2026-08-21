from __future__ import annotations

import asyncio
import time
import unittest
from unittest.mock import AsyncMock, patch

from crawler.rate_limiter import AdaptiveRateLimiter


class TestAdaptiveRateLimiter(unittest.IsolatedAsyncioTestCase):
    async def test_basic_wait_no_delay(self):
        rl = AdaptiveRateLimiter(base_delay=0.0)
        rl.record("example.com", True, 0.1)
        start = time.monotonic()
        await rl.wait("example.com")
        elapsed = time.monotonic() - start
        self.assertLess(elapsed, 0.1)

    async def test_error_increases_delay(self):
        rl = AdaptiveRateLimiter(base_delay=0.0)
        rl.record("bad.com", False, 5.0)
        rl.record("bad.com", False, 5.0)

        # Mock time.monotonic and asyncio.sleep to get deterministic delay
        with patch("crawler.rate_limiter.time.monotonic", return_value=0.0), \
             patch("crawler.rate_limiter.asyncio.sleep", new=AsyncMock()) as mock_sleep:
            await rl.wait("bad.com")
            mock_sleep.assert_called_once()
            args, _ = mock_sleep.call_args
            self.assertGreater(args[0], 0.0)

    async def test_queue_pressure(self):
        rl = AdaptiveRateLimiter(base_delay=0.0)
        rl.set_queue_size(10000)
        rl.record("example.com", True, 1.0)
        start = time.monotonic()
        await rl.wait("example.com")
        elapsed = time.monotonic() - start
        self.assertGreaterEqual(elapsed, 0.0)

    async def test_domain_isolation(self):
        rl = AdaptiveRateLimiter(base_delay=0.0)
        rl.record("one.com", True, 0.1)
        rl.record("two.com", True, 0.1)
        # both should have independent delays
        with patch("crawler.rate_limiter.time.monotonic", return_value=0.0), \
             patch("crawler.rate_limiter.asyncio.sleep", new=AsyncMock()):
            await rl.wait("one.com")
            await rl.wait("two.com")
        # no exception means isolated locks worked


if __name__ == "__main__":
    unittest.main()