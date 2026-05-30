#!/usr/bin/env python3
"""Fail when README and Netlify API redirect origins drift."""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse


README_ORIGIN_PATTERN = re.compile(r"Public synthetic API origin:\s*`(?P<origin>https?://[^`]+)`")
REDIRECT_PATTERN = re.compile(r"^/api/\*\s+(?P<origin>https?://\S+)/api/:splat\s+200$", re.MULTILINE)


def _host(origin: str) -> str:
    parsed = urlparse(origin.rstrip("/"))
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise SystemExit(f"Invalid origin in deploy configuration: {origin!r}")
    return parsed.netloc


def _match(pattern: re.Pattern[str], text: str, source: Path) -> str:
    match = pattern.search(text)
    if not match:
        raise SystemExit(f"Could not find deploy API origin marker in {source}")
    return match.group("origin").rstrip("/")


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    readme_path = repo_root / "README.md"
    redirects_path = repo_root / "frontend" / "public" / "_redirects"

    readme_origin = _match(README_ORIGIN_PATTERN, readme_path.read_text(encoding="utf-8"), readme_path)
    redirect_origin = _match(
        REDIRECT_PATTERN,
        redirects_path.read_text(encoding="utf-8"),
        redirects_path,
    )

    if _host(readme_origin) != _host(redirect_origin):
        raise SystemExit(
            "Deploy API origin drift: "
            f"README host {_host(readme_origin)!r} != redirects host {_host(redirect_origin)!r}"
        )

    print(f"Deploy API origin aligned: {_host(readme_origin)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
