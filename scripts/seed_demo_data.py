"""Opt-in synthetic demo seed + guided "first trip" path.

A fresh tester sees nothing today: every surface is gated behind self-service
sign-up and trip creation, so a non-developer cannot evaluate the workspace,
planner, scenario comparison, or map. This script provisions one synthetic demo
user plus one leisure and one business trip using the existing service layer, so
that an authenticated ``GET /api/workspace/{trip_id}`` immediately returns ranked
scenarios and inventory bundles.

Safety/data-zone guarantees:

* **Opt-in only.** The seed runs only when ``TRIP_PLANNER_SEED_DEMO`` is truthy.
  With the flag unset it no-ops (and logs) so it can never seed by default --
  including in production.
* **Synthetic only.** Titles/summaries/regions are obviously synthetic.
* **No external LLM.** The seeded trips carry full trip-frame context, so the
  workspace renders via the planner's deterministic ``fallback`` mode (the
  default). The seed never sets ``provider=openai`` / model / ``OPENAI_API_KEY``.

Run it for a non-production checkout with::

    TRIP_PLANNER_SEED_DEMO=1 python scripts/seed_demo_data.py
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import date, timedelta

from fastapi import HTTPException

from trip_planner.app.services.auth import (
    AuthenticatedUser,
    authenticate_user,
    create_account,
)
from trip_planner.app.services.trips import create_trip, list_trips
from trip_planner.persistence.db import ensure_database_ready, get_session_factory

logger = logging.getLogger(__name__)

#: Environment flag that must be truthy for the seed to run.
SEED_ENV_FLAG = "TRIP_PLANNER_SEED_DEMO"
_TRUTHY = {"1", "true", "yes", "on"}

#: Documented synthetic demo credentials (non-production only).
DEMO_EMAIL = "demo@trip-planner.local"
DEMO_PASSWORD = "demo-trip-planner-2026"  # synthetic; >= 8 chars
DEMO_DISPLAY_NAME = "Demo Tester"

#: Stable titles let the seed stay idempotent across re-runs.
DEMO_LEISURE_TITLE = "Demo Kyoto cultural week (synthetic)"
DEMO_BUSINESS_TITLE = "Demo Washington DC client visit (synthetic)"


@dataclass(frozen=True)
class DemoSeedResult:
    """Identifiers a caller (or the README) needs to reach the seeded demo."""

    email: str
    password: str
    leisure_trip_id: str
    business_trip_id: str

    def workspace_urls(self) -> list[str]:
        return [
            f"/workspace/{self.leisure_trip_id}",
            f"/workspace/{self.business_trip_id}",
        ]


def seed_enabled() -> bool:
    """Return True only when the opt-in flag is explicitly truthy."""

    return os.environ.get(SEED_ENV_FLAG, "").strip().lower() in _TRUTHY


def _ensure_demo_user(db_session) -> AuthenticatedUser:
    """Create the demo account if absent; otherwise reuse it (idempotent)."""

    try:
        user = create_account(
            db_session,
            email=DEMO_EMAIL,
            password=DEMO_PASSWORD,
            display_name=DEMO_DISPLAY_NAME,
        )
    except HTTPException as error:
        if error.status_code != 409:
            raise
        # Account already exists from a prior seed run -- reuse it.
        user = authenticate_user(db_session, email=DEMO_EMAIL, password=DEMO_PASSWORD)
    return AuthenticatedUser(
        user_id=user.user_id,
        email=user.email,
        display_name=user.display_name,
    )


def _ensure_trip(
    db_session,
    *,
    user: AuthenticatedUser,
    existing_by_title: dict[str, str],
    title: str,
    summary: str,
    mode: str,
    primary_regions: list[str],
    traveler_kind: str,
    traveler_count: int,
    duration_days: int,
    start_offset_days: int,
    traveler_notes: str,
) -> str:
    """Create the demo trip if absent; otherwise reuse it (idempotent).

    The trip frame carries destination + dates + duration so the workspace
    renders ranked scenarios via the deterministic fallback planner rather than a
    ``missing_destination`` / ``missing_dates`` partial.
    """

    if title in existing_by_title:
        return existing_by_title[title]

    # Future, deterministic-relative dates keep the demo trip "upcoming".
    start = date.today() + timedelta(days=start_offset_days)
    end = start + timedelta(days=duration_days - 1)
    created = create_trip(
        db_session,
        user=user,
        title=title,
        summary=summary,
        mode=mode,
        start_date=start.isoformat(),
        end_date=end.isoformat(),
        duration_days=duration_days,
        primary_regions=primary_regions,
        traveler_kind=traveler_kind,
        traveler_count=traveler_count,
        traveler_notes=traveler_notes,
    )
    return created["trip_id"]


def seed_demo_data(*, force: bool = False) -> DemoSeedResult | None:
    """Provision the synthetic demo user + two trips.

    Returns the :class:`DemoSeedResult` when seeding ran, or ``None`` when the
    opt-in flag was unset (and ``force`` was not passed), having made no writes.
    """

    if not (force or seed_enabled()):
        logger.info(
            "Demo seed skipped: set %s=1 to provision synthetic demo data.",
            SEED_ENV_FLAG,
        )
        return None

    ensure_database_ready()
    session = get_session_factory()()
    try:
        user = _ensure_demo_user(session)
        existing_by_title = {
            trip["title"]: trip["trip_id"] for trip in list_trips(session, user=user)
        }

        leisure_trip_id = _ensure_trip(
            session,
            user=user,
            existing_by_title=existing_by_title,
            title=DEMO_LEISURE_TITLE,
            summary="Seven days of Kyoto culture, food, and low-transfer neighborhood exploration.",
            mode="leisure",
            primary_regions=["Kyoto", "Osaka"],
            traveler_kind="solo",
            traveler_count=1,
            duration_days=7,
            start_offset_days=90,
            traveler_notes=(
                "Synthetic overseas leisure canary: moderate budget, cultural sites, food, "
                "and simple transfers. Safe to delete."
            ),
        )
        business_trip_id = _ensure_trip(
            session,
            user=user,
            existing_by_title=existing_by_title,
            title=DEMO_BUSINESS_TITLE,
            summary="A three-person Washington DC client meeting with an arrival buffer.",
            mode="business",
            primary_regions=["Washington DC"],
            traveler_kind="team",
            traveler_count=3,
            duration_days=3,
            start_offset_days=75,
            traveler_notes=(
                "Synthetic US business canary: economy travel, central lodging, explicit "
                "budget, and manager-review posture. Safe to delete."
            ),
        )
    finally:
        session.close()

    result = DemoSeedResult(
        email=DEMO_EMAIL,
        password=DEMO_PASSWORD,
        leisure_trip_id=leisure_trip_id,
        business_trip_id=business_trip_id,
    )
    logger.info(
        "Seeded synthetic demo data: user=%s leisure=%s business=%s",
        result.email,
        result.leisure_trip_id,
        result.business_trip_id,
    )
    return result


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    result = seed_demo_data()
    if result is None:
        print(
            f"Demo seed is opt-in. Re-run with {SEED_ENV_FLAG}=1 to provision "
            "synthetic demo data (non-production only)."
        )
        return 0

    print("Synthetic demo data seeded (deterministic fallback planner, no external LLM).")
    print("  Sign in at /login with:")
    print(f"    email:    {result.email}")
    print(f"    password: {result.password}")
    print("  Then open a populated workspace:")
    for url in result.workspace_urls():
        print(f"    {url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
