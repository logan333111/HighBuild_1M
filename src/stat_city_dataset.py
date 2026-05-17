#!/usr/bin/env python3

"""Count per-city processed dataset statistics.

The script scans:
  data/processed/images/<city_dir>/*.jpg
  data/processed/masks/<city_dir>/masks/*.tif[f]
  data/processed/coco_json/<city_dir>/*.json

Building counts and ratios are computed from processed COCO annotations by
default. Optional source GeoJSON diagnostics can be enabled when raw coverage
needs to be checked. Height is read from annotation["attributes"]["height"]
first, then annotation["height"] as a fallback.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable


DEFAULT_BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_PROJ_DIR = Path(sys.prefix) / "share" / "proj"
DEFAULT_GDAL_DIR = Path(sys.prefix) / "share" / "gdal"

if "PROJ_LIB" not in os.environ and DEFAULT_PROJ_DIR.exists():
    os.environ["PROJ_LIB"] = str(DEFAULT_PROJ_DIR)
if "GDAL_DATA" not in os.environ and DEFAULT_GDAL_DIR.exists():
    os.environ["GDAL_DATA"] = str(DEFAULT_GDAL_DIR)

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}
MASK_EXTS = {".tif", ".tiff"}
TARGET_METERS = 256
FEATURE_TYPE_RE = re.compile(rb'"type"\s*:\s*"Feature"')
GRID_IMAGE_RE = re.compile(r"^grid_(\d+)_z(\d+)\.")
SOURCE_FEATURE_COUNT_CACHE: dict[Path, int] = {}


CITY_METADATA = {
    "Africa_SouthAfrica_CapeTown": {
        "region": "Africa",
        "country": "SouthAfrica",
        "city": "CapeTown",
        "city_group": "SouthAfrica_CapeTown",
    },
    "Asia_HongKong_HongKong": {
        "region": "Asia",
        "country": "HongKong",
        "city": "HongKong",
        "city_group": "HongKong_HongKong",
    },
    "Asia_Japan_Osaka": {
        "region": "Asia",
        "country": "Japan",
        "city": "Osaka",
        "city_group": "Japan_Osaka",
    },
    "Europe_Austria_Vienna": {
        "region": "Europe",
        "country": "Austria",
        "city": "Vienna",
        "city_group": "Austria_Vienna",
    },
    "Europe_Denmark_Aarhus": {
        "region": "Europe",
        "country": "Denmark",
        "city": "Aarhus",
        "city_group": "Denmark_Aarhus",
    },
    "Europe_Denmark_Copenhagen": {
        "region": "Europe",
        "country": "Denmark",
        "city": "Copenhagen",
        "city_group": "Denmark_Copenhagen",
    },
    "Europe_Denmark_Odense": {
        "region": "Europe",
        "country": "Denmark",
        "city": "Odense",
        "city_group": "Denmark_Odense",
    },
    "Europe_France_Lyon": {
        "region": "Europe",
        "country": "France",
        "city": "Lyon",
        "city_group": "France_Lyon",
    },
    "Europe_France_Marseille": {
        "region": "Europe",
        "country": "France",
        "city": "Marseille",
        "city_group": "France_Marseille",
    },
    "Europe_France_Paris": {
        "region": "Europe",
        "country": "France",
        "city": "Paris",
        "city_group": "France_Paris",
    },
    "Europe_France_Strasbourg": {
        "region": "Europe",
        "country": "France",
        "city": "Strasbourg",
        "city_group": "France_Strasbourg",
    },
    "Europe_France_Toulouse": {
        "region": "Europe",
        "country": "France",
        "city": "Toulouse",
        "city_group": "France_Toulouse",
    },
    "Europe_Germany_Berlin": {
        "region": "Europe",
        "country": "Germany",
        "city": "Berlin",
        "city_group": "Germany_Berlin",
    },
    "Europe_Germany_Frankfurt": {
        "region": "Europe",
        "country": "Germany",
        "city": "Frankfurt",
        "city_group": "Germany_Frankfurt",
    },
    "Europe_Germany_Munich": {
        "region": "Europe",
        "country": "Germany",
        "city": "Munich",
        "city_group": "Germany_Munich",
    },
    "Europe_Netherlands_Amsterdam": {
        "region": "Europe",
        "country": "Netherlands",
        "city": "Amsterdam",
        "city_group": "Netherlands_Amsterdam",
    },
    "NorthAmerica_Canada_Toronto": {
        "region": "NorthAmerica",
        "country": "Canada",
        "city": "Toronto",
        "city_group": "Canada_Toronto",
    },
    "NorthAmerica_Canada_Vancouver": {
        "region": "NorthAmerica",
        "country": "Canada",
        "city": "Vancouver",
        "city_group": "Canada_Vancouver",
    },
    "NorthAmerica_USA_Chicago": {
        "region": "NorthAmerica",
        "country": "USA",
        "city": "Chicago",
        "city_group": "USA_Chicago",
    },
    "NorthAmerica_USA_LosAngeles": {
        "region": "NorthAmerica",
        "country": "USA",
        "city": "LosAngeles",
        "city_group": "USA_LosAngeles",
    },
    "NorthAmerica_USA_NewYork": {
        "region": "NorthAmerica",
        "country": "USA",
        "city": "NewYork",
        "city_group": "USA_NewYork",
    },
    "NorthAmerica_USA_SanFrancisco": {
        "region": "NorthAmerica",
        "country": "USA",
        "city": "SanFrancisco",
        "city_group": "USA_SanFrancisco",
    },
    "NorthAmerica_USA_Seattle": {
        "region": "NorthAmerica",
        "country": "USA",
        "city": "Seattle",
        "city_group": "USA_Seattle",
    },
    "Oceania_Australia_Melbourne": {
        "region": "Oceania",
        "country": "Australia",
        "city": "Melbourne",
        "city_group": "Australia_Melbourne",
    },
    "Oceania_Australia_Sydney": {
        "region": "Oceania",
        "country": "Australia",
        "city": "Sydney",
        "city_group": "Australia_Sydney",
    },
    "SouthAmerica_Brazil_SaoPaulo": {
        "region": "SouthAmerica",
        "country": "Brazil",
        "city": "SaoPaulo",
        "city_group": "Brazil_SaoPaulo",
    },
}

@dataclass
class CityStats:
    region: str
    country: str
    city: str
    city_group: str
    city_dirs: set[str] = field(default_factory=set)
    image_count: int = 0
    height_mask_count: int = 0
    coco_json_count: int = 0
    paired_sample_count: int = 0
    source_geojson_counts: dict[str, int] = field(default_factory=dict)
    source_geojson_error_count: int = 0
    source_covered_buildings: int | None = None
    source_coverage_error_count: int = 0
    building_instances: int = 0
    valid_height_buildings: int = 0
    true_height_buildings: int = 0
    estimated_height_buildings: int = 0
    unknown_height_buildings: int = 0
    json_error_count: int = 0

    @property
    def valid_height_ratio(self) -> float | None:
        if self.building_instances == 0:
            return None
        return self.valid_height_buildings / self.building_instances

    @property
    def true_height_ratio(self) -> float | None:
        if self.building_instances == 0:
            return None
        return self.true_height_buildings / self.building_instances

    @property
    def estimated_height_ratio(self) -> float | None:
        if self.building_instances == 0:
            return None
        return self.estimated_height_buildings / self.building_instances

    @property
    def unknown_height_ratio(self) -> float | None:
        if self.building_instances == 0:
            return None
        return self.unknown_height_buildings / self.building_instances

    @property
    def source_geojson_buildings(self) -> int:
        return sum(self.source_geojson_counts.values())

    @property
    def source_geojson_paths(self) -> str:
        if not self.source_geojson_counts:
            return "n/a"
        return ";".join(sorted(self.source_geojson_counts))

    @property
    def coco_vs_source_delta(self) -> int | None:
        source_count = self.source_geojson_buildings
        if source_count == 0:
            return None
        return self.building_instances - source_count

    @property
    def coco_vs_source_ratio(self) -> float | None:
        source_count = self.source_geojson_buildings
        if source_count == 0:
            return None
        return self.building_instances / source_count

    @property
    def source_coverage_ratio(self) -> float | None:
        source_count = self.source_geojson_buildings
        if source_count == 0 or self.source_covered_buildings is None:
            return None
        return self.source_covered_buildings / source_count

    @property
    def coco_vs_covered_delta(self) -> int | None:
        if self.source_covered_buildings is None:
            return None
        return self.building_instances - self.source_covered_buildings

    @property
    def coco_vs_covered_ratio(self) -> float | None:
        if not self.source_covered_buildings:
            return None
        return self.building_instances / self.source_covered_buildings

    def add(self, other: "CityStats") -> None:
        self.city_dirs.update(other.city_dirs)
        self.image_count += other.image_count
        self.height_mask_count += other.height_mask_count
        self.coco_json_count += other.coco_json_count
        self.paired_sample_count += other.paired_sample_count
        self.source_geojson_counts.update(other.source_geojson_counts)
        self.source_geojson_error_count += other.source_geojson_error_count
        if other.source_covered_buildings is not None:
            if self.source_covered_buildings is None:
                self.source_covered_buildings = 0
            self.source_covered_buildings += other.source_covered_buildings
        self.source_coverage_error_count += other.source_coverage_error_count
        self.building_instances += other.building_instances
        self.valid_height_buildings += other.valid_height_buildings
        self.true_height_buildings += other.true_height_buildings
        self.estimated_height_buildings += other.estimated_height_buildings
        self.unknown_height_buildings += other.unknown_height_buildings
        self.json_error_count += other.json_error_count


def iter_files(path: Path, exts: set[str]) -> Iterable[Path]:
    if not path.exists():
        return []
    return sorted(p for p in path.iterdir() if p.is_file() and p.suffix.lower() in exts)


def file_stems(paths: Iterable[Path]) -> set[str]:
    return {p.stem for p in paths}


def normalize_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def source_base_key(value: str) -> str:
    normalized = normalize_name(value)
    for token in ("filtered", "buildingsfull", "full", "ready", "exact"):
        normalized = normalized.replace(token, "")
    return normalized


def list_source_geojsons(base_dir: Path) -> list[Path]:
    raw_root = base_dir / "data" / "raw"
    if not raw_root.exists():
        return []
    return sorted(path for path in raw_root.rglob("*.geojson") if path.is_file())


def select_source_geojson(
    base_dir: Path,
    city_dir: str,
    meta: dict[str, str],
    raw_geojsons: list[Path],
) -> Path | None:
    city_norm = normalize_name(city_dir)
    city_base = source_base_key(city_dir)
    group_norm = normalize_name(meta["city_group"])
    group_base = source_base_key(meta["city_group"])
    city_name_norm = normalize_name(meta["city"])
    country_norm = normalize_name(meta["country"])

    scored: list[tuple[int, int, int, str, Path]] = []
    for path in raw_geojsons:
        stem = path.stem
        stem_norm = normalize_name(stem)
        stem_base = source_base_key(stem)

        match_score = 0
        if stem_norm == city_norm:
            match_score += 100
        if stem_base and stem_base == city_base:
            match_score += 90
        if city_base and (city_base in stem_base or stem_base in city_base):
            match_score += 70
        if group_norm and group_norm in stem_norm:
            match_score += 60
        if group_base and group_base in stem_base:
            match_score += 50
        if city_name_norm and city_name_norm in stem_norm:
            match_score += 30
        if country_norm and country_norm in stem_norm:
            match_score += 10

        if match_score == 0:
            continue

        filtered_score = 1 if "filtered" in stem.lower() else 0

        scored.append((filtered_score, match_score, -len(path.parts), str(path), path))

    if not scored:
        return None

    scored.sort(reverse=True)
    return scored[0][-1]


def relative_path_text(base_dir: Path, path: Path) -> str:
    try:
        return str(path.relative_to(base_dir))
    except ValueError:
        return str(path)


def count_source_geojson_features(path: Path) -> int:
    cached = SOURCE_FEATURE_COUNT_CACHE.get(path)
    if cached is not None:
        return cached

    count = 0
    tail = b""
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(8 * 1024 * 1024)
            if not chunk:
                break
            data = tail + chunk
            tail_len = len(tail)
            count += sum(1 for match in FEATURE_TYPE_RE.finditer(data) if match.end() > tail_len)
            tail = data[-64:]

    SOURCE_FEATURE_COUNT_CACHE[path] = count
    return count


def get_meters_per_pixel(zoom: int, latitude: float) -> float:
    return (156543.03392 * math.cos(math.radians(latitude))) / (2**zoom)


def lnglat_to_global_pixel(lng: float, lat: float, zoom: int) -> tuple[float, float]:
    n = 2.0**zoom
    pixel_x = ((lng + 180.0) / 360.0) * n * 256.0
    lat_rad = math.radians(lat)
    pixel_y = (1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n * 256.0
    return pixel_x, pixel_y


def pixel_x_to_lon(global_x: float, zoom: int) -> float:
    world_size = 256 * (2**zoom)
    return (global_x / world_size) * 360.0 - 180.0


def pixel_y_to_lat(global_y: float, zoom: int) -> float:
    world_size = 256 * (2**zoom)
    n = math.pi - (2.0 * math.pi * global_y) / world_size
    return math.degrees(math.atan(math.sinh(n)))


def generate_city_grids(
    total_bounds: tuple[float, float, float, float],
    target_meters: int,
    zoom: int,
    latitude: float,
) -> list[dict[str, int]]:
    min_lng, min_lat, max_lng, max_lat = total_bounds
    step_pixels = int(target_meters / get_meters_per_pixel(zoom, latitude))
    x_start, y_start = lnglat_to_global_pixel(min_lng, max_lat, zoom)
    x_end, y_end = lnglat_to_global_pixel(max_lng, min_lat, zoom)

    grids = []
    grid_id = 0
    y = int(y_start)
    while y < int(y_end):
        x = int(x_start)
        while x < int(x_end):
            grids.append(
                {
                    "grid_id": grid_id,
                    "global_x_start": x,
                    "global_y_start": y,
                    "global_x_end": x + step_pixels,
                    "global_y_end": y + step_pixels,
                    "pixel_size": step_pixels,
                }
            )
            grid_id += 1
            x += step_pixels
        y += step_pixels
    return grids


def grid_to_lonlat_bbox(grid: dict[str, int], zoom: int) -> tuple[float, float, float, float]:
    west = pixel_x_to_lon(grid["global_x_start"], zoom)
    east = pixel_x_to_lon(grid["global_x_end"], zoom)
    north = pixel_y_to_lat(grid["global_y_start"], zoom)
    south = pixel_y_to_lat(grid["global_y_end"], zoom)
    return min(west, east), min(south, north), max(west, east), max(south, north)


def saved_grid_ids_and_zoom(image_files: list[Path]) -> tuple[set[int], int | None]:
    grid_ids = set()
    zooms = set()
    for path in image_files:
        match = GRID_IMAGE_RE.match(path.name)
        if not match:
            continue
        grid_ids.add(int(match.group(1)))
        zooms.add(int(match.group(2)))
    if not zooms:
        return grid_ids, None
    if len(zooms) > 1:
        raise ValueError(f"Multiple zoom levels found in one city directory: {sorted(zooms)}")
    return grid_ids, next(iter(zooms))


def count_source_buildings_covered_by_saved_grids(
    source_geojson: Path,
    image_files: list[Path],
) -> int:
    import geopandas as gpd
    from shapely.geometry import box

    saved_grid_ids, zoom = saved_grid_ids_and_zoom(image_files)
    if zoom is None or not saved_grid_ids:
        return 0

    gdf = gpd.read_file(source_geojson)
    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")
    elif str(gdf.crs) != "EPSG:4326":
        gdf = gdf.to_crs("EPSG:4326")

    minx, miny, maxx, maxy = gdf.total_bounds
    center_lat = (miny + maxy) / 2.0
    grids = generate_city_grids((minx, miny, maxx, maxy), TARGET_METERS, zoom, center_lat)
    sindex = gdf.sindex
    covered = set()

    for grid in grids:
        if grid["grid_id"] not in saved_grid_ids:
            continue
        grid_box = box(*grid_to_lonlat_bbox(grid, zoom))
        candidate_idx = list(sindex.intersection(grid_box.bounds))
        for idx in candidate_idx:
            if gdf.geometry.iloc[idx].intersects(grid_box):
                covered.add(idx)

    return len(covered)


def parse_height(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return bool(value)


def annotation_height(annotation: dict[str, Any]) -> float | None:
    attrs = annotation.get("attributes")
    if isinstance(attrs, dict) and "height" in attrs:
        return parse_height(attrs.get("height"))
    return parse_height(annotation.get("height"))


def annotation_is_estimated(annotation: dict[str, Any]) -> bool:
    attrs = annotation.get("attributes")
    if isinstance(attrs, dict) and "is_estimated_height" in attrs:
        return parse_bool(attrs.get("is_estimated_height"))
    return parse_bool(annotation.get("is_estimated_height", False))


def count_json_annotations(json_path: Path) -> tuple[int, int, int, int, int]:
    with json_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    annotations = payload.get("annotations", [])
    if not isinstance(annotations, list):
        return 0, 0, 0, 0, 0

    total = len(annotations)
    valid = 0
    true_height = 0
    estimated = 0
    unknown = 0

    for annotation in annotations:
        if not isinstance(annotation, dict):
            unknown += 1
            continue

        height = annotation_height(annotation)
        if height is None or height < 0:
            unknown += 1
            continue

        valid += 1
        if annotation_is_estimated(annotation):
            estimated += 1
        else:
            true_height += 1

    return total, valid, true_height, estimated, unknown


def metadata_for_city_dir(city_dir: str) -> dict[str, str]:
    meta = CITY_METADATA.get(city_dir)
    if meta:
        return meta
    return {
        "region": "Unknown",
        "country": "Unknown",
        "city": city_dir,
        "city_group": city_dir,
    }


def collect_city_dir_stats(
    base_dir: Path,
    city_dir: str,
    raw_geojsons: list[Path],
    with_source_geojson: bool,
    with_source_coverage: bool,
) -> CityStats:
    meta = metadata_for_city_dir(city_dir)
    image_dir = base_dir / "data" / "processed" / "images" / city_dir
    mask_dir = base_dir / "data" / "processed" / "masks" / city_dir / "masks"
    json_dir = base_dir / "data" / "processed" / "coco_json" / city_dir

    image_files = list(iter_files(image_dir, IMAGE_EXTS))
    mask_files = list(iter_files(mask_dir, MASK_EXTS))
    json_files = list(iter_files(json_dir, {".json"}))

    stats = CityStats(
        region=meta["region"],
        country=meta["country"],
        city=meta["city"],
        city_group=meta["city_group"],
        city_dirs={city_dir},
        image_count=len(image_files),
        height_mask_count=len(mask_files),
        coco_json_count=len(json_files),
        paired_sample_count=len(file_stems(image_files) & file_stems(mask_files) & file_stems(json_files)),
    )

    source_geojson = None
    if with_source_geojson or with_source_coverage:
        source_geojson = select_source_geojson(base_dir, city_dir, meta, raw_geojsons)

    if source_geojson is not None:
        try:
            stats.source_geojson_counts[relative_path_text(base_dir, source_geojson)] = (
                count_source_geojson_features(source_geojson)
            )
        except OSError:
            stats.source_geojson_error_count += 1
        if with_source_coverage:
            try:
                stats.source_covered_buildings = count_source_buildings_covered_by_saved_grids(
                    source_geojson,
                    image_files,
                )
            except Exception:
                stats.source_coverage_error_count += 1

    for json_path in json_files:
        try:
            total, valid, true_height, estimated, unknown = count_json_annotations(json_path)
        except (OSError, json.JSONDecodeError):
            stats.json_error_count += 1
            continue

        stats.building_instances += total
        stats.valid_height_buildings += valid
        stats.true_height_buildings += true_height
        stats.estimated_height_buildings += estimated
        stats.unknown_height_buildings += unknown

    return stats


def discover_city_dirs(base_dir: Path) -> list[str]:
    roots = [
        base_dir / "data" / "processed" / "images",
        base_dir / "data" / "processed" / "masks",
        base_dir / "data" / "processed" / "coco_json",
    ]
    city_dirs: set[str] = set()
    for root in roots:
        if root.exists():
            city_dirs.update(p.name for p in root.iterdir() if p.is_dir())
    return sorted(city_dirs)


def group_stats(stats_by_dir: list[CityStats], group_by: str) -> list[CityStats]:
    if group_by == "city_dir":
        return stats_by_dir

    grouped: dict[str, CityStats] = {}
    for stats in stats_by_dir:
        key = stats.city_group if group_by == "city_group" else f"{stats.region}/{stats.country}/{stats.city}"
        if key not in grouped:
            grouped[key] = CityStats(
                region=stats.region,
                country=stats.country,
                city=stats.city,
                city_group=stats.city_group,
            )
        grouped[key].add(stats)
    return sorted(grouped.values(), key=lambda s: (s.region, s.country, s.city, s.city_group))


def ratio_text(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value * 100:.2f}%"


def multiplier_text(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.4f}x"


def optional_int_text(value: int | None) -> str | int:
    if value is None:
        return "n/a"
    return value


def rows_from_stats(
    stats_list: list[CityStats],
    include_source_geojson: bool,
    include_source_coverage: bool,
) -> list[dict[str, str | int]]:
    rows = []
    for stats in stats_list:
        row: dict[str, str | int] = {
            "region": stats.region,
            "country": stats.country,
            "city": stats.city,
            "city_group": stats.city_group,
            "city_dirs": ";".join(sorted(stats.city_dirs)),
            "image_count": stats.image_count,
            "height_mask_count": stats.height_mask_count,
            "coco_json_count": stats.coco_json_count,
            "paired_sample_count": stats.paired_sample_count,
            "building_instances": stats.building_instances,
            "valid_height_buildings": stats.valid_height_buildings,
            "valid_height_ratio": ratio_text(stats.valid_height_ratio),
            "true_height_buildings": stats.true_height_buildings,
            "true_height_ratio": ratio_text(stats.true_height_ratio),
            "estimated_height_buildings": stats.estimated_height_buildings,
            "estimated_height_ratio": ratio_text(stats.estimated_height_ratio),
            "unknown_height_buildings": stats.unknown_height_buildings,
            "unknown_height_ratio": ratio_text(stats.unknown_height_ratio),
            "json_error_count": stats.json_error_count,
        }
        if include_source_geojson:
            row.update(
                {
                    "source_geojson_path": stats.source_geojson_paths,
                    "source_geojson_buildings": stats.source_geojson_buildings,
                    "source_geojson_error_count": stats.source_geojson_error_count,
                    "coco_vs_source_delta": optional_int_text(stats.coco_vs_source_delta),
                    "coco_vs_source_ratio": multiplier_text(stats.coco_vs_source_ratio),
                }
            )
        if include_source_coverage:
            row.update(
                {
                    "source_covered_buildings": optional_int_text(stats.source_covered_buildings),
                    "source_coverage_ratio": ratio_text(stats.source_coverage_ratio),
                    "source_coverage_error_count": stats.source_coverage_error_count,
                    "coco_vs_covered_delta": optional_int_text(stats.coco_vs_covered_delta),
                    "coco_vs_covered_ratio": multiplier_text(stats.coco_vs_covered_ratio),
                }
            )
        rows.append(row)
    return rows


def write_csv(rows: list[dict[str, str | int]], output: Path | None) -> None:
    if not rows:
        return
    fieldnames = list(rows[0].keys())
    if output:
        handle = output.open("w", encoding="utf-8", newline="")
        close = True
    else:
        import sys

        handle = sys.stdout
        close = False
    try:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    finally:
        if close:
            handle.close()


def escape_md(value: object) -> str:
    return str(value).replace("|", "\\|")


def labels_for_rows(rows: list[dict[str, str | int]]) -> list[tuple[str, str]]:
    headers = [
        ("region", "Region"),
        ("country", "Country/Region"),
        ("city", "City"),
        ("city_group", "City group"),
        ("city_dirs", "Data directories"),
        ("image_count", "Image count"),
        ("height_mask_count", "Height mask count"),
        ("coco_json_count", "COCO JSON count"),
        ("paired_sample_count", "Pairable sample count"),
        ("source_geojson_path", "Source GeoJSON file"),
        ("source_geojson_buildings", "Unique source GeoJSON buildings"),
        ("source_geojson_error_count", "Source GeoJSON stat error count"),
        ("building_instances", "Total COCO building instances"),
        ("coco_vs_source_delta", "COCO instances minus source buildings"),
        ("coco_vs_source_ratio", "COCO/source building ratio"),
        ("source_covered_buildings", "Source GeoJSON buildings covered by saved images"),
        ("source_coverage_ratio", "Saved image source coverage ratio"),
        ("source_coverage_error_count", "Source coverage stat error count"),
        ("coco_vs_covered_delta", "COCO instances minus covered source buildings"),
        ("coco_vs_covered_ratio", "COCO/covered source building ratio"),
        ("valid_height_buildings", "Valid-height building count"),
        ("valid_height_ratio", "Valid-height building ratio"),
        ("true_height_buildings", "True-height building count"),
        ("true_height_ratio", "True-height building ratio"),
        ("estimated_height_buildings", "Estimated-height building count"),
        ("estimated_height_ratio", "Estimated-height building ratio"),
        ("unknown_height_buildings", "Unknown-height building count"),
        ("unknown_height_ratio", "Unknown-height building ratio"),
        ("json_error_count", "JSON error count"),
    ]
    if not rows:
        return headers
    available = set(rows[0])
    return [(key, title) for key, title in headers if key in available]


def write_markdown(rows: list[dict[str, str | int]], output: Path | None) -> None:
    headers = labels_for_rows(rows)
    lines = [
        "| " + " | ".join(title for _, title in headers) + " |",
        "|" + "|".join("---" for _ in headers) + "|",
    ]
    for row in rows:
        lines.append("| " + " | ".join(escape_md(row[key]) for key, _ in headers) + " |")
    text = "\n".join(lines) + "\n"
    if output:
        output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")


def write_json(rows: list[dict[str, str | int]], output: Path | None) -> None:
    text = json.dumps(rows, ensure_ascii=False, indent=2) + "\n"
    if output:
        output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")


def write_key_value(rows: list[dict[str, str | int]], output: Path | None) -> None:
    labels = labels_for_rows(rows)
    blocks = []
    for index, row in enumerate(rows, start=1):
        lines = [f"[{index}] {row['city_group']}"]
        lines.extend(f"{label}: {row[key]}" for key, label in labels)
        blocks.append("\n".join(lines))
    text = "\n\n".join(blocks) + ("\n" if blocks else "")
    if output:
        output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Count images, height masks, COCO JSON files, and building height annotations for each city."
    )
    parser.add_argument(
        "--base-dir",
        type=Path,
        default=DEFAULT_BASE_DIR,
        help=f"Dataset root directory. Default: {DEFAULT_BASE_DIR}",
    )
    parser.add_argument(
        "--city-dir",
        action="append",
        default=[],
        help="Only count the specified city directory. Can be repeated. Defaults to all cities.",
    )
    parser.add_argument(
        "--group-by",
        choices=["city_dir", "city_group", "city"],
        default="city_dir",
        help="Aggregation level: city_dir writes one row per directory; city_group/city merge directories for the same city.",
    )
    parser.add_argument(
        "--format",
        choices=["kv", "csv", "json", "md"],
        default="kv",
        help="Output format. Defaults to kv key-value output.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Output file path. Prints to the terminal when omitted.",
    )
    parser.add_argument(
        "--with-source-geojson",
        action="store_true",
        help="Also output unique source GeoJSON building counts. By default, only COCO/processed data is counted.",
    )
    parser.add_argument(
        "--with-source-coverage",
        action="store_true",
        help=(
            "Also count how many unique source GeoJSON buildings fall within the saved image grid coverage; "
            "requires geopandas and is slower than the standard statistics."
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    base_dir = args.base_dir.resolve()
    city_dirs = args.city_dir or discover_city_dirs(base_dir)
    include_source_geojson = args.with_source_geojson or args.with_source_coverage
    raw_geojsons = list_source_geojsons(base_dir) if include_source_geojson else []

    stats_by_dir = [
        collect_city_dir_stats(
            base_dir,
            city_dir,
            raw_geojsons,
            with_source_geojson=include_source_geojson,
            with_source_coverage=args.with_source_coverage,
        )
        for city_dir in sorted(city_dirs)
    ]
    stats_list = group_stats(stats_by_dir, args.group_by)
    rows = rows_from_stats(
        stats_list,
        include_source_geojson=include_source_geojson,
        include_source_coverage=args.with_source_coverage,
    )

    if args.format == "kv":
        write_key_value(rows, args.output)
    elif args.format == "csv":
        write_csv(rows, args.output)
    elif args.format == "json":
        write_json(rows, args.output)
    else:
        write_markdown(rows, args.output)


if __name__ == "__main__":
    main()
