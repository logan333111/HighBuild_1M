import cv2
import json
import os
import sys

def inspect(tile_name):
    """
    Data sanity checker for mask TIFF and COCO JSON files.
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    tiff_path = os.path.join(base_dir, 'data', 'processed', 'masks', f'{tile_name}.tiff')
    json_path = os.path.join(base_dir, 'data', 'processed', 'coco_json', f'{tile_name}.json')

    print(f"================ Inspect tile: {tile_name} ================")


    if not os.path.exists(tiff_path):
        print(f"❌ TIFF file not found: {tiff_path}")
    else:

        mask = cv2.imread(tiff_path, cv2.IMREAD_UNCHANGED)
        print(f"✅ TIFF shape: {mask.shape}, dtype: {mask.dtype}")

        nonzero_pixels = mask[mask > 0]
        if len(nonzero_pixels) == 0:
            print("ℹ️ No building pixels found in TIFF (all zeros).")
        else:
            print(f"📍 Found {len(nonzero_pixels)} building pixels.")
            print(f"📏 First 10 non-zero pixel heights (m): {nonzero_pixels[:10].tolist()}")

    print("\n---------------------------------------------------------")


    if not os.path.exists(json_path):
        print(f"❌ JSON file not found: {json_path}")
    else:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        print(f"✅ JSON contains {len(data['annotations'])} building annotations.")
        if len(data['annotations']) > 0:
            print("📝 First annotation sample (COCO instance format):")
            sample = data['annotations'][0]
            sample_coords = sample['segmentation'][0]
            sample['segmentation'] = [sample_coords[:8] + ["... truncated for display"]]
            print(json.dumps(sample, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: conda run -n bh_env python src/inspect_data.py <tile_name>")
        print("Example: conda run -n bh_env python src/inspect_data.py hznu/masks/grid_00000_z18")
    else:
        inspect(sys.argv[1])
