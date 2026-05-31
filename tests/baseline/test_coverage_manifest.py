"""Coverage manifest -- which metric dimensions are exercised; emit report.

Uses the generic ``baseline_kit.CoverageManifest``. The app supplies the input
space (the transport metric dimensions) and the touched set (metrics referenced
by an ordering).
"""

from __future__ import annotations


from baseline_kit import CoverageManifest, load_catalog

from . import adapter
from .conftest import CATALOG_PATH, REPO_ROOT

REPORT_PATH = REPO_ROOT / "docs" / "reports" / "baseline-coverage.md"


def _build_manifest() -> CoverageManifest:
    catalog = load_catalog(CATALOG_PATH)
    touched = {o["metric"] for o in catalog.get("orderings", [])}
    return CoverageManifest(
        all_keys=set(adapter.METRIC_KEYS),
        touched_keys=touched,
        priority_params=list(catalog.get("priority_metrics", [])),
        title="Trip-planner baseline coverage manifest",
    )


def test_ordering_metrics_exist():
    m = _build_manifest()
    assert not m.unknown_catalog_keys, (
        "Catalog references metrics not produced by the adapter: "
        f"{sorted(m.unknown_catalog_keys)}"
    )


def test_priority_metrics_covered():
    m = _build_manifest()
    assert not m.priority_gaps, "Priority metrics with no ordering: " + ", ".join(m.priority_gaps)


def test_emit_coverage_report():
    m = _build_manifest()
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(m.to_markdown())
    assert REPORT_PATH.exists()
