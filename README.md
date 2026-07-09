# Riffle: The Fly Guide

Riffle is an Idaho-first fly fishing conditions guide that helps anglers decide where to fish based on daily river and weather conditions.

## Link
[Riffle](https://riffle-fly-guide.github.io/riffle-fly-guide/)

## Current MVP

This first version is a static prototype deployed through GitHub Pages.

## Future Plan

- Use `data/reaches.json` as the reach catalog
- Use `scripts/update_conditions.py` to fetch USGS/NWS data
- Publish `data/daily_conditions.json` as the static data source for GitHub Pages
- Use GitHub Actions to update conditions daily
- Add local fly shop report attribution

## Data Refresh

The site is designed to work without a database. GitHub Actions runs the updater,
writes `data/daily_conditions.json`, and commits the result back to the repo.

Manual run:

```powershell
python scripts/update_conditions.py
```

On GitHub, use the **Update daily river conditions** workflow to run it manually,
or let the scheduled daily run update the site.

## Daily Automation Setup

The workflow file is:

```text
.github/workflows/update-conditions.yml
```

It runs every day at `12:15 UTC`, which is roughly `6:15 AM Mountain Daylight Time`.

To make the daily commit work on GitHub:

1. Go to the repo on GitHub.
2. Open **Settings > Actions > General**.
3. Under **Workflow permissions**, select **Read and write permissions**.
4. Save.
5. Open **Actions > Update daily river conditions**.
6. Run it manually once with **Run workflow**.

If the manual run succeeds, the schedule will keep updating `data/daily_conditions.json`.

## Notes

- NWS requires a unique `User-Agent`.
- USGS Water Services are useful for the MVP, but USGS says those endpoints will be decommissioned in early 2027.
- Reach gage IDs should be verified carefully before treating a score as production quality.
