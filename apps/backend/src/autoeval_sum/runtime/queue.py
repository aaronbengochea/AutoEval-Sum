"""
Run queue — single active run + FIFO waiting list.

Only one run executes at a time.  Concurrent start requests are serialised
via an asyncio.Lock; callers that arrive while a run is active receive
`queued` status and wait for the active run to finish (or be cancelled)
before proceeding.

Usage
-----
    queue = get_run_queue()
    async with queue.acquire(run_id, db):
        # run is now "running"; execute the graph here
        ...
"""

import asyncio
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from autoeval_sum.db.client import DynamoDBClient
from autoeval_sum.db.runs import update_run_status
from autoeval_sum.models.runs import RunStatus

log = logging.getLogger(__name__)


class RunQueue:
    """
    In-process FIFO run queue.

    Guarantees one active run at a time.  Waiting runs queue up by
    obtaining the asyncio.Lock in order.  Cancel requests set a flag that
    graph nodes poll at case boundaries.
    """

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._active_run_id: str | None = None
        self._cancel_requested: bool = False

    @property
    def active_run_id(self) -> str | None:
        return self._active_run_id

    @property
    def is_busy(self) -> bool:
        return self._lock.locked()

    def request_cancel(self) -> bool:
        """
        Signal the active run to stop at the next case boundary.
        Returns True if a run was active, False if nothing to cancel.
        """
        if self._active_run_id is None:
            return False
        self._cancel_requested = True
        log.info("Cancel requested for run %s.", self._active_run_id)
        return True

    def check_cancel(self) -> bool:
        """Called by graph nodes at case boundaries to detect a pending cancel."""
        return self._cancel_requested

    @asynccontextmanager
    async def acquire(
        self, run_id: str, db: DynamoDBClient
    ) -> AsyncGenerator[None, None]:
        """
        Async context manager that serialises run execution.

        On entry the caller waits for the lock (queued), then transitions
        the run to `running`.  On exit (normal or exception) the run status
        is updated and the lock is released so the next queued run can start.
        """
        log.info("Run %s waiting for queue slot.", run_id)
        async with self._lock:
            self._active_run_id = run_id
            self._cancel_requested = False
            await update_run_status(run_id, RunStatus.running, db)
            log.info("Run %s is now active.", run_id)
            try:
                yield
            finally:
                self._active_run_id = None
                self._cancel_requested = False


# ── Module-level singleton ─────────────────────────────────────────────────────

_queue: RunQueue | None = None


def get_run_queue() -> RunQueue:
    """Return the process-level RunQueue singleton."""
    global _queue
    if _queue is None:
        _queue = RunQueue()
    return _queue
