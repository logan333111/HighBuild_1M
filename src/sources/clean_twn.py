import geopandas as gpd
from shapely import force_2d
import os

print("⏳ 正在读取 126 万栋台湾(台中)建筑的庞大数据，请耐心等待...")
# 替换成你真实的相对路径
gdf = gpd.read_file('data/raw/01-SHP/114期末_B0001_1216n.shp')

print(f"📦 初始建筑数量: {len(gdf)} 栋")

# 1. 破译密码：将 B1C (楼层数) 转换为数字，缺失值默认算作 1 层
gdf['B1C'] = gdf['B1C'].fillna(1).astype(float)
gdf = gdf[gdf['B1C'] > 0] # 剔除无效楼层

# 2. 核心转换：按照每层 3 米估算物理高度
gdf['height'] = gdf['B1C'] * 3.0

# 3. 维度降级：去除庞大的 Z 轴海拔，将 3D 多边形“拍扁”成 2D 地基轮廓
print("🔨 正在进行几何降维 (POLYGON Z -> POLYGON)...")
gdf['geometry'] = force_2d(gdf.geometry)

# 4. 空间重投影：将 TWD97 (EPSG:3826) 转换为国际经纬度 WGS84 (EPSG:4326)
print("🌍 正在将坐标系重投影为国际标准 WGS84 (对齐卫星图)...")
# 如果原本没有指定 crs，先强制指定为台湾标准 TWD97
if gdf.crs is None:
    gdf.set_crs(epsg=3826, inplace=True)
gdf = gdf.to_crs(epsg=4326)

# 5. 极致瘦身：只保留几何形状和高度
gdf = gdf[['geometry', 'height']]

# 保存
os.makedirs('data/raw', exist_ok=True)
output_path = 'data/raw/TWN_Buildings_ready.geojson'

print("💾 正在保存为最终版 GeoJSON (文件较大，请稍候)...")
gdf.to_file(output_path, driver='GeoJSON')

print(f"🎉 台湾板块提炼完成！最终获得 {len(gdf)} 栋纯净建筑。")
print(f"📍 文件已保存至: {output_path}")