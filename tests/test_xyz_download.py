import os
import requests
import mercantile
import numpy as np
import rasterio
from rasterio.transform import from_bounds
import geopandas as gpd
from io import BytesIO
from PIL import Image

def download_xyz_satellite_imagery(geojson_path, output_image_path, zoom_level=18):
    """
    根据 GeoJSON 提取边界框，计算并下载覆盖范围的 Google Satellite XYZ 图像切片，
    拼接并加入标准地理坐标系信息 (EPSG:3857)，然后裁剪到极高精度。
    """
    print(f"🌍 正在解析目标文件: {geojson_path}")
    
    # 读取 GeoJSON 获取边界框
    try:
        gdf = gpd.read_file(geojson_path)
        if gdf.crs != "EPSG:4326":
            gdf = gdf.to_crs("EPSG:4326")
        
        # 提取目标边界框 [minx, miny, maxx, maxy]
        minx, miny, maxx, maxy = gdf.total_bounds
        print(f"🎯 提取目标经纬度范围: 经度 {minx:.4f}~{maxx:.4f}, 纬度 {miny:.4f}~{maxy:.4f}")
    except Exception as e:
        print(f"解析 GeoJSON 失败: {e}")
        return

    # 1. 计算覆盖此边界框的所有地图切片
    # z=18 时，赤道处物理分辨率大约为 0.59 米/像素；z=19 为 0.3米
    tiles = list(mercantile.tiles(minx, miny, maxx, maxy, zoom_level))
    if not tiles:
        print("未获取到瓦片。")
        return

    # 行列范围
    min_tx = min([t.x for t in tiles])
    max_tx = max([t.x for t in tiles])
    min_ty = min([t.y for t in tiles])
    max_ty = max([t.y for t in tiles])

    tile_width = 256
    tile_height = 256
    
    # 构造拼接的大图
    total_width = (max_tx - min_tx + 1) * tile_width
    total_height = (max_ty - min_ty + 1) * tile_height
    stitched_image = Image.new('RGB', (total_width, total_height))

    # Google Satellite 瓦片服务 (lyrs=s 纯卫星图, 无标签)
    # 或者可以使用 Esri 天地图: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
    tile_url_template = "https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

    print(f"⏳ 正在下载 {len(tiles)} 张高分辨率正射影像切片 (Zoom={zoom_level})...")
    
    # 2. 单独下载各个切片并拼接
    for tile in tiles:
        url = tile_url_template.format(x=tile.x, y=tile.y, z=tile.z)
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                tile_img = Image.open(BytesIO(response.content)).convert("RGB")
                paste_x = (tile.x - min_tx) * tile_width
                paste_y = (tile.y - min_ty) * tile_height
                stitched_image.paste(tile_img, (paste_x, paste_y))
            else:
                print(f"警告：瓦片 {tile.x},{tile.y} 下载失败，状态码: {response.status_code}")
        except Exception as e:
            print(f"警告：瓦片 {url} 下载出错 -> {e}")

    # 3. 为图像赋予准确的地理空间坐标 (Georeferencing)
    # 计算最左上和最右下瓦片的 Web Mercator (EPSG:3857) 坐标边界
    top_left_tile = mercantile.Tile(min_tx, min_ty, zoom_level)
    bottom_right_tile = mercantile.Tile(max_tx, max_ty, zoom_level)

    tl_bounds = mercantile.xy_bounds(top_left_tile)
    br_bounds = mercantile.xy_bounds(bottom_right_tile)

    full_min_x = tl_bounds.left
    full_max_x = br_bounds.right
    full_min_y = br_bounds.bottom # Y 轴向上，所以 bottom 较小
    full_max_y = tl_bounds.top

    # 生成 Rasterio 识别的变换矩阵
    transform = from_bounds(full_min_x, full_min_y, full_max_x, full_max_y, total_width, total_height)

    # 4. 保存具有坐标系的高精度底图
    os.makedirs(os.path.dirname(output_image_path), exist_ok=True)
    
    img_array = np.array(stitched_image)
    # 转置成 rasterio 期望的格式 (Bands, Height, Width)
    img_array = img_array.transpose((2, 0, 1))

    # 使用临时文件保存大的拼接好的 TIFF
    temp_tiff = output_image_path.replace('.tif', '_raw.tif')
    with rasterio.open(
        temp_tiff, 'w',
        driver='GTiff',
        height=total_height, width=total_width,
        count=3, dtype=img_array.dtype,
        crs="EPSG:3857", transform=transform
    ) as dest:
        dest.write(img_array)

    # 5. 完全精准地裁切到 GeoJSON 边界。
    # 把原本 4326 经纬度的 GeoJSON 转为 3857 Web Mercator 以便和图像坐标系匹配裁切
    print("✂️ 正在根据多边形精确提取感兴趣区域...")
    gdf_3857 = gdf.to_crs("EPSG:3857")
    
    try:
        import rioxarray
        from shapely.geometry import box
        
        with rioxarray.open_rasterio(temp_tiff) as raster:
            # 使用包含所有建筑群的边界框进行裁剪
            clip_bbox = gdf_3857.total_bounds
            clipped_raster = raster.rio.clip_box(
                minx=clip_bbox[0], miny=clip_bbox[1], maxx=clip_bbox[2], maxy=clip_bbox[3]
            )
            clipped_raster.rio.to_raster(output_image_path)
            
        print(f"✅ 成功! 获取了 1米以内物理分辨率影像，保存至: {output_image_path}")
        # 清理临时拼接文件
        os.remove(temp_tiff)
        
    except Exception as e:
        print(f"⚠️ 裁剪过程中发生异常，保留了原拼接图像: {e}")

if __name__ == "__main__":
    # 使用 hznu.geojson 来验证效果
    geojson_file = "./data/raw/hznu.geojson"
    out_file = "./satellite_dataset/hznu_1m_resolution.tif"
    
    # 变焦级别 18 对应地球赤道处约 0.6米/像素
    download_xyz_satellite_imagery(geojson_file, out_file, zoom_level=18)
