"""build_html.py – placeholder renderer.
Reads itineraries JSON and writes bundle/analytical/index.html
and bundle/experiential/index.html using Jinja2 templates.
"""

# scripts/build_html.py  (updated)

from jinja2 import Environment, FileSystemLoader
from pathlib import Path
import json

TEMPLATE_DIR = Path("bundle")
OUT_ANALYTICAL   = TEMPLATE_DIR / "analytical"   / "index.html"
OUT_EXPERIENTIAL = TEMPLATE_DIR / "experiential" / "index.html"

def load_itins():
    with open("data/itineraries_compact.json", encoding="utf-8") as f:
        return json.load(f)["itineraries"]

# --- NEW render function ---
def render(template_name: str, context: dict, out_path: Path):
    env  = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))
    tmpl = env.get_template(template_name)           # e.g. "analytical/index.html"
    html = tmpl.render(context)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    print(f"✓ Wrote {out_path}")

def main():
    itins = load_itins()
    ctx   = {"itins": itins}
    render("analytical/index.html",   ctx, OUT_ANALYTICAL)
    render("experiential/index.html", ctx, OUT_EXPERIENTIAL)

if __name__ == "__main__":
    main()
    
