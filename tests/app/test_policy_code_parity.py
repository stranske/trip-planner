"""The chat and the Policy tab must explain the same rule codes the same way.

`trip_planner/app/services/policy_codes.py` mirrors `frontend/src/lib/policyCodes.ts`; this
fails if a code is added to one and not the other, or if the advice diverges.
"""

import re
from pathlib import Path

from trip_planner.app.services.policy_codes import EXPLANATIONS

_TS = Path(__file__).resolve().parents[2] / "frontend/src/lib/policyCodes.ts"


def _typescript_entries() -> dict[str, tuple[str, str]]:
    text = _TS.read_text(encoding="utf-8")
    entries: dict[str, tuple[str, str]] = {}
    pattern = re.compile(
        r'^\s{2}"?([A-Za-z0-9_-]+)"?: \{\s*meaning:\s*"(.*?)",\s*whatToDo:\s*"(.*?)",?\s*\},',
        re.S | re.M,
    )
    for code, meaning, what_to_do in pattern.findall(text):
        entries[code] = (" ".join(meaning.split()), " ".join(what_to_do.split()))
    return entries


def test_both_sides_explain_the_same_codes_the_same_way() -> None:
    typescript = _typescript_entries()
    assert typescript, "could not read any entries from policyCodes.ts"
    assert set(typescript) == set(EXPLANATIONS)
    for code, (meaning, what_to_do) in EXPLANATIONS.items():
        assert typescript[code] == (meaning, what_to_do), code
