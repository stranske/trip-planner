#!/usr/bin/env python3
"""Generate Netlify redirects from the configured API origin."""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlparse


DEFAULT_API_ORIGIN = "https://trip-planner-api-s40u.onrender.com"


def _api_origin() -> str:
    # Only the Netlify deploy origin drives _redirects generation. VITE_API_BASE_URL
    # is intentionally NOT consulted: it configures direct-call (local/preview/internal)
    # builds that bypass Netlify redirects, so consuming it here would emit a redirect
    # host that disagrees with the documented public origin and fail the drift check.
    origin = os.environ.get("TRIP_PLANNER_API_ORIGIN")
    origin = (origin or DEFAULT_API_ORIGIN).strip().rstrip("/")
    parsed = urlparse(origin)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise SystemExit(f"Invalid API origin: {origin!r}")
    if parsed.path or parsed.params or parsed.query or parsed.fragment:
        raise SystemExit(
            f"API origin must be scheme + host only (no path/query/fragment): {origin!r}"
        )
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
