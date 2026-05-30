#!/usr/bin/env python3
"""Generate Netlify redirects from the configured API origin."""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlparse


DEFAULT_API_ORIGIN = "https://trip-planner-api-s40u.onrender.com"


def _api_origin() -> str:
    origin = os.environ.get("TRIP_PLANNER_API_ORIGIN") or os.environ.get("VITE_API_BASE_URL")
    origin = (origin or DEFAULT_API_ORIGIN).strip().rstrip("/")
    parsed = urlparse(origin)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise SystemExit(f"Invalid API origin: {origin!r}")
    return origin


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    redirects_path = repo_root / "frontend" / "public" / "_redirects"
    origin = _api_origin()
    redirects_path.write_text(
        f"/api/* {origin}/api/:splat 200\n/* /index.html 200\n",
        encoding="utf-8",
    )
    print(f"Wrote {redirects_path} for API origin {origin}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
