"""
Execution policies for the LangGraph runtime.

Provides:
- TokenBudget  — tracks cumulative token usage; raises TokenBudgetExceeded on cap
- with_retry   — async 3-retry exponential backoff with jitter for external calls
- make_semaphore — creates a bounded asyncio.Semaphore
"""

import asyncio
import logging
import random

log = logging.getLogger(__name__)

# Per-call token overhead estimates (prompt + response, excluding doc text)
SUMMARIZER_OVERHEAD_TOKENS = 600
JUDGE_OVERHEAD_TOKENS = 400
EVAL_AUTHOR_FLAT_TOKENS = 6_000
CURRICULUM_FLAT_TOKENS = 12_000


class TokenBudgetExceededError(Exception):
    """Raised when a run exceeds its configured token cap."""

    def __init__(self, used: int, cap: int) -> None:
        self.used = used
        self.cap = cap
        super().__init__(f"Token budget exceeded: {used} > {cap}")


class TokenBudget:
    """
    Stateful token counter for a single run.

    Thread-safe for asyncio (single-threaded event loop).
    Raises TokenBudgetExceeded on the call that would push over the cap.
    """

    def __init__(self, cap: int, initial: int = 0) -> None:
        self._cap = cap
        self._used = initial

    @property
    def used(self) -> int:
        return self._used

    @property
    def cap(self) -> int:
        return self._cap

    def add(self, tokens: int) -> None:
        """
        Add `tokens` to the running total.

        Raises
        ------
        TokenBudgetExceededError
            If the new total would exceed the cap.
        """
        new_total = self._used + tokens
        if new_total > self._cap:
            raise TokenBudgetExceededError(new_total, self._cap)
        self._used = new_total


async def with_retry(
    coro_fn,  # type: ignore[type-arg]
    *args: object,
    max_retries: int = 3,
    base_delay: float = 1.0,
    jitter: float = 0.3,
    **kwargs: object,
) -> object:
    """
    Retry an async coroutine function up to `max_retries` times with
    exponential backoff and uniform random jitter.

    Parameters
    ----------
    coro_fn:
        Async callable to invoke.
    *args / **kwargs:
        Arguments forwarded to coro_fn.
    max_retries:
        Maximum number of attempts (default 3; i.e. up to 2 retries after first attempt).
    base_delay:
        Initial wait before first retry in seconds (doubles each attempt).
    jitter:
        Maximum random jitter fraction added to each delay.

    Raises
    ------
    Exception
        Re-raises the last exception if all attempts are exhausted.
    """
    last_exc: Exception | None = None
    delay = base_delay
    for attempt in range(1, max_retries + 1):
        try:
            return await coro_fn(*args, **kwargs)
        except Exception as exc:
            last_exc = exc
            if attempt == max_retries:
                log.warning(
                    "All %d retries exhausted for %s: %s",
                    max_retries,
                    getattr(coro_fn, "__name__", repr(coro_fn)),
                    exc,
                )
                break
            jitter_secs = random.uniform(0, jitter * delay)
            wait = delay + jitter_secs
            log.info(
                "Attempt %d/%d failed (%s); retrying in %.2fs",
                attempt,
                max_retries,
                exc,
                wait,
            )
            await asyncio.sleep(wait)
            delay *= 2

    raise last_exc  # type: ignore[misc]


def make_semaphore(n: int) -> asyncio.Semaphore:
    """Return a new asyncio.Semaphore with `n` slots."""
    return asyncio.Semaphore(n)
