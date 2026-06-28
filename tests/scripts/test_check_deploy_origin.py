"""Tests for scripts/check_deploy_origin.py."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts import check_deploy_origin as cdo


def _write_repo_layout(
    tmp_path: Path,
    *,
    readme_origin: str = "https://api.example.com",
    redirect_origin: str = "https://api.example.com",
    readme_marker: bool = True,
    redirect_marker: bool = True,
) -> Path:
    repo_root = tmp_path / "repo"
    scripts_dir = repo_root / "scripts"
    public_dir = repo_root / "frontend" / "public"
    scripts_dir.mkdir(parents=True)
    public_dir.mkdir(parents=True)

    readme_text = (
        f"Public synthetic API origin: `{readme_origin}`\n"
        if readme_marker
        else "No deploy origin marker here.\n"
    )
    redirects_text = (
        f"/api/*  {redirect_origin}/api/:splat  200\n"
        if redirect_marker
        else "# no deploy redirect marker\n"
    )

    (repo_root / "README.md").write_text(readme_text, encoding="utf-8")
    (public_dir / "_redirects").write_text(redirects_text, encoding="utf-8")
    script_path = scripts_dir / "check_deploy_origin.py"
    script_path.write_text("# test path placeholder\n", encoding="utf-8")
    return script_path


class TestHost:
    """Tests for _host() function."""

    def test_accepts_https_origin(self) -> None:
        assert cdo._host("https://example.com") == "example.com"

    def test_accepts_http_origin(self) -> None:
        assert cdo._host("http://example.com") == "example.com"

    def test_accepts_origin_with_trailing_slash(self) -> None:
        assert cdo._host("https://example.com/") == "example.com"

    def test_accepts_origin_with_subdomain(self) -> None:
        assert cdo._host("https://api.example.com") == "api.example.com"

    def test_accepts_origin_with_port(self) -> None:
        assert cdo._host("https://example.com:8080") == "example.com:8080"

    def test_rejects_missing_scheme(self) -> None:
        with pytest.raises(SystemExit) as exc_info:
            cdo._host("example.com")
        assert "Invalid origin in deploy configuration" in str(exc_info.value)
        assert "example.com" in str(exc_info.value)

    def test_rejects_invalid_scheme(self) -> None:
        with pytest.raises(SystemExit) as exc_info:
            cdo._host("ftp://example.com")
        assert "Invalid origin in deploy configuration" in str(exc_info.value)

    def test_rejects_missing_host(self) -> None:
        with pytest.raises(SystemExit) as exc_info:
            cdo._host("https://")
        assert "Invalid origin in deploy configuration" in str(exc_info.value)

    def test_rejects_path(self) -> None:
        with pytest.raises(SystemExit) as exc_info:
            cdo._host("https://example.com/api")
        assert "Deploy origin must be scheme + host only" in str(exc_info.value)
        assert "no path/query/fragment" in str(exc_info.value)

    def test_rejects_query_string(self) -> None:
        with pytest.raises(SystemExit) as exc_info:
            cdo._host("https://example.com?foo=bar")
        assert "Deploy origin must be scheme + host only" in str(exc_info.value)
        assert "no path/query/fragment" in str(exc_info.value)

    def test_rejects_fragment(self) -> None:
        with pytest.raises(SystemExit) as exc_info:
            cdo._host("https://example.com#section")
        assert "Deploy origin must be scheme + host only" in str(exc_info.value)
        assert "no path/query/fragment" in str(exc_info.value)

    def test_rejects_path_and_query(self) -> None:
        with pytest.raises(SystemExit) as exc_info:
            cdo._host("https://example.com/api?foo=bar")
        assert "Deploy origin must be scheme + host only" in str(exc_info.value)


class TestMatch:
    """Tests for _match() function."""

    def test_extracts_readme_origin(self, tmp_path: Path) -> None:
        readme_path = tmp_path / "README.md"
        readme_content = 'Public synthetic API origin: `https://api.example.com`'
        readme_path.write_text(readme_content, encoding="utf-8")

        result = cdo._match(cdo.README_ORIGIN_PATTERN, readme_content, readme_path)
        assert result == "https://api.example.com"

    def test_extracts_readme_origin_strips_trailing_slash(self, tmp_path: Path) -> None:
        readme_path = tmp_path / "README.md"
        readme_content = 'Public synthetic API origin: `https://api.example.com/`'
        readme_path.write_text(readme_content, encoding="utf-8")

        result = cdo._match(cdo.README_ORIGIN_PATTERN, readme_content, readme_path)
        assert result == "https://api.example.com"

    def test_extracts_redirects_origin(self, tmp_path: Path) -> None:
        redirects_path = tmp_path / "_redirects"
        redirects_content = "/api/*  https://api.example.com/api/:splat  200"
        redirects_path.write_text(redirects_content, encoding="utf-8")

        result = cdo._match(cdo.REDIRECT_PATTERN, redirects_content, redirects_path)
        assert result == "https://api.example.com"

    def test_extracts_redirects_origin_strips_trailing_slash(self, tmp_path: Path) -> None:
        redirects_path = tmp_path / "_redirects"
        redirects_content = "/api/*  https://api.example.com//api/:splat  200"
        redirects_path.write_text(redirects_content, encoding="utf-8")

        result = cdo._match(cdo.REDIRECT_PATTERN, redirects_content, redirects_path)
        assert result == "https://api.example.com"

    def test_missing_marker_fails_with_readme_message(self, tmp_path: Path) -> None:
        readme_path = tmp_path / "README.md"
        readme_content = "No origin marker here"
        readme_path.write_text(readme_content, encoding="utf-8")

        with pytest.raises(SystemExit) as exc_info:
            cdo._match(cdo.README_ORIGIN_PATTERN, readme_content, readme_path)
        assert "Could not find deploy API origin marker in " in str(exc_info.value)
        assert "README.md" in str(exc_info.value)

    def test_missing_marker_fails_with_redirects_message(self, tmp_path: Path) -> None:
        redirects_path = tmp_path / "_redirects"
        redirects_content = "# No redirects here"
        redirects_path.write_text(redirects_content, encoding="utf-8")

        with pytest.raises(SystemExit) as exc_info:
            cdo._match(cdo.REDIRECT_PATTERN, redirects_content, redirects_path)
        assert "Could not find deploy API origin marker in " in str(exc_info.value)
        assert "_redirects" in str(exc_info.value)


class TestMain:
    """Tests for main() using a temporary repo layout."""

    def test_success_path_aligned_hosts(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        script_path = _write_repo_layout(tmp_path)
        monkeypatch.setattr(cdo, "__file__", str(script_path))

        assert cdo.main() == 0

        assert capsys.readouterr().out.strip() == "Deploy API origin aligned: api.example.com"

    def test_drift_failure_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        script_path = _write_repo_layout(
            tmp_path,
            readme_origin="https://api.example.com",
            redirect_origin="https://different-api.example.com",
        )
        monkeypatch.setattr(cdo, "__file__", str(script_path))

        with pytest.raises(SystemExit) as exc_info:
            cdo.main()

        error_msg = str(exc_info.value)
        assert "Deploy API origin drift:" in error_msg
        assert "README host 'api.example.com'" in error_msg
        assert "redirects host 'different-api.example.com'" in error_msg

    def test_missing_marker_failure_in_main(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        script_path = _write_repo_layout(tmp_path, readme_marker=False)
        monkeypatch.setattr(cdo, "__file__", str(script_path))

        with pytest.raises(SystemExit) as exc_info:
            cdo.main()

        error_msg = str(exc_info.value)
        assert "Could not find deploy API origin marker" in error_msg
        assert "README.md" in error_msg
