from __future__ import annotations

import ast
from pathlib import Path

FORBIDDEN_METHODS = {
    "submit_proposal",
    "fetch_policy_constraints",
    "fetch_evaluation_result",
    "poll_execution_status",
}


def _forbidden_overrides_for_source(source: str) -> list[tuple[str, str]]:
    tree = ast.parse(source)
    violations: list[tuple[str, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        base_names = {base.id for base in node.bases if isinstance(base, ast.Name)}
        if "BaseTPPIntegrationClient" not in base_names:
            continue
        for body_node in node.body:
            if isinstance(body_node, ast.FunctionDef) and body_node.name in FORBIDDEN_METHODS:
                violations.append((node.name, body_node.name))
    return violations


def test_tpp_test_fakes_override_only_execute() -> None:
    test_dir = Path("tests")
    violations: list[str] = []
    for path in test_dir.rglob("*.py"):
        found = _forbidden_overrides_for_source(path.read_text(encoding="utf-8"))
        for class_name, method_name in found:
            violations.append(f"{path}:{class_name}.{method_name}")
    assert not violations, "TPP fake clients must override only execute(): " + ", ".join(violations)


def test_interface_rule_detector_catches_forbidden_override() -> None:
    source = """
class BadFake(BaseTPPIntegrationClient):
    def execute(self, request):
        return request

    def submit_proposal(self, request):
        return request
"""
    assert _forbidden_overrides_for_source(source) == [("BadFake", "submit_proposal")]


def test_policy_passive_client_inherits_base_and_overrides_only_execute() -> None:
    policy_source = Path("trip_planner/app/services/policy.py").read_text(encoding="utf-8")
    tree = ast.parse(policy_source)
    passive_client = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef) and node.name == "_PassiveTPPClient"
    )

    base_names = {base.id for base in passive_client.bases if isinstance(base, ast.Name)}
    assert "BaseTPPIntegrationClient" in base_names

    method_names = {node.name for node in passive_client.body if isinstance(node, ast.FunctionDef)}
    assert method_names <= {"__init__", "execute"}
