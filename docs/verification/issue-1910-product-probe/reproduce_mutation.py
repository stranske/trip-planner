"""Reproduce the TP3 production mutation; invoke with the repository interpreter."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BASELINE = "47173b69d1c2d420d21983abd172e4b821038266"
SOURCE = ROOT / "scripts/check_full_product_verification.py"
TEST = "tests/scripts/test_check_full_product_verification.py::test_product_probe_report_marks_constant_figures_fabricated"


def main() -> None:
    subprocess.run(["git", "cat-file", "-e", BASELINE], cwd=ROOT, check=True)
    output = (
        Path(sys.argv[1]) if len(sys.argv) > 1 else Path(tempfile.mkdtemp(prefix="tp1910-proof-"))
    )
    output.mkdir(parents=True, exist_ok=True)
    original = SOURCE.read_bytes()
    text = original.decode()
    start = text.index("    moved = [pair[0][")
    end = text.index("\n\ndef _probe_planner", start)
    mutated = (
        text[:start] + '    return "WORKS"  # deliberately ignore cross-pair figures\n' + text[end:]
    ).encode()
    (output / "original-source.py").write_bytes(original)
    (output / "mutated-source.py").write_bytes(mutated)
    commands = []
    try:
        SOURCE.write_bytes(mutated)
        command = [sys.executable, "-m", "pytest", TEST, "-q", f"--junitxml={output / 'red.xml'}"]
        red = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
        commands.append(command)
        (output / "red.log").write_text(red.stdout + red.stderr)
        tree = ET.parse(output / "red.xml")
        cases = tree.findall(".//testcase")
        failures = tree.findall(".//failure")
        assert red.returncode == 1 and len(cases) == 2 and len(failures) == 1
        assert (
            "constant-figures"
            in next(case for case in cases if case.find("failure") is not None).attrib["name"]
        )
        assert "FABRICATED" in (failures[0].text or "") and "WORKS" in (failures[0].text or "")
    finally:
        SOURCE.write_bytes(original)
        assert SOURCE.read_bytes() == original
    command = [sys.executable, "-m", "pytest", TEST, "-q", f"--junitxml={output / 'green.xml'}"]
    green = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=True)
    commands.append(command)
    (output / "green.log").write_text(green.stdout + green.stderr)
    tree = ET.parse(output / "green.xml")
    assert len(tree.findall(".//testcase")) == 2
    assert not tree.findall(".//failure") and not tree.findall(".//error")

    def digest(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    (output / "mutation.json").write_text(
        json.dumps(
            {
                "baseline": BASELINE,
                "commands": commands,
                "original_sha256": digest(original),
                "mutated_sha256": digest(mutated),
                "restored_sha256": digest(SOURCE.read_bytes()),
                "red": {"tests": 2, "failures": 1, "errors": 0},
                "green": {"tests": 2, "failures": 0, "errors": 0},
            },
            indent=2,
        )
        + "\n"
    )
    print(output)


if __name__ == "__main__":
    main()
