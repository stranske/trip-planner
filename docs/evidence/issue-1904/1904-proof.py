"""Replay in an exclusively owned checkout; pass an external output directory.

Usage: python docs/evidence/issue-1904/1904-proof.py /tmp/issue-1904-replay
Original immutable capture identities are in validation.json.
"""

import pathlib
import subprocess
import sys
import hashlib
import json
import xml.etree.ElementTree as ET


def main():
    P = pathlib.Path(sys.argv[1]).resolve()
    P.mkdir(parents=True, exist_ok=True)
    W = pathlib.Path(__file__).resolve().parents[3]
    PYTHON = sys.executable
    f = W / "trip_planner/app/services/proposal.py"
    original = f.read_bytes()

    def sha(b):
        return hashlib.sha256(b).hexdigest()

    test = "tests/app/test_proposal.py::test_native_submit_then_reoptimize_without_injected_source_version"

    def run(label):
        args = [
            PYTHON,
            "-m",
            "pytest",
            test,
            "-q",
            "--tb=short",
            "--junitxml=" + str(P / (label + ".xml")),
        ]
        r = subprocess.run(args, cwd=W, text=True, capture_output=True)
        (P / (label + ".log")).write_text(r.stdout + r.stderr)
        root = ET.parse(P / (label + ".xml")).getroot()
        cases = list(root.iter("testcase"))
        return {
            "argv": args,
            "exit": r.returncode,
            "tests": len(cases),
            "failures": sum((c.find("failure") is not None for c in cases)),
            "errors": sum((c.find("error") is not None for c in cases)),
            "skips": sum((c.find("skipped") is not None for c in cases)),
        }

    rows = []
    try:
        needle = (
            b"source_version = _submission_source_version(workspace, resolved_scenario_id, trip_id)"
        )
        assert original.count(needle) == 1
        f.write_bytes(original.replace(needle, b"source_version = None"))
        red = run("1904-builder-red")
        assert red["exit"] == 1 and red["failures"] == 1 and (red["errors"] == 0), red
        rows.append({"mutation": "Remove native builder lineage assignment", "result": red})
        f.write_bytes(original)
        assert sha(f.read_bytes()) == sha(original)
        green = run("1904-builder-restored")
        assert (
            green["exit"] == 0
            and green["tests"] == 1
            and (green["errors"] == green["failures"] == green["skips"] == 0)
        ), green
        rows.append({"restored": green})
        old = subprocess.run(
            [
                "git",
                "show",
                "47173b69d1c2d420d21983abd172e4b821038266:trip_planner/app/services/proposal.py",
            ],
            cwd=W,
            capture_output=True,
            check=True,
        ).stdout
        assert sha(old) == "7bb55167a363aae24c5bba3e1388681b901b4a0cb4db85c88ebd09c8efa68a09"
        f.write_bytes(old)
        red = run("1904-original-red")
        assert red["exit"] == 1 and red["failures"] == 1 and (red["errors"] == 0), red
        rows.append(
            {
                "mutation": "Actual original production proposal module",
                "source_sha256": sha(old),
                "result": red,
            }
        )
    finally:
        f.write_bytes(original)
        assert sha(f.read_bytes()) == sha(original)
    final = run("1904-restored")
    assert (
        final["exit"] == 0
        and final["tests"] == 1
        and (final["errors"] == final["failures"] == final["skips"] == 0)
    ), final
    (P / "1904-causal.json").write_text(
        json.dumps(
            {
                "source_sha256": sha(original),
                "restored_byte_identical": True,
                "rows": rows,
                "final": final,
            },
            indent=2,
        )
    )
    print(json.dumps(rows))
    print("FINAL", final)


if __name__ == "__main__":
    main()
