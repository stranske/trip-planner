# trip-planner
<br>markdown<br>## Static HTML Bundle<br>The self‑contained demo bundle lives in `/bundle/`.<br><br>**Local test:**<br><br>file:///home/oai/share/bundle/index.html<br><br><br>**Deploy:** 

## Quick Start

1. **Install deps**

```bash
pip install -r requirements.txt

python scripts/validate_request.py   # schema check
python scripts/generate_itins.py     # writes data/itineraries_*.json
python scripts/build_html.py         # renders bundle/ HTML


