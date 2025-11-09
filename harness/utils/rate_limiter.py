from __future__ import annotations
import time
import threading
from time import perf_counter
from typing import Optional, Dict

from . import profiling


class TokenBucketLimiter:
    """
    Simple cross-thread token bucket limiter for RPM (requests/min) and TPM (tokens/min).
    - Thread-safe acquire() that blocks until sufficient tokens are available.
    - If a capacity is <= 0, that dimension is disabled.
    """

    def __init__(self, rpm: float = 0.0, tpm: float = 0.0, name: str | None = None):
        """
        Initialize the limiter with requests-per-minute (RPM) and tokens-per-minute (TPM) capacities and set up thread synchronization.
        
        Parameters:
            rpm (float): Maximum requests per minute; negative values treated as zero (disabled).
            tpm (float): Maximum tokens per minute; negative values treated as zero (disabled).
            name (str | None): Optional human-readable name for the limiter; defaults to "limiter".
        
        Notes:
            - Both capacities are stored as non-negative floats.
            - Each bucket's current tokens start at 50% of its capacity to reduce an initial burst.
            - Refill rates are computed per second from the minute capacities.
            - A lock and associated condition variable are created for cross-thread coordination, and an initial timestamp is recorded for refilling.
        """
        self.lock = threading.Lock()
        self.cond = threading.Condition(self.lock)
        self.name = name or "limiter"
        # capacities per minute
        self.req_capacity = float(max(rpm, 0.0))
        self.tok_capacity = float(max(tpm, 0.0))
        # current tokens start at 50% capacity to reduce initial burst
        self.req_tokens = self.req_capacity * 0.5
        self.tok_tokens = self.tok_capacity * 0.5
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

    def acquire(self, token_cost: float, req_cost: float = 1.0, enable_profiling: bool = False) -> None:
        """
        Block until both token and request buckets have enough capacity, then consume the requested amounts.
        
        If a bucket's configured capacity is less than or equal to zero, that bucket is ignored (no limiting for that dimension). This method may sleep while waiting for tokens to refill.
        
        Parameters:
            token_cost (float): Estimated number of tokens required for the operation (e.g., prompt + completion).
            req_cost (float): Number of request units to consume (defaults to 1.0).
        """
        timer = perf_counter() if enable_profiling and profiling.is_enabled() else None
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
                # Only log significant waits (>5s) to reduce spam
                if wait_s > 5.0:
                    try:
                        print(
                            f"[rate-limit] {self.name}: sleeping ~{wait_s:.1f}s "
                            f"(need tok={need_tok:.0f}; cap tpm={self.tok_capacity:.0f}/m)",
                            flush=True
                        )
                    except Exception:
                        pass
                self.cond.wait(timeout=min(max(wait_req, 0.01), max(wait_tok, 0.01), 30.0))
        if timer is not None:
            elapsed_ms = (perf_counter() - timer) * 1000
            if elapsed_ms > 10:
                profiling.log("rate_limiter", "acquire", elapsed_ms, context=f"limiter={self.name}")


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