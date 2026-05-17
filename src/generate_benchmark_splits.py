import csv
import glob
import itertools
import json
import os
import random
import re
from collections import Counter, defaultdict
from dataclasses import dataclass


BASE_DIR = "/data2/hgq/BuildingHeight_Dataset"
IMAGE_ROOT = os.path.join(BASE_DIR, "data", "processed", "images")
MASK_ROOT = os.path.join(BASE_DIR, "data", "processed", "masks")
JSON_ROOT = os.path.join(BASE_DIR, "data", "processed", "coco_json")
OUTPUT_ROOT = os.path.join(BASE_DIR, "benchmark_v1")
SEED = 42
PATCH_SIZE = 256
PATCH_GRID = 4
SKIP_JSON_STATS = os.environ.get("BENCHMARK_SKIP_JSON_STATS") == "1"


CITY_METADATA = {
    "Africa_CapeTown_buildings_Filtered": {
        "country": "SouthAfrica",
        "region": "Africa",
        "city": "CapeTown",
        "city_group": "SouthAfrica_CapeTown",
    },
    "America_NewYork_Filtered": {
        "country": "USA",
        "region": "NorthAmerica",
        "city": "NewYork",
        "city_group": "USA_NewYork",
    },
    "Amsterdam_buildings_Filtered": {
        "country": "Netherlands",
        "region": "Europe",
        "city": "Amsterdam",
        "city_group": "Netherlands_Amsterdam",
    },
    "Canada_Toronto_Filtered": {
        "country": "Canada",
        "region": "NorthAmerica",
        "city": "Toronto",
        "city_group": "Canada_Toronto",
    },
    "Canada_Vancouver_buildings_Filtered": {
        "country": "Canada",
        "region": "NorthAmerica",
        "city": "Vancouver",
        "city_group": "Canada_Vancouver",
    },
    "Chicago_buildings_full": {
        "country": "USA",
        "region": "NorthAmerica",
        "city": "Chicago",
        "city_group": "USA_Chicago",
    },
    "Denmark_Aarhus_Filtered": {
        "country": "Denmark",
        "region": "Europe",
        "city": "Aarhus",
        "city_group": "Denmark_Aarhus",
    },
    "Denmark_Copenhagen_Filtered": {
        "country": "Denmark",
        "region": "Europe",
        "city": "Copenhagen",
        "city_group": "Denmark_Copenhagen",
    },
    "Denmark_Odense_Filtered": {
        "country": "Denmark",
        "region": "Europe",
        "city": "Odense",
        "city_group": "Denmark_Odense",
    },
    "France_Lyon_buildings_full": {
        "country": "France",
        "region": "Europe",
        "city": "Lyon",
        "city_group": "France_Lyon",
    },
    "France_Marseille_buildings_full": {
        "country": "France",
        "region": "Europe",
        "city": "Marseille",
        "city_group": "France_Marseille",
    },
    "France_Paris_buildings_full": {
        "country": "France",
        "region": "Europe",
        "city": "Paris",
        "city_group": "France_Paris",
    },
    "France_Strasbourg_buildings_full": {
        "country": "France",
        "region": "Europe",
        "city": "Strasbourg",
        "city_group": "France_Strasbourg",
    },
    "France_Toulouse_buildings_full": {
        "country": "France",
        "region": "Europe",
        "city": "Toulouse",
        "city_group": "France_Toulouse",
    },
    "Germany_Berlin_buildings_full": {
        "country": "Germany",
        "region": "Europe",
        "city": "Berlin",
        "city_group": "Germany_Berlin",
    },
    "Germany_Frankfurt_buildings_full": {
        "country": "Germany",
        "region": "Europe",
        "city": "Frankfurt",
        "city_group": "Germany_Frankfurt",
    },
    "Germany_Munich_buildings_full": {
        "country": "Germany",
        "region": "Europe",
        "city": "Munich",
        "city_group": "Germany_Munich",
    },
    "HKG_Core": {
        "country": "HongKong",
        "region": "Asia",
        "city": "HongKong",
        "city_group": "HongKong_HKG",
    },
    "Japan_Osaka_buildings_full": {
        "country": "Japan",
        "region": "Asia",
        "city": "Osaka",
        "city_group": "Japan_Osaka",
    },
    "LosAngeles_Downtown_buildings_full": {
        "country": "USA",
        "region": "NorthAmerica",
        "city": "LosAngeles",
        "city_group": "USA_LosAngeles",
    },
    "Netherlands_Amsterdam_buildings_ready": {
        "country": "Netherlands",
        "region": "Europe",
        "city": "Amsterdam",
        "city_group": "Netherlands_Amsterdam",
    },
    "Netherlands_Tile_GT": {
        "country": "Netherlands",
        "region": "Europe",
        "city": "Amsterdam",
        "city_group": "Netherlands_Amsterdam",
    },
    "Netherlands_Tile_GT_472": {
        "country": "Netherlands",
        "region": "Europe",
        "city": "Amsterdam",
        "city_group": "Netherlands_Amsterdam",
    },
    "NewYork_Manhattan_buildings_full": {
        "country": "USA",
        "region": "NorthAmerica",
        "city": "NewYork",
        "city_group": "USA_NewYork",
    },
    "Oceania_Auckland_buildings_full": {
        "country": "NewZealand",
        "region": "Oceania",
        "city": "Auckland",
        "city_group": "NewZealand_Auckland",
    },
    "Oceania_Melbourne_buildings_full": {
        "country": "Australia",
        "region": "Oceania",
        "city": "Melbourne",
        "city_group": "Australia_Melbourne",
    },
    "Oceania_Sydney_buildings_full": {
        "country": "Australia",
        "region": "Oceania",
        "city": "Sydney",
        "city_group": "Australia_Sydney",
    },
    "SanFrancisco_FiDi_buildings_full": {
        "country": "USA",
        "region": "NorthAmerica",
        "city": "SanFrancisco",
        "city_group": "USA_SanFrancisco",
    },
    "Seattle_Downtown_buildings_full": {
        "country": "USA",
        "region": "NorthAmerica",
        "city": "Seattle",
        "city_group": "USA_Seattle",
    },
    "TWN_Buildings_ready": {
        "country": "Taiwan",
        "region": "Asia",
        "city": "Taiwan",
        "city_group": "Taiwan_TWN",
    },
    "berlin_all_buildings_height_Filtered": {
        "country": "Germany",
        "region": "Europe",
        "city": "Berlin",
        "city_group": "Germany_Berlin",
    },
    "paris_buildings_with_height_Filtered": {
        "country": "France",
        "region": "Europe",
        "city": "Paris",
        "city_group": "France_Paris",
    },
}


CITY_SPLIT_VAL_GROUPS = {
    "Japan_Osaka",
    "Denmark_Copenhagen",
    "Australia_Melbourne",
    "France_Lyon",
    "Germany_Frankfurt",
}

CITY_SPLIT_TEST_GROUPS = {
    "Netherlands_Amsterdam",
    "Taiwan_TWN",
    "France_Toulouse",
    "Germany_Berlin",
    "Australia_Sydney",
    "Denmark_Aarhus",
    "USA_Chicago",
    "USA_LosAngeles",
    "USA_SanFrancisco",
    "USA_Seattle",
    "NewZealand_Auckland",
    "France_Paris",
    "France_Strasbourg",
    "France_Marseille",
    "Germany_Munich",
    "Canada_Vancouver",
    "Denmark_Odense",
    "USA_NewYork",
}

SAME_COUNTRY_SPLITS = {
    "train": {
        "Denmark_Copenhagen",
        "France_Toulouse",
        "Germany_Berlin",
        "USA_Chicago",
    },
    "val": {
        "Denmark_Aarhus",
        "France_Marseille",
        "Germany_Frankfurt",
        "USA_LosAngeles",
    },
    "test": {
        "Denmark_Odense",
        "France_Lyon",
        "France_Paris",
        "France_Strasbourg",
        "Germany_Munich",
        "USA_SanFrancisco",
        "USA_Seattle",
        "USA_NewYork",
    },
}

SAME_COUNTRY_COUNTRIES = {"Denmark", "France", "Germany", "USA"}


@dataclass
class TileRecord:
    tile_id: str
    tile_name: str
    city_dir: str
    city: str
    city_group: str
    country: str
    region: str
    image_path: str
    mask_path: str
    json_path: str
    num_annotations: int
    unknown_annotations: int
    estimated_annotations: int
    has_unknown: bool
    has_estimated: bool


def ensure_dir(path):
    os.makedirs(path, exist_ok=True)


def matched_basenames(city_dir):
    image_dir = os.path.join(IMAGE_ROOT, city_dir)
    mask_dir = os.path.join(MASK_ROOT, city_dir, "masks")
    json_dir = os.path.join(JSON_ROOT, city_dir)
    image_names = {
        os.path.splitext(os.path.basename(path))[0]
        for path in glob.glob(os.path.join(image_dir, "*.jpg"))
    }
    mask_names = set()
    for path in glob.glob(os.path.join(mask_dir, "*.tif*")):
        basename = os.path.basename(path)
        if basename.endswith(".tiff"):
            mask_names.add(basename[:-5])
        elif basename.endswith(".tif"):
            mask_names.add(basename[:-4])
    json_names = {
        os.path.splitext(os.path.basename(path))[0]
        for path in glob.glob(os.path.join(json_dir, "*.json"))
    }
    return sorted(image_names & mask_names & json_names)


def parse_json_stats(json_path):
    if SKIP_JSON_STATS:
        return 0, 0, 0
    with open(json_path, "rb") as handle:
        data = handle.read()
    annotations = data.count(b'"image_id"')
    unknown = len(re.findall(rb'"height"\s*:\s*-', data))
    estimated = len(re.findall(rb'"is_estimated_height"\s*:\s*true', data))
    return annotations, unknown, estimated


def build_tile_records():
    records = []
    skipped = []
    for city_dir in sorted(os.listdir(IMAGE_ROOT)):
        if city_dir not in CITY_METADATA:
            continue
        meta = CITY_METADATA[city_dir]
        for basename in matched_basenames(city_dir):
            image_path = os.path.join(IMAGE_ROOT, city_dir, basename + ".jpg")
            mask_path = os.path.join(MASK_ROOT, city_dir, "masks", basename + ".tiff")
            if not os.path.exists(mask_path):
                mask_path = os.path.join(MASK_ROOT, city_dir, "masks", basename + ".tif")
            json_path = os.path.join(JSON_ROOT, city_dir, basename + ".json")
            if not (os.path.exists(image_path) and os.path.exists(mask_path) and os.path.exists(json_path)):
                skipped.append((city_dir, basename))
                continue
            num_annotations, unknown, estimated = parse_json_stats(json_path)
            tile_id = f"{meta['city_group']}/{city_dir}/{basename}"
            records.append(
                TileRecord(
                    tile_id=tile_id,
                    tile_name=basename,
                    city_dir=city_dir,
                    city=meta["city"],
                    city_group=meta["city_group"],
                    country=meta["country"],
                    region=meta["region"],
                    image_path=image_path,
                    mask_path=mask_path,
                    json_path=json_path,
                    num_annotations=num_annotations,
                    unknown_annotations=unknown,
                    estimated_annotations=estimated,
                    has_unknown=unknown > 0,
                    has_estimated=estimated > 0,
                )
            )
    return records, skipped


def build_patch_rows(tile_records):
    rows = []
    for record in tile_records:
        for row in range(PATCH_GRID):
            for col in range(PATCH_GRID):
                y0 = row * PATCH_SIZE
                x0 = col * PATCH_SIZE
                patch_id = f"{record.tile_id}#y{y0:03d}_x{x0:03d}"
                rows.append(
                    {
                        "patch_id": patch_id,
                        "tile_id": record.tile_id,
                        "city_group": record.city_group,
                        "country": record.country,
                        "region": record.region,
                        "row": row,
                        "col": col,
                        "x0": x0,
                        "y0": y0,
                        "patch_size": PATCH_SIZE,
                    }
                )
    return rows


def write_csv(path, fieldnames, rows):
    ensure_dir(os.path.dirname(path))
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def sequential_64_16_20_split(items, seed_key):
    rng = random.Random(f"{SEED}:{seed_key}")
    shuffled = list(items)
    rng.shuffle(shuffled)
    total = len(shuffled)
    test_count = int(total * 0.2)
    if total >= 5 and test_count == 0:
        test_count = 1
    train_pool_count = total - test_count
    val_count = int(train_pool_count * 0.2)
    if train_pool_count >= 5 and val_count == 0:
        val_count = 1
    train_count = total - test_count - val_count
    return {
        "train": shuffled[:train_count],
        "val": shuffled[train_count:train_count + val_count],
        "test": shuffled[train_count + val_count:],
    }


def group_records(tile_records, attr_name):
    grouped = defaultdict(list)
    for record in tile_records:
        grouped[getattr(record, attr_name)].append(record)
    return grouped


def build_same_city_random(tile_records):
    grouped = group_records(tile_records, "city_group")
    split_map = {"train": [], "val": [], "test": []}
    for group_name, records in sorted(grouped.items()):
        local = sequential_64_16_20_split(records, group_name)
        for split_name in split_map:
            split_map[split_name].extend(local[split_name])
    return split_map


def build_cross_city(tile_records):
    split_map = {"train": [], "val": [], "test": []}
    grouped = group_records(tile_records, "city_group")
    for group_name, records in grouped.items():
        if group_name in CITY_SPLIT_VAL_GROUPS:
            split_map["val"].extend(records)
        elif group_name in CITY_SPLIT_TEST_GROUPS:
            split_map["test"].extend(records)
        else:
            split_map["train"].extend(records)
    return split_map


def build_same_country(tile_records):
    split_map = {"train": [], "val": [], "test": []}
    for record in tile_records:
        if record.country not in SAME_COUNTRY_COUNTRIES:
            continue
        assigned = None
        for split_name, groups in SAME_COUNTRY_SPLITS.items():
            if record.city_group in groups:
                assigned = split_name
                break
        if assigned is None:
            raise ValueError(f"Unassigned same-country city group: {record.city_group}")
        split_map[assigned].append(record)
    return split_map


def search_cross_country(country_totals):
    countries = sorted(country_totals)
    values = [country_totals[country] for country in countries]
    total = sum(values)
    target_train = total * 0.64
    target_val = total * 0.16
    target_test = total * 0.20
    best = None
    for assignment in itertools.product(range(3), repeat=len(countries)):
        if 1 not in assignment or 2 not in assignment:
            continue
        if sum(1 for item in assignment if item == 1) < 2:
            continue
        if sum(1 for item in assignment if item == 2) < 2:
            continue
        sums = [0, 0, 0]
        counts = [0, 0, 0]
        for idx, split_idx in enumerate(assignment):
            sums[split_idx] += values[idx]
            counts[split_idx] += 1
        score = (
            (sums[0] - target_train) ** 2
            + (sums[1] - target_val) ** 2
            + (sums[2] - target_test) ** 2
            + 100000 * (abs(counts[1] - 3) + abs(counts[2] - 4))
        )
        if best is None or score < best[0]:
            best = (score, assignment, sums)
    mapping = {}
    for country, split_idx in zip(countries, best[1]):
        mapping[country] = ("train", "val", "test")[split_idx]
    return mapping, best[2]


def build_cross_country(tile_records):
    country_totals = Counter(record.country for record in tile_records)
    split_by_country, target_sums = search_cross_country(country_totals)
    split_map = {"train": [], "val": [], "test": []}
    for record in tile_records:
        split_map[split_by_country[record.country]].append(record)
    return split_map, split_by_country, target_sums


def sort_ids(values):
    return sorted(values)


def write_split_files(root_dir, split_map):
    for split_name, records in split_map.items():
        tile_ids = sort_ids(record.tile_id for record in records)
        split_dir = os.path.join(root_dir, "tiles_1024")
        ensure_dir(split_dir)
        with open(os.path.join(split_dir, f"{split_name}.txt"), "w", encoding="utf-8") as handle:
            handle.write("\n".join(tile_ids))
        patch_ids = []
        for tile_id in tile_ids:
            for row in range(PATCH_GRID):
                for col in range(PATCH_GRID):
                    patch_ids.append(f"{tile_id}#y{row * PATCH_SIZE:03d}_x{col * PATCH_SIZE:03d}")
        patch_dir = os.path.join(root_dir, "patches_256")
        ensure_dir(patch_dir)
        with open(os.path.join(patch_dir, f"{split_name}.txt"), "w", encoding="utf-8") as handle:
            handle.write("\n".join(patch_ids))


def summarize_split(split_map):
    summary = {}
    for split_name, records in split_map.items():
        regions = Counter(record.region for record in records)
        countries = Counter(record.country for record in records)
        cities = Counter(record.city_group for record in records)
        summary[split_name] = {
            "tiles": len(records),
            "patches_256": len(records) * PATCH_GRID * PATCH_GRID,
            "countries": dict(sorted(countries.items())),
            "regions": dict(sorted(regions.items())),
            "city_groups": dict(sorted(cities.items())),
            "estimated_tiles": sum(1 for record in records if record.has_estimated),
            "unknown_tiles": sum(1 for record in records if record.has_unknown),
        }
    return summary


def write_manifest(tile_records, patch_rows):
    tile_rows = []
    for record in tile_records:
        tile_rows.append(
            {
                "tile_id": record.tile_id,
                "tile_name": record.tile_name,
                "city_dir": record.city_dir,
                "city": record.city,
                "city_group": record.city_group,
                "country": record.country,
                "region": record.region,
                "image_path": record.image_path,
                "mask_path": record.mask_path,
                "json_path": record.json_path,
                "num_annotations": record.num_annotations,
                "unknown_annotations": record.unknown_annotations,
                "estimated_annotations": record.estimated_annotations,
                "has_unknown": int(record.has_unknown),
                "has_estimated": int(record.has_estimated),
            }
        )
    write_csv(
        os.path.join(OUTPUT_ROOT, "manifest_tiles_1024.csv"),
        [
            "tile_id",
            "tile_name",
            "city_dir",
            "city",
            "city_group",
            "country",
            "region",
            "image_path",
            "mask_path",
            "json_path",
            "num_annotations",
            "unknown_annotations",
            "estimated_annotations",
            "has_unknown",
            "has_estimated",
        ],
        tile_rows,
    )
    write_csv(
        os.path.join(OUTPUT_ROOT, "manifest_patches_256.csv"),
        [
            "patch_id",
            "tile_id",
            "city_group",
            "country",
            "region",
            "row",
            "col",
            "x0",
            "y0",
            "patch_size",
        ],
        patch_rows,
    )


def write_report(tile_records, skipped, split_summaries, cross_country_assignment, cross_country_sums):
    total_tiles = len(tile_records)
    total_patches = total_tiles * PATCH_GRID * PATCH_GRID
    city_counts = Counter(record.city_group for record in tile_records)
    country_counts = Counter(record.country for record in tile_records)
    region_counts = Counter(record.region for record in tile_records)
    total_annotations = sum(record.num_annotations for record in tile_records)
    total_unknown = sum(record.unknown_annotations for record in tile_records)
    total_estimated = sum(record.estimated_annotations for record in tile_records)

    lines = []
    lines.append("# Benchmark V1 Split Report")
    lines.append("")
    lines.append("## Overall")
    lines.append("")
    lines.append(f"- tiles_1024: {total_tiles}")
    lines.append(f"- patches_256: {total_patches}")
    lines.append(f"- city_groups: {len(city_counts)}")
    lines.append(f"- countries: {len(country_counts)}")
    lines.append(f"- regions: {len(region_counts)}")
    lines.append(f"- annotations: {total_annotations}")
    lines.append(f"- unknown_height_annotations: {total_unknown}")
    lines.append(f"- estimated_height_annotations: {total_estimated}")
    lines.append(f"- skipped_unmatched_tiles: {len(skipped)}")
    if SKIP_JSON_STATS:
        lines.append("- annotation_stats: skipped by BENCHMARK_SKIP_JSON_STATS=1")
    lines.append("")
    lines.append("## Tiles By Country")
    lines.append("")
    for country, count in sorted(country_counts.items()):
        lines.append(f"- {country}: {count}")
    lines.append("")
    lines.append("## Tiles By City Group")
    lines.append("")
    for city_group, count in sorted(city_counts.items()):
        lines.append(f"- {city_group}: {count}")
    lines.append("")
    lines.append("## Splits")
    lines.append("")

    split_display = {
        "same_city_random": "Same-city random split",
        "cross_city": "Cross-city test",
        "same_country": "Same-country cross-city split",
        "cross_country": "Cross-country test",
    }

    for split_key, summary in split_summaries.items():
        lines.append(f"### {split_display[split_key]}")
        lines.append("")
        for split_name in ("train", "val", "test"):
            block = summary[split_name]
            lines.append(
                f"- {split_name}: tiles={block['tiles']}, patches_256={block['patches_256']}, "
                f"unknown_tiles={block['unknown_tiles']}, estimated_tiles={block['estimated_tiles']}"
            )
        lines.append("")
        lines.append("Countries:")
        for split_name in ("train", "val", "test"):
            lines.append(f"- {split_name}: {summary[split_name]['countries']}")
        lines.append("")
        lines.append("Regions:")
        for split_name in ("train", "val", "test"):
            lines.append(f"- {split_name}: {summary[split_name]['regions']}")
        lines.append("")

    lines.append("## Cross-Country Assignment")
    lines.append("")
    for country, split_name in sorted(cross_country_assignment.items()):
        lines.append(f"- {country}: {split_name}")
    lines.append("")
    lines.append(f"- cross_country_target_tiles: train={cross_country_sums[0]}, val={cross_country_sums[1]}, test={cross_country_sums[2]}")
    lines.append("")
    lines.append("## Notes")
    lines.append("")
    lines.append("- All 256 patches inherit the split of their parent 1024 tile to avoid data leakage.")
    lines.append("- Same-country cross-city split only uses Denmark, France, Germany, and USA because each has at least three cities, allowing train, val, and test to use different cities.")
    lines.append("- Cross-country testing assigns whole countries exclusively, so no country appears in both train and test.")

    report_path = os.path.join(OUTPUT_ROOT, "split_report.md")
    with open(report_path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def main():
    ensure_dir(OUTPUT_ROOT)
    tile_records, skipped = build_tile_records()
    patch_rows = build_patch_rows(tile_records)
    write_manifest(tile_records, patch_rows)

    same_city_random = build_same_city_random(tile_records)
    cross_city = build_cross_city(tile_records)
    same_country = build_same_country(tile_records)
    cross_country, cross_country_assignment, cross_country_sums = build_cross_country(tile_records)

    split_maps = {
        "same_city_random": same_city_random,
        "cross_city": cross_city,
        "same_country": same_country,
        "cross_country": cross_country,
    }

    split_summaries = {}
    for split_key, split_map in split_maps.items():
        split_dir = os.path.join(OUTPUT_ROOT, "splits", split_key)
        write_split_files(split_dir, split_map)
        split_summaries[split_key] = summarize_split(split_map)

    with open(os.path.join(OUTPUT_ROOT, "cross_country_assignment.json"), "w", encoding="utf-8") as handle:
        json.dump(cross_country_assignment, handle, indent=2, ensure_ascii=False)

    write_report(tile_records, skipped, split_summaries, cross_country_assignment, cross_country_sums)

    print(f"Generated benchmark_v1 under {OUTPUT_ROOT}")
    print(f"Tiles: {len(tile_records)}")
    print(f"Patches: {len(patch_rows)}")
    for split_key, summary in split_summaries.items():
        print(split_key, {name: block['tiles'] for name, block in summary.items()})


if __name__ == "__main__":
    main()
