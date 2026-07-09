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
    "RiffleFlyGuide/0.1 (https://github.com/torsten-mikkola/riffle-fly-guide)",
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


def fetch_usgs_values(site_ids: list[str]) -> dict[str, object]:
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
    values_by_site: dict[str, dict[str, str]] = {site_id: {} for site_id in site_ids}

    for series in data.get("value", {}).get("timeSeries", []):
        site_no = series.get("sourceInfo", {}).get("siteCode", [{}])[0].get("value")
        if site_no not in values_by_site:
            continue
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
            flow_cfs = round(float(latest))
            values_by_site[site_no]["flowCfs"] = flow_cfs
            values_by_site[site_no]["flow"] = f"{flow_cfs:,} cfs"
        elif code == "00065":
            gage_height_ft = float(latest)
            values_by_site[site_no]["gageHeightFt"] = round(gage_height_ft, 2)
            values_by_site[site_no]["gageHeight"] = f"{gage_height_ft:.2f} ft"
        elif code == "00010":
            fahrenheit = float(latest) * 9 / 5 + 32
            values_by_site[site_no]["waterTempF"] = round(fahrenheit, 1)
            values_by_site[site_no]["water"] = f"{fahrenheit:.0f}F"

    values: dict[str, object] = {}
    for site_id in site_ids:
        site_values = values_by_site.get(site_id, {})
        for key in ("flow", "flowCfs", "gageHeight", "gageHeightFt", "water", "waterTempF"):
            if key not in values and key in site_values:
                values[key] = site_values[key]
                if key in ("flow", "flowCfs") and "flowSourceSite" not in values:
                    values["flowSourceSite"] = site_id
                elif key in ("gageHeight", "gageHeightFt") and "gageHeightSourceSite" not in values:
                    values["gageHeightSourceSite"] = site_id
                elif key in ("water", "waterTempF") and "waterTempSourceSite" not in values:
                    values["waterTempSourceSite"] = site_id
    return values


def score_flow(flow_cfs: float | int | None, rules: dict) -> tuple[int, str, bool]:
    if flow_cfs is None:
        return 4, "flow gage is not yet mapped or did not return live CFS", False

    flow_rules = rules.get("flowCfs")
    if not flow_rules:
        return 12, "live USGS flow is available, but no reach-specific range is configured", False

    ideal_min = flow_rules["idealMin"]
    ideal_max = flow_rules["idealMax"]
    usable_min = flow_rules["usableMin"]
    usable_max = flow_rules["usableMax"]

    if ideal_min <= flow_cfs <= ideal_max:
        return 25, f"flow is in this reach's ideal range ({ideal_min:,}-{ideal_max:,} cfs)", False
    if usable_min <= flow_cfs < ideal_min:
        return 18, f"flow is usable but below the ideal range ({ideal_min:,}-{ideal_max:,} cfs)", False
    if ideal_max < flow_cfs <= usable_max:
        return 16, f"flow is usable but above the ideal range ({ideal_min:,}-{ideal_max:,} cfs)", False

    too_low = flow_cfs < usable_min
    extreme = flow_cfs < usable_min * 0.55 or flow_cfs > usable_max * 1.25
    if too_low:
        return 5, f"flow is below this reach's usable range ({usable_min:,}-{usable_max:,} cfs)", extreme
    return 3, f"flow is above this reach's usable range ({usable_min:,}-{usable_max:,} cfs)", extreme


def score_temperature(temp_f: float | int | None) -> tuple[int, str, bool]:
    if temp_f is None:
        return 8, "water temperature is missing, so temperature confidence is limited", False
    if 50 <= temp_f <= 60:
        return 22, "water temperature is in the prime trout feeding window", False
    if 45 <= temp_f < 50 or 60 < temp_f <= 64:
        return 18, "water temperature is productive for trout", False
    if 40 <= temp_f < 45:
        return 10, "water is cold; expect slower metabolism and deeper/subsurface feeding", False
    if temp_f >= 67.5:
        return 0, "water is too warm for an ethical trout recommendation", True
    if 64 < temp_f < 67.5:
        return 6, "water is warm; fish early and monitor stress", False
    return 3, "water is very cold; trout may feed selectively or briefly", False


def score_weather(forecast: list[dict[str, str]]) -> tuple[int, list[str]]:
    if not forecast:
        return 4, ["weather forecast is missing"]

    text = " ".join(
        f"{window.get('wind', '')} {window.get('note', '')}" for window in forecast
    ).lower()
    score = 13
    notes = ["forecast window is available"]

    if any(speed in text for speed in ["20 mph", "25 mph", "30 mph", "35 mph"]):
        score -= 10
        notes.append("wind could make presentation or boat control difficult")
    elif "mph" in text:
        score += 2
        notes.append("wind data is available")

    if any(word in text for word in ["thunder", "storm", "showers", "rain"]):
        score -= 5
        notes.append("storm or precipitation risk lowers confidence")

    return max(0, min(15, score)), notes


def score_reach(reach: dict, usgs: dict, forecast: list[dict[str, str]]) -> tuple[str, int, str]:
    score = 25
    why_parts = []
    hard_stop = False

    rules = reach.get("conditionRules", {})
    flow_score, flow_note, flow_extreme = score_flow(usgs.get("flowCfs"), rules)
    score += flow_score
    why_parts.append(flow_note)
    hard_stop = hard_stop or flow_extreme

    temp_score, temp_note, temp_stop = score_temperature(usgs.get("waterTempF"))
    score += temp_score
    why_parts.append(temp_note)
    hard_stop = hard_stop or temp_stop

    weather_score, weather_notes = score_weather(forecast)
    score += weather_score
    why_parts.extend(weather_notes)

    confidence = rules.get("confidence", "low" if not reach.get("primaryUsgsSite") else "medium")
    if confidence == "high":
        score += 5
        why_parts.append("gage confidence is high")
    elif confidence == "medium":
        score += 2
        why_parts.append("gage confidence is moderate")
    else:
        score -= 8
        why_parts.append("gage or flow-range confidence still needs local validation")

    if temp_stop:
        score = min(score, 49)
    elif flow_extreme:
        score = min(score, 58)

    if hard_stop and usgs.get("waterTempF", 0) >= 67.5:
        status = "skip"
    elif hard_stop and usgs.get("flowCfs") is not None:
        status = "skip" if score < 60 else "watch"
    elif score >= 82:
        status = "good"
    elif score >= 68:
        status = "watch"
    elif score >= 50:
        status = "limited"
    else:
        status = "skip"

    why = "Condition score uses reach-specific flow range, trout temperature, weather, and gage confidence; " + ", ".join(why_parts) + "."
    return status, max(0, min(100, score)), why


def build_conditions() -> dict:
    catalog = json.loads(REACHES_PATH.read_text(encoding="utf-8"))
    generated_at = datetime.now(timezone.utc).isoformat()
    successful_forecasts = 0
    successful_usgs = 0
    output = {
        "generatedAt": generated_at,
        "sourceStatus": {
            "usgs": "live where gage IDs are mapped",
            "nws": "live point/hourly forecasts",
            "reports": "manual placeholders",
        },
        "quality": {
            "successfulForecasts": 0,
            "successfulUsgs": 0,
            "totalReaches": len(catalog["reaches"]),
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
            if forecast:
                successful_forecasts += 1
        except (KeyError, urllib.error.URLError, TimeoutError, ValueError) as exc:
            forecast = []
            condition["sourceErrors"].append(f"NWS: {exc}")

        try:
            usgs = fetch_usgs_values(reach.get("usgsSites", []))
            condition.update(usgs)
            if usgs:
                successful_usgs += 1
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

    output["quality"]["successfulForecasts"] = successful_forecasts
    output["quality"]["successfulUsgs"] = successful_usgs
    return output


def main() -> int:
    conditions = build_conditions()
    if conditions["quality"]["successfulForecasts"] == 0:
        print("No live NWS forecasts were retrieved; leaving existing daily_conditions.json unchanged.")
        return 1
    OUTPUT_PATH.write_text(json.dumps(conditions, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
