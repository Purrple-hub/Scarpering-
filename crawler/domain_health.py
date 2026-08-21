from __future__ import annotations

import time
from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass
class DomainState:
    consecutive_errors: int = 0
    blocked_until: float = 0.0
    cooldown_until: float = 0.0
    successes: int = 0


class DomainHealthManager:
    def __init__(self) -> None:
        self.states: dict[str, DomainState] = {}
        self.blocked_statuses = {403, 429, 503}

    @staticmethod
    def get_domain(url: str) -> str:
        return urlparse(url).netloc.lower()

    def _get_state(self, domain: str) -> DomainState:
        if domain not in self.states:
            self.states[domain] = DomainState()
        return self.states[domain]

    def can_request(self, domain: str) -> bool:
        state = self._get_state(domain)
        now = time.monotonic()
        return now >= max(state.blocked_until, state.cooldown_until)

    def record_success(self, domain: str) -> None:
        state = self._get_state(domain)
        state.successes += 1
        state.consecutive_errors = 0
        state.cooldown_until = 0.0

    def record_failure(self, domain: str, status: int = 0) -> None:
        state = self._get_state(domain)
        state.consecutive_errors += 1
        backoff = min(3600, 60 * (2 ** state.consecutive_errors))
        now = time.monotonic()
        if status in self.blocked_statuses:
            state.blocked_until = now + backoff
        else:
            state.cooldown_until = now + backoff