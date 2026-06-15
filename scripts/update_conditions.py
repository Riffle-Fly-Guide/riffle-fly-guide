#!/usr/bin/env python3
"""Generate static daily river condition data for GitHub Pages.

This script is intentionally dependency-free so it can run in GitHub Actions
without installing packages. It reads data/reaches.json and writes
data/daily_conditions.json.

USGS note: this uses the current Water Services instantaneous-values endpoint
for MVP purposes. USGS says Water Services will be decommissioned in early 2027,
so the long-term version should migrate to api.waterdata.usgs.gov.
"""

from __future__ import annotations

import json
import os
import statistics
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REACHES_PATH = ROOT / "data" / "reaches.json"
OUTPUT_PATH = ROOT / "data" / "daily_conditions.json"

NWS_USER_AGENT = os.environ.get(
    "NWS_USER_AGENT",
    "FishableToday/0.1 (https://github.com/your-account/fishable-today)",
)


def fetch_json(url: str, headers: dict[str, str] | None = None) -> dict:
    request = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(request, timeout=25) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_nws_forecast(lat: float, lon: float) -> list[dict[str, str]]:
    headers = {
        "User-Agent": NWS_USER_AGENT,
        "Accept": "application/geo+json",
    }
    point = fetch_json(f"https://api.weather.gov/points/{lat},{lon}", headers)
    hourly_url = point["properties"]["forecastHourly"]
    hourly = fetch_json(hourly_url, headers)
    periods = hourly.get("properties", {}).get("periods", [])[:16]

    windows = [
        ("Morning", range(5, 11)),
        ("Midday", range(11, 15)),
        ("Afternoon", range(15, 19)),
        ("Evening", range(19, 23)),
    ]
    result = []
    for label, hours in windows:
        matching = []
        for period in periods:
          start = datetime.fromisoformat(period["startTime"].replace("Z", "+00:00"))
          if start.hour in hours:
              matching.append(period)
        bucket = matching or periods[:1]
        temps = [p.get("temperature") for p in bucket if isinstance(p.get("temperature"), (int, float))]
        winds = [p.get("windSpeed", "") for p in bucket if p.get("windSpeed")]
        short = bucket[0].get("shortForecast", "forecast pending") if bucket else "forecast pending"
        temp_label = f"{round(statistics.mean(temps))}F" if temps else "pending"
        wind_label = winds[0] if winds else "pending"
        result.append({"label": label, "temp": temp_label, "wind": wind_label, "note": short.lower()})
    return result


def fetch_usgs_values(site_ids: list[str]) -> dict[str, str]:
    if not site_ids:
        return {}

    params = urllib.parse.urlencode(
        {
            "format": "json",
            "sites": ",".join(site_ids),
            "parameterCd": "00060,00065,00010",
            "period": "P2D",
            "siteStatus": "all",
        }
    )
    data = fetch_json(f"https://waterservices.usgs.gov/nwis/iv/?{params}")
    values: dict[str, str] = {}

    for series in data.get("value", {}).get("timeSeries", []):
        variable = series.get("variable", {})
        code = variable.get("variableCode", [{}])[0].get("value")
        latest = None
        for block in series.get("values", []):
            for item in block.get("value", []):
                if item.get("value") not in (None, ""):
                    latest = item.get("value")
        if latest is None:
            continue
        if code == "00060":
            values["flow"] = f"{round(float(latest)):,} cfs"
        elif code == "00065":
            values["gageHeight"] = f"{float(latest):.2f} ft"
        elif code == "00010":
            values["water"] = f"{float(latest):.0f}F"
    return values


def score_reach(reach: dict, usgs: dict, forecast: list[dict[str, str]]) -> tuple[str, int, str]:
    score = 65
    why_parts = []

    if usgs.get("flow"):
        score += 8
        why_parts.append("live USGS flow is available")
    else:
        score -= 6
        why_parts.append("flow gage is not yet mapped")

    if usgs.get("water"):
        score += 8
        why_parts.append("water temperature is available")

    wind_text = " ".join(window.get("wind", "") for window in forecast).lower()
    if "mph" in wind_text:
        score += 6
    if any(word in wind_text for word in ["20", "25", "30"]):
        score -= 15
        why_parts.append("wind could affect the fishing window")

    if score >= 82:
        status = "good"
    elif score >= 65:
        status = "watch"
    elif score >= 50:
        status = "limited"
    else:
        status = "skip"

    why = "Condition score generated from mapped USGS/NWS sources; " + ", ".join(why_parts) + "."
    return status, max(0, min(100, score)), why


def build_conditions() -> dict:
    catalog = json.loads(REACHES_PATH.read_text(encoding="utf-8"))
    generated_at = datetime.now(timezone.utc).isoformat()
    output = {
        "generatedAt": generated_at,
        "sourceStatus": {
            "usgs": "live where gage IDs are mapped",
            "nws": "live point/hourly forecasts",
            "reports": "manual placeholders",
        },
        "reaches": [],
    }

    for reach in catalog["reaches"]:
        condition = {
            "id": reach["id"],
            "forecast": [],
            "sourceErrors": [],
        }
        try:
            forecast = fetch_nws_forecast(reach["lat"], reach["lon"])
            condition["forecast"] = forecast
        except (KeyError, urllib.error.URLError, TimeoutError, ValueError) as exc:
            forecast = []
            condition["sourceErrors"].append(f"NWS: {exc}")

        try:
            usgs = fetch_usgs_values(reach.get("usgsSites", []))
            condition.update(usgs)
        except (KeyError, urllib.error.URLError, TimeoutError, ValueError) as exc:
            usgs = {}
            condition["sourceErrors"].append(f"USGS: {exc}")

        status, score, why = score_reach(reach, usgs, forecast)
        condition.update(
            {
                "status": status,
                "score": score,
                "pressure": "forecast-driven",
                "weather": forecast[0]["note"] if forecast else "forecast pending",
                "why": why,
            }
        )
        output["reaches"].append(condition)

    return output


def main() -> int:
    conditions = build_conditions()
    OUTPUT_PATH.write_text(json.dumps(conditions, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
