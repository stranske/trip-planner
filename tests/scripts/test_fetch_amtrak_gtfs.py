"""Feed publication keeps prior data and isolates overlapping downloads."""

from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import fetch_amtrak_gtfs
from trip_planner.sources import rail_schedule


def schedule():
    return SimpleNamespace(stations=[1], trips=[1, 2], calendar={})


def test_validation_precedes_publication(tmp_path, monkeypatch):
    target = tmp_path / "GTFS.zip"
    target.write_bytes(b"previous valid feed")
    monkeypatch.setattr(fetch_amtrak_gtfs, "urlopen", lambda *a, **k: BytesIO(b"new feed"))

    def load(partial):
        assert partial.read_bytes() == b"new feed"
        assert target.read_bytes() == b"previous valid feed"
        return schedule()

    monkeypatch.setattr(rail_schedule, "_load", load)
    assert fetch_amtrak_gtfs.main([str(target)]) == 0
    assert target.read_bytes() == b"new feed"
    assert list(tmp_path.iterdir()) == [target]


@pytest.mark.parametrize("failure", ["download", "validation"])
def test_failure_preserves_target_and_cleans_own_partial(tmp_path, monkeypatch, failure):
    target = tmp_path / "GTFS.zip"
    target.write_bytes(b"previous valid feed")

    class BrokenDownload(BytesIO):
        def read(self, *args):
            raise OSError("truncated transfer")

    response = BrokenDownload() if failure == "download" else BytesIO(b"invalid feed")
    monkeypatch.setattr(fetch_amtrak_gtfs, "urlopen", lambda *a, **k: response)

    def load(partial):
        raise ValueError("invalid timetable")

    monkeypatch.setattr(rail_schedule, "_load", load)
    with pytest.raises((OSError, ValueError)):
        fetch_amtrak_gtfs.main([str(target)])
    assert target.read_bytes() == b"previous valid feed"
    assert list(tmp_path.iterdir()) == [target]


def test_overlapping_fetches_do_not_replace_or_remove_another_partial(tmp_path, monkeypatch):
    target = tmp_path / "GTFS.zip"
    target.write_bytes(b"previous valid feed")
    unrelated = target.with_suffix(".partial")
    unrelated.write_bytes(b"another process owns this")
    monkeypatch.setattr(fetch_amtrak_gtfs, "urlopen", lambda url, **k: BytesIO(url.encode()))
    validated_paths = []

    def load(partial: Path):
        validated_paths.append(partial)
        payload = partial.read_bytes()
        if payload == b"outer":
            assert fetch_amtrak_gtfs.main([str(target), "--url", "inner"]) == 0
            assert target.read_bytes() == b"inner"
            assert partial.read_bytes() == b"outer"
        return schedule()

    monkeypatch.setattr(rail_schedule, "_load", load)
    assert fetch_amtrak_gtfs.main([str(target), "--url", "outer"]) == 0
    assert len(set(validated_paths)) == 2
    assert target.read_bytes() == b"outer"
    assert unrelated.read_bytes() == b"another process owns this"
    assert sorted(tmp_path.iterdir()) == sorted([target, unrelated])
