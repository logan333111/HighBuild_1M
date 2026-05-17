import os
import sys
import math
import argparse
import random

import geopandas as gpd
import numpy as np
from PIL import Image
from shapely.geometry import box

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sources import get_source
from dataset_engine import generate_labels_for_grid
import geo_utils
import config


def safe_set_postfix(grid_iter, **kwargs):
    if hasattr(grid_iter, "set_postfix"):
        grid_iter.set_postfix(**kwargs)


def append_log(log_path, text):
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(text.rstrip("\n") + "\n")


def get_valid_image_stats(img: Image.Image):
    arr = np.array(img)

    if arr.ndim != 3:
        return {
            "has_alpha": False,
            "valid_count": arr.size,
            "total_count": arr.size,
            "mean": float(np.mean(arr)),
            "min": int(np.min(arr)),
            "max": int(np.max(arr)),
            "std": float(np.std(arr)),
            "is_fully_transparent": False,
        }


    if arr.shape[2] == 4:
        alpha = arr[:, :, 3]
        valid_mask = alpha > 0
        valid_count = int(np.sum(valid_mask))
        total_count = int(alpha.shape[0] * alpha.shape[1])

        if valid_count == 0:
            return {
                "has_alpha": True,
                "valid_count": 0,
                "total_count": total_count,
                "mean": None,
                "min": None,
                "max": None,
                "std": None,
                "is_fully_transparent": True,
            }

        rgb_valid = arr[:, :, :3][valid_mask]
        return {
            "has_alpha": True,
            "valid_count": valid_count,
            "total_count": total_count,
            "mean": float(np.mean(rgb_valid)),
            "min": int(np.min(rgb_valid)),
            "max": int(np.max(rgb_valid)),
            "std": float(np.std(rgb_valid)),
            "is_fully_transparent": False,
        }


    rgb = arr[:, :, :3]
    total_count = int(rgb.shape[0] * rgb.shape[1])

    return {
        "has_alpha": False,
        "valid_count": total_count,
        "total_count": total_count,
        "mean": float(np.mean(rgb)),
        "min": int(np.min(rgb)),
        "max": int(np.max(rgb)),
        "std": float(np.std(rgb)),
        "is_fully_transparent": False,
    }


def is_probably_white(stats):
    return (
        stats["mean"] is not None
        and stats["std"] is not None
        and stats["mean"] > 250
        and stats["std"] < 5
    )


def is_probably_black(stats):
    return (
        stats["mean"] is not None
        and stats["std"] is not None
        and stats["mean"] < 5
        and stats["std"] < 5
    )


def save_debug_image(img: Image.Image, path: str):
    parent = os.path.dirname(path)
    os.makedirs(parent, exist_ok=True)

    if img.mode in ("RGBA", "LA"):
        img = img.convert("RGB")

    img.save(path, quality=95)


def select_center_grid(all_grids):
    """
    Generic logic to select the true center grid for any city.
    """
    all_min_x = min(g["global_x_start"] for g in all_grids)
    all_max_x = max(g["global_x_end"] for g in all_grids)
    all_min_y = min(g["global_y_start"] for g in all_grids)
    all_max_y = max(g["global_y_end"] for g in all_grids)

    target_cx = (all_min_x + all_max_x) / 2.0
    target_cy = (all_min_y + all_max_y) / 2.0

    def grid_center_distance_sq(g):
        gx = (g["global_x_start"] + g["global_x_end"]) / 2.0
        gy = (g["global_y_start"] + g["global_y_end"]) / 2.0
        return (gx - target_cx) ** 2 + (gy - target_cy) ** 2

    return min(all_grids, key=grid_center_distance_sq)


def pixel_x_to_lon(global_x, zoom_level):
    world_size = 256 * (2 ** zoom_level)
    return (global_x / world_size) * 360.0 - 180.0


def pixel_y_to_lat(global_y, zoom_level):
    world_size = 256 * (2 ** zoom_level)
    n = math.pi - (2.0 * math.pi * global_y) / world_size
    return math.degrees(math.atan(math.sinh(n)))


def grid_to_lonlat_bbox(grid, zoom_level, pad_pixels=0):
    x0 = grid["global_x_start"] - pad_pixels
    x1 = grid["global_x_end"] + pad_pixels
    y0 = grid["global_y_start"] - pad_pixels
    y1 = grid["global_y_end"] + pad_pixels

    west = pixel_x_to_lon(x0, zoom_level)
    east = pixel_x_to_lon(x1, zoom_level)
    north = pixel_y_to_lat(y0, zoom_level)
    south = pixel_y_to_lat(y1, zoom_level)

    xmin = min(west, east)
    xmax = max(west, east)
    ymin = min(south, north)
    ymax = max(south, north)

    return xmin, ymin, xmax, ymax


def prefilter_grids_by_building_intersection(all_grids, gdf_4326, zoom_level, pad_pixels=0):
    """
    Keep only grids that intersect building geometry.
    Works for all cities.
    """
    if gdf_4326.empty:
        return []

    if gdf_4326.crs != "EPSG:4326":
        raise ValueError("prefilter_grids_by_building_intersection requires gdf to be EPSG:4326")

    sindex = gdf_4326.sindex
    kept = []

    for grid in all_grids:
        xmin, ymin, xmax, ymax = grid_to_lonlat_bbox(grid, zoom_level, pad_pixels=pad_pixels)
        grid_box = box(xmin, ymin, xmax, ymax)

        candidate_idx = list(sindex.intersection(grid_box.bounds))
        if not candidate_idx:
            continue

        candidates = gdf_4326.iloc[candidate_idx]
        if candidates.intersects(grid_box).any():
            kept.append(grid)

    return kept


def main():
    parser = argparse.ArgumentParser(
        description="Cut physical-region tiles and generate 1024x1024 imagery with building masks"
    )
    parser.add_argument("--geojson", type=str, required=True, help="Input GeoJSON boundary file")
    parser.add_argument(
        "--source",
        type=str,
        required=True,
        choices=[
            "usa", "fra", "jpn", "nld",  "hkg",
            "deu", "syd", "mel", "afr", "bax", "van", "tor", "dam", "can","aut"
        ],
        help="Manually specify the data source"
    )
    parser.add_argument(
        "--sample_rate",
        type=float,
        default=1.0,
        help="Random sampling ratio (0.0 to 1.0)"
    )
    parser.add_argument(
        "--debug_save_rejected",
        action="store_true",
        help="Save rejected bad tiles for debugging"
    )


    parser.add_argument(
        "--debug_grid_mode",
        type=str,
        default="none",
        choices=["none", "first", "center"],
        help="Single-grid debug mode: none=normal, first=first grid only, center=center grid only"
    )
    parser.add_argument(
        "--debug_grid_id",
        type=int,
        default=None,
        help="Specify a single grid_id to run; overrides debug_grid_mode"
    )


    parser.add_argument(
        "--prefilter_grids_by_buildings",
        action="store_true",
        help="Keep only grids that intersect building geometry, reducing empty and invalid requests"
    )
    parser.add_argument(
        "--prefilter_pad_pixels",
        type=int,
        default=0,
        help="Pad the grid bbox during prefiltering to avoid dropping edge buildings"
    )

    args = parser.parse_args()

    geojson_path = args.geojson
    source_name = args.source
    sample_rate = args.sample_rate
    debug_save_rejected = args.debug_save_rejected
    debug_grid_mode = args.debug_grid_mode
    debug_grid_id = args.debug_grid_id
    prefilter_grids = args.prefilter_grids_by_buildings
    prefilter_pad_pixels = args.prefilter_pad_pixels

    item_id = os.path.splitext(os.path.basename(geojson_path))[0]
    out_img_dir = os.path.join(config.IMAGES_DIR, item_id)
    out_msk_root = os.path.join(config.MASKS_DIR, item_id)
    out_json_dir = os.path.join(config.COCO_DIR, item_id)

    os.makedirs(out_img_dir, exist_ok=True)
    os.makedirs(out_msk_root, exist_ok=True)
    os.makedirs(out_json_dir, exist_ok=True)

    out_mask_subdir = os.path.join(out_msk_root, "masks")
    out_viz_subdir = os.path.join(out_msk_root, "viz")
    os.makedirs(out_mask_subdir, exist_ok=True)
    os.makedirs(out_viz_subdir, exist_ok=True)

    checkpoint_path = os.path.join(out_json_dir, "checkpoint_gid.txt")
    log_path = os.path.join(out_json_dir, "process_log.txt")
    reject_dir = os.path.join(out_json_dir, "debug_rejected")
    if debug_save_rejected:
        os.makedirs(reject_dir, exist_ok=True)

    append_log(log_path, "[INIT] process started")

    print(f"📍 Starting task: {item_id} | source: {source_name.upper()}")

    gdf = gpd.read_file(geojson_path)
    if gdf.empty:
        raise ValueError(f"GeoJSON empty: {geojson_path}")

    if gdf.crs != "EPSG:4326":
        print(f"🔄 Detected CRS {gdf.crs}, converting to EPSG:4326 ...")
        gdf = gdf.to_crs("EPSG:4326")

    minx, miny, maxx, maxy = gdf.total_bounds
    center_lat = (miny + maxy) / 2.0

    print("🚀 Initializing source and grid system...")
    source_obj = get_source(source_name)

    if hasattr(source_obj, "zoom_level"):
        zoom_level = source_obj.zoom_level
    elif hasattr(source_obj, "get_zoom_level"):
        zoom_level = source_obj.get_zoom_level()
    else:
        raise AttributeError(f"Source object for {source_name} has no zoom_level or get_zoom_level")

    all_grids = geo_utils.generate_city_grid(
        (minx, miny, maxx, maxy),
        config.TARGET_METERS,
        zoom_level,
        center_lat
    )

    raw_grid_count = len(all_grids)


    if prefilter_grids:
        print("🧹 Prefiltering grids by building geometry...")
        all_grids = prefilter_grids_by_building_intersection(
            all_grids=all_grids,
            gdf_4326=gdf,
            zoom_level=zoom_level,
            pad_pixels=prefilter_pad_pixels
        )
        print(f"🧹 Prefilter complete: {raw_grid_count} -> {len(all_grids)} grids")


    if 0.0 < sample_rate < 1.0:
        num_to_sample = int(len(all_grids) * sample_rate)
        random.seed(42)
        grids = random.sample(all_grids, num_to_sample)
        grids.sort(key=lambda x: x["grid_id"])
        print(
            f"🎲 Random sampling mode enabled ({sample_rate * 100:.2f}%): "
            f"original {len(all_grids)} grids -> sampled {len(grids)} grids"
        )
    else:
        grids = all_grids


    if debug_grid_id is not None:
        matched = [g for g in all_grids if g["grid_id"] == debug_grid_id]
        if not matched:
            raise ValueError(f"grid_id={debug_grid_id} not found")
        grids = [matched[0]]
        print(
            f"🧪 Debug mode: only test specified grid "
            f"gid={matched[0]['grid_id']}, "
            f"x={matched[0]['global_x_start']}~{matched[0]['global_x_end']}, "
            f"y={matched[0]['global_y_start']}~{matched[0]['global_y_end']}"
        )
    elif debug_grid_mode == "first":
        grids = [all_grids[0]]
        print(
            f"🧪 Debug mode: only test the first grid "
            f"gid={all_grids[0]['grid_id']}, "
            f"x={all_grids[0]['global_x_start']}~{all_grids[0]['global_x_end']}, "
            f"y={all_grids[0]['global_y_start']}~{all_grids[0]['global_y_end']}"
        )
    elif debug_grid_mode == "center":
        center_grid = select_center_grid(all_grids)
        grids = [center_grid]
        print(
            f"🧪 Debug mode: only test the center grid "
            f"gid={center_grid['grid_id']}, "
            f"x={center_grid['global_x_start']}~{center_grid['global_x_end']}, "
            f"y={center_grid['global_y_start']}~{center_grid['global_y_end']}"
        )

    total_grids = len(grids)
    print(f"🗺️ This run will process {total_grids} training grids.")

    start_gid = 0
    if os.path.exists(checkpoint_path) and debug_grid_id is None and debug_grid_mode == "none":
        with open(checkpoint_path, "r", encoding="utf-8") as f:
            try:
                start_gid = int(f.read().strip())
                print(f"🔄 Found checkpoint, resuming from GID {start_gid}...")
            except Exception:
                start_gid = 0

    try:
        from tqdm import tqdm
        grid_iter = tqdm(grids, desc=f"📦 {item_id}", unit="grid")
    except ImportError:
        grid_iter = grids

    for grid in grid_iter:
        gid = grid["grid_id"]

        if gid < start_gid:
            continue

        img_path = os.path.join(out_img_dir, f"grid_{gid:05d}_z{zoom_level}.jpg")
        msk_path = os.path.join(out_mask_subdir, f"grid_{gid:05d}_z{zoom_level}.tiff")
        vis_path = os.path.join(out_viz_subdir, f"grid_{gid:05d}_z{zoom_level}_vis.png")
        json_path = os.path.join(out_json_dir, f"grid_{gid:05d}_z{zoom_level}.json")

        if os.path.exists(img_path) and os.path.exists(msk_path) and os.path.exists(json_path):
            continue

        try:
            grid_img = source_obj.fetch_image_for_grid(grid)
            if grid_img is None:
                safe_set_postfix(grid_iter, status="rejected: download failed")
                append_log(log_path, f"[{gid}] rejected: image fetch failed (fetch_image_for_grid returned None)")
                continue

            final_img = grid_img.resize(
                (config.OUTPUT_IMAGE_SIZE, config.OUTPUT_IMAGE_SIZE),
                Image.Resampling.LANCZOS
            )

            stats = get_valid_image_stats(final_img)

            if stats["has_alpha"]:
                append_log(
                    log_path,
                    f"[{gid}] alpha_valid={stats['valid_count']}/{stats['total_count']}"
                )

            if stats["is_fully_transparent"]:
                safe_set_postfix(grid_iter, status="rejected: fully transparent")
                append_log(log_path, f"[{gid}] rejected: export returned fully transparent image | grid={grid}")

                if debug_save_rejected:
                    reject_path = os.path.join(reject_dir, f"grid_{gid:05d}_transparent.jpg")
                    save_debug_image(final_img, reject_path)
                    append_log(log_path, f"[{gid}] saved transparent debug image: {reject_path}")

                continue

            append_log(
                log_path,
                f"[{gid}] stats: mean={stats['mean']:.2f}, min={stats['min']}, "
                f"max={stats['max']}, std={stats['std']:.2f}"
            )

            if is_probably_white(stats):
                safe_set_postfix(grid_iter, status="rejected: blank white image")
                append_log(log_path, f"[{gid}] rejected: server returned blank white image | grid={grid}")

                if debug_save_rejected:
                    reject_path = os.path.join(reject_dir, f"grid_{gid:05d}_white.jpg")
                    save_debug_image(final_img, reject_path)
                    append_log(log_path, f"[{gid}] saved white debug image: {reject_path}")

                continue

            if is_probably_black(stats):
                safe_set_postfix(grid_iter, status="rejected: blank black image")
                append_log(log_path, f"[{gid}] rejected: server returned blank black image | grid={grid}")

                if debug_save_rejected:
                    reject_path = os.path.join(reject_dir, f"grid_{gid:05d}_black.jpg")
                    save_debug_image(final_img, reject_path)
                    append_log(log_path, f"[{gid}] saved black debug image: {reject_path}")

                continue

            final_img_to_save = final_img.convert("RGB") if final_img.mode != "RGB" else final_img
            final_img_to_save.save(img_path, quality=95)

            generate_labels_for_grid(
                grid=grid,
                gdf=gdf,
                zoom_level=zoom_level,
                output_image_size=config.OUTPUT_IMAGE_SIZE,
                img_path=img_path,
                msk_path=msk_path,
                vis_path=vis_path,
                json_path=json_path,
                gid=gid
            )

            if os.path.exists(msk_path):
                with Image.open(msk_path) as temp_msk:
                    msk_array = np.array(temp_msk)

                if np.max(msk_array) == 0 and np.min(msk_array) == 0:
                    for p in [img_path, msk_path, vis_path, json_path]:
                        if os.path.exists(p):
                            os.remove(p)

                    safe_set_postfix(grid_iter, status="cleaned: no buildings")
                    append_log(log_path, f"[{gid}] cleaned: no buildings in this area, removed image/mask/json")
                    continue

            if debug_grid_id is None and debug_grid_mode == "none":
                with open(checkpoint_path, "w", encoding="utf-8") as f:
                    f.write(str(gid + 1))

            safe_set_postfix(grid_iter, status="saved successfully")
            append_log(log_path, f"[{gid}] saved successfully")

        except Exception as e:
            safe_set_postfix(grid_iter, status="❌ skipped due to error")
            append_log(log_path, f"[{gid}] ❌ error skipped: {repr(e)}")
            continue

    print(f"\n✨ {item_id} task complete!")


if __name__ == "__main__":
    main()
