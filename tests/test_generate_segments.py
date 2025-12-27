import json
from unittest.mock import MagicMock, patch

import scripts.generate_segments as gs


def fake_chat_completion(*args, **kwargs):
    """Return a stubbed OpenAI response matching the expected schema."""
    fake_resp = MagicMock()
    fake_resp.choices = [
        MagicMock(
            message=MagicMock(
                content=json.dumps(
                    {
                        "segments": [
                            {"id": "SEG1", "Nat": 3, "Cult": 2, "GS": 4, "EB": 3}
                        ]
                    }
                )
            )
        )
    ]
    return fake_resp


@patch("openai.ChatCompletion.create", side_effect=fake_chat_completion)
def test_generate_segments_schema(mock_openai, tmp_path):
    """generate_segments.py should write a JSON file with expected keys."""
    out_path = tmp_path / "segments_master.json"
    gs.main(output_path=str(out_path))  # assumes generate_segments.py has main()

    data = json.loads(out_path.read_text())
    assert "segments" in data

    seg = data["segments"][0]
    for key in ("id", "Nat", "Cult", "GS", "EB"):
        assert key in seg
