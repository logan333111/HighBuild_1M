import os
import sys
import geopandas as gpd

# 自动搞定烦人的路径问题
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sources import get_source
from dataset_engine import generate_labels_for_grid
import geo_utils
import config

print("⏳ 正在读取 55 万栋大阪建筑...")
gdf = gpd.read_file("data/raw/Japan_Osaka_buildings_full.geojson")

# 找到大阪的正中心
minx, miny, maxx, maxy = gdf.total_bounds
center_lon = (minx + maxx) / 2.0
center_lat = (miny + maxy) / 2.0
print(f"🎯 锁定大阪市中心坐标: {center_lon}, {center_lat}")

source_obj = get_source('jpn')
zoom_level = source_obj.zoom_level

# 🛠️ 修复点：划定市中心一小块区域，让官方的 geo_utils 去算瓦片坐标
test_bounds = (center_lon, center_lat, center_lon + 0.002, center_lat + 0.002)
grids = geo_utils.generate_city_grid(test_bounds, config.TARGET_METERS, zoom_level, center_lat)

# 拿出第一个合法的网格
grid = grids[0]
grid['grid_id'] = 99999  # 改个特殊 ID 防冲突

print("🖼️ 正在下载市中心影像...")
grid_img = source_obj.fetch_image_for_grid(grid)

# 确保存放测试图的文件夹存在
os.makedirs("data/processed/masks/Japan_Osaka_buildings_full/viz", exist_ok=True)
os.makedirs("data/processed/masks/Japan_Osaka_buildings_full/masks", exist_ok=True)

img_path = "data/processed/masks/Japan_Osaka_buildings_full/viz/test_center_img.jpg"
vis_path = "data/processed/masks/Japan_Osaka_buildings_full/viz/test_center_mask.png"
msk_path = "data/processed/masks/Japan_Osaka_buildings_full/masks/test_center.tiff"

if not grid_img:
    print("❌ 影像下载失败！")
else:
    grid_img = grid_img.resize((1024, 1024))
    grid_img.save(img_path)
    print("🎨 正在生成掩码...")
    generate_labels_for_grid(grid, gdf, zoom_level, 1024, img_path, msk_path, vis_path, "test_center.json", 99999)
    print(f"🎉 抽查完毕！快去 data/processed/masks/Japan_Osaka_buildings_full/viz/ 里面看 test_center_mask.png！")