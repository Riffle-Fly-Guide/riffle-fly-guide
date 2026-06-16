# USGS Gage Verification

## Goal

Assign each fishable reach one or more trustworthy USGS gages.

The nearest gage is not automatically correct. A gage should represent the water an angler is actually deciding to fish.

## Verification Rules

Use a gage when:

- It is on the same river/fork as the reach.
- It is on the same side of major dams, reservoirs, diversions, or tributary confluences.
- Its real-time streamflow parameter `00060` is active.
- Its position makes sense for the decision being made.
- It supports the type of question the app asks: wadeability, floatability, runoff, release changes, or water temperature.

Avoid a gage when:

- It is nearby but on a different fork.
- It is above a dam when the reach is below the dam.
- It is below a large tributary when the reach is above that tributary.
- It measures a different water body or reservoir condition.
- It lacks real-time streamflow.

## Workflow

1. Run:

   ```powershell
   python scripts/find_usgs_gage_candidates.py
   ```

2. Open:

   ```text
   data/usgs_gage_candidates.json
   ```

3. For each reach, inspect the candidate names and USGS links.

4. Pick:

   - `primaryUsgsSite`: best representative gage
   - `secondaryUsgsSites`: useful context gages
   - `gageNotes`: why the gage was chosen

5. Update `data/reaches.json`.

## Production Catalog Shape

```json
{
  "id": "boise-main-town",
  "usgsSites": ["13206000"],
  "primaryUsgsSite": "13206000",
  "gageNotes": "Boise River at Glenwood Bridge is representative of the in-town Boise reach."
}
```

## Important

USGS Water Services are useful for this MVP, but USGS says they will be decommissioned in early 2027. Keep the gage catalog separate from the API client so we can migrate the data-fetching layer later without redoing the verification work.
