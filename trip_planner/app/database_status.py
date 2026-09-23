"""Whether this process's database is ready, as observed rather than assumed.

The service deliberately starts when database initialisation fails, so a deploy is not marked
failed by an expired or briefly unreachable database. Until issue 1851, /api/health then said
"ok" regardless, which is how a deployment answered every trip request with an error while its
status page reported a healthy backend.

The record is not a latch. A failed check is retried from the health route, at most once per
``RETRY_INTERVAL_SECONDS``, so the report clears on its own once the database is reachable, and
it carries when it was last checked so a stale failure is visible as stale.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

logger = logging.getLogger(__name__)

RETRY_INTERVAL_SECONDS = 30.0


@dataclass
class DatabaseStatus:
    initialise: Callable[[], None]
    ready: bool = False
    reason: str | None = "not checked yet"
    checked_at: datetime | None = None
    _checked_monotonic: float | None = None

    def check(self) -> DatabaseStatus:
        try:
            self.initialise()
        except Exception as error:  # noqa: BLE001 - any failure means "not ready"
            logger.exception("Database initialisation failed; the service is degraded.")
            self.ready = False
            self.reason = f"{type(error).__name__}: database initialisation failed"
        else:
            self.ready = True
            self.reason = None
        self.checked_at = datetime.now(UTC)
        self._checked_monotonic = time.monotonic()
        return self

    def refresh_if_due(self) -> DatabaseStatus:
        """Retry a failed check once the interval has passed; a ready database is not re-probed."""

        if self.ready:
            return self
        last = self._checked_monotonic
        if last is None or time.monotonic() - last >= RETRY_INTERVAL_SECONDS:
            return self.check()
        return self
