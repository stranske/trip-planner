"""Guard PRODUCT_CONTRACT.md status cells against offline product-probe drift."""

from __future__ import annotations

import json
import re
from collections import Counter
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
        cells = [cell.strip() for cell in re.split(r"(?<!\\)\|", match.group(2))]
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
    assert len(probe_rows) == len(probe), "Duplicate contract IDs in offline probe"
    assert documented.keys() == probe.keys() == {f"TP{i}" for i in range(1, 8)}
    mismatches = {
        tp: {"documented": documented[tp], "probe": probe[tp]}
        for tp in documented
        if documented[tp] != probe[tp]
    }
    assert not mismatches, mismatches


def test_product_contract_status_column_matches_cli_report(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    report_path = tmp_path / "product-probe.json"
    assert verifier.main(["--live-tpp", "off", "--contract-report", str(report_path)]) == 0
    report = json.loads(report_path.read_text(encoding="utf-8"))
    documented = _contract_status_by_id(
        (verifier.REPO_ROOT / "docs" / "PRODUCT_CONTRACT.md").read_text(encoding="utf-8")
    )
    assert len(report) == len(documented) == 7
    assert {row["id"]: row["verdict"] for row in report} == documented

    # Derive the expected headline from the document, independently of the report.
    counts = Counter(documented.values())
    expected_headline = (
        "product-probe: "
        + ", ".join(f"{verdict} {counts[verdict]}" for verdict in verifier.CONTRACT_VERDICTS)
        + f" of {len(documented)}"
    )
    assert expected_headline in capsys.readouterr().out.splitlines()


def test_pre_1962_tp3_fabricated_fails_against_partial_probe(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Issue #1964 AC: restore TP3 FABRICATED while the probe reports PARTIAL → drift fails.

    Uses the real ``docs/PRODUCT_CONTRACT.md`` table shape (not a stub row) so a
    parser that only works on minimal fixtures cannot satisfy the deliberate-break
    gate. Probe is monkeypatched to the current offline map with TP3 PARTIAL.
    """
    real_text = (verifier.REPO_ROOT / "docs" / "PRODUCT_CONTRACT.md").read_text(encoding="utf-8")
    assert _contract_status_by_id(real_text)["TP3"] == "PARTIAL"

    broken_lines: list[str] = []
    replaced = False
    for line in real_text.splitlines(keepends=True):
        if (
            not replaced
            and re.match(r"^[ \t]*\|[ \t]*TP3[ \t]*\|", line)
            and re.search(r"\|[ \t]*PARTIAL[ \t]*\|[ \t]*$", line)
        ):
            line = re.sub(
                r"\|[ \t]*PARTIAL[ \t]*\|([ \t]*\n?)$", r"| FABRICATED |\1", line, count=1
            )
            replaced = True
        broken_lines.append(line)
    assert replaced, "TP3 PARTIAL status cell not found in PRODUCT_CONTRACT.md"
    broken_text = "".join(broken_lines)
    assert _contract_status_by_id(broken_text)["TP3"] == "FABRICATED"

    contract_path = tmp_path / "docs" / "PRODUCT_CONTRACT.md"
    contract_path.parent.mkdir()
    contract_path.write_text(broken_text, encoding="utf-8")
    monkeypatch.setattr(verifier, "REPO_ROOT", tmp_path)
    probe = {f"TP{i}": "WORKS" if i in {1, 2, 5, 6} else "PARTIAL" for i in range(1, 8)}
    monkeypatch.setattr(
        verifier,
        "run_contract_report",
        lambda: [{"id": contract_id, "verdict": status} for contract_id, status in probe.items()],
    )

    with pytest.raises(AssertionError) as failure:
        test_product_contract_status_column_matches_offline_probe()

    assert str({"TP3": {"documented": "FABRICATED", "probe": "PARTIAL"}}) in str(failure.value)


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
@pytest.mark.parametrize("changed_source", ["document", "probe"])
def test_drift_guard_rejects_changed_verdicts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    changed_verdicts: dict[str, str],
    changed_source: str,
) -> None:
    documented = {f"TP{i}": "WORKS" if i in {1, 2, 5, 6} else "PARTIAL" for i in range(1, 8)}
    probe = documented.copy()
    if changed_source == "document":
        documented.update(changed_verdicts)
    else:
        probe.update(changed_verdicts)
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
    probe_rows = [{"id": contract_id, "verdict": status} for contract_id, status in probe.items()]
    monkeypatch.setattr(verifier, "run_contract_report", lambda: probe_rows)

    with pytest.raises(AssertionError) as failure:
        test_product_contract_status_column_matches_offline_probe()

    mismatches = {
        contract_id: {"documented": documented[contract_id], "probe": probe[contract_id]}
        for contract_id in changed_verdicts
    }
    assert str(mismatches) in str(failure.value)


@pytest.mark.parametrize("duplicate_verdict", ["WORKS", "BROKEN"])
def test_drift_guard_rejects_duplicate_probe_ids(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, duplicate_verdict: str
) -> None:
    contract_path = tmp_path / "docs" / "PRODUCT_CONTRACT.md"
    contract_path.parent.mkdir()
    contract_path.write_text(
        "\n".join(f"| TP{i} | journey | route | probe | WORKS |" for i in range(1, 8)),
        encoding="utf-8",
    )
    # A later matching verdict must not hide an earlier conflicting observation.
    probe_rows = [{"id": "TP1", "verdict": duplicate_verdict}] + [
        {"id": f"TP{i}", "verdict": "WORKS"} for i in range(1, 8)
    ]
    monkeypatch.setattr(verifier, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(verifier, "run_contract_report", lambda: probe_rows)

    with pytest.raises(AssertionError, match="Duplicate contract IDs in offline probe"):
        test_product_contract_status_column_matches_offline_probe()


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


@pytest.mark.parametrize("cell_index", range(3), ids=["journey", "route", "probe"])
def test_contract_status_parser_accepts_escaped_pipes(cell_index: int) -> None:
    cells = ["traveller", "route", "probe", "PARTIAL"]
    cells[cell_index] += r" \| alternative"
    assert _contract_status_by_id("| TP3 | " + " | ".join(cells) + " |") == {"TP3": "PARTIAL"}


@pytest.mark.parametrize("status", ["works", "UNKNOWN", ""])
def test_invalid_contract_status_is_reported(status: str) -> None:
    with pytest.raises(AssertionError, match="Invalid status for TP1"):
        _contract_status_by_id(f"| TP1 | traveller | route | probe | {status} |\n")


@pytest.mark.parametrize(
    "row",
    [
        "| TP1 | traveller | route | WORKS |",
        "| TP1 | traveller | route | probe | extra | WORKS |",
        r"| TP1 | traveller \| route | probe | WORKS |",
    ],
)
def test_contract_status_parser_rejects_wrong_column_count(row: str) -> None:
    with pytest.raises(AssertionError, match="Expected five columns for TP1"):
        _contract_status_by_id(row)
