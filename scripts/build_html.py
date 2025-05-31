"""build_html.py – placeholder renderer.
Reads itineraries JSON and writes bundle/analytical/index.html
and bundle/experiential/index.html using Jinja2 templates.
"""

import json
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

TEMPLATE_DIR = Path("bundle")
OUT_ANALYTICAL = TEMPLATE_DIR / "analytical" / "index.html"
OUT_EXPERIENTIAL = TEMPLATE_DIR / "experiential" / "index.html"

def load_itins():
    with open("data/itineraries_compact.json", encoding="utf-8") as f:
        return json.load(f)["itineraries"]

def render(template_path: Path, context: dict, out_path: Path):
    env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))
    tmpl = env.get_template(str(template_path.relative_to(TEMPLATE_DIR)))
    html = tmpl.render(context)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    print(f"✓ Wrote {out_path}")

def main():
    itins = load_itins()
    ctx = {"itins": itins}
    render(Path("analytical/index.html"), ctx, OUT_ANALYTICAL)
    render(Path("experiential/index.html"), ctx, OUT_EXPERIENTIAL)

if __name__ == "__main__":
    main()
