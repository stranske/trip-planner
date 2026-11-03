"""Guard PRODUCT_CONTRACT.md status cells against offline product-probe drift."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from scripts import check_full_product_verification as verifier


def _contract_status_by_id(contract_text: str) -> dict[str, str]:
    rows: dict[str, str] = {}
    for match in re.finditer(
        r"^[ \t]*\|[ \t]*(TP\d+)[ \t]*\|(.*)\|[ \t]*$",
        contract_text,
        re.MULTILINE,
    ):
        contract_id = match.group(1)
        assert contract_id not in rows, f"Duplicate contract ID: {contract_id}"
        cells = [cell.strip() for cell in match.group(2).split("|")]
        assert len(cells) == 4, f"Expected five columns for {contract_id}"
        status = cells[3]
        assert status in verifier.CONTRACT_VERDICTS, f"Invalid status for {contract_id}: {status!r}"
        rows[contract_id] = status
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


@pytest.mark.parametrize(
    "changed_verdicts",
    [
        {"TP3": "FABRICATED"},
        {"TP5": "BROKEN"},
        {"TP6": "BROKEN"},
        {"TP7": "BROKEN"},
        # A headline-only comparison would miss this swap between contract IDs.
        {"TP3": "WORKS", "TP5": "PARTIAL"},
    ],
    ids=["stale-tp3", "stale-tp5", "stale-tp6", "stale-tp7", "same-headline"],
)
def test_drift_guard_rejects_changed_probe_verdicts(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, changed_verdicts: dict[str, str]
) -> None:
    documented = {f"TP{i}": "WORKS" if i in {1, 2, 5, 6} else "PARTIAL" for i in range(1, 8)}
    contract_path = tmp_path / "docs" / "PRODUCT_CONTRACT.md"
    contract_path.parent.mkdir()
    contract_path.write_text(
        "\n".join(
            f"| {contract_id} | journey | route | probe | {status} |"
            for contract_id, status in documented.items()
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(verifier, "REPO_ROOT", tmp_path)
    probe_rows = [
        {"id": contract_id, "verdict": changed_verdicts.get(contract_id, status)}
        for contract_id, status in documented.items()
    ]
    monkeypatch.setattr(verifier, "run_contract_report", lambda: probe_rows)

    with pytest.raises(AssertionError) as failure:
        test_product_contract_status_column_matches_offline_probe()

    mismatches = {
        contract_id: {"documented": documented[contract_id], "probe": verdict}
        for contract_id, verdict in changed_verdicts.items()
    }
    assert str(mismatches) in str(failure.value)


@pytest.mark.parametrize(
    "duplicate",
    [
        "| TP1 | current | route | probe | WORKS |",
        "|TP1| current |route|probe|WORKS|",
        "  | TP1 | current | route | probe | WORKS |  ",
        "| TP1 | current | route | probe | works |",
    ],
)
def test_duplicate_contract_id_cannot_hide_stale_status(duplicate: str) -> None:
    text = f"| TP1 | stale | route | probe | BROKEN |\n{duplicate}\n"
    with pytest.raises(AssertionError, match="Duplicate contract ID: TP1"):
        _contract_status_by_id(text)


def test_contract_status_parser_accepts_markdown_table_spacing() -> None:
    text = "  |TP1| traveller | route | probe |WORKS|  \n\t| TP2 | trip |route|probe|PARTIAL|\n"
    assert _contract_status_by_id(text) == {"TP1": "WORKS", "TP2": "PARTIAL"}


@pytest.mark.parametrize("status", ["works", "UNKNOWN", ""])
def test_invalid_contract_status_is_reported(status: str) -> None:
    with pytest.raises(AssertionError, match="Invalid status for TP1"):
        _contract_status_by_id(f"| TP1 | traveller | route | probe | {status} |\n")


@pytest.mark.parametrize(
    "row",
    [
        "| TP1 | traveller | route | WORKS |",
        "| TP1 | traveller | route | probe | extra | WORKS |",
    ],
)
def test_contract_status_parser_rejects_wrong_column_count(row: str) -> None:
    with pytest.raises(AssertionError, match="Expected five columns for TP1"):
        _contract_status_by_id(row)
