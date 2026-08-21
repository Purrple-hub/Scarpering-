from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from dataclasses import dataclass, field

import psutil


@dataclass
class RateState:
    last_request: float = 0.0
    error_rate: float = 0.0
    latency: float = 0.0
    delay: float = 0.0


class AdaptiveRateLimiter:
    def __init__(self, base_delay: float = 0.1, memory_limit_mb: int = 1024) -> None:
        self.base_delay = base_delay
        self.memory_limit_mb = memory_limit_mb
        self.states: dict[str, RateState] = defaultdict(RateState)
        self.locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self.queue_size = 0

    def set_queue_size(self, size: int) -> None:
        self.queue_size = size

    def record(self, domain: str, success: bool, latency: float) -> None:
        state = self.states[domain]
        alpha = 0.3
        if success:
            state.error_rate *= 1 - alpha
            state.latency = state.latency * (1 - alpha) + latency * alpha
        else:
            state.error_rate = state.error_rate * (1 - alpha) + alpha
            state.latency = state.latency * (1 - alpha) + latency * alpha

    async def wait(self, domain: str) -> None:
        lock = self.locks[domain]
        async with lock:
            state = self.states[domain]
            now = time.monotonic()
            mem = psutil.virtual_memory()
            mem_pressure = max(0.0, (mem.percent - 70.0) / 30.0)
            queue_pressure = min(1.0, self.queue_size / 10000.0)
            latency_pressure = max(0.0, state.latency - 1.0) * 0.5
            error_pressure = state.error_rate * 5.0
            delay = max(
                self.base_delay,
                self.base_delay + error_pressure + latency_pressure + mem_pressure + queue_pressure * 0.5,
            )
            state.delay = delay
            wait_sec = state.last_request + delay - now
            if wait_sec > 0:
                await asyncio.sleep(wait_sec)
            state.last_request = time.monotonic()