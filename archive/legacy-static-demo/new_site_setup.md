# How to Add a New Trip Site (Option A – Branch + Netlify Site)

## 1. Create a Branch

```bash
git checkout -b trip-<destination>-<year>


## 2. Generate the Trip

### 2.1  Edit `request.json`
1. Open `request.json` (root of the repo).  
2. Fill or update these keys:
   | Key | Example | Notes |
   |-----|---------|-------|
   | `trip_window.min_weeks` | `3` | Minimum trip length |
   | `trip_window.max_weeks` | `5` | Maximum trip length |
   | `trip_window.months`    | `["September", "October"]` | Allowed months |
   | `must_see`              | `["Plitvice", "Lauterbrunnen"]` | Always‑include list |
   | `nature_ratio`          | `0.7` | 0 = all culture, 1 = all nature |
   | `complexity_tolerance`  | `"medium"` | `"low"`, `"medium"`, or `"high"` |
   | `cost_sensitivity`      | `0.3` | 0 = ignore cost, 1 = shoestring |

3. **Save** the file.

### 2.2  (Optional) Update Segment Scores
* Open `data/segments_master.json`.  
* Add or adjust destinations.  Each entry looks like:

```jsonc
{
  "id": "plitvice",
  "name": "Plitvice Lakes NP",
  "segment_cost": 3,
  "natural": 5,
  "cultural": 1,
  "global_significance": 5,
  "experience_bundle": 2,
  "complexity": { "TL": 3, "NW": 2, "OS": 3, "AC": 1 },
  "cluster_id": "N1",
  "category": "unique_natural"
}

python scripts/validate_request.py        # schema check
python scripts/generate_itins.py          # writes itineraries_*.json
python scripts/build_html.py              # rewrites bundle/ HTML
git add request.json data/ bundle/
git commit -m "Generate itineraries for <trip>"
git push --set-upstream origin trip-<destination>-<year>

## 3. Add a Netlify Site
Log into Netlify.
Click Add new project → Import from Git.
Select this repo and set Branch to deploy to trip-<destination>-<year>.
After Netlify finishes, open Project configuration → Project details and copy the Project ID (Site ID).

##4. Add GitHub Secrets
In GitHub, go to Repo → Settings → Secrets and variables → Actions.
Click New repository secret twice:
Name	Value
NETLIFY_TOKEN_<TRIP>	(your existing personal access token)
NETLIFY_SITE_ID_<TRIP>	(the Site ID you just copied)
Use an uppercase identifier for <TRIP> (e.g., ITALY2026) so the secret names are unique.

## 5. Add a Branch‑Specific Workflow
Create .github/workflows/netlify-<trip>.yml:

name: Deploy <Trip>
on:
  push:
    branches: [trip-<destination>-<year>]
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Build HTML
        run: python scripts/build_html.py
      - name: Deploy to Netlify
        uses: nwtgck/actions-netlify@v2
        with:
          publish-dir: ./bundle
          production-deploy: true
          NETLIFY_AUTH_TOKEN: ${{ secrets.NETLIFY_TOKEN_<TRIP> }}
          NETLIFY_SITE_ID: ${{ secrets.NETLIFY_SITE_ID_<TRIP> }}

## 6. Verify
Push any change on the branch.
Check Actions tab for a green run.
Netlify will show a new deploy for the new site.
