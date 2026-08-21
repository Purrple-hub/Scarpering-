from __future__ import annotations

import time
import unittest
from unittest.mock import patch

from crawler.domain_health import DomainHealthManager


class TestDomainHealthManager(unittest.TestCase):
    def setUp(self):
        self.dhm = DomainHealthManager()
        self.domain = "example.com"

    def test_initial_state(self):
        self.assertTrue(self.dhm.can_request(self.domain))

    def test_success_resets_errors(self):
        self.dhm.record_failure(self.domain, 500)
        self.dhm.record_success(self.domain)
        state = self.dhm.states[self.domain]
        self.assertEqual(state.consecutive_errors, 0)

    def test_blocked_status_backoff(self):
        with patch("time.monotonic", return_value=0.0):
            self.dhm.record_failure(self.domain, 429)
            self.assertFalse(self.dhm.can_request(self.domain))
        # 429 is blocked status, backoff = 60 * 2^1 = 120 seconds
        with patch("time.monotonic", return_value=121.0):
            self.assertTrue(self.dhm.can_request(self.domain))

    def test_exponential_backoff(self):
        with patch("time.monotonic", return_value=0.0):
            self.dhm.record_failure(self.domain, 503)
            first_cooldown = self.dhm.states[self.domain].blocked_until
        with patch("time.monotonic", return_value=first_cooldown):
            self.dhm.record_failure(self.domain, 503)
            second_cooldown = self.dhm.states[self.domain].blocked_until
        self.assertGreater(second_cooldown, first_cooldown)

    def test_non_blocked_failure_cooldown(self):
        with patch("time.monotonic", return_value=0.0):
            self.dhm.record_failure(self.domain, 500)
            self.assertFalse(self.dhm.can_request(self.domain))
        # 500 is non-blocked, but backoff = 60 * 2^1 = 120 seconds
        with patch("time.monotonic", return_value=121.0):
            self.assertTrue(self.dhm.can_request(self.domain))

    def test_unknown_domain_handling(self):
        self.assertTrue(self.dhm.can_request("unknown.com"))
        with patch("time.monotonic", return_value=0.0):
            self.dhm.record_failure("unknown.com", 0)
            self.assertFalse(self.dhm.can_request("unknown.com"))

    def tearDown(self):
        del self.dhm


if __name__ == "__main__":
    unittest.main()