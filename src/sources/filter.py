import geopandas as gpd
import os
import pandas as pd

def filter_and_sample_dataset(input_path, output_path):
    print(f"⏳ Loading large dataset (about 1-2 minutes): {os.path.basename(input_path)}...")
    gdf = gpd.read_file(input_path)
    initial_count = len(gdf)
    print(f"   ▶ Initial feature count: {initial_count}")


    print("\n🧹 1. Starting attribute filtering (drop invalid heights and noise)...")


    height_candidates = ['height', 'HEIGHT', 'height_roof', 'ALTURA', 'ele_height', 'Height', 'hauteur']
    height_col = next((col for col in height_candidates if col in gdf.columns), None)

    if height_col:
        print(f"   🔎 Found height field: '{height_col}'")
        if height_col != 'height':
            gdf['height'] = gdf[height_col]


        gdf['height'] = pd.to_numeric(gdf['height'], errors='coerce')

        invalid_mask = gdf['height'].isna()
        if invalid_mask.any():
            print(f"   Dropped {invalid_mask.sum()} buildings with invalid height values")
            gdf = gdf[~invalid_mask]
    else:
        available_cols = list(gdf.columns)
        print(f"   No recognized height field found. Available columns: {available_cols}")
        raise KeyError("No valid height-related fields found in the dataset. Please check column names.")

    mask_height = (gdf['height'] >= 1.0) & (gdf['height'] <= 800.0)
    gdf = gdf[mask_height]
    print(f"   ▶ Height valid (>1m and <800m) remaining: {len(gdf)}")


    print("\n📏 2. Starting area filtering...")

    gdf_proj = gdf.to_crs(epsg=6933)
    gdf['area_sqm'] = gdf_proj.geometry.area

    mask_area = (gdf['area_sqm'] >= 5.0)
    gdf = gdf[mask_area]
    gdf = gdf.drop(columns=['area_sqm'])
    print(f"   ▶ Area valid (>=5 sqm) remaining: {len(gdf)}")


    print("\n📦 3. No downsampling; keep all cleaned buildings...")
    print(f"   ▶ Post-clean count: {len(gdf)}")


    print(f"\n💾 Saving cleaned dataset to: {output_path}...")
    gdf = gdf[gdf.geometry.is_valid & ~gdf.geometry.is_empty]


    columns_to_drop = ['OBJECTID', 'Shape.STArea()', 'Shape.STLength()']
    gdf = gdf.drop(columns=[col for col in columns_to_drop if col in gdf.columns])


    gdf.crs = None


    gdf.to_file(output_path, driver='GeoJSON')
    print(f"Filtering complete! Final saved count: {len(gdf)}")

if __name__ == "__main__":
    input_file = "/data2/hgq/BuildingHeight_Dataset/data/raw/austria/vienna_lod14/vienna_lod14_buildings.geojson"
    output_file = "/data2/hgq/BuildingHeight_Dataset/data/raw/vienna_lod14_buildings.geojson"


    if os.path.exists(input_file):
        filter_and_sample_dataset(input_file, output_file)
    else:
        print(f"❌ Input file not found: {input_file}")
