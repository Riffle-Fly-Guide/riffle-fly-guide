#!/usr/bin/env python3
"""Find candidate USGS stream gages for each configured fishing reach.

The output is a review file, not an automatic catalog update. Gage assignment
needs human review because the nearest gage is often not the right gage for a
fishable reach, especially around forks, dams, reservoirs, and tributaries.
"""

from __future__ import annotations

import csv
import io
import json
import math
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REACHES_PATH = ROOT / "data" / "reaches.json"
OUTPUT_PATH = ROOT / "data" / "usgs_gage_candidates.json"


def haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    earth_radius_miles = 3958.8
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * earth_radius_miles * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def read_rdb(text: str) -> list[dict[str, str]]:
    lines = [line for line in text.splitlines() if line and not line.startswith("#")]
    if len(lines) < 3:
        return []
    header = lines[0].split("\t")
    data_lines = lines[2:]
    reader = csv.DictReader(io.StringIO("\n".join(data_lines)), fieldnames=header, delimiter="\t")
    return list(reader)


def fetch_candidates(lat: float, lon: float, half_degree: float = 0.6) -> list[dict[str, object]]:
    west = lon - half_degree
    east = lon + half_degree
    south = lat - half_degree
    north = lat + half_degree
    bbox = ",".join(f"{value:.6f}" for value in (west, south, east, north))
    params = urllib.parse.urlencode(
        {
            "format": "rdb",
            "bBox": bbox,
            "siteType": "ST",
            "parameterCd": "00060",
            "siteStatus": "active",
        },
        safe=",",
    )
    url = f"https://waterservices.usgs.gov/nwis/site/?{params}"
    with urllib.request.urlopen(url, timeout=30) as response:
        rows = read_rdb(response.read().decode("utf-8"))

    candidates = []
    for row in rows:
        try:
            site_lat = float(row["dec_lat_va"])
            site_lon = float(row["dec_long_va"])
        except (KeyError, TypeError, ValueError):
            continue
        candidates.append(
            {
                "siteNo": row.get("site_no", ""),
                "stationName": row.get("station_nm", ""),
                "siteType": row.get("site_tp_cd", ""),
                "lat": site_lat,
                "lon": site_lon,
                "distanceMiles": round(haversine_miles(lat, lon, site_lat, site_lon), 1),
                "usgsUrl": f"https://waterdata.usgs.gov/monitoring-location/{row.get('site_no', '')}/",
            }
        )
    return sorted(candidates, key=lambda item: item["distanceMiles"])[:12]


def main() -> int:
    catalog = json.loads(REACHES_PATH.read_text(encoding="utf-8"))
    output = {
        "generatedBy": "scripts/find_usgs_gage_candidates.py",
        "source": "USGS Site Service, active stream sites with streamflow parameter 00060",
        "reviewNotes": [
            "Nearest is not always correct.",
            "Prefer gages on the same fork/section and same side of major dams or tributaries.",
            "For tailwaters, below-dam release gages are often more useful than nearby reservoir or upstream gages.",
        ],
        "reaches": [],
    }

    for reach in catalog["reaches"]:
        try:
            candidates = fetch_candidates(reach["lat"], reach["lon"])
            error = None
        except urllib.error.HTTPError as exc:
            candidates = []
            error = f"USGS HTTP {exc.code}"
        except urllib.error.URLError as exc:
            candidates = []
            error = f"USGS URL error: {exc}"
        output["reaches"].append(
            {
                "id": reach["id"],
                "name": reach["name"],
                "lat": reach["lat"],
                "lon": reach["lon"],
                "currentUsgsSites": reach.get("usgsSites", []),
                "queryError": error,
                "candidates": candidates,
            }
        )

    OUTPUT_PATH.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
