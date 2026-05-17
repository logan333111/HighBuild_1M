import argparse
import json
import re
from collections import Counter
from pathlib import Path

import cv2
import numpy as np
from PIL import Image


HEIGHT_MINUS_ONE_RE = re.compile(r'"height"\s*:\s*-1(?:\.0+)?(?:\s*[,}])')
IMAGE_EXTS = (".jpg", ".jpeg", ".png")
MASK_EXTS = (".tif", ".tiff")


def repo_root():
    return Path(__file__).resolve().parents[1]


def default_data_root():
    return repo_root() / "data"


def is_unknown_height(value):
    try:
        return float(value) == -1.0
    except (TypeError, ValueError):
        return False


def clean_raw_geojson_file(path, dry_run):
    stats = Counter(files_seen=1)
    tmp_path = path.with_suffix(path.suffix + ".tmp_clean")

    in_features = False
    kept_feature_count = 0
    changed = False

    if dry_run:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.lstrip().startswith('{ "type": "Feature"'):
                    stats["raw_features_seen"] += 1
                    if HEIGHT_MINUS_ONE_RE.search(line):
                        stats["raw_features_removed"] += 1
        if stats["raw_features_removed"]:
            stats["raw_files_updated"] += 1
        return stats

    with path.open("r", encoding="utf-8") as src, tmp_path.open("w", encoding="utf-8") as dst:
        for line in src:
            stripped = line.strip()

            if not in_features:
                dst.write(line)
                if stripped == '"features": [':
                    in_features = True
                continue

            if stripped.startswith('{ "type": "Feature"'):
                stats["raw_features_seen"] += 1
                if HEIGHT_MINUS_ONE_RE.search(line):
                    stats["raw_features_removed"] += 1
                    changed = True
                    continue

                feature_line = line.rstrip("\n").rstrip()
                if feature_line.endswith(","):
                    feature_line = feature_line[:-1].rstrip()
                if kept_feature_count > 0:
                    dst.write(",\n")
                dst.write(feature_line)
                kept_feature_count += 1
                continue

            if stripped == "]":
                if kept_feature_count > 0:
                    dst.write("\n")
                dst.write(line)
                in_features = False
                continue

            dst.write(line)

    if changed:
        tmp_path.replace(path)
        stats["raw_files_updated"] += 1
    else:
        tmp_path.unlink(missing_ok=True)

    return stats


def clean_raw_geojsons(data_root, dry_run):
    stats = Counter()
    raw_root = data_root / "raw"
    if not raw_root.exists():
        return stats

    for path in sorted(raw_root.rglob("*.geojson")):
        file_stats = clean_raw_geojson_file(path, dry_run)
        stats.update(file_stats)
        if file_stats.get("raw_features_removed"):
            print(
                f"raw\t{path.relative_to(data_root)}\tremoved={file_stats['raw_features_removed']}",
                flush=True,
            )

    return stats


def find_one_with_stem(directory, stem, exts):
    if not directory.exists():
        return None
    for ext in exts:
        path = directory / f"{stem}{ext}"
        if path.exists():
            return path
    return None


def find_viz(viz_dir, stem):
    if not viz_dir.exists():
        return None
    for ext in (".png", ".jpg", ".jpeg"):
        path = viz_dir / f"{stem}_vis{ext}"
        if path.exists():
            return path
    return None


def annotation_height(annotation):
    attrs = annotation.get("attributes")
    if not isinstance(attrs, dict):
        return None
    return attrs.get("height")


def rebuild_mask_and_viz(payload, mask_path, viz_path):
    images = payload.get("images") or []
    width = int(images[0].get("width", 1024)) if images else 1024
    height = int(images[0].get("height", 1024)) if images else 1024
    mask_arr = np.zeros((height, width), dtype=np.float32)

    for ann in payload.get("annotations") or []:
        h = annotation_height(ann)
        if h is None:
            continue
        try:
            h = float(h)
        except (TypeError, ValueError):
            continue

        segments = ann.get("segmentation") or []
        if segments and isinstance(segments[0], (int, float)):
            segments = [segments]

        for flat in segments:
            if not flat or len(flat) < 6:
                continue
            pts = np.array(flat, dtype=np.float32).reshape((-1, 2))
            pts[:, 0] = np.clip(pts[:, 0], 0, width)
            pts[:, 1] = np.clip(pts[:, 1], 0, height)
            pts = np.rint(pts).astype(np.int32).reshape((-1, 1, 2))
            cv2.fillPoly(mask_arr, [pts], h)

    if mask_path is not None:
        cv2.imwrite(str(mask_path), mask_arr)

    if viz_path is not None:
        rgb = np.zeros((height, width, 3), dtype=np.uint8)
        positive = mask_arr > 0
        if positive.any():
            max_h = float(mask_arr[positive].max())
            if max_h > 0:
                vals = np.power(mask_arr[positive] / max_h, 0.4)
                gray = np.clip(vals * 255.0, 0, 255).astype(np.uint8)
                rgb[positive] = np.stack([gray, gray, gray], axis=1)
        negative = mask_arr < 0
        if negative.any():
            rgb[negative] = [255, 51, 51]
        Image.fromarray(rgb).save(viz_path)


def delete_sample(stem, image_dir, json_path, mask_dir, viz_dir, dry_run):
    deleted = 0
    paths = [
        find_one_with_stem(image_dir, stem, IMAGE_EXTS),
        json_path,
        find_one_with_stem(mask_dir, stem, MASK_EXTS),
        find_viz(viz_dir, stem),
    ]
    if dry_run:
        return sum(1 for path in paths if path is not None and path.exists())

    for path in paths:
        if path is not None and path.exists():
            path.unlink()
            deleted += 1
    return deleted


def clean_processed(data_root, dry_run):
    stats = Counter()
    processed_root = data_root / "processed"
    json_root = processed_root / "coco_json"
    image_root = processed_root / "images"
    masks_root = processed_root / "masks"
    if not json_root.exists():
        return stats

    for city_dir in sorted(path for path in json_root.iterdir() if path.is_dir()):
        city = city_dir.name
        image_dir = image_root / city
        mask_dir = masks_root / city / "masks"
        viz_dir = masks_root / city / "viz"
        city_stats = Counter()

        for json_path in sorted(city_dir.glob("*.json")):
            stats["json_files_seen"] += 1
            city_stats["json_files_seen"] += 1
            stem = json_path.stem

            with json_path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)

            annotations = payload.get("annotations") or []
            keep = []
            removed = 0
            for ann in annotations:
                stats["annotations_seen"] += 1
                city_stats["annotations_seen"] += 1
                if is_unknown_height(annotation_height(ann)):
                    removed += 1
                    continue
                keep.append(ann)

            if not removed:
                continue

            stats["annotations_removed"] += removed
            city_stats["annotations_removed"] += removed

            if not keep:
                files_deleted = delete_sample(stem, image_dir, json_path, mask_dir, viz_dir, dry_run)
                stats["empty_samples_removed"] += 1
                stats["files_deleted"] += files_deleted
                city_stats["empty_samples_removed"] += 1
                city_stats["files_deleted"] += files_deleted
                continue

            for idx, ann in enumerate(keep, start=1):
                ann["id"] = idx
            payload["annotations"] = keep

            if not dry_run:
                with json_path.open("w", encoding="utf-8") as handle:
                    json.dump(payload, handle, indent=2, ensure_ascii=False)
                rebuild_mask_and_viz(
                    payload=payload,
                    mask_path=find_one_with_stem(mask_dir, stem, MASK_EXTS),
                    viz_path=find_viz(viz_dir, stem),
                )

            stats["json_files_updated"] += 1
            city_stats["json_files_updated"] += 1

        if city_stats.get("annotations_removed") or city_stats.get("empty_samples_removed"):
            print(
                (
                    f"processed\t{city}\tremoved={city_stats['annotations_removed']}\t"
                    f"json_updated={city_stats['json_files_updated']}\t"
                    f"empty_samples_removed={city_stats['empty_samples_removed']}\t"
                    f"files_deleted={city_stats['files_deleted']}"
                ),
                flush=True,
            )

    return stats


def print_summary(title, stats):
    print(f"\n=== {title} ===")
    if not stats:
        print("no changes")
        return
    for key in sorted(stats):
        print(f"{key}: {stats[key]}")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Remove buildings whose height is -1 from data/raw and data/processed."
    )
    parser.add_argument("--data-root", type=Path, default=default_data_root())
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-raw", action="store_true")
    parser.add_argument("--skip-processed", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()
    data_root = args.data_root.resolve()
    if not data_root.exists():
        raise FileNotFoundError(data_root)

    mode = "DRY-RUN" if args.dry_run else "APPLY"
    print(f"[{mode}] data_root={data_root}", flush=True)

    raw_stats = Counter()
    processed_stats = Counter()
    if not args.skip_raw:
        raw_stats = clean_raw_geojsons(data_root, args.dry_run)
    if not args.skip_processed:
        processed_stats = clean_processed(data_root, args.dry_run)

    print_summary("raw", raw_stats)
    print_summary("processed", processed_stats)


if __name__ == "__main__":
    main()
