"""Stub generator: reads request.json, scores segments, and writes
itineraries_compact.json and itineraries_extended.json.
Replace placeholder logic with full implementation later.
"""

import json

import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))
from scripts.calc_penalty import calcPenalty  # fixed import
COMPACT_DAYS  = 21
EXTENDED_DAYS = 35

def load_request(path="request.json"):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def load_segments(path="data/segments_master.json"):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)["segments"]

def score_segment(seg, CS):
    base = (
        0.35 * seg["natural"] +
        0.15 * seg["cultural"] +
        0.25 * seg["global_significance"] +
        0.15 * seg["experience_bundle"]
    )
    penalty = calcPenalty(seg["segment_cost"], seg["global_significance"], CS)
    return round(base - penalty, 2)

def main():
    req      = load_request()
    CS       = req.get("cost_sensitivity", 0)
    segments = load_segments()

    for seg in segments:
        seg["score"] = score_segment(seg, CS)

    segments_sorted = sorted(segments, key=lambda s: s["score"], reverse=True)
    compact  = {"days": COMPACT_DAYS,  "segments": segments_sorted[:10]}
    extended = {"days": EXTENDED_DAYS, "segments": segments_sorted[:16]}

    with open("data/itineraries_compact.json", "w", encoding="utf-8") as f:
        json.dump({"itineraries": [compact]}, f, indent=2)
    with open("data/itineraries_extended.json", "w", encoding="utf-8") as f:
        json.dump({"itineraries": [extended]}, f, indent=2)
if __name__ == "__main__":
    main()
