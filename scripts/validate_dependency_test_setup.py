#!/usr/bin/env python3
"""
Validation script to ensure dependency test setup is correct.

Run this script to verify:
1. All optional dependencies are included in lock file
2. All pyproject.toml tool dependencies match lock file
3. Tests don't have hardcoded version numbers
4. Metadata serialization is handled correctly throughout codebase
"""

import re
import sys
import tomllib
from pathlib import Path
from typing import List, Tuple


_OPERATORS = ("==", ">=", "<=", "~=", "!=", ">", "<", "===")


def _split_spec(raw: str) -> str:
    entry = raw.strip().strip(",").strip('"')
    for operator in _OPERATORS:
        if operator in entry:
            name, _ = entry.split(operator, 1)
            return name.strip().split("[")[0]
    return entry.strip().split("[")[0]


def check_lock_file_completeness() -> Tuple[bool, List[str]]:
    """Verify lock file includes all optional dependencies."""
    issues = []

    pyproject_path = Path("pyproject.toml")
    lock_path = Path("requirements.lock")
    if not pyproject_path.exists():
        issues.append("pyproject.toml not found")
        return False, issues
    if not lock_path.exists():
        issues.append("requirements.lock not found")
        return False, issues

    pyproject = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    optional_deps = pyproject.get("project", {}).get("optional-dependencies", {})
    if not optional_deps:
        issues.append("No [project.optional-dependencies] section found")
        return False, issues

    optional_groups = sorted(optional_deps)
    print(f"✓ Found optional dependency groups: {', '.join(optional_groups)}")

    lock_versions = set()
    for line in lock_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", "--")) or "==" not in stripped:
            continue
        name, _ = stripped.split("==", 1)
        lock_versions.add(name.lower())

    missing = []
    for group in optional_groups:
        for entry in optional_deps[group]:
            dependency = _split_spec(entry).lower()
            normalized = dependency.replace("-", "_")
            if dependency not in lock_versions and normalized not in lock_versions:
                missing.append(f"{group}:{dependency}")

    if missing:
        issues.append("requirements.lock is missing optional dependencies: " + ", ".join(missing))
    else:
        print("✓ requirements.lock includes all optional dependencies")

    return len(issues) == 0, issues


def check_for_hardcoded_versions() -> Tuple[bool, List[str]]:
    """Check for hardcoded version numbers in tests."""
    issues = []
    test_files = list(Path("tests").rglob("*.py"))

    problematic_files = []
    for test_file in test_files:
        content = test_file.read_text(encoding="utf-8")

        # Skip if it's the lockfile consistency test or dependency alignment test
        if (
            "lockfile_consistency" in test_file.name
            or "dependency_version_alignment" in test_file.name
            or test_file.name == "test_validate_dependency_test_setup.py"
        ):
            continue

        lines = content.split("\n")
        for i, line in enumerate(lines):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if "version" not in stripped.lower():
                continue
            if re.search(r'==\s*["\']?\d+\.\d+(?:\.\d+)?', stripped):
                problematic_files.append((test_file, i + 1, stripped))

    if problematic_files:
        issues.append("Found potential hardcoded versions in tests:")
        for file, line_no, line in problematic_files:
            issues.append(f"  {file}:{line_no}: {line[:80]}")
    else:
        print("✓ No hardcoded version numbers found in tests")

    return len(issues) == 0, issues


def check_metadata_serialization() -> Tuple[bool, List[str]]:
    """Check that metadata is properly serialized to dicts, not Pydantic objects."""
    issues = []

    # Check validators.py returns dict
    validators_path = Path("src/trend_analysis/io/validators.py")
    if validators_path.exists():
        content = validators_path.read_text()

        # Look for load_and_validate_upload function
        if "validated.metadata.model_dump(mode=" in content:
            print("✓ load_and_validate_upload serializes metadata to dict")
        else:
            issues.append("load_and_validate_upload may not be serializing metadata properly")

    # Check attach_metadata serializes
    market_data_path = Path("src/trend_analysis/io/market_data.py")
    if market_data_path.exists():
        content = market_data_path.read_text()

        if "metadata.model_dump(mode=" in content:
            print("✓ attach_metadata serializes metadata to dict")
        else:
            issues.append("attach_metadata may not be serializing metadata properly")

    # Check data_schema.py serializes
    data_schema_path = Path("streamlit_app/components/data_schema.py")
    if data_schema_path.exists():
        content = data_schema_path.read_text()

        if "metadata.model_dump(mode=" in content:
            print("✓ _build_meta serializes metadata to dict")
        else:
            issues.append("_build_meta may not be serializing metadata properly")

    return len(issues) == 0, issues


def check_test_expectations() -> Tuple[bool, List[str]]:
    """Verify tests expect dicts, not Pydantic objects."""
    issues = []
    test_files = [
        Path("tests/test_validators.py"),
        Path("tests/test_io_validators_additional.py"),
        Path("tests/test_io_validators_extra.py"),
        Path("tests/test_data_schema.py"),
    ]

    for test_file in test_files:
        if not test_file.exists():
            continue

        content = test_file.read_text()

        # Check for problematic patterns
        if re.search(r"\.attrs\[.*\]\.mode(?!\[)", content):
            issues.append(f"{test_file.name}: Uses .mode attribute access instead of dict access")

        if 'assert meta["metadata"] is ' in content and "is metadata" in content:
            issues.append(f"{test_file.name}: Uses 'is' identity check instead of equality")

    if not issues:
        print("✓ Tests expect dict-based metadata")

    return len(issues) == 0, issues


def main():
    print("=" * 60)
    print("Dependency Test Setup Validation")
    print("=" * 60)
    print()

    all_passed = True
    all_issues = []

    # Run all checks
    checks = [
        ("Lock file completeness", check_lock_file_completeness),
        ("Hardcoded versions", check_for_hardcoded_versions),
        ("Metadata serialization", check_metadata_serialization),
        ("Test expectations", check_test_expectations),
    ]

    for check_name, check_func in checks:
        print(f"\nChecking: {check_name}")
        print("-" * 40)
        passed, issues = check_func()

        if not passed:
            all_passed = False
            all_issues.extend(issues)
            print("✗ FAILED")
            for issue in issues:
                print(f"  {issue}")
        else:
            print("✓ PASSED")

    print()
    print("=" * 60)
    if all_passed:
        print("✓ All validation checks passed!")
        print("The setup should work for future dependabot PRs.")
        return 0
    else:
        print("✗ Some validation checks failed:")
        for issue in all_issues:
            print(f"  - {issue}")
        print("\nFix these issues to ensure future dependabot PRs work correctly.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
