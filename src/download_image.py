import os
import argparse
import requests
import numpy as np
import cv2
import rasterio
from rasterio.transform import from_bounds
import geopandas as gpd
from io import BytesIO
import json
from PIL import Image
import warnings
from rasterio.errors import NotGeoreferencedWarning

warnings.filterwarnings('ignore', category=NotGeoreferencedWarning)

def get_bbox_fast(geojson_path):
    """快速流式解析 GeoJSON 的 bbox，避免用 GeoPandas 导致大文件 OOM"""
    with open(geojson_path, 'r', encoding='utf-8') as f:
         data = json.load(f)
    all_coords = []
    def flatten(item):
        if isinstance(item, (list, tuple)):
            if len(item) == 2 and isinstance(item[0], (int, float)):
                all_coords.append(item)
            else:
                for sub in item: flatten(sub)
    for feature in data.get('features', []):
        geom = feature.get('geometry', {})
        if not geom: continue
        flatten(geom.get('coordinates', []))
    if not all_coords:
        raise ValueError("GeoJSON 中未找到有效坐标")
    coords_arr = np.array(all_coords)
    minx, miny = coords_arr.min(axis=0)
    maxx, maxy = coords_arr.max(axis=0)
    return [minx, miny, maxx, maxy]

def get_image_for_grid(grid, tiles, zoom_level, url_template, headers, source):
    """提取与单个网格对应的图像切片并拼接"""
    from concurrent.futures import ThreadPoolExecutor
    # 根据网格的全局像素坐标，反算它涉及哪些瓦片
    min_tx = grid['global_x_start'] // 256
    max_tx = grid['global_x_end'] // 256
    min_ty = grid['global_y_start'] // 256
    max_ty = grid['global_y_end'] // 256
    
    # 构建当前网格的画布
    pixel_size = grid['pixel_size']
    stitched_image = Image.new('RGB', (pixel_size, pixel_size))
    
    def fetch_tile(tx, ty):
        url = url_template.format(x=tx, y=ty, z=zoom_level)
        try:
            response = requests.get(url, headers=headers, timeout=5)
            if response.status_code == 200:
                return (tx, ty, Image.open(BytesIO(response.content)).convert("RGB"))
        except Exception:
            pass
        return (tx, ty, None)

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = []
        for tx in range(min_tx, max_tx + 1):
            for ty in range(min_ty, max_ty + 1):
                futures.append(executor.submit(fetch_tile, tx, ty))
        
        for future in futures:
            tx, ty, img = future.result()
            if img:
                # 计算瓦片在画布上的粘贴位置 (注意画布左上角不一定是瓦片左上角)
                paste_x = (tx * 256) - grid['global_x_start']
                paste_y = (ty * 256) - grid['global_y_start']
                stitched_image.paste(img, (paste_x, paste_y))
                
    return stitched_image

def process_city(geojson_path, source):
    import geo_utils
    from geo_utils import generate_city_grid, lnglat_to_global_pixel
    import config
    from config import TARGET_METERS, OUTPUT_IMAGE_SIZE, IMAGES_DIR, MASKS_DIR, COCO_DIR
    import rasterio.features
    from shapely.geometry import shape

    item_id = os.path.splitext(os.path.basename(geojson_path))[0]
    out_img_dir = os.path.join(IMAGES_DIR, item_id)
    out_msk_dir = os.path.join(MASKS_DIR, item_id)
    os.makedirs(out_img_dir, exist_ok=True)
    os.makedirs(out_msk_dir, exist_ok=True)

    if source == 'usa':
        zoom_level = 18
        # 使用更为合规且主要由 NAIP 提供北美源的 ESRI 影像层
        url_template = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
    elif source == 'fra':
        zoom_level = 19
        url_template = "https://data.geopf.fr/wmts?SERVICE=WMTS&VERSION=1.0.0&REQUEST=GetTile&LAYER=ORTHOIMAGERY.ORTHOPHOTOS&STYLE=normal&FORMAT=image/jpeg&TILEMATRIXSET=PM&TILEMATRIX={z}&TILEROW={y}&TILECOL={x}"
    elif source == 'nzl':
        zoom_level = 19
        url_template = "https://basemaps.linz.govt.nz/v1/tiles/aerial/EPSG:3857/{z}/{x}/{y}.webp"
    else:
        print(f"❌ 不支持的影像源: {source}")
        return

    print(f"📍 正在处理地平线任务: {item_id} (采用 {source.upper()} 高清数据源)")
    
    # 完整读取 GeoJSON 以构建掩码
    gdf = gpd.read_file(geojson_path)
    if gdf.crs != "EPSG:4326":
        gdf = gdf.to_crs("EPSG:4326")
    
    minx, miny, maxx, maxy = gdf.total_bounds
    # 为了防止全城没数据导致报错，稍微取个中心点估算纬度用于切分网格
    center_lat = (miny + maxy) / 2.0
    
    grids = generate_city_grid((minx, miny, maxx, maxy), TARGET_METERS, zoom_level, center_lat)
    print(f"🗺️ 按照 {TARGET_METERS}m 物理步长，城市总计被切分为 {len(grids)} 个训练网格。")

    headers = {'User-Agent': 'BuildingHeight_Research_Pipeline'}
    
    try:
        from tqdm import tqdm
        grid_iter = tqdm(grids, desc=f"📦 生成数据集批次 ({OUTPUT_IMAGE_SIZE}x{OUTPUT_IMAGE_SIZE})")
    except ImportError:
        grid_iter = grids
        
    for grid in grid_iter:
        gid = grid['grid_id']
        img_path = os.path.join(out_img_dir, f"grid_{gid:05d}_z{zoom_level}.jpg")
        # 定义当前网格的统一输出目录结构
        city_mask_root = os.path.join(MASKS_DIR, item_id)
        out_mask_subdir = os.path.join(city_mask_root, 'masks')
        out_viz_subdir = os.path.join(city_mask_root, 'viz')
        os.makedirs(out_mask_subdir, exist_ok=True)
        os.makedirs(out_viz_subdir, exist_ok=True)

        msk_path = os.path.join(out_mask_subdir, f"grid_{gid:05d}_z{zoom_level}.tiff")
        vis_path = os.path.join(out_viz_subdir, f"grid_{gid:05d}_z{zoom_level}_vis.png")
        
        # 为了加速断点续传，存在则跳过
        if os.path.exists(img_path) and os.path.exists(msk_path):
            continue

        # 1. 下载并拼接该网格的卫星底图
        grid_img = get_image_for_grid(grid, None, zoom_level, url_template, headers, source)
        # 强制缩放到用户所需的 1024x1024 模型输入尺寸
        final_img = grid_img.resize((OUTPUT_IMAGE_SIZE, OUTPUT_IMAGE_SIZE), Image.Resampling.LANCZOS)
        final_img.save(img_path, quality=95)

        # 2. 生成建筑物精确高度掩码 (Height Mask) 以及 COCO 实例分割标签
        # 初始化当前网格画布的 COCO 字典
        coco_format = {
            "images": [
                {
                    "id": gid,
                    "file_name": os.path.basename(img_path),
                    "width": OUTPUT_IMAGE_SIZE,
                    "height": OUTPUT_IMAGE_SIZE
                }
            ],
            "annotations": [],
            "categories": [
                {"id": 1, "name": "building"}
            ]
        }
        
        annotation_id = 1
        
        # -- 3.2 绘制高度掩码图 (Height Mask) --
        mask_arr = np.zeros((OUTPUT_IMAGE_SIZE, OUTPUT_IMAGE_SIZE), dtype=np.float32)
        
        for _, row in gdf.iterrows():
            geom = row.geometry
            if geom.is_empty:
                continue
                
            # 提取高度，如果没有 height 属性则默认为 1.0
            try:
                build_height = float(row.get('height', 1.0))
                if np.isnan(build_height):
                    build_height = 1.0
            except:
                build_height = 1.0
            
            # 将经纬度转换为当前网格内部像素坐标
            def transform_to_grid_pixels(lng, lat):
                gx, gy = lnglat_to_global_pixel(lng, lat, zoom_level)
                px = gx - grid['global_x_start']
                py = gy - grid['global_y_start']
                scale = OUTPUT_IMAGE_SIZE / grid['pixel_size']
                return px * scale, py * scale

            from shapely.ops import transform
            transformed_geom = transform(transform_to_grid_pixels, geom)
            
            # 仅保留和当前画布有交集的建筑物
            box = transformed_geom.bounds
            if box[0] < OUTPUT_IMAGE_SIZE and box[2] > 0 and box[1] < OUTPUT_IMAGE_SIZE and box[3] > 0:
                # ------ 使用 cv2.fillPoly 绘制高度掩码 ------
                # 提取多边形坐标并转换为 cv2 需要的格式
                if transformed_geom.geom_type == 'Polygon':
                    polys = [transformed_geom]
                elif transformed_geom.geom_type == 'MultiPolygon':
                    polys = list(transformed_geom.geoms)
                else:
                    polys = []

                for poly in polys:
                    # 获取外边界坐标
                    exterior_pts = np.array(poly.exterior.coords, np.int32).reshape((-1, 1, 2))
                    cv2.fillPoly(mask_arr, [exterior_pts], float(build_height))
                    # 如果有内孔，也需要处理 (通常建筑没孔，但为了严谨...)
                    for interior in poly.interiors:
                        interior_pts = np.array(interior.coords, np.int32).reshape((-1, 1, 2))
                        cv2.fillPoly(mask_arr, [interior_pts], 0.0) # 孔洞部分填充背景 0
                
                # ------ 计算 COCO 格式的标注 ------
                from shapely.geometry import Polygon
                
                # 如果是多部分组合面(MultiPolygon)，由于代码复杂度暂只取主外边界
                if transformed_geom.geom_type == 'MultiPolygon':
                    # 寻找面积最大的 Polygon
                    geom_parts = list(transformed_geom.geoms)
                    poly = max(geom_parts, key=lambda a: a.area)
                else:
                    poly = transformed_geom
                    
                # 记录为 COCO 的 bbox: [x, y, width, height]
                xmin, ymin, xmax, ymax = poly.bounds
                w = xmax - xmin
                h = ymax - ymin
                
                # 提取语义分割需要的多边形控制点 (外环 coordinates)
                # COCO 的 segmentation 是一个按顺序的平铺数组 [x1, y1, x2, y2, ...]
                exterior_coords = list(poly.exterior.coords)
                seg_flat = []
                for pt in exterior_coords[:-1]: # 去掉自动闭合的最后一点
                    seg_flat.extend([pt[0], pt[1]])

                coco_format["annotations"].append({
                    "id": annotation_id,
                    "image_id": gid,
                    "category_id": 1,
                    "segmentation": [seg_flat],
                    "area": poly.area,
                    "bbox": [xmin, ymin, w, h],
                    "iscrowd": 0,
                    "attributes": {
                        "height": build_height
                    }
                })
                annotation_id += 1
        # -- 3.3 保存 Mask --
        # 使用 cv2.imwrite 保存为 TIFF 格式以支持 float32 精确高度
        cv2.imwrite(msk_path, mask_arr)
            
        # --- 新增：为人类肉眼特制一张彩色可视化热力图 ---
        # 物理高度（比如 5 米）在灰度图里非常暗（亮度为 5/255），为了方便人眼预览，我们需要归一化并上色
        
        # 排除背景 0.0 计算最大高度，用来做动态对比度拉伸
        max_h = np.max(mask_arr)
        if max_h > 0:
            import matplotlib.pyplot as plt
            # 采用非线性（开根号/Gamma压缩）归一化，极大提亮低矮建筑的视觉可见度
            # 以防止哪怕是一个 400米的超高层建筑把其他 5-10 米的普通建筑压成纯黑
            norm_mask = np.power(mask_arr / max_h, 0.4)
            # 使用灰度色带 (灰度越白代表越高)
            cmap = plt.get_cmap('gray') 
            color_mask = cmap(norm_mask)
            
            # 把原本背景是 0 的地方重新变回死黑
            color_mask[mask_arr == 0.0] = [0, 0, 0, 1] 
            
            # 转换为 8 位 RGB 图像并保存
            vis_img = Image.fromarray((color_mask[:, :, :3] * 255).astype(np.uint8))
            vis_img.save(vis_path)
        else:
            # 如果全是平地没建筑，直接存一张黑图
            Image.new('RGB', (OUTPUT_IMAGE_SIZE, OUTPUT_IMAGE_SIZE)).save(vis_path)
            
        # 3. 将对应批次的 COCO 字典写入同名 JSON 文件
        out_json_dir = os.path.join(COCO_DIR, item_id)
        os.makedirs(out_json_dir, exist_ok=True)
        json_path = os.path.join(out_json_dir, f"grid_{gid:05d}_z{zoom_level}.json")
        with open(json_path, 'w', encoding='utf-8') as jf:
            json.dump(coco_format, jf, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="按物理尺度切割并生成 1024x1024 遥感影像与建筑掩码数据集")
    parser.add_argument("--geojson", type=str, required=True, help="输入的 geojson 边界文件")
    parser.add_argument("--source", type=str, required=True, choices=['usa', 'fra', 'nzl'], 
                        help="手动指定要使用的优质影像源: 'usa'(NAIP 0.6m), 'fra'(IGN 0.2m), 'nzl'(LINZ 0.3m)")
    args = parser.parse_args()
    process_city(args.geojson, args.source)
