from __future__ import annotations
import time
import threading
from typing import Optional, Dict


class TokenBucketLimiter:
    """
    Simple cross-thread token bucket limiter for RPM (requests/min) and TPM (tokens/min).
    - Thread-safe acquire() that blocks until sufficient tokens are available.
    - If a capacity is <= 0, that dimension is disabled.
    """

    def __init__(self, rpm: float = 0.0, tpm: float = 0.0, name: str | None = None):
        self.lock = threading.Lock()
        self.cond = threading.Condition(self.lock)
        self.name = name or "limiter"
        # capacities per minute
        self.req_capacity = float(max(rpm, 0.0))
        self.tok_capacity = float(max(tpm, 0.0))
        # current tokens start full (burst allowed up to capacity)
        self.req_tokens = self.req_capacity
        self.tok_tokens = self.tok_capacity
        # refill rates per second
        self.req_rate = self.req_capacity / 60.0
        self.tok_rate = self.tok_capacity / 60.0
        self.last = time.monotonic()

    def _refill(self) -> None:
        now = time.monotonic()
        dt = max(0.0, now - self.last)
        self.last = now
        if self.req_capacity > 0:
            self.req_tokens = min(self.req_capacity, self.req_tokens + dt * self.req_rate)
        if self.tok_capacity > 0:
            self.tok_tokens = min(self.tok_capacity, self.tok_tokens + dt * self.tok_rate)

    def acquire(self, token_cost: float, req_cost: float = 1.0) -> None:
        """
        Block until both buckets have enough tokens for this request.
        token_cost: estimated tokens for prompt + completion
        req_cost: number of request units (default 1)
        """
        with self.cond:
            while True:
                self._refill()
                need_req = max(0.0, req_cost - (self.req_tokens if self.req_capacity > 0 else req_cost))
                need_tok = max(0.0, token_cost - (self.tok_tokens if self.tok_capacity > 0 else token_cost))
                if need_req <= 0 and need_tok <= 0:
                    # consume
                    if self.req_capacity > 0:
                        self.req_tokens -= req_cost
                    if self.tok_capacity > 0:
                        self.tok_tokens -= token_cost
                    return
                # compute time to next availability for each bucket
                wait_req = (
                    (need_req / self.req_rate)
                    if (self.req_capacity > 0 and self.req_rate > 0 and need_req > 0)
                    else 0.0
                )
                wait_tok = (
                    (need_tok / self.tok_rate)
                    if (self.tok_capacity > 0 and self.tok_rate > 0 and need_tok > 0)
                    else 0.0
                )
                wait_s = max(wait_req, wait_tok, 0.01)
                # Log expected wait time before we block
                # Example: [rate-limit] openai: sleeping ~1.11s (need req=0.0 tok=556.0; caps rpm=30000/m tpm=30000/m)
                try:
                    print(
                        f"[rate-limit] {self.name}: sleeping ~{wait_s:.2f}s "
                        f"(need req={need_req:.1f} tok={need_tok:.1f}; "
                        f"caps rpm={self.req_capacity:.0f}/m tpm={self.tok_capacity:.0f}/m)"
                    )
                except Exception:
                    pass
                self.cond.wait(timeout=min(max(wait_req, 0.01), max(wait_tok, 0.01), 5.0))


_LIMITERS: Dict[str, TokenBucketLimiter] = {}
_LIM_LOCK = threading.Lock()


def get_limiter(key: str, rpm: float = 0.0, tpm: float = 0.0) -> TokenBucketLimiter:
    """Return a process-wide shared limiter for the given key."""
    global _LIMITERS
    with _LIM_LOCK:
        lm = _LIMITERS.get(key)
        if lm is None:
            lm = TokenBucketLimiter(rpm=rpm, tpm=tpm, name=key)
            _LIMITERS[key] = lm
        return lm
