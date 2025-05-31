# Trip Planner – Phase 2 Task List
_Last updated: 2025‑05‑31_

---

## Completed in Phase 2

### 1. Soft Cost Penalty
* **Formula**  
  `Penalty = 0.5 × (SegmentCost – 1) × CS × (1 – GS/5)`  
  *CostWeight = 0.5; GS ≥ 4 → Penalty = 0.*
* **Cost tiers**: 1 = Budget, 2 = Mid‑Range, 3 = Premium.
* Example table included in spec.

### 2. UI Controls
* **Toggle** “Consider cost?”  
* **Cost Sensitivity Slider** (0 = Splurge, 1 = Shoestring).  
* **Hide Cost in Output** checkbox.  
* **World‑Class Tooltip** for GS safeguard.
* **UI Profile** (per‑traveler feature flags) example:
  ```json
  {
    "show_cost_toggle": false,
    "show_sensitivity_slider": false,
    "show_hide_cost_checkbox": false,
    "show_opportunity_cost_matrix": true,
    "show_complexity_icons": true,
    "show_route_map": true,
    "show_signature_moments": true
  }
