import overturemaps
import pandas as pd
import geopandas as gpd
from shapely import wkb
import os

target_cities = {
    "France_Paris": (2.250, 48.810, 2.420, 48.900),
    "France_Toulouse": (1.420, 43.580, 1.460, 43.620)
}

print("🚀 启动【全量捕获 + 忽略掩码(-1.0)】机制...")

for city_name, bbox in target_cities.items():
    print(f"\n📍 正在处理: {city_name}")
    try:
        table = overturemaps.record_batch_reader("building", bbox).read_all()
        df = table.to_pandas()
        
        buildings_gdf = gpd.GeoDataFrame(
            df, geometry=df['geometry'].apply(wkb.loads), crs="EPSG:4326"
        )
        
        # 1. 字段对齐
        if 'height' not in buildings_gdf.columns: buildings_gdf['height'] = pd.NA
        if 'num_floors' not in buildings_gdf.columns: buildings_gdf['num_floors'] = pd.NA
        
        buildings_gdf['height'] = pd.to_numeric(buildings_gdf['height'], errors='coerce')
        buildings_gdf['num_floors'] = pd.to_numeric(buildings_gdf['num_floors'], errors='coerce')

        # 2. 楼层折算 3 米
        buildings_gdf['height'] = buildings_gdf['height'].fillna(buildings_gdf['num_floors'] * 3.0)

        # 🚨 【核心修改点】🚨
        # 以前我们是：直接删掉没有 height 的数据 (导致掩码图缺失大片建筑)
        # 现在我们是：保留它们！把没有高度的建筑强行赋值为 -1.0
        buildings_gdf['height'] = buildings_gdf['height'].fillna(-1.0)
        
        # 此时的 buildings_gdf 包含了卫星图上可见的 *所有* 建筑！
        
        # 统计真值与忽略掩码的数量
        valid_height_count = len(buildings_gdf[buildings_gdf['height'] > 0])
        ignore_height_count = len(buildings_gdf[buildings_gdf['height'] == -1.0])
        print(f"   🏢 捕获全量建筑: {len(buildings_gdf)} 栋")
        print(f"      - 具备有效高度 (>0): {valid_height_count} 栋")
        print(f"      - 仅有轮廓 (标为 -1.0): {ignore_height_count} 栋")

        output_file = f"{city_name}_buildings_full.geojson"
        buildings_gdf.to_file(output_file, driver="GeoJSON")
        print(f"   ✅ 已保存全量无损标签: {output_file}")

    except Exception as e:
        print(f"   ❌ 处理错误: {e}")