from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
TRIP_PLANNER_ROOT = REPO_ROOT / "trip_planner"


def _production_tests_import_offenders() -> list[str]:
    offenders: list[str] = []
    for path in TRIP_PLANNER_ROOT.rglob("*.py"):
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if "from tests." in stripped or stripped.startswith("import tests"):
                offenders.append(f"{path.relative_to(REPO_ROOT)}:{line_no}: {stripped}")
    return offenders


def test_no_production_imports_from_tests_package() -> None:
    offenders = _production_tests_import_offenders()
    assert offenders == [], "Production code must not import from tests:\n" + "\n".join(offenders)


def test_app_imports_from_installed_wheel_without_tests_package() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        wheel_dir = tmp / "wheels"
        venv_dir = tmp / "venv"
        wheel_dir.mkdir()

        subprocess.run(
            [sys.executable, "-m", "pip", "wheel", ".", "--no-deps", "-w", str(wheel_dir)],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        wheels = [wheel for wheel in wheel_dir.glob("trip_planner-*.whl")]
        assert (
            len(wheels) == 1
        ), f"expected one trip_planner wheel, found: {list(wheel_dir.glob('*.whl'))}"

        subprocess.run(
            [sys.executable, "-m", "venv", str(venv_dir)],
            check=True,
            capture_output=True,
            text=True,
        )
        venv_python = venv_dir / "bin" / "python"
        subprocess.run(
            [str(venv_python), "-m", "pip", "install", str(wheels[0])],
            check=True,
            capture_output=True,
            text=True,
        )

        result = subprocess.run(
            [
                str(venv_python),
                "-c",
                (
                    "from trip_planner.app.services.auth import AuthenticatedUser\n"
                    "from trip_planner.app.services.workspace import get_workspace_payload\n"
                    "from trip_planner.app.services.workspace_fixtures import load_trip_record\n"
                    "class _StubSession:\n"
                    "    def scalar(self, _stmt):\n"
                    "        return None\n"
                    "trip_id = 'trip-leisure-kyoto-draft'\n"
                    "assert load_trip_record('leisure_draft_trip.json').trip.trip_id == trip_id\n"
                    "payload = get_workspace_payload(\n"
                    "    _StubSession(),\n"
                    "    user=AuthenticatedUser(\n"
                    "        user_id='user-leisure-1',\n"
                    "        email='leisure@example.com',\n"
                    "        display_name='Leisure User',\n"
                    "    ),\n"
                    "    trip_id=trip_id,\n"
                    ")\n"
                    "assert payload is not None\n"
                    "assert payload['sample_data']['is_sample'] is True\n"
                    "assert payload['trip_record']['trip']['trip_id'] == trip_id\n"
                ),
            ],
            cwd=tmp,
            check=False,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr or result.stdout


def test_scenario_personas_match_packaged_fixture_map() -> None:
    from trip_planner.preferences.fixture_corpus import load_fixture_map

    fixture_map = load_fixture_map()
    urban_historian = fixture_map["urban-historian"]
    assert urban_historian.id == "urban-historian"
    assert urban_historian.profile.to_dict()["profile_kind"] == "leisure"
    assert urban_historian.intended_interpretation.dominant_dimensions


@pytest.mark.parametrize(
    "bad_import_line",
    [
        "from tests.preferences.fixture_corpus import load_fixture_map",
    ],
)
def test_production_tests_import_guard_fails_on_deliberate_break(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    bad_import_line: str,
) -> None:
    # Exercise the same scanner on a private tree. Mutating the checkout races
    # with the production guard and wheel builds in other pytest-xdist workers.
    package_root = tmp_path / "trip_planner"
    scenarios_path = package_root / "app" / "services" / "scenarios.py"
    scenarios_path.parent.mkdir(parents=True)
    scenarios_path.write_text(
        "from trip_planner.preferences.fixture_corpus import load_fixture_map\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(sys.modules[__name__], "REPO_ROOT", tmp_path)
    monkeypatch.setattr(sys.modules[__name__], "TRIP_PLANNER_ROOT", package_root)
    assert _production_tests_import_offenders() == []

    scenarios_path.write_text(bad_import_line + "\n", encoding="utf-8")
    assert _production_tests_import_offenders() == [
        f"{scenarios_path.relative_to(tmp_path)}:1: {bad_import_line}"
    ]
