import json
import os
from unittest.mock import patch

import scripts.generate_segments as gs  # noqa: E402


def fake_chat_completion(*args, **kwargs):
    """Return a stubbed OpenAI response content matching the expected schema."""
    return json.dumps([{"id": "SEG1", "Nat": 3, "Cult": 2, "GS": 4, "EB": 3}])


@patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
@patch("scripts.generate_segments._create_chat_completion", side_effect=fake_chat_completion)
def test_generate_segments_schema(mock_openai, tmp_path, monkeypatch):
    """generate_segments.py should write a JSON file with expected keys."""
    # Create a minimal request.json for the script
    request_json = tmp_path / "request.json"
    request_json.write_text(
        json.dumps(
            {
                "nature_ratio": 0.5,
                "must_see": ["Paris", "Rome"],
                "trip_window": {"months": ["June", "July"]},
            }
        )
    )

    # Change to tmp_path so the script finds request.json
    monkeypatch.chdir(tmp_path)

    out_path = tmp_path / "segments_master.json"
    gs.main(output_path=str(out_path))

    data = json.loads(out_path.read_text())
    assert "segments" in data

    seg = data["segments"][0]
    for key in ("id", "Nat", "Cult", "GS", "EB"):
        assert key in seg
