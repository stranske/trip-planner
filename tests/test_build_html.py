import importlib
import scripts.build_html as build_html


def test_build_html_executes():
    """Ensure build_html.main() runs without raising exceptions."""
    build_html.main()
