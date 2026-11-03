"""Guard PRODUCT_CONTRACT.md status cells against offline product-probe drift."""

from __future__ import annotations

import re

import pytest

from scripts import check_full_product_verification as verifier


def _contract_status_by_id(contract_text: str) -> dict[str, str]:
    rows: dict[str, str] = {}
    for match in re.finditer(
        r"^\| (TP\d+) \|.*\| ([A-Z]+) \|$",
        contract_text,
        re.MULTILINE,
    ):
        contract_id = match.group(1)
        assert contract_id not in rows, f"Duplicate contract ID: {contract_id}"
        rows[contract_id] = match.group(2)
    return rows


def test_product_contract_status_column_matches_offline_probe() -> None:
    contract_path = verifier.REPO_ROOT / "docs" / "PRODUCT_CONTRACT.md"
    contract_text = contract_path.read_text(encoding="utf-8")
    documented = _contract_status_by_id(contract_text)
    probe_rows = verifier.run_contract_report()
    probe = {row["id"]: row["verdict"] for row in probe_rows}
    assert documented.keys() == probe.keys() == {f"TP{i}" for i in range(1, 8)}
    mismatches = {
        tp: {"documented": documented[tp], "probe": probe[tp]}
        for tp in documented
        if documented[tp] != probe[tp]
    }
    assert not mismatches, mismatches


def test_duplicate_contract_id_cannot_hide_stale_status() -> None:
    text = "| TP1 | stale | BROKEN |\n| TP1 | current | WORKS |\n"
    with pytest.raises(AssertionError, match="Duplicate contract ID: TP1"):
        _contract_status_by_id(text)
