import geopandas as gpd

print("⏳ 正在读取全港建筑数据...")
gdf = gpd.read_file("data/raw/HKG_Buildings_ready.geojson")

# 锁定维多利亚港两岸极高密度区（中环、湾仔、尖沙咀、旺角）的经纬度边界
minx, miny, maxx, maxy = 114.130, 22.260, 114.220, 22.320

print("🔪 正在裁剪核心都会区...")
# cx 是 GeoPandas 极其强大的空间切片工具
core_gdf = gdf.cx[minx:maxx, miny:maxy]

output_path = "data/raw/HKG_Core.geojson"
core_gdf.to_file(output_path, driver="GeoJSON")

print(f"🎉 裁剪完成！从 23万栋 中精炼出 {len(core_gdf)} 栋核心区摩天大楼。")
print(f"📍 核心区文件已保存至: {output_path}")