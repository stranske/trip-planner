from __future__ import annotations

import ast
from pathlib import Path

FORBIDDEN_METHODS = {
    "submit_proposal",
    "fetch_policy_constraints",
    "fetch_evaluation_result",
    "poll_execution_status",
}

CANONICAL_CLIENT_METHODS = {
    "fetch_policy_constraints",
    "submit_proposal",
    "fetch_evaluation_result",
    "poll_execution_status",
}


def _base_name(base: ast.expr) -> str | None:
    if isinstance(base, ast.Name):
        return base.id
    if isinstance(base, ast.Attribute):
        return base.attr
    return None


def _forbidden_overrides_for_source(source: str) -> list[tuple[str, str]]:
    tree = ast.parse(source)
    violations: list[tuple[str, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        base_names = {name for base in node.bases if (name := _base_name(base)) is not None}
        if "BaseTPPIntegrationClient" not in base_names:
            continue
        for body_node in node.body:
            if (
                isinstance(body_node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and body_node.name in FORBIDDEN_METHODS
            ):
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


def test_interface_rule_detector_catches_forbidden_override_with_qualified_base() -> None:
    source = """
class BadFake(client.BaseTPPIntegrationClient):
    def execute(self, request):
        return request

    def poll_execution_status(self, request):
        return request
"""
    assert _forbidden_overrides_for_source(source) == [("BadFake", "poll_execution_status")]


def test_interface_rule_detector_catches_async_forbidden_override() -> None:
    source = """
class BadFake(BaseTPPIntegrationClient):
    def execute(self, request):
        return request

    async def fetch_evaluation_result(self, request):
        return request
"""
    assert _forbidden_overrides_for_source(source) == [("BadFake", "fetch_evaluation_result")]


def test_policy_passive_client_inherits_base_and_overrides_only_execute() -> None:
    policy_source = Path("trip_planner/app/services/policy.py").read_text(encoding="utf-8")
    tree = ast.parse(policy_source)
    passive_client = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef) and node.name == "_PassiveTPPClient"
    )

    base_names = {name for base in passive_client.bases if (name := _base_name(base)) is not None}
    assert "BaseTPPIntegrationClient" in base_names

    method_names = {node.name for node in passive_client.body if isinstance(node, ast.FunctionDef)}
    assert method_names <= {"__init__", "execute"}


def test_tpp_client_interface_surface_remains_canonical() -> None:
    source = Path("trip_planner/integrations/tpp/client.py").read_text(encoding="utf-8")
    tree = ast.parse(source)

    protocol_node = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef) and node.name == "TPPIntegrationClient"
    )
    base_node = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef) and node.name == "BaseTPPIntegrationClient"
    )

    protocol_methods = {
        node.name
        for node in protocol_node.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and not node.name.startswith("_")
    }
    base_methods = {
        node.name
        for node in base_node.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and not node.name.startswith("_")
    }

    assert protocol_methods == CANONICAL_CLIENT_METHODS
    assert base_methods == CANONICAL_CLIENT_METHODS | {"execute"}
