import json
from pathlib import Path

import pytest

from scripts import build_html


@pytest.mark.parametrize("itineraries", [[{"days": 21}, {"days": 7}], []], ids=["trips", "empty"])
def test_build_html_executes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, itineraries: list[dict[str, int]]
) -> None:
    """Render both bundles without overwriting the repository's HTML sources."""
    monkeypatch.chdir(tmp_path)
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "itineraries_compact.json").write_text(
        json.dumps({"itineraries": itineraries}), encoding="utf-8"
    )
    for variant in ("analytical", "experiential"):
        template = tmp_path / "bundle" / variant / "index.html"
        template.parent.mkdir(parents=True)
        template.write_text(
            f"<title>{variant}</title>"
            "{% for itin in itins %}<p>{{ itin.days }} days</p>{% endfor %}",
            encoding="utf-8",
        )

    build_html.main()

    for variant in ("analytical", "experiential"):
        rendered = (tmp_path / "bundle" / variant / "index.html").read_text(encoding="utf-8")
        assert rendered == f"<title>{variant}</title>" + "".join(
            f"<p>{itin['days']} days</p>" for itin in itineraries
        )
