import sys
from pathlib import Path

# Ensure project root is on the import path so we can import `scripts`.
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

import scripts.build_html as build_html


def test_build_html_executes():
    """Ensure build_html.main() runs without raising exceptions."""
    build_html.main()
