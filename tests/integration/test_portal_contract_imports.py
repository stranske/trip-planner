"""A pinned service must not reuse dependencies from a different TPP installation."""

from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType

import pytest

from tests.integration.portal_contract_checkout import verify_portal_contract_imports


@pytest.fixture(autouse=True)
def isolate_synthetic_producer_namespace(monkeypatch: pytest.MonkeyPatch):
    """These unit tests install synthetic modules; retain real app imports outside each test."""
    for name in list(sys.modules):
        if name == "travel_plan_permission" or name.startswith("travel_plan_permission."):
            monkeypatch.delitem(sys.modules, name)


def _module(name: str, path: Path) -> ModuleType:
    module = ModuleType(name)
    module.__file__ = str(path)
    return module


@pytest.mark.parametrize("name", ["travel_plan_permission", "travel_plan_permission.policy"])
def test_pinned_contract_rejects_preloaded_foreign_dependencies(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    checkout = tmp_path / "producer"
    module = _module(name, tmp_path / "installed" / "policy.py")
    monkeypatch.setitem(sys.modules, name, module)

    with pytest.raises(pytest.UsageError, match="outside the pinned TPP checkout"):
        verify_portal_contract_imports(checkout)


def test_pinned_service_cannot_hide_a_foreign_policy_module(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "src" / "travel_plan_permission"
    monkeypatch.setitem(
        sys.modules,
        "travel_plan_permission.http_service",
        _module("travel_plan_permission.http_service", source / "http_service.py"),
    )
    monkeypatch.setitem(
        sys.modules,
        "travel_plan_permission.policy",
        _module("travel_plan_permission.policy", tmp_path / "installed" / "policy.py"),
    )

    with pytest.raises(pytest.UsageError, match="outside the pinned TPP checkout"):
        verify_portal_contract_imports(tmp_path)


def test_pinned_package_rejects_a_foreign_search_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "src" / "travel_plan_permission"
    module = _module("travel_plan_permission", source / "__init__.py")
    module.__path__ = [str(source), str(tmp_path / "installed")]
    monkeypatch.setitem(sys.modules, module.__name__, module)

    with pytest.raises(pytest.UsageError, match="outside the pinned TPP checkout"):
        verify_portal_contract_imports(tmp_path)


def test_pinned_contract_accepts_dependencies_from_its_source_tree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "src" / "travel_plan_permission"
    package = _module("travel_plan_permission", source / "__init__.py")
    package.__path__ = [str(source)]
    monkeypatch.setitem(sys.modules, package.__name__, package)
    monkeypatch.setitem(
        sys.modules,
        "travel_plan_permission.policy",
        _module("travel_plan_permission.policy", source / "policy.py"),
    )
    # Similarly named packages outside TPP's namespace do not affect its contract.
    monkeypatch.setitem(
        sys.modules,
        "travel_plan_permission_extra",
        _module("travel_plan_permission_extra", tmp_path / "unrelated.py"),
    )

    verify_portal_contract_imports(tmp_path)


def test_pinned_contract_cannot_verify_a_module_without_source_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = ModuleType("travel_plan_permission.policy")
    monkeypatch.setitem(sys.modules, module.__name__, module)

    with pytest.raises(pytest.UsageError, match="Cannot verify pinned TPP module"):
        verify_portal_contract_imports(tmp_path)


def test_pinned_contract_rejects_source_symlinks_to_another_checkout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    foreign = tmp_path / "installed"
    foreign.mkdir()
    (foreign / "policy.py").touch()
    source = tmp_path / "producer" / "src"
    source.mkdir(parents=True)
    (source / "travel_plan_permission").symlink_to(foreign, target_is_directory=True)
    module = _module("travel_plan_permission.policy", source / "travel_plan_permission/policy.py")
    monkeypatch.setitem(sys.modules, module.__name__, module)

    with pytest.raises(pytest.UsageError, match="outside the pinned TPP checkout"):
        verify_portal_contract_imports(tmp_path / "producer")
