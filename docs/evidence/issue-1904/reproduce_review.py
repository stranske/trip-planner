"""Replay the two review regressions in an exclusively owned checkout.

Usage: python docs/evidence/issue-1904/reproduce_review.py /tmp/issue-1904-review
"""

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET


def main():
    root = Path(__file__).resolve().parents[3]
    out = Path(sys.argv[1]).resolve()
    assert not out.is_relative_to(root), "Use an external evidence directory"
    out.mkdir(parents=True, exist_ok=True)
    source = root / "trip_planner/app/services/proposal.py"
    original = source.read_bytes()
    previous = subprocess.check_output(
        [
            "git",
            "show",
            "62673c2845ed914bdc8f8d9178e04699f8ce5b39:trip_planner/app/services/proposal.py",
        ],
        cwd=root,
    )
    assert (
        hashlib.sha256(previous).hexdigest()
        == "676eb734e1cf9a70fbbca39ca42ec6c626a9c932b3eaa9aa0939dadae6117728"
    )
    nodes = [
        "tests/app/test_proposal.py::test_native_lineage_prefers_current_saved_scenario_for_shared_itinerary",
        "tests/app/test_proposal.py::test_unsupported_saved_lineage_is_not_advertised_or_reoptimized",
    ]

    def run(label):
        argv = [
            sys.executable,
            "-m",
            "pytest",
            *nodes,
            "-q",
            "--tb=short",
            "--junitxml=" + str(out / (label + ".xml")),
        ]
        result = subprocess.run(argv, cwd=root, text=True, capture_output=True)
        (out / (label + ".log")).write_text(result.stdout + result.stderr)
        cases = list(ET.parse(out / (label + ".xml")).getroot().iter("testcase"))
        return {
            "exit": result.returncode,
            "tests": len(cases),
            "failures": sum(c.find("failure") is not None for c in cases),
            "errors": sum(c.find("error") is not None for c in cases),
            "skips": sum(c.find("skipped") is not None for c in cases),
        }

    try:
        source.write_bytes(previous)
        red = run("prior-red")
        assert red == {"exit": 1, "tests": 2, "failures": 2, "errors": 0, "skips": 0}, red
    finally:
        source.write_bytes(original)
        assert source.read_bytes() == original
    green = run("current-green")
    assert green == {"exit": 0, "tests": 2, "failures": 0, "errors": 0, "skips": 0}, green
    receipt = {
        "baseline": "62673c2845ed914bdc8f8d9178e04699f8ce5b39",
        "baseline_sha256": "676eb734e1cf9a70fbbca39ca42ec6c626a9c932b3eaa9aa0939dadae6117728",
        "current_sha256": hashlib.sha256(original).hexdigest(),
        "restored_byte_identical": source.read_bytes() == original,
        "red": red,
        "green": green,
    }
    (out / "receipt.json").write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt))


if __name__ == "__main__":
    main()
