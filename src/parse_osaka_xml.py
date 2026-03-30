import os
import glob
import pandas as pd
import geopandas as gpd
from shapely.geometry import Polygon
import xml.etree.ElementTree as ET
from tqdm import tqdm

def parse_plateau_v3_gml():
    gml_dir = "data/raw/osaka_citygml/udx/bldg/"
    output_file = "data/raw/Japan_Osaka_buildings_full.geojson"

    ns = {
        'core': 'http://www.opengis.net/citygml/2.0',
        'bldg': 'http://www.opengis.net/citygml/building/2.0',
        'gml': 'http://www.opengis.net/gml'
    }

    gml_files = glob.glob(os.path.join(gml_dir, "*.gml"))
    print(f"🚀 开始解析 {len(gml_files)} 个分块...")
    all_buildings = []

    for file_path in tqdm(gml_files, desc="提取几何体"):
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()

            for bldg in root.findall('.//bldg:Building', ns):
                # 1. 获取高度
                height = 0.0
                h_node = bldg.find('.//bldg:measuredHeight', ns)
                if h_node is not None and h_node.text:
                    height = float(h_node.text)
                else:
                    continue

                # 2. 核心魔法：找出所有坐标串，取投影面积最大的（绝对是屋顶或底座）
                max_area = 0
                best_poly = None
                
                pos_list_nodes = bldg.findall('.//gml:posList', ns)
                for pos_node in pos_list_nodes:
                    if not pos_node.text: continue
                    coords = [float(x) for x in pos_node.text.split()]
                    points = []
                    
                    # (Lat, Lon, Alt) 转换为 Shapely 用的 (Lon, Lat)
                    for i in range(0, len(coords), 3):
                        if i + 1 >= len(coords): break
                        lat, lon = coords[i], coords[i+1]
                        points.append((lon, lat))
                    
                    if len(points) < 3: continue
                    
                    try:
                        poly = Polygon(points)
                        if not poly.is_valid: poly = poly.buffer(0)
                        
                        # 保留面积最大的面
                        if poly.area > max_area:
                            max_area = poly.area
                            best_poly = poly
                    except:
                        continue

                # 只要最大面积大于 1e-9 (过滤垂直墙壁的噪点)，就保留
                if best_poly and max_area > 1e-9:
                    all_buildings.append({'height': height, 'geometry': best_poly})
        except Exception as e:
            pass

    print("🔄 正在打包 GeoJSON...")
    gdf = gpd.GeoDataFrame(all_buildings, crs="EPSG:4326")
    gdf = gdf[gdf['height'] > 0]
    
    # 强制覆盖旧文件
    if os.path.exists(output_file):
        os.remove(output_file)
        
    gdf.to_file(output_file, driver='GeoJSON')
    print(f"🎉 成功！总计提取 {len(gdf)} 栋带面积的建筑！")

if __name__ == "__main__":
    parse_plateau_v3_gml()