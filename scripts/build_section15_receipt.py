#!/usr/bin/env python3
"""Build a section-15 execution receipt from same-run Cross-Repo Smoke evidence.

The receipt follows `docs/design-coverage-map.md` section 15. It records the observed
result only; any missing, incomplete or mismatched evidence leaves it ineligible for PASS.
Standard library only, so it still runs after a failed dependency install.
"""

from __future__ import annotations

import argparse
import json
import platform
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

CONFIGURED_FULL_PRODUCT_COMMAND = (
    "python scripts/check_full_product_verification.py --live-tpp=required"
)
PINNED_TWO_APP_COMMAND = (
    "../Travel-Plan-Permission/.venv/bin/python -m pytest "
    "tests/integration/test_tpp_portal_contract.py "
    "tests/integration/test_authenticated_two_app_handoff.py -q"
)
EXPECTED_COMMANDS = {
    "configured_full_product": CONFIGURED_FULL_PRODUCT_COMMAND,
    "pinned_two_app": PINNED_TWO_APP_COMMAND,
}
# Mirror verifier.FULL_PRODUCT_REQUIRED_CHECKS; stay import-free for stdlib-only runs.
FULL_PRODUCT_REQUIRED_CHECK_NAMES = (
    "frontend-runtime-smoke",
    "local-leisure-journey",
    "local-business-journey",
    "live-tpp",
)
_SHA = re.compile(r"[0-9a-f]{40}")
_RUN_URL = re.compile(r"https://github\.com/[^/\s?#]+/[^/\s?#]+/actions/runs/[1-9][0-9]*")
_ARTIFACT_URL = re.compile(_RUN_URL.pattern + r"/artifacts/[1-9][0-9]*")


def environment(layer: str, *, runner: str, python_version: str) -> str:
    """Describe the bounded environment; local loopback never implies hosted transport."""
    base = f"GitHub Actions {runner} runner, CPython {python_version}"
    if layer == "pinned_two_app":
        return (
            f"{base}; one interpreter (TPP .venv) importing both apps; pinned "
            "Travel-Plan-Permission producer served by in-process uvicorn on 127.0.0.1 "
            "loopback HTTP; trip-planner consumer in-process; TPP bootstrap-token auth with "
            "test-minted tokens and test signing secrets; temporary SQLite stores; no "
            "external providers; not hosted and not in an approved deployment perimeter"
        )
    return (
        f"{base}; trip-planner in-process TestClient with temporary file SQLite; pinned "
        "Travel-Plan-Permission auto-started as a local subprocess on 127.0.0.1 loopback "
        "HTTP with a static CI access token (TPP_OIDC_PROVIDER=google, no real OIDC); "
        "planner forced to deterministic fallback (no managed LLM call); Maps provider "
        "unconfigured (fallback map); local fixture envelopes enabled; not hosted and not "
        "in an approved deployment perimeter"
    )


def _load_json(path: Path | None) -> dict[str, Any] | None:
    if path is None or not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def _full_product_observation(
    result_path: Path | None,
) -> tuple[dict[str, Any], str | None, list[dict[str, Any]], list[str]]:
    result = _load_json(result_path)
    if result is None:
        observed: dict[str, Any] = {
            "status": "MISSING",
            "summary": "No strict full-product result was written.",
        }
        return observed, None, [], ["strict full-product result missing or unreadable"]
    reasons = []
    required = result.get("required_checks")
    if not isinstance(required, list) or not required:
        reasons.append("strict result lists no required checks")
        required = []
    names: list[str] = []
    for check in required:
        if not isinstance(check, dict):
            continue
        name = check.get("name")
        if isinstance(name, str):
            names.append(name)
    if len(names) != len(required):
        reasons.append("required_checks entries must be objects with a name")
    required_set = set(FULL_PRODUCT_REQUIRED_CHECK_NAMES)
    seen: set[str] = set()
    for name in names:
        if name in seen:
            reasons.append(f"duplicate required check name: {name}")
        seen.add(name)
        if name not in required_set:
            reasons.append(f"unknown required check name: {name}")
    for name in FULL_PRODUCT_REQUIRED_CHECK_NAMES:
        if name not in seen:
            reasons.append(f"required check missing: {name}")
    statuses = [check.get("status") for check in required if isinstance(check, dict)]
    skipped = sum(status in {"SKIPPED", "BLOCKED"} for status in statuses)
    if result.get("exit_code") != 0:
        reasons.append(f"strict gate exit code {result.get('exit_code')!r}")
    if result.get("status") != "PASS":
        reasons.append(f"strict result status {result.get('status')!r}")
    if len(statuses) != len(required) or any(status != "PASS" for status in statuses):
        reasons.append("not every required check passed")
    summary = "Required checks: " + ", ".join(
        f"{check.get('name')}={check.get('status')}"
        for check in required
        if isinstance(check, dict)
    )
    observed = {
        "status": result.get("status") if isinstance(result.get("status"), str) else "UNKNOWN",
        "summary": summary,
        "skipped": skipped,
        "required_checks": required,
        "exit_code": result.get("exit_code"),
    }
    if isinstance(result.get("failure"), str):
        observed["failure"] = result["failure"]
    optional = result.get("optional_observations")
    command = result.get("command") if isinstance(result.get("command"), str) else None
    return observed, command, optional if isinstance(optional, list) else [], reasons


def _pinned_two_app_observation(
    junit_path: Path | None, exit_code: int | None
) -> tuple[dict[str, Any], list[str]]:
    if junit_path is None or not junit_path.is_file():
        observed: dict[str, Any] = {
            "status": "MISSING",
            "summary": "No pinned two-app pytest report was written.",
        }
        return observed, ["pinned two-app pytest report missing"]
    try:
        root = ET.parse(junit_path).getroot()
    except (OSError, ET.ParseError):
        observed = {
            "status": "MISSING",
            "summary": "Pinned two-app pytest report is unreadable.",
        }
        return observed, ["pinned two-app pytest report unreadable"]
    suites = [root] if root.tag == "testsuite" else root.findall("testsuite")
    counts = {
        key: sum(int(suite.get(key, "0") or 0) for suite in suites)
        for key in ("tests", "failures", "errors", "skipped")
    }
    passed = counts["tests"] - counts["failures"] - counts["errors"] - counts["skipped"]
    reasons = []
    if exit_code != 0:
        reasons.append(f"pytest exit code {exit_code!r}")
    if counts["tests"] == 0:
        reasons.append("pytest collected no tests")
    if counts["failures"] or counts["errors"]:
        reasons.append("pytest reported failures or errors")
    if counts["skipped"]:
        reasons.append("pytest skipped required tests")
    status = "PASS" if not reasons else ("SKIPPED" if counts["skipped"] else "FAIL")
    observed = {
        "status": status,
        "summary": (
            f"{passed} passed, {counts['failures']} failed, {counts['errors']} errors, "
            f"{counts['skipped']} skipped of {counts['tests']} pinned two-app tests"
        ),
        "skipped": counts["skipped"],
        "passed": passed,
        "failed": counts["failures"],
        "errors": counts["errors"],
        "tests": counts["tests"],
        "exit_code": exit_code,
    }
    return observed, reasons


def build_receipt(
    *,
    layer: str,
    consumer_sha: str,
    producer_sha: str,
    run_url: str,
    artifact_url: str,
    environment_text: str,
    result_json: Path | None = None,
    junit_xml: Path | None = None,
    pytest_exit_code: int | None = None,
) -> dict[str, Any]:
    expected_command = EXPECTED_COMMANDS[layer]
    observations: list[dict[str, Any]] = []
    if layer == "configured_full_product":
        observed, recorded_command, observations, reasons = _full_product_observation(result_json)
        if observed.get("status") == "MISSING":
            command = expected_command
        else:
            if not recorded_command or not recorded_command.strip():
                reasons.append("strict result recorded no command")
            command = recorded_command or expected_command
    else:
        observed, reasons = _pinned_two_app_observation(junit_xml, pytest_exit_code)
        command = expected_command
    if command != expected_command:
        reasons.append("recorded command is not the layer's required command")
    for name, sha in (("consumer_sha", consumer_sha), ("producer_sha", producer_sha)):
        if not _SHA.fullmatch(sha):
            reasons.append(f"{name} is not a full 40-character SHA")
    if not _RUN_URL.fullmatch(run_url):
        reasons.append("run URL is not an Actions run URL")
    if not _ARTIFACT_URL.fullmatch(artifact_url):
        reasons.append("evidence artifact URL is missing or not an Actions artifact URL")
    elif artifact_url.rsplit("/artifacts/", 1)[0] != run_url:
        reasons.append("evidence artifact does not belong to this run")
    if reasons:
        # Fail closed: an incomplete receipt keeps its observations but never reads as PASS.
        if observed.get("status") == "PASS":
            observed["status"] = "INELIGIBLE"
        observed["ineligible_reasons"] = reasons
    observed.setdefault("skipped", None)
    return {
        "layer": layer,
        "consumer_sha": consumer_sha,
        "producer_sha": producer_sha,
        "environment": environment_text,
        "command": command,
        "run": run_url,
        "artifact": artifact_url,
        "observed_result": observed,
        # Optional provider skips stay visible but outside the claimed layer.
        "observations_outside_claim": observations,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--layer", choices=sorted(EXPECTED_COMMANDS), required=True)
    parser.add_argument("--consumer-sha", default="")
    parser.add_argument("--producer-sha", default="")
    parser.add_argument("--run-url", default="")
    parser.add_argument("--artifact-url", default="")
    parser.add_argument("--result-json", type=Path)
    parser.add_argument("--junit-xml", type=Path)
    parser.add_argument("--pytest-exit-code-file", type=Path)
    parser.add_argument("--runner", default="ubuntu-latest")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    exit_code: int | None = None
    if args.pytest_exit_code_file is not None and args.pytest_exit_code_file.is_file():
        try:
            exit_code = int(args.pytest_exit_code_file.read_text(encoding="utf-8").strip())
        except ValueError:
            exit_code = None
    receipt = build_receipt(
        layer=args.layer,
        consumer_sha=args.consumer_sha.strip(),
        producer_sha=args.producer_sha.strip(),
        run_url=args.run_url.strip(),
        artifact_url=args.artifact_url.strip(),
        environment_text=environment(
            args.layer, runner=args.runner, python_version=platform.python_version()
        ),
        result_json=args.result_json,
        junit_xml=args.junit_xml,
        pytest_exit_code=exit_code,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    observed = receipt["observed_result"]
    print(f"{args.layer}: {observed['status']} - {observed['summary']}")
    for reason in observed.get("ineligible_reasons", []):
        print(f"  ineligible: {reason}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
