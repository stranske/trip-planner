from trip_planner.app.main import get_allowed_cors_origin_regex, get_allowed_cors_origins


def test_allowed_cors_origins_keep_local_defaults(monkeypatch) -> None:
    monkeypatch.delenv("TRIP_PLANNER_CORS_ORIGINS", raising=False)

    assert get_allowed_cors_origins() == [
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ]


def test_allowed_cors_origins_add_hosted_frontends(monkeypatch) -> None:
    monkeypatch.setenv(
        "TRIP_PLANNER_CORS_ORIGINS",
        "https://trip-planner.netlify.app/, https://preview.example.netlify.app",
    )

    assert get_allowed_cors_origins() == [
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "https://trip-planner.netlify.app",
        "https://preview.example.netlify.app",
    ]


def test_allowed_cors_origin_regex_is_optional(monkeypatch) -> None:
    monkeypatch.delenv("TRIP_PLANNER_CORS_ORIGIN_REGEX", raising=False)

    assert get_allowed_cors_origin_regex() is None


def test_allowed_cors_origin_regex_returns_configured_pattern(monkeypatch) -> None:
    monkeypatch.setenv(
        "TRIP_PLANNER_CORS_ORIGIN_REGEX",
        r" https://deploy-preview-[0-9]+--trip-planner\.netlify\.app ",
    )

    assert get_allowed_cors_origin_regex() == r"https://deploy-preview-[0-9]+--trip-planner\.netlify\.app"
