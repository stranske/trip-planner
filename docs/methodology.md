# Trip Planner Methodology

## 1. Scoring Factors
- **Natural** (0‑5)
- **Cultural** (0‑5)
- **Global Significance (GS)** (0‑5)
- **Experience Bundle (EB)** (0‑5)

```
BaseScore = 0.35*Natural + 0.15*Cultural + 0.25*GS + 0.15*EB
```

## 2. Complexity Model (0‑20 → rescale 1‑5)
| TL | NW | OS | AC |
|----|----|----|----|
Transfers, traffic | Way‑finding | Queues | Lodging distance |

```
Complexity = TL + NW + OS + AC
```

## 3. Soft Cost Penalty (optional)
```
Penalty = 0.5 * (SegmentCost‑1) * CS * (1‑GS/5)
```
*GS ≥ 4 ⇒ Penalty = 0*

## 4. Route Segments
Treat iconic trains / drives as their own segments with **RouteScore** and Mode‑Affinity bonus.

## 5. Itinerary Generation Flow
1. Random weight seeds → Pareto (Score, Complexity, Nature:Cultural).
2. Tag quadrants (Nature‑heavy vs. Culture‑heavy, Low vs. High Complexity).
3. Pick 3‑4 representatives (two extremes, one balanced, one wildcard).
4. Create **Compact (21 d)** and **Extended (35 d)** versions.
5. Compute Opportunity‑Cost‑of‑Time matrix.

## 6. Presentation
- **Analytical** template: tables, scores, cost/complexity charts.
- **Experiential** template: narrative, hides numbers.
- Hide‑cost toggle removes all cost icons/text.

## 7. UI Controls
- Consider‑cost toggle
- Cost Sensitivity slider (0‑1)
- Hide‑cost checkbox
- UI Profile flags per traveler.

## 8. Data Files
- `data/segments_master.json`
- `data/itineraries_compact.json`
- `data/itineraries_extended.json`

## 9. Deployment
- Static HTML bundle → Netlify auto‑deploy from GitHub.
- PDFs generated from public URLs outside the VM.
