import json
import re
import socket
from pathlib import Path
from typing import Any

import pytest

from trip_planner.preferences.legacy_request_adapter import (
    adapt_legacy_request,
    load_legacy_request,
)


def test_legacy_request_adapter_maps_existing_request_shape() -> None:
    request_path = Path("request.json")
    payload = json.loads(request_path.read_text(encoding="utf-8"))

    profile = adapt_legacy_request(payload)

    assert profile.hard_constraints.must_include_places == payload["must_see"]
    assert profile.trip_frame.season_window == payload["trip_window"]["months"]
    assert profile.budget_model.total_budget_sensitivity == payload["cost_sensitivity"]
    assert (
        "Mapped from legacy nature_ratio field."
        in profile.tradeoff_dimensions["nature_vs_culture"].notes
    )
    assert profile.hybrid_factors["route_modes"].preferences["rail"] == 1.0


def test_legacy_request_adapter_maps_nature_ratio_onto_canonical_axis() -> None:
    profile = adapt_legacy_request(
        {
            "trip_window": {"months": ["May"]},
            "must_see": [],
            "nature_ratio": 0.75,
            "complexity_tolerance": "medium",
            "cost_sensitivity": 0.3,
        }
    )

    assert profile.tradeoff_dimensions["nature_vs_culture"].value == 0.5


def test_legacy_request_adapter_maps_complexity_tolerance() -> None:
    profile = adapt_legacy_request(
        {
            "trip_window": {"months": ["June"]},
            "must_see": [],
            "nature_ratio": 0.5,
            "complexity_tolerance": "low",
            "cost_sensitivity": 0.3,
        }
    )

    assert profile.tradeoff_dimensions["movement_vs_friction"].value < 0
    assert profile.tradeoff_dimensions["recovery_vs_intensity"].value > 0
    assert profile.tradeoff_dimensions["self_reliance_vs_convenience"].value < 0


def test_legacy_request_adapter_rejects_invalid_budget_sensitivity() -> None:
    try:
        adapt_legacy_request(
            {
                "trip_window": {"months": ["June"]},
                "must_see": [],
                "nature_ratio": 0.5,
                "complexity_tolerance": "medium",
                "cost_sensitivity": 1.5,
            }
        )
    except ValueError as exc:
        assert "total_budget_sensitivity" in str(exc)
    else:
        raise AssertionError("Invalid legacy budget sensitivity should fail validation")


def test_load_legacy_request_reads_from_path(tmp_path: Path) -> None:
    request_path = tmp_path / "request.json"
    request_path.write_text(
        json.dumps(
            {
                "trip_window": {
                    "months": ["September"],
                    "min_weeks": 2,
                    "max_weeks": 3,
                },
                "must_see": ["Kyoto"],
                "nature_ratio": 0.4,
                "complexity_tolerance": "high",
                "cost_sensitivity": 0.2,
                "route_passions": {"train": 4},
            }
        ),
        encoding="utf-8",
    )

    profile = load_legacy_request(request_path)

    assert profile.hard_constraints.must_include_places == ["Kyoto"]
    assert profile.hybrid_factors["route_modes"].preferences["rail"] == 1.0


def _coverage_map_reference_errors(text: str, root: Path) -> list[str]:
    """Validate explicit citations, not implementation or test behavior."""
    import re

    errors = []
    for token in re.findall(r"(?<!`)`([^`\n]+)`(?!`)", text):
        if any(character.isspace() for character in token):
            continue
        is_path = (
            token.endswith("/")
            or token == "Makefile"
            or re.search(r"\.(?:py|tsx?|ya?ml|md)$", token)
        )
        if not is_path:
            continue
        candidate = root / token
        if not candidate.exists():
            errors.append(f"Missing explicit path: {token}")
        elif not candidate.resolve().is_relative_to(root.resolve()):
            errors.append(f"Path escapes repository: {token}")
    for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", text):
        if "://" in target or target.startswith("#"):
            continue
        path = target.split("#", 1)[0]
        if not path:
            continue
        candidate = root / "docs" / path
        if not candidate.exists() or not candidate.resolve().is_relative_to(root.resolve()):
            errors.append(f"Missing document-relative link: {target}")
    return errors


def test_design_coverage_map_references_are_addressable() -> None:
    root = Path(__file__).resolve().parents[2]
    text = (root / "docs/design-coverage-map.md").read_text(encoding="utf-8")
    assert _coverage_map_reference_errors(text, root) == []


def test_coverage_map_path_check_rejects_missing_and_accepts_same_directory_links() -> None:
    root = Path(__file__).resolve().parents[2]
    assert _coverage_map_reference_errors("`tests/no-such-coverage-proof.py`", root)
    assert _coverage_map_reference_errors("[contract](domain-contracts.md)", root) == []


_PROOF_LAYERS = {
    "fixture_lifecycle",
    "local_http_transport",
    "pinned_two_app",
    "native_lineage",
    "configured_full_product",
    "hosted_in_perimeter",
    "maps_provider",
    "deployment_restart",
}


def _coverage_claim_errors(claim: dict, root: Path) -> list[str]:
    """Check a bounded receipt contract offline; never infer execution from paths."""

    def local_file(value: object) -> Path | None:
        if not isinstance(value, str) or not value or Path(value).is_absolute():
            return None
        path = (root / value).resolve()
        return path if path.is_relative_to(root.resolve()) and path.is_file() else None

    if claim.get("layer") not in _PROOF_LAYERS:
        return ["Unknown proof layer"]
    if claim.get("status") == "UNVERIFIED":
        gate = claim.get("required_gate")
        return (
            [] if isinstance(gate, str) and gate.strip() else ["UNVERIFIED needs a required gate"]
        )
    if claim.get("status") != "VERIFIED":
        return ["Unknown execution status"]

    receipt_path = local_file(claim.get("receipt"))
    if receipt_path is None or receipt_path.suffix != ".json":
        return ["VERIFIED needs a local JSON receipt, not a workflow filename"]
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ["Unreadable JSON receipt"]
    if not isinstance(receipt, dict):
        return ["Receipt must be an object"]

    errors = []
    for field in ("layer", "consumer_sha", "producer_sha", "environment", "command"):
        value = claim.get(field)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"Missing claim {field}")
        elif receipt.get(field) != value:
            errors.append(f"Receipt {field} mismatch")
        if field.endswith("_sha") and not re.fullmatch(r"[0-9a-f]{40}", str(value)):
            errors.append(f"{field} must be an exact full SHA")
    for field in ("run", "artifact"):
        locator = receipt.get(field)
        # Remote locators are checked for shape only, never fetched. A local
        # locator must resolve to a retained file, not workflow configuration.
        remote_pattern = r"https://github\.com/[^/\s]+/[^/\s]+/actions/runs/[1-9][0-9]*"
        if field == "artifact":
            remote_pattern += r"/artifacts/[1-9][0-9]*"
        path = local_file(locator)
        if not (
            isinstance(locator, str)
            and re.fullmatch(remote_pattern, locator)
            or path is not None
            and path.suffix in {".log", ".txt", ".json", ".zip"}
        ):
            errors.append(f"Missing or invalid {field} locator")
    observed = receipt.get("observed_result")
    if not isinstance(observed, dict) or not (
        observed.get("status") == "PASS"
        and isinstance(observed.get("summary"), str)
        and observed["summary"].strip()
        and type(observed.get("skipped")) is int
        and observed.get("skipped") == 0
    ):
        errors.append("Receipt needs an observed PASS, summary and zero skips")
    if claim["layer"] == "configured_full_product" and claim.get("command") != (
        "python scripts/check_full_product_verification.py --live-tpp=required"
    ):
        errors.append("Configured full-product proof needs the required live-TPP gate")
    return errors


def _coverage_map_execution_errors(text: str, root: Path) -> list[str]:
    """Apply the receipt contract and prose consistency checks to a document."""
    blocks = re.findall(r"```json\n(.*?)\n```", text, re.DOTALL)
    assert len(blocks) == 1, "Keep execution claims in one structured registry"
    claims = json.loads(blocks[0])["execution_claims"]
    assert len(claims) == len(_PROOF_LAYERS)
    assert {claim["layer"] for claim in claims} == _PROOF_LAYERS
    errors = [error for claim in claims for error in _coverage_claim_errors(claim, root)]
    configured = next(claim for claim in claims if claim["layer"] == "configured_full_product")
    # Read the current-status declaration, not status words in later caveats.
    # Word boundaries distinguish VERIFIED from the suffix of UNVERIFIED.
    for prefix, pattern in (
        (
            "| Current full-product configured TPP transport |",
            r"\bcurrent configured execution (UNVERIFIED|VERIFIED)\b",
        ),
        (
            "> **Current configured execution:",
            r"^> \*\*Current configured execution: (UNVERIFIED|VERIFIED)\b",
        ),
    ):
        line = next(line for line in text.splitlines() if line.startswith(prefix))
        status = re.search(pattern, line)
        if status is None or status.group(1) != configured["status"]:
            errors.append(f"Configured execution status mismatch: {prefix}")
    return errors


@pytest.mark.parametrize(
    "case",
    [
        "repository",
        "unverified",
        "unverified-without-gate",
        "workflow-only",
        "missing-receipt",
        "malformed-receipt",
        "non-object-receipt",
        "receipt-outside-root",
        "receipt-symlink-outside-root",
        "run-symlink-outside-root",
        "artifact-symlink-outside-root",
        "nested-local-locators",
        "unknown-layer",
        "unknown-status",
        "short-sha",
        "short-producer-sha",
        "missing-run",
        "missing-artifact",
        "workflow-as-run",
        "workflow-as-artifact",
        "missing-local-artifact",
        "missing-observed-result",
        "failed-result",
        "skipped-result",
        "empty-summary",
        "optional-gate",
        "disabled-gate",
        "remote-locators",
        "document-verified",
        "document-workflow-only",
        "document-missing-receipt",
        "document-row-status-mismatch",
        "document-preamble-status-mismatch",
        "document-row-status-decoy",
        "document-preamble-status-decoy",
    ]
    + [f"missing-{field}" for field in ("consumer_sha", "producer_sha", "environment", "command")]
    + [
        f"missing-receipt-{field}"
        for field in ("layer", "consumer_sha", "producer_sha", "environment", "command")
    ]
    + [
        f"mismatched-{field}"
        for field in ("layer", "consumer_sha", "producer_sha", "environment", "command")
    ]
    + [f"unverified-{layer}" for layer in sorted(_PROOF_LAYERS)]
    + [f"verified-{layer}" for layer in sorted(_PROOF_LAYERS)]
    + [f"workflow-only-{layer}" for layer in sorted(_PROOF_LAYERS)]
    + [
        f"remote-{field}-{kind}"
        for field in ("run", "artifact")
        for kind in ("workflow", "missing-id", "wrong-kind")
    ]
    + [f"invalid-skips-{kind}" for kind in ("boolean", "float", "string", "null", "missing")],
)
def test_coverage_map_keeps_claims_scoped_to_their_evidence(
    case: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def reject_network(*args, **kwargs):
        pytest.fail("Receipt validation must not make network requests")

    monkeypatch.setattr(socket, "create_connection", reject_network)
    monkeypatch.setattr(socket, "getaddrinfo", reject_network)
    monkeypatch.setattr(socket.socket, "connect", reject_network)
    monkeypatch.setattr(socket.socket, "connect_ex", reject_network)

    root = Path(__file__).resolve().parents[2]
    text = (root / "docs/design-coverage-map.md").read_text(encoding="utf-8")
    normalized = " ".join(text.split())
    legacy = next(
        line for line in text.splitlines() if line.startswith("| Legacy request adapter |")
    )
    assert "tests/preferences/test_legacy_request_adapter.py" in legacy
    assert "no dedicated test" not in legacy
    assert "allow_fixture_fallback=False" in text
    assert "Path validity is a documentation check, not behavioral verification" in normalized
    assert "Historical May baseline (not rerun)" in text
    assert "976 passed, 1 xfailed" in text
    for owner in ("F50", "F51", "F52"):
        assert owner in text
    workflow = (root / ".github/workflows/cross-repo-smoke.yml").read_text(encoding="utf-8")
    pin = re.search(r"TPP_PINNED_REF: ([0-9a-f]{40})", workflow)
    assert pin is not None and pin.group(1) in text
    assert "tests/integration/test_authenticated_two_app_handoff.py" in text
    assert "python scripts/check_full_product_verification.py --live-tpp=required" in text
    assert _coverage_map_execution_errors(text, root) == []
    if case == "repository":
        return

    # Synthetic local fixtures exercise validation, never establish a real run.
    claim: dict[str, Any] = {
        "layer": "configured_full_product",
        "status": "VERIFIED",
        "consumer_sha": "a" * 40,
        "producer_sha": "b" * 40,
        "environment": "local Linux / Python 3.14 / HTTP / SQLite / synthetic providers",
        "command": "python scripts/check_full_product_verification.py --live-tpp=required",
        "receipt": "receipt.json",
    }
    receipt: dict[str, Any] = {
        key: value for key, value in claim.items() if key not in {"status", "receipt"}
    }
    receipt.update(
        run="run.log",
        artifact="result.json",
        observed_result={
            "status": "PASS",
            "summary": "Synthetic scoped journey passed",
            "skipped": 0,
        },
    )
    (tmp_path / "run.log").write_text("Synthetic local run fixture\n", encoding="utf-8")
    (tmp_path / "result.json").write_text('{"fixture": true}\n', encoding="utf-8")
    (tmp_path / "workflow.yml").write_text("name: configuration only\n", encoding="utf-8")
    expected_errors = {
        "unverified-without-gate": ["UNVERIFIED needs a required gate"],
        "workflow-only": ["VERIFIED needs a local JSON receipt, not a workflow filename"],
        "missing-receipt": ["VERIFIED needs a local JSON receipt, not a workflow filename"],
        "malformed-receipt": ["Unreadable JSON receipt"],
        "non-object-receipt": ["Receipt must be an object"],
        "receipt-outside-root": ["VERIFIED needs a local JSON receipt, not a workflow filename"],
        "receipt-symlink-outside-root": [
            "VERIFIED needs a local JSON receipt, not a workflow filename"
        ],
        "run-symlink-outside-root": ["Missing or invalid run locator"],
        "artifact-symlink-outside-root": ["Missing or invalid artifact locator"],
        "unknown-layer": ["Unknown proof layer"],
        "unknown-status": ["Unknown execution status"],
        "short-sha": ["consumer_sha must be an exact full SHA"],
        "short-producer-sha": ["producer_sha must be an exact full SHA"],
        "missing-run": ["Missing or invalid run locator"],
        "missing-artifact": ["Missing or invalid artifact locator"],
        "workflow-as-run": ["Missing or invalid run locator"],
        "workflow-as-artifact": ["Missing or invalid artifact locator"],
        "missing-local-artifact": ["Missing or invalid artifact locator"],
        "missing-observed-result": ["Receipt needs an observed PASS, summary and zero skips"],
        "failed-result": ["Receipt needs an observed PASS, summary and zero skips"],
        "skipped-result": ["Receipt needs an observed PASS, summary and zero skips"],
        "empty-summary": ["Receipt needs an observed PASS, summary and zero skips"],
        "optional-gate": ["Configured full-product proof needs the required live-TPP gate"],
        "disabled-gate": ["Configured full-product proof needs the required live-TPP gate"],
        "document-workflow-only": ["VERIFIED needs a local JSON receipt, not a workflow filename"],
        "document-missing-receipt": [
            "VERIFIED needs a local JSON receipt, not a workflow filename"
        ],
        "document-row-status-mismatch": [
            "Configured execution status mismatch: | Current full-product configured TPP transport |"
        ],
        "document-preamble-status-mismatch": [
            "Configured execution status mismatch: > **Current configured execution:"
        ],
        "document-row-status-decoy": [
            "Configured execution status mismatch: | Current full-product configured TPP transport |"
        ],
        "document-preamble-status-decoy": [
            "Configured execution status mismatch: > **Current configured execution:"
        ],
    }
    expected = expected_errors.get(case, [])
    if case.startswith("verified-"):
        claim["layer"] = receipt["layer"] = case.removeprefix("verified-")
    elif case.startswith("unverified-") and case.removeprefix("unverified-") in _PROOF_LAYERS:
        claim = {
            "layer": case.removeprefix("unverified-"),
            "status": "UNVERIFIED",
            "required_gate": "Retain a scoped execution receipt before promotion",
        }
    elif case.startswith("missing-receipt-"):
        field = case.removeprefix("missing-receipt-")
        receipt.pop(field)
        expected = [f"Receipt {field} mismatch"]
    elif case.startswith("missing-") and case.removeprefix("missing-") in {
        "consumer_sha",
        "producer_sha",
        "environment",
        "command",
    }:
        field = case.removeprefix("missing-")
        claim.pop(field)
        expected = [f"Missing claim {field}"]
        if field.endswith("_sha"):
            expected.append(f"{field} must be an exact full SHA")
        if field == "command":
            expected.append("Configured full-product proof needs the required live-TPP gate")
    elif case.startswith("mismatched-"):
        field = case.removeprefix("mismatched-")
        receipt[field] = "c" * 40 if field.endswith("_sha") else "another scope"
        expected = [f"Receipt {field} mismatch"]
    elif case == "unverified":
        claim = {
            "layer": "configured_full_product",
            "status": "UNVERIFIED",
            "required_gate": "Run gate",
        }
    elif case == "unverified-without-gate":
        claim = {"layer": "configured_full_product", "status": "UNVERIFIED"}
    elif case == "workflow-only":
        claim = {
            "layer": "configured_full_product",
            "status": "VERIFIED",
            "receipt": "workflow.yml",
        }
    elif case.startswith("workflow-only-"):
        # Even otherwise complete claims cannot substitute configuration for a
        # receipt, regardless of which proof layer they would promote.
        claim["layer"] = receipt["layer"] = case.removeprefix("workflow-only-")
        claim["receipt"] = "workflow.yml"
        expected = expected_errors["workflow-only"]
    elif case == "receipt-outside-root" or case.endswith("-symlink-outside-root"):
        field = case.split("-", 1)[0]
        suffix = ".log" if field == "run" else ".json"
        outside = tmp_path.parent / f"{tmp_path.name}-outside{suffix}"
        outside.write_text(json.dumps(receipt), encoding="utf-8")
        assert outside.is_file() and not outside.resolve().is_relative_to(tmp_path.resolve())
        if case == "receipt-outside-root":
            claim["receipt"] = f"../{outside.name}"
        else:
            link = tmp_path / f"linked{suffix}"
            link.symlink_to(outside)
            assert link.is_file()
            if field == "receipt":
                claim[field] = link.name
            else:
                receipt[field] = link.name
    elif case == "nested-local-locators":
        retained = tmp_path / "retained"
        retained.mkdir()
        (tmp_path / "run.log").rename(retained / "run.log")
        (tmp_path / "result.json").rename(retained / "result.json")
        receipt["run"] = "retained/run.log"
        receipt["artifact"] = "retained/result.json"
        claim["receipt"] = "retained/receipt.json"
    elif case == "unknown-layer":
        claim["layer"] = "all_layers"
    elif case == "unknown-status":
        claim["status"] = "IMPLEMENTED"
    elif case in {"short-sha", "short-producer-sha"}:
        field = "producer_sha" if case == "short-producer-sha" else "consumer_sha"
        claim[field] = receipt[field] = "abcdef0"
    elif case in {"missing-run", "missing-artifact", "missing-observed-result"}:
        receipt.pop(case.removeprefix("missing-").replace("-", "_"))
    elif case in {"workflow-as-run", "workflow-as-artifact"}:
        receipt[case.removeprefix("workflow-as-")] = "workflow.yml"
    elif case == "missing-local-artifact":
        receipt["artifact"] = "absent.json"
    elif case == "failed-result":
        receipt["observed_result"]["status"] = "FAIL"
    elif case == "skipped-result":
        receipt["observed_result"]["skipped"] = 1
    elif case.startswith("invalid-skips-"):
        kind = case.removeprefix("invalid-skips-")
        if kind == "missing":
            receipt["observed_result"].pop("skipped")
        else:
            receipt["observed_result"]["skipped"] = {
                "boolean": False,
                "float": 0.0,
                "string": "0",
                "null": None,
            }[kind]
        expected = ["Receipt needs an observed PASS, summary and zero skips"]
    elif case == "empty-summary":
        receipt["observed_result"]["summary"] = " "
    elif case in {"optional-gate", "disabled-gate"}:
        command = "python scripts/check_full_product_verification.py"
        claim["command"] = receipt["command"] = command + (
            " --live-tpp=off" if case == "disabled-gate" else ""
        )
    elif case == "remote-locators":
        receipt["run"] = "https://github.com/example/fixture/actions/runs/123"
        receipt["artifact"] = "https://github.com/example/fixture/actions/runs/123/artifacts/456"
    elif case.startswith("remote-"):
        _, field, kind = case.split("-", 2)
        run_url = "https://github.com/example/fixture/actions/runs/123"
        # A workflow page is configuration; run and artifact locators also
        # cannot substitute for each other, even when hosted on GitHub.
        receipt[field] = {
            "workflow": "https://github.com/example/fixture/actions/workflows/smoke.yml",
            "missing-id": run_url + "/artifacts/" if field == "artifact" else run_url[:-3],
            "wrong-kind": run_url if field == "artifact" else run_url + "/artifacts/456",
        }[kind]
        expected = [f"Missing or invalid {field} locator"]
    elif not case.startswith("document-") and case not in {
        "missing-receipt",
        "malformed-receipt",
        "non-object-receipt",
    }:
        raise AssertionError(f"Unhandled fixture case: {case}")

    receipt_path = tmp_path / (
        "retained/receipt.json" if case == "nested-local-locators" else "receipt.json"
    )
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    if case == "missing-receipt":
        receipt_path.unlink()
    elif case == "malformed-receipt":
        receipt_path.write_text("{", encoding="utf-8")
    elif case == "non-object-receipt":
        receipt_path.write_text("[]", encoding="utf-8")
    if case.startswith("document-"):
        # Promote only an in-memory copy, using the same checks as the real map.
        block = re.search(r"```json\n(.*?)\n```", text, re.DOTALL)
        assert block is not None
        registry = json.loads(block.group(1))
        configured = next(
            item
            for item in registry["execution_claims"]
            if item["layer"] == "configured_full_product"
        )
        previous_status = configured["status"]
        configured.clear()
        configured.update(claim)
        if case == "document-workflow-only":
            configured["receipt"] = "workflow.yml"
        elif case == "document-missing-receipt":
            receipt_path.unlink()
        text = text[: block.start(1)] + json.dumps(registry) + text[block.end(1) :]
        lines = text.splitlines()
        for index, line in enumerate(lines):
            if line.startswith("| Current full-product configured TPP transport |"):
                promote = case not in {
                    "document-row-status-mismatch",
                    "document-row-status-decoy",
                }
            elif line.startswith("> **Current configured execution:"):
                promote = case not in {
                    "document-preamble-status-mismatch",
                    "document-preamble-status-decoy",
                }
            else:
                continue
            status = "VERIFIED" if promote else "UNVERIFIED"
            lines[index] = re.sub(rf"\b{previous_status}\b", status, line)
            if not promote and case.endswith("-decoy"):
                lines[index] += " Historical examples may be VERIFIED for a different pair."
        assert _coverage_map_execution_errors("\n".join(lines), tmp_path) == expected
        return
    errors = _coverage_claim_errors(claim, tmp_path)
    assert errors == expected
