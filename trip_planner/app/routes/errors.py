"""Stable public HTTP errors for workspace routes."""

from __future__ import annotations

import logging
from uuid import uuid4

from fastapi import HTTPException

logger = logging.getLogger(__name__)


def public_http_error(
    error: Exception,
    *,
    status_code: int,
    message: str,
) -> HTTPException:
    """Log the internal error and return a correlation-safe public response."""
    reference_id = uuid4().hex
    logger.error(
        "%s (reference_id=%s)",
        message,
        reference_id,
        exc_info=error,
    )
    return HTTPException(
        status_code=status_code,
        detail=f"{message} Reference ID: {reference_id}.",
    )
