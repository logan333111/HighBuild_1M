import os
import json

def stat_cleaned_buildings(file_path):
    print(f"[INFO] Analyzing cleaned data: {os.path.basename(file_path)}")

    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    features = data.get('features', [])
    total_buildings = len(features)

    if total_buildings == 0:
        print("   ⚠️ [WARN] This file has no building data.\n")
        return

    true_height_count = 0
    estimated_count = 0
    missing_count = 0

    for feature in features:
        props = feature.get('properties', {})


        height = props.get('height', -1)


        if height is None:
            height = -1


        is_estimated = props.get('is_estimated_height', False)


        if height > 0 and not is_estimated:

            true_height_count += 1
        elif height > 0 and is_estimated:

            estimated_count += 1
        else:

            missing_count += 1

    print(f"   Total buildings: {total_buildings}")
    if total_buildings > 0:
        print(f"   True heights: {true_height_count} buildings ({true_height_count/total_buildings*100:.1f}%)")
        print(f"   Floor-based estimates: {estimated_count} buildings ({estimated_count/total_buildings*100:.1f}%)")
        print(f"   Missing data (-1): {missing_count} buildings ({missing_count/total_buildings*100:.1f}%)\n")

if __name__ == "__main__":

    target_file = "/data2/hgq/BuildingHeight_Dataset/data/raw/Africa_CapeTown_buildings_Filtered.geojson"

    if os.path.exists(target_file):
        stat_cleaned_buildings(target_file)
    else:
        print(f"[ERROR] File not found: {target_file}. Check that the path is correct.")