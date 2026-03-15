import geopandas as gpd
from pystac_client import Client
import rioxarray
from shapely.geometry import box
import os

def process_geojson_to_satellite_chip(geojson_path, output_image_path):
    """
    读取包含建筑物高度和位置的 GeoJSON 文件，
    自动寻找并截取对应区域的高清卫星图。
    """
    print(f"正在解析文件: {geojson_path}")
    
    # 1. 读取 GeoJSON 并获取边界框 (Bounding Box)
    try:
        # GeoPandas 可以极其方便地读取 GeoJSON 并处理坐标系
        gdf = gpd.read_file(geojson_path)
        
        # 确保坐标系是标准的经纬度 WGS84 (EPSG:4326)
        if gdf.crs != "EPSG:4326":
            gdf = gdf.to_crs("EPSG:4326")
            
        # 获取总边界框 [minx, miny, maxx, maxy]
        bounds = gdf.total_bounds
        roi_bbox = list(bounds)
        print(f"提取到目标区域边界: {roi_bbox}")
        
    except Exception as e:
        print(f"解析 GeoJSON 失败: {e}")
        return

    # 2. 连接到开源的 STAC 目录 (这里以 Earth Search 为例)
    # Earth Search 是 AWS 维护的开源目录，包含丰富的公开数据集
    stac_api_url = "https://earth-search.aws.element84.com/v1"
    try:
        catalog = Client.open(stac_api_url)
    except Exception as e:
        print(f"连接 STAC 目录失败: {e}")
        return

    # 3. 搜索该区域的卫星影像
    print("正在全球开源卫星数据库中检索该区域...")
    try:
        search = catalog.search(
            bbox=roi_bbox,
            # 指定搜寻 Sentinel-2 L2A 数据
            collections=["sentinel-2-l2a"], 
            # 限制云量小于 10%
            query={"eo:cloud_cover": {"lt": 10}}, 
            max_items=5
        )
        items = list(search.items())
    except Exception as e:
        print(f"搜索失败: {e}")
        return

    if not items:
        print("未找到符合条件的免费开源影像。")
        return
        
    # 取第一张影像
    best_item = items[0]
    print(f"找到匹配影像，拍摄日期: {best_item.datetime}")

    # 4. 获取影像的云端直链 (COG URL)
    # Earth Search v1 中的 Sentinel-2 visual 波段
    if 'visual' in best_item.assets:
        asset_url = best_item.assets['visual'].href
    else:
        print(f"该影像不包含直接的可视化真彩色波段。可用 assets 列表: {list(best_item.assets.keys())}")
        return

    # 5. 云端动态裁切并下载
    print(f"正在从云端实时裁切并下载该建筑群的影像 (URL: {asset_url})...")
    try:
        # rioxarray 可以直接读取云端 URL
        with rioxarray.open_rasterio(asset_url) as raster:
            # 按照 GeoJSON 的边界框进行裁切
            clipped_raster = raster.rio.clip_box(
                minx=roi_bbox[0], 
                miny=roi_bbox[1], 
                maxx=roi_bbox[2], 
                maxy=roi_bbox[3],
                crs="EPSG:4326"
            )
            
            # 将裁切好的“截图”保存为高精度 TIFF 格式
            os.makedirs(os.path.dirname(output_image_path), exist_ok=True)
            clipped_raster.rio.to_raster(output_image_path)
            print(f"✅ 成功截取并保存至: {output_image_path}")
            
    except Exception as e:
        print(f"裁切下载过程中出错: {e}")

if __name__ == "__main__":
    # 使用项目中的真实 GeoJSON 文件做测试
    sample_geojson = "./data/raw/hznu.geojson"
    output_tiff = "./satellite_dataset/hznu_stac_crop.tif"
    
    if os.path.exists(sample_geojson):
        process_geojson_to_satellite_chip(sample_geojson, output_tiff)
    else:
        print(f"错误：请检查 geojson 文件路径 ({sample_geojson}) 是否正确。")
