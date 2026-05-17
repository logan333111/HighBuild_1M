import argparse
import json
from collections import Counter
from pathlib import Path

import numpy as np
from PIL import Image


IMAGE_EXTS = {".jpg", ".jpeg", ".png"}
MASK_EXTS = {".tif", ".tiff"}
VIZ_SUFFIX = "_vis"


def repo_root():
    return Path(__file__).resolve().parents[1]


def default_processed_root():
    return repo_root() / "data" / "processed"


def collect_image_files(image_dir):
    mapping = {}
    if not image_dir.exists():
        return mapping
    for path in sorted(image_dir.iterdir()):
        if path.is_file() and path.suffix.lower() in IMAGE_EXTS:
            mapping[path.stem] = path
    return mapping


def collect_json_files(json_dir):
    mapping = {}
    if not json_dir.exists():
        return mapping
    for path in sorted(json_dir.iterdir()):
        if path.is_file() and path.suffix.lower() == ".json":
            mapping[path.stem] = path
    return mapping


def collect_mask_files(mask_dir):
    mapping = {}
    if not mask_dir.exists():
        return mapping
    for path in sorted(mask_dir.iterdir()):
        if path.is_file() and path.suffix.lower() in MASK_EXTS:
            mapping[path.stem] = path
    return mapping


def collect_viz_files(viz_dir):
    mapping = {}
    if not viz_dir.exists():
        return mapping
    for path in sorted(viz_dir.iterdir()):
        if not path.is_file():
            continue
        stem = path.stem
        if stem.endswith(VIZ_SUFFIX):
            mapping[stem[: -len(VIZ_SUFFIX)]] = path
    return mapping


def delete_path(path, dry_run):
    if not path or not path.exists():
        return False
    if dry_run:
        return True
    path.unlink()
    return True


def sample_paths_for_stem(stem, images, jsons, masks, vizs):
    return [
        images.get(stem),
        jsons.get(stem),
        masks.get(stem),
        vizs.get(stem),
    ]


def compute_valid_pixel_ratio(image_path, black_threshold):
    with Image.open(image_path) as img:
        arr = np.array(img)

    if arr.ndim == 2:
        valid = arr > black_threshold
    elif arr.shape[2] == 4:
        alpha = arr[:, :, 3] > 0
        rgb_valid = (arr[:, :, :3] > black_threshold).any(axis=2)
        valid = alpha & rgb_valid
    else:
        valid = (arr[:, :, :3] > black_threshold).any(axis=2)

    return float(np.mean(valid))


def annotation_is_oob(annotation, width, height):
    bbox = annotation.get("bbox") or []
    if len(bbox) >= 4:
        x, y, w, h = bbox[:4]
        if x < 0 or y < 0 or x + w > width or y + h > height:
            return True

    segmentation = annotation.get("segmentation") or []
    if segmentation and isinstance(segmentation[0], (int, float)):
        segmentation = [segmentation]

    for flat in segmentation:
        xs = flat[0::2]
        ys = flat[1::2]
        if xs and ys and (
            min(xs) < 0 or min(ys) < 0 or max(xs) > width or max(ys) > height
        ):
            return True

    return False


def polygon_area(points):
    if len(points) < 3:
        return 0.0
    area = 0.0
    for idx, (x1, y1) in enumerate(points):
        x2, y2 = points[(idx + 1) % len(points)]
        area += x1 * y2 - x2 * y1
    return abs(area) * 0.5


def dedupe_consecutive_points(points):
    deduped = []
    for point in points:
        if not deduped or point != deduped[-1]:
            deduped.append(point)
    if len(deduped) > 1 and deduped[0] == deduped[-1]:
        deduped.pop()
    return deduped


def clip_points(points, inside_fn, intersect_fn):
    if not points:
        return []

    output = []
    previous = points[-1]
    previous_inside = inside_fn(previous)
    for current in points:
        current_inside = inside_fn(current)
        if current_inside:
            if not previous_inside:
                output.append(intersect_fn(previous, current))
            output.append(current)
        elif previous_inside:
            output.append(intersect_fn(previous, current))
        previous = current
        previous_inside = current_inside

    return dedupe_consecutive_points(output)


def intersect_vertical(boundary_x, p1, p2):
    x1, y1 = p1
    x2, y2 = p2
    if x1 == x2:
        return float(boundary_x), float(y1)
    ratio = (boundary_x - x1) / (x2 - x1)
    return float(boundary_x), float(y1 + ratio * (y2 - y1))


def intersect_horizontal(boundary_y, p1, p2):
    x1, y1 = p1
    x2, y2 = p2
    if y1 == y2:
        return float(x1), float(boundary_y)
    ratio = (boundary_y - y1) / (y2 - y1)
    return float(x1 + ratio * (x2 - x1)), float(boundary_y)


def clip_polygon_to_canvas(points, width, height):
    clipped = dedupe_consecutive_points(points)
    if len(clipped) < 3:
        return []

    clipped = clip_points(
        clipped,
        inside_fn=lambda p: p[0] >= 0.0,
        intersect_fn=lambda p1, p2: intersect_vertical(0.0, p1, p2),
    )
    clipped = clip_points(
        clipped,
        inside_fn=lambda p: p[0] <= float(width),
        intersect_fn=lambda p1, p2: intersect_vertical(float(width), p1, p2),
    )
    clipped = clip_points(
        clipped,
        inside_fn=lambda p: p[1] >= 0.0,
        intersect_fn=lambda p1, p2: intersect_horizontal(0.0, p1, p2),
    )
    clipped = clip_points(
        clipped,
        inside_fn=lambda p: p[1] <= float(height),
        intersect_fn=lambda p1, p2: intersect_horizontal(float(height), p1, p2),
    )
    clipped = dedupe_consecutive_points(clipped)

    if len(clipped) < 3 or polygon_area(clipped) <= 0.0:
        return []
    return clipped


def flat_to_points(flat):
    if len(flat) < 6 or len(flat) % 2 != 0:
        return []
    return [(float(flat[idx]), float(flat[idx + 1])) for idx in range(0, len(flat), 2)]


def annotation_segments(annotation):
    segmentation = annotation.get("segmentation") or []
    if segmentation and isinstance(segmentation[0], (int, float)):
        segmentation = [segmentation]

    segments = []
    for flat in segmentation:
        points = flat_to_points(flat)
        if points:
            segments.append(points)

    if segments:
        return segments

    bbox = annotation.get("bbox") or []
    if len(bbox) >= 4:
        x, y, w, h = bbox[:4]
        if w > 0 and h > 0:
            return [[
                (float(x), float(y)),
                (float(x + w), float(y)),
                (float(x + w), float(y + h)),
                (float(x), float(y + h)),
            ]]

    return []


def clip_annotation(annotation, width, height):
    segments = annotation_segments(annotation)
    if not segments:
        return None, False, True

    clipped_segments = []
    for points in segments:
        clipped = clip_polygon_to_canvas(points, width, height)
        if clipped:
            flat = []
            for x, y in clipped:
                flat.extend([float(x), float(y)])
            if len(flat) >= 6:
                clipped_segments.append(flat)

    if not clipped_segments:
        return None, True, True

    xs = []
    ys = []
    total_area = 0.0
    for flat in clipped_segments:
        points = flat_to_points(flat)
        xs.extend([point[0] for point in points])
        ys.extend([point[1] for point in points])
        total_area += polygon_area(points)

    if not xs or not ys or total_area <= 0.0:
        return None, True, True

    xmin = min(xs)
    ymin = min(ys)
    xmax = max(xs)
    ymax = max(ys)
    updated = dict(annotation)
    updated["segmentation"] = clipped_segments
    updated["bbox"] = [
        float(xmin),
        float(ymin),
        float(xmax - xmin),
        float(ymax - ymin),
    ]
    updated["area"] = float(total_area)
    changed = annotation_is_oob(annotation, width, height)
    return updated, changed, False


def write_json(path, payload, dry_run):
    if dry_run:
        return
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)


def remove_sample(stem, images, jsons, masks, vizs, dry_run, stats, reason):
    deleted = 0
    for path in sample_paths_for_stem(stem, images, jsons, masks, vizs):
        if delete_path(path, dry_run):
            deleted += 1
    stats[reason] += 1
    stats["files_deleted"] += deleted


def process_city(city_dir, processed_root, valid_pixel_threshold, black_threshold, dry_run):
    city_stats = Counter()

    image_dir = processed_root / "images" / city_dir
    json_dir = processed_root / "coco_json" / city_dir
    mask_root = processed_root / "masks" / city_dir
    mask_dir = mask_root / "masks"
    viz_dir = mask_root / "viz"

    images = collect_image_files(image_dir)
    jsons = collect_json_files(json_dir)
    masks = collect_mask_files(mask_dir)
    vizs = collect_viz_files(viz_dir)

    city_stats["images_before"] = len(images)
    city_stats["json_before"] = len(jsons)
    city_stats["masks_before"] = len(masks)
    city_stats["viz_before"] = len(vizs)

    paired_stem_set = set(images) & set(jsons)
    paired_stems = sorted(paired_stem_set)
    orphan_stems = (set(images) | set(jsons) | set(masks) | set(vizs)) - paired_stem_set
    for stem in sorted(orphan_stems):
        remove_sample(stem, images, jsons, masks, vizs, dry_run, city_stats, "orphan_samples_removed")

    city_stats["paired_before_filter"] = len(paired_stems)
    print(f"paired_before_filter: {city_stats['paired_before_filter']}", flush=True)

    for index, stem in enumerate(paired_stems, start=1):
        image_path = images.get(stem)
        json_path = jsons.get(stem)
        mask_path = masks.get(stem)
        viz_path = vizs.get(stem)

        if image_path is None or json_path is None:
            continue

        city_stats["paired_scanned"] += 1
        if mask_path is None:
            city_stats["missing_mask_pairs"] += 1
        if viz_path is None:
            city_stats["missing_viz_pairs"] += 1

        try:
            valid_ratio = compute_valid_pixel_ratio(image_path, black_threshold)
        except Exception:
            remove_sample(stem, images, jsons, masks, vizs, dry_run, city_stats, "broken_image_removed")
            continue

        if valid_ratio < valid_pixel_threshold:
            city_stats["low_valid_pixel_ratio_removed"] += 1
            city_stats["low_valid_pixel_ratio_sum"] += valid_ratio
            remove_sample(stem, images, jsons, masks, vizs, dry_run, city_stats, "samples_removed_after_threshold")
            continue

        try:
            with open(json_path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except Exception:
            remove_sample(stem, images, jsons, masks, vizs, dry_run, city_stats, "broken_json_removed")
            continue

        try:
            with Image.open(image_path) as img:
                width, height = img.size
        except Exception:
            remove_sample(stem, images, jsons, masks, vizs, dry_run, city_stats, "broken_image_removed")
            continue

        images_block = payload.get("images") or []
        if images_block:
            images_block[0]["width"] = width
            images_block[0]["height"] = height
            images_block[0]["file_name"] = image_path.name

        changed_file = False
        new_annotations = []
        next_ann_id = 1
        for annotation in payload.get("annotations", []):
            city_stats["annotations_scanned"] += 1
            if not annotation_is_oob(annotation, width, height):
                updated = dict(annotation)
                changed = False
                dropped = False
            else:
                updated, changed, dropped = clip_annotation(annotation, width, height)
            if dropped:
                city_stats["annotations_dropped_after_clip"] += 1
                changed_file = True
                continue
            if changed:
                city_stats["annotations_clipped"] += 1
                changed_file = True
            updated["id"] = next_ann_id
            next_ann_id += 1
            new_annotations.append(updated)

        if not new_annotations:
            remove_sample(stem, images, jsons, masks, vizs, dry_run, city_stats, "empty_after_annotation_cleaning")
            continue

        if changed_file:
            payload["annotations"] = new_annotations
            write_json(json_path, payload, dry_run)
            city_stats["json_files_updated"] += 1

        city_stats["samples_kept"] += 1

        if index == 1 or index % 50 == 0 or index == city_stats["paired_before_filter"]:
            print(
                (
                    f"[{city_dir}] progress {index}/{city_stats['paired_before_filter']} | "
                    f"kept={city_stats.get('samples_kept', 0)} | "
                    f"low_valid_removed={city_stats.get('samples_removed_after_threshold', 0)} | "
                    f"empty_removed={city_stats.get('empty_after_annotation_cleaning', 0)} | "
                    f"json_updated={city_stats.get('json_files_updated', 0)}"
                ),
                flush=True,
            )

    return city_stats


def discover_city_dirs(processed_root):
    groups = []
    for subdir in ("images", "coco_json", "masks"):
        root = processed_root / subdir
        if not root.exists():
            continue
        groups.extend([path.name for path in root.iterdir() if path.is_dir()])
    return sorted(set(groups))


def parse_args():
    parser = argparse.ArgumentParser(
        description="Clean processed data by clipping out-of-bounds annotations, removing unpaired samples, and deleting samples with too few valid pixels."
    )
    parser.add_argument(
        "--processed-root",
        type=Path,
        default=default_processed_root(),
        help="Processed root directory. Defaults to data/processed.",
    )
    parser.add_argument(
        "--valid-pixel-threshold",
        type=float,
        default=0.30,
        help="Minimum valid pixel ratio. Samples below this value are deleted.",
    )
    parser.add_argument(
        "--black-threshold",
        type=int,
        default=5,
        help="Pixel threshold for black borders. Any RGB channel above this value counts as valid.",
    )
    parser.add_argument(
        "--city",
        nargs="*",
        default=None,
        help="Only clean selected city directories, e.g. --city berlin_all_buildings_height_Filtered Canada_Toronto_Filtered.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print statistics without modifying files.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    processed_root = args.processed_root.resolve()

    if not processed_root.exists():
        raise FileNotFoundError(f"Processed directory not found: {processed_root}")

    city_dirs = args.city or discover_city_dirs(processed_root)
    if not city_dirs:
        raise RuntimeError(f"No city directories found under {processed_root}")

    mode = "DRY-RUN" if args.dry_run else "APPLY"
    print(f"[{mode}] processed_root={processed_root}")
    print(
        f"[{mode}] valid_pixel_threshold={args.valid_pixel_threshold:.2%}, "
        f"black_threshold={args.black_threshold}"
    )

    grand_total = Counter()
    for city_dir in city_dirs:
        print(f"\n=== {city_dir} ===")
        city_stats = process_city(
            city_dir=city_dir,
            processed_root=processed_root,
            valid_pixel_threshold=args.valid_pixel_threshold,
            black_threshold=args.black_threshold,
            dry_run=args.dry_run,
        )
        grand_total.update(city_stats)

        for key in [
            "paired_scanned",
            "samples_kept",
            "orphan_samples_removed",
            "samples_removed_after_threshold",
            "broken_image_removed",
            "broken_json_removed",
            "empty_after_annotation_cleaning",
            "annotations_clipped",
            "annotations_dropped_after_clip",
            "json_files_updated",
            "missing_mask_pairs",
            "missing_viz_pairs",
            "files_deleted",
        ]:
            if city_stats.get(key):
                print(f"{key}: {city_stats[key]}")

    print("\n=== Summary ===")
    for key in [
        "paired_scanned",
        "samples_kept",
        "orphan_samples_removed",
        "samples_removed_after_threshold",
        "broken_image_removed",
        "broken_json_removed",
        "empty_after_annotation_cleaning",
        "annotations_scanned",
        "annotations_clipped",
        "annotations_dropped_after_clip",
        "json_files_updated",
        "missing_mask_pairs",
        "missing_viz_pairs",
        "files_deleted",
    ]:
        if grand_total.get(key):
            print(f"{key}: {grand_total[key]}")


if __name__ == "__main__":
    main()
