import csv
import json
from pathlib import Path

import requests


MIN_LON = 120.461107
MIN_LAT = 24.005987
MAX_LON = 121.348150
MAX_LAT = 24.437670

API_URL = "https://gis.ardswc.gov.tw/api/ardswc/tiles/ortho/json"

OUT_DIR = Path("/data2/hgq/BuildingHeight_Dataset/data/raw/twn/moa_uav")
OUT_DIR.mkdir(parents=True, exist_ok=True)

OUT_CSV = OUT_DIR / "moa_uav_candidates_in_twn_bbox.csv"
OUT_GEOJSON = OUT_DIR / "moa_uav_candidates_in_twn_bbox.geojson"


def to_float(v):
    try:
        if v is None or v == "":
            return None
        return float(v)
    except Exception:
        return None


def intersects_bbox(west, south, east, north):
    return not (
        east < MIN_LON
        or west > MAX_LON
        or north < MIN_LAT
        or south > MAX_LAT
    )


def fetch_all_records():
    """
    Use the official ARDSWC UAV ortho API.
    Use limit/offset pagination to avoid oversized responses.
    """
    all_records = []
    limit = 1000
    offset = 0

    while True:
        params = {
            "limit": limit,
            "offset": offset,
        }

        print(f"[GET] offset={offset}, limit={limit}")
        r = requests.get(API_URL, params=params, timeout=120)
        r.raise_for_status()
        data = r.json()

        if not isinstance(data, list):
            raise RuntimeError(f"Unexpected response: {type(data)} {data}")

        if not data:
            break

        all_records.extend(data)
        print(f"[INFO] total loaded = {len(all_records)}")

        if len(data) < limit:
            break

        offset += limit

    return all_records


def maybe_parse_center_from_access_url(access_url):
    """
    Fallback:
    AccessURL folder names usually look like:
    20260127_120595580_023465264_16_000_RSImage_UAV_Ortho/
    where 120595580 -> 120.595580
         023465264 -> 23.465264
    """
    if not access_url:
        return None, None

    name = access_url.rstrip("/").split("/")[-1]
    parts = name.split("_")

    if len(parts) < 3:
        return None, None

    try:
        lon_raw = parts[1]
        lat_raw = parts[2]
        lon = float(lon_raw) / 1_000_000.0
        lat = float(lat_raw) / 1_000_000.0
        return lon, lat
    except Exception:
        return None, None


def main():
    records = fetch_all_records()
    print(f"[INFO] all records = {len(records)}")

    candidates = []

    for rec in records:
        west = to_float(rec.get("WestBoundLongitude"))
        east = to_float(rec.get("EastBoundLongitude"))
        south = to_float(rec.get("SouthBoundLatitude"))
        north = to_float(rec.get("NorthBoundLatitude"))

        center_lon = to_float(rec.get("CenterLongitude"))
        center_lat = to_float(rec.get("CenterLatitude"))

        if center_lon is None or center_lat is None:
            center_lon, center_lat = maybe_parse_center_from_access_url(
                rec.get("AccessURL")
            )


        has_bounds = None not in (west, east, south, north)

        if has_bounds:
            hit = intersects_bbox(west, south, east, north)
        else:

            hit = (
                center_lon is not None
                and center_lat is not None
                and MIN_LON <= center_lon <= MAX_LON
                and MIN_LAT <= center_lat <= MAX_LAT
            )

            west = east = center_lon
            south = north = center_lat

        if not hit:
            continue

        title = str(rec.get("Title", ""))
        project_name = str(rec.get("ProjectName", ""))

        is_taichung_keyword = any(
            k in (title + project_name)
            for k in ["\u53f0\u4e2d", "\u81fa\u4e2d", "Taichung"]
        )

        item = {
            "Id": rec.get("Id"),
            "Title": title,
            "ProjectNo": rec.get("ProjectNo"),
            "ProjectName": project_name,
            "Date": rec.get("Date"),
            "Class": rec.get("Class"),
            "AccessURL": rec.get("AccessURL"),
            "CenterLongitude": center_lon,
            "CenterLatitude": center_lat,
            "WestBoundLongitude": west,
            "EastBoundLongitude": east,
            "SouthBoundLatitude": south,
            "NorthBoundLatitude": north,
            "HasBounds": has_bounds,
            "TaichungKeyword": is_taichung_keyword,
        }

        candidates.append(item)


    candidates.sort(key=lambda x: str(x.get("Date") or ""), reverse=True)

    print("=" * 80)
    print(f"[RESULT] candidates intersecting your bbox = {len(candidates)}")
    print("=" * 80)

    for i, c in enumerate(candidates[:50], start=1):
        print(
            f"{i:03d} | {c['Date']} | {c['Title']} | "
            f"center=({c['CenterLongitude']}, {c['CenterLatitude']}) | "
            f"bounds=({c['WestBoundLongitude']}, {c['SouthBoundLatitude']}, "
            f"{c['EastBoundLongitude']}, {c['NorthBoundLatitude']}) | "
            f"taichung={c['TaichungKeyword']}"
        )
        print(f"      {c['AccessURL']}")

    if candidates:
        fieldnames = list(candidates[0].keys())
        with open(OUT_CSV, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(candidates)

        features = []
        for c in candidates:
            west = c["WestBoundLongitude"]
            east = c["EastBoundLongitude"]
            south = c["SouthBoundLatitude"]
            north = c["NorthBoundLatitude"]

            if None in (west, east, south, north):
                continue

            features.append(
                {
                    "type": "Feature",
                    "properties": c,
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [[
                            [west, south],
                            [east, south],
                            [east, north],
                            [west, north],
                            [west, south],
                        ]],
                    },
                }
            )

        geojson = {
            "type": "FeatureCollection",
            "features": features,
        }

        with open(OUT_GEOJSON, "w", encoding="utf-8") as f:
            json.dump(geojson, f, ensure_ascii=False, indent=2)

    print("=" * 80)
    print(f"[SAVED] {OUT_CSV}")
    print(f"[SAVED] {OUT_GEOJSON}")


if __name__ == "__main__":
    main()