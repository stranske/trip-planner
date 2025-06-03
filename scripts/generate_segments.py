#!/usr/bin/env python3
"""Generate additional destination segments with OpenAI and save to data/segments_generated.json."""
import os, json, re, sys
from pathlib import Path

try:
    import openai  # type: ignore
except ImportError:
    sys.exit("openai package not installed. Add 'openai' to requirements.txt or pip install openai in CI.")


PROMPT_TEMPLATE = """
You are a travel‑planning assistant. Suggest up to 20 additional European destinations
that match these criteria:

• Nature vs culture ratio: {nature_ratio:.0%} nature, {culture_ratio:.0%} culture
• Must‑see list (already included): {must_see}
• Trip window months: {months}
• Avoid duplicates of the must‑see list.

Return JSON in this schema:
[
  {{
    "id": "lake_bled",
    "name": "Lake Bled",
    "natural": 5,
    "cultural": 2,
    "global_significance": 3,
    "experience_bundle": 3,
    "segment_cost": 2
  }},
  ...
]
"""

def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")

def main() -> None:
    req_path = Path("request.json")
    if not req_path.exists():
        sys.exit("request.json not found; cannot generate segments.")

    req = json.loads(req_path.read_text())
    nature_ratio = float(req.get("nature_ratio", 0.5))
    culture_ratio = 1 - nature_ratio
    must_see = ", ".join(req.get("must_see", []))
    months = ", ".join(req["trip_window"].get("months", []))

    prompt = PROMPT_TEMPLATE.format(
        nature_ratio=nature_ratio,
        culture_ratio=culture_ratio,
        must_see=must_see or "(none)",
        months=months or "(any)"
    )

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        sys.exit("OPENAI_API_KEY environment variable not set.")
    openai.api_key = api_key

    response = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
    )

    content = response.choices[0].message.content
    start = content.find("[")
    end = content.rfind("]") + 1
    if start == -1 or end == -1:
        sys.exit("Could not find JSON array in model response.")

    try:
        segments = json.loads(content[start:end])
    except json.JSONDecodeError as e:
        sys.exit(f"Failed to parse JSON from model: {e}")

    # Ensure every segment has an id
    for seg in segments:
        seg.setdefault("id", slugify(seg.get("name", "")))

    out_path = Path("data/segments_generated.json")
    out_path.write_text(json.dumps({"segments": segments}, indent=2))
    print(f"Wrote {len(segments)} AI‑generated segments to {out_path}.")

def main(output_path: str = "data/segments_master.json"):
    # ... existing generation logic ...
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(segments_data, f, indent=2)

if __name__ == "__main__":
    main()
if __name__ == "__main__":
    main()
