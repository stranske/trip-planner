"""Exercise the Gate commit-status script against fork token failures."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import textwrap
from pathlib import Path
from typing import Any

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
GATE_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "pr-00-gate.yml"
STEP_NAME = "Report Gate commit status"

RUNNER_JS = textwrap.dedent("""
    const fs = require('fs');
    const vm = require('vm');
    const src = fs.readFileSync(process.argv[2], 'utf8');

    function makeError(status, message, headers = {}, responseMessage = null) {
      const error = new Error(message);
      error.status = status;
      error.response = { headers, data: { message: responseMessage } };
      return error;
    }

    async function runCase({ headRepo, baseRepo, error, state }) {
      const failures = [];
      const statusRequests = [];
      const warnings = [];
      const summaryWrites = [];
      const summaryRaw = [];
      const summaryStub = {
        addHeading() { return summaryStub; },
        addRaw(text) { summaryRaw.push(String(text)); return summaryStub; },
        async write() { summaryWrites.push('write'); },
      };
      const sandbox = {
        process: {
          env: {
            STATE: state,
            DESCRIPTION: 'all checks passed',
            TARGET_URL: 'https://example.invalid/run',
          },
        },
        console: { log() {} },
        core: {
          setFailed: (message) => failures.push(String(message)),
          warning: (message) => warnings.push(String(message)),
          summary: summaryStub,
        },
        context: {
          repo: { owner: 'stranske', repo: 'trip-planner' },
          sha: 'basesha',
          payload: {
            pull_request: {
              head: {
                sha: 'headsha',
                repo: headRepo === null ? null : { full_name: headRepo },
              },
              base: { repo: { full_name: baseRepo } },
            },
          },
        },
        github: {
          rest: {
            repos: {
              createCommitStatus: async (request) => {
                statusRequests.push(request);
                if (error) throw error;
              },
            },
          },
        },
      };
      vm.createContext(sandbox);
      let threw = null;
      try {
        await vm.runInContext('(async () => {\\n' + src + '\\n})()', sandbox);
      } catch (error) {
        threw = {
          status: error.status === undefined ? null : error.status,
          message: String(error.message),
        };
      }
      return {
        failures,
        warnings,
        summaryWrites: summaryWrites.length,
        summaryRaw,
        statusRequests,
        threw,
      };
    }

    const FORK = {
      headRepo: 'outside-contributor/trip-planner',
      baseRepo: 'stranske/trip-planner',
    };
    const SAME = {
      headRepo: 'stranske/trip-planner',
      baseRepo: 'stranske/trip-planner',
    };

    (async () => {
      const outcomes = {
        fork_read_only: await runCase({
          ...FORK,
          state: 'success',
          error: makeError(403, 'Resource not accessible by integration'),
        }),
        fork_read_only_failure: await runCase({
          ...FORK,
          state: 'failure',
          error: makeError(403, 'Resource not accessible by integration'),
        }),
        fork_read_only_error: await runCase({
          ...FORK,
          state: 'error',
          error: makeError(403, 'Resource not accessible by integration'),
        }),
        fork_read_only_pending: await runCase({
          ...FORK,
          state: 'pending',
          error: makeError(403, 'Resource not accessible by integration'),
        }),
        deleted_fork_read_only: await runCase({
          headRepo: null,
          baseRepo: 'stranske/trip-planner',
          state: 'success',
          error: makeError(403, 'Resource not accessible by integration'),
        }),
        same_repo_read_only: await runCase({
          ...SAME,
          state: 'success',
          error: makeError(403, 'Resource not accessible by integration'),
        }),
        fork_rate_limit: await runCase({
          ...FORK,
          state: 'success',
          error: makeError(403, 'API rate limit exceeded'),
        }),
        fork_rate_limit_failure: await runCase({
          ...FORK,
          state: 'failure',
          error: makeError(403, 'API rate limit exceeded'),
        }),
        fork_rate_limit_error: await runCase({
          ...FORK,
          state: 'error',
          error: makeError(403, 'API rate limit exceeded'),
        }),
        fork_rate_limit_pending: await runCase({
          ...FORK,
          state: 'pending',
          error: makeError(403, 'API rate limit exceeded'),
        }),
        fork_rate_limit_response_message: await runCase({
          ...FORK,
          state: 'success',
          error: makeError(403, 'Forbidden', {}, 'secondary rate limit exceeded'),
        }),
        fork_primary_rate_limit_header: await runCase({
          ...FORK,
          state: 'success',
          error: makeError(403, 'Forbidden', { 'x-ratelimit-remaining': '0' }),
        }),
        fork_secondary_rate_limit_header: await runCase({
          ...FORK,
          state: 'success',
          error: makeError(403, 'Forbidden', { 'retry-after': '60' }),
        }),
        fork_server_error: await runCase({
          ...FORK,
          state: 'success',
          error: makeError(500, 'Internal server error'),
        }),
        happy_path: await runCase({ ...FORK, state: 'success', error: null }),
      };
      process.stdout.write(JSON.stringify(outcomes));
    })();
    """).strip()


def _extract_status_script() -> str:
    document = yaml.safe_load(GATE_WORKFLOW.read_text(encoding="utf-8"))
    for job in document["jobs"].values():
        for step in job.get("steps") or []:
            if step.get("name") == STEP_NAME:
                return str(step["with"]["script"])
    raise AssertionError(f"{GATE_WORKFLOW} no longer defines {STEP_NAME!r}")


@pytest.fixture(scope="module")
def outcomes(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    node = shutil.which("node")
    if node is None:  # pragma: no cover - depends on the host
        message = "node is required to execute the Gate github-script step"
        if os.environ.get("CI"):
            pytest.fail(message)
        pytest.skip(message)

    workdir = tmp_path_factory.mktemp("gate-status")
    step_path = workdir / "step.js"
    step_path.write_text(_extract_status_script(), encoding="utf-8")
    runner_path = workdir / "runner.js"
    runner_path.write_text(RUNNER_JS, encoding="utf-8")

    completed = subprocess.run(
        [node, str(runner_path), str(step_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    return dict(json.loads(completed.stdout))


def test_fork_read_only_403_does_not_fail_the_gate(outcomes: dict[str, Any]) -> None:
    assert outcomes["fork_read_only"]["threw"] is None
    assert outcomes["fork_read_only"]["failures"] == []


def test_fork_read_only_403_reports_the_real_verdict(outcomes: dict[str, Any]) -> None:
    case = outcomes["fork_read_only"]
    warning = " ".join(case["warnings"])
    summary = " ".join(case["summaryRaw"])
    assert "read-only" in warning
    assert "'success'" in warning
    assert case["summaryWrites"] == 1
    assert "headsha" in summary
    assert "success" in summary
    assert "all checks passed" in summary


def test_fork_read_only_403_preserves_failure_verdict(
    outcomes: dict[str, Any],
) -> None:
    case = outcomes["fork_read_only_failure"]
    warning = " ".join(case["warnings"])
    summary = " ".join(case["summaryRaw"])
    assert case["threw"] is None
    assert "'failure'" in warning
    assert "failure" in summary
    assert len(case["failures"]) == 1
    assert "'failure'" in case["failures"][0]


@pytest.mark.parametrize("state", ["error", "pending"])
def test_fork_read_only_403_fails_closed_for_other_non_success_verdicts(
    outcomes: dict[str, Any], state: str
) -> None:
    case = outcomes[f"fork_read_only_{state}"]
    assert case["threw"] is None
    assert len(case["failures"]) == 1
    assert f"'{state}'" in case["failures"][0]


def test_deleted_fork_read_only_403_reports_the_verdict(
    outcomes: dict[str, Any],
) -> None:
    case = outcomes["deleted_fork_read_only"]
    warning = " ".join(case["warnings"])
    assert case["threw"] is None
    assert "deleted source repository" in warning
    assert case["summaryWrites"] == 1


def test_same_repo_403_still_fails_the_gate(outcomes: dict[str, Any]) -> None:
    case = outcomes["same_repo_read_only"]
    assert case["threw"]["status"] == 403
    assert case["summaryWrites"] == 0
    assert case["failures"] == []
    assert not any("read-only" in warning for warning in case["warnings"])


def test_rate_limit_403_keeps_its_own_path(outcomes: dict[str, Any]) -> None:
    for key in (
        "fork_rate_limit",
        "fork_rate_limit_response_message",
        "fork_primary_rate_limit_header",
        "fork_secondary_rate_limit_header",
    ):
        case = outcomes[key]
        assert case["threw"] is None
        assert any("Rate limit" in warning for warning in case["warnings"])
        assert case["summaryWrites"] == 0


@pytest.mark.parametrize("state", ["failure", "error", "pending"])
def test_rate_limit_403_fails_closed_for_non_success_verdicts(
    outcomes: dict[str, Any], state: str
) -> None:
    case = outcomes[f"fork_rate_limit_{state}"]
    assert case["threw"] is None
    assert len(case["failures"]) == 1
    assert f"'{state}'" in case["failures"][0]


def test_non_403_errors_still_fail_the_gate(outcomes: dict[str, Any]) -> None:
    assert outcomes["fork_server_error"]["threw"]["status"] == 500


def test_successful_status_write_is_silent(outcomes: dict[str, Any]) -> None:
    case = outcomes["happy_path"]
    assert case["threw"] is None
    assert case["warnings"] == []
    assert case["failures"] == []
    assert case["summaryWrites"] == 0
    assert case["summaryRaw"] == []
    assert case["statusRequests"] == [
        {
            "owner": "stranske",
            "repo": "trip-planner",
            "sha": "headsha",
            "state": "success",
            "context": "Gate / gate",
            "description": "all checks passed",
            "target_url": "https://example.invalid/run",
        }
    ]
