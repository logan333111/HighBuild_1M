import os
import cv2
import json
import math
import numpy as np
import matplotlib.pyplot as plt
from PIL import Image

def generate_labels_for_grid(grid, gdf, zoom_level, output_image_size, img_path, msk_path, vis_path, json_path, gid):
    from geo_utils import lnglat_to_global_pixel
    from shapely.ops import transform
    from shapely.geometry import Polygon


    coco_format = {
        "images": [
            {
                "id": gid,
                "file_name": os.path.basename(img_path),
                "width": output_image_size,
                "height": output_image_size
            }
        ],
        "annotations": [],
        "categories": [
            {"id": 1, "name": "building"}
        ]
    }

    annotation_id = 1

    mask_arr = np.zeros((output_image_size, output_image_size), dtype=np.float32)


    def pixel2deg(px, py, zoom):
        n = 256.0 * (2 ** zoom)
        lon = (px / n) * 360.0 - 180.0
        lat_rad = math.atan(math.sinh(math.pi * (1 - 2 * py / n)))
        lat = math.degrees(lat_rad)
        return lon, lat


    min_lng, max_lat = pixel2deg(grid['global_x_start'], grid['global_y_start'], zoom_level)
    max_lng, min_lat = pixel2deg(grid['global_x_end'], grid['global_y_end'], zoom_level)


    local_gdf = gdf.cx[min_lng:max_lng, min_lat:max_lat]


    for _, row in local_gdf.iterrows():
        geom = row.geometry
        if geom.is_empty:
            continue


        try:
            build_height = float(row.get('height', 1.0))
            if np.isnan(build_height):
                build_height = 1.0
        except:
            build_height = 1.0


        def transform_to_grid_pixels(lng, lat, z=None):
            gx, gy = lnglat_to_global_pixel(lng, lat, zoom_level)
            px = gx - grid['global_x_start']
            py = gy - grid['global_y_start']

            scale = output_image_size / grid['pixel_size']
            return px * scale, py * scale


        transformed_geom = transform(transform_to_grid_pixels, geom)


        box = transformed_geom.bounds
        if box[0] < output_image_size and box[2] > 0 and box[1] < output_image_size and box[3] > 0:

            if transformed_geom.geom_type == 'Polygon':
                polys = [transformed_geom]
            elif transformed_geom.geom_type == 'MultiPolygon':
                polys = list(transformed_geom.geoms)
            else:
                polys = []


            for poly in polys:

                exterior_pts = np.array(poly.exterior.coords, np.int32).reshape((-1, 1, 2))

                cv2.fillPoly(mask_arr, [exterior_pts], float(build_height))


                for interior in poly.interiors:
                    interior_pts = np.array(interior.coords, np.int32).reshape((-1, 1, 2))
                    cv2.fillPoly(mask_arr, [interior_pts], 0.0)


            if transformed_geom.geom_type == 'MultiPolygon':
                geom_parts = list(transformed_geom.geoms)
                poly = max(geom_parts, key=lambda a: a.area)
            else:
                poly = transformed_geom


            xmin, ymin, xmax, ymax = poly.bounds
            w = xmax - xmin
            h = ymax - ymin


            exterior_coords = list(poly.exterior.coords)
            seg_flat = []
            for pt in exterior_coords[:-1]:
                seg_flat.extend([pt[0], pt[1]])


            coco_format["annotations"].append({
                "id": annotation_id,
                "image_id": gid,
                "category_id": 1,
                "segmentation": [seg_flat],
                "area": poly.area,
                "bbox": [xmin, ymin, w, h],
                "iscrowd": 0,
                "attributes": {
                    "height": build_height,

                    "is_estimated_height": bool(row.get('is_estimated_height', False))
                }
            })
            annotation_id += 1


    cv2.imwrite(msk_path, mask_arr)


    max_h = np.max(mask_arr) if np.max(mask_arr) > 0 else 0.0
    color_mask = np.zeros((output_image_size, output_image_size, 4), dtype=np.float32)
    color_mask[:, :] = [0, 0, 0, 1]

    if max_h > 0:
        valid_mask = mask_arr > 0
        norm_vals = np.power(mask_arr[valid_mask] / max_h, 0.4)
        cmap = plt.get_cmap('gray')
        color_mask[valid_mask] = cmap(norm_vals)


    unknown_mask = mask_arr < 0.0
    color_mask[unknown_mask] = [1.0, 0.2, 0.2, 1.0]

    vis_img = Image.fromarray((color_mask[:, :, :3] * 255).astype(np.uint8))
    vis_img.save(vis_path)


    with open(json_path, 'w', encoding='utf-8') as jf:
        json.dump(coco_format, jf, indent=2, ensure_ascii=False)