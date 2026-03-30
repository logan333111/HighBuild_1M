import os
import cv2
import json
import numpy as np
import matplotlib.pyplot as plt
from PIL import Image

def generate_labels_for_grid(grid, gdf, zoom_level, output_image_size, img_path, msk_path, vis_path, json_path, gid):
    """
    【核心标签生成引擎】
    该函数负责接收一个城市网格 (grid) 和下载好的卫星图，并将其对应的建筑轮廓转化为供深度学习使用的标签格式。
    
    产生两个主要的标签：
    1. TIFF 掩膜图 (Mask): 用于图像分割模型 (如 U-Net)。图中每个建筑的像素值等于它的真实高度。
    2. COCO JSON: 用于实例分割/目标检测模型 (如 Mask R-CNN)。记录每个建筑的多边形顶点、边界框和高度。
    
    参数说明:
        grid: 当前要处理的网格信息 (包含像素起止点)
        gdf: 包含所有建筑多边形的 GeoDataFrame (已自动加载 GeoJSON)
        zoom_level: 当前瓦片缩放级别 (决定了1像素代表多少米)
        output_image_size: 裁剪出的标准方块图片大小 (例如 1024x1024)
        img_path, msk_path, vis_path, json_path: 分别对应原图、高度掩膜图、可视化热力图、JSON标注的保存路径
        gid: 网格的唯一编号 (id)
    """
    from geo_utils import lnglat_to_global_pixel
    from shapely.ops import transform
    from shapely.geometry import Polygon

    # 初始化 COCO JSON 标注的基本骨架
    coco_format = {
        "images": [
            {
                "id": gid,
                "file_name": os.path.basename(img_path),
                "width": output_image_size,
                "height": output_image_size
            }
        ],
        "annotations": [],
        "categories": [
            {"id": 1, "name": "building"}  # 只有一个类别：建筑
        ]
    }
    
    annotation_id = 1
    # 初始化一张全黑的浮点数掩膜图 (0.0 表示平地/没有建筑物)
    mask_arr = np.zeros((output_image_size, output_image_size), dtype=np.float32)
    
    # 遍历 GeoJSON 中的每一栋建筑
    for _, row in gdf.iterrows():
        geom = row.geometry
        if geom.is_empty:
            continue
            
        # 读取建筑的高度 (如果有缺失值则默认 1.0 米)
        try:
            build_height = float(row.get('height', 1.0))
            if np.isnan(build_height):
                build_height = 1.0
        except:
            build_height = 1.0
        
        # 这是一个投影转换函数：把真实的地球经纬度，转化为当前这张 1024x1024 图片上的像素坐标 (x, y)
        def transform_to_grid_pixels(lng, lat):
            gx, gy = lnglat_to_global_pixel(lng, lat, zoom_level)
            px = gx - grid['global_x_start']
            py = gy - grid['global_y_start']
            # 根据网格的物理大小缩放到目标的输出尺寸
            scale = output_image_size / grid['pixel_size']
            return px * scale, py * scale

        # 执行坐标转换，把地球多边形变成图片上的像素多边形
        transformed_geom = transform(transform_to_grid_pixels, geom)
        
        # 获取这栋房子的矩形包围盒，只有至少一部分在这个 1024x1024 图片以内的房子，才会画上去
        box = transformed_geom.bounds
        if box[0] < output_image_size and box[2] > 0 and box[1] < output_image_size and box[3] > 0:
            # 兼容处理单一多边形和组合多边形
            if transformed_geom.geom_type == 'Polygon':
                polys = [transformed_geom]
            elif transformed_geom.geom_type == 'MultiPolygon':
                polys = list(transformed_geom.geoms)
            else:
                polys = []

            # ================= 第 1 步：绘制 TIFF 高度掩膜图 =================
            for poly in polys:
                # 获取建筑多边形的外圈顶点
                exterior_pts = np.array(poly.exterior.coords, np.int32).reshape((-1, 1, 2))
                # 用建筑的高度 fillPoly 填充满整个多边形区域 (例如楼高 15.5m，这里的像素值就是 15.5)
                cv2.fillPoly(mask_arr, [exterior_pts], float(build_height))
                
                # 如果这个建筑中间是个天井（有内圈镂空），我们要把中间圈出来并重新填成 0
                for interior in poly.interiors:
                    interior_pts = np.array(interior.coords, np.int32).reshape((-1, 1, 2))
                    cv2.fillPoly(mask_arr, [interior_pts], 0.0) 
            
            # ================= 第 2 步：提取 COCO 需要的边框和顶点 =================
            if transformed_geom.geom_type == 'MultiPolygon':
                geom_parts = list(transformed_geom.geoms)
                poly = max(geom_parts, key=lambda a: a.area)  # 若是多个建筑拼成的只选最大的
            else:
                poly = transformed_geom
                
            # xmin(左上角X), ymin(左上角Y), w(宽度), h(高度)
            xmin, ymin, xmax, ymax = poly.bounds
            w = xmax - xmin
            h = ymax - ymin
            
            # 将多边形的顶点平铺成 [x1,y1,x2,y2,x3,y3...] 即 COCO 要求的格式
            exterior_coords = list(poly.exterior.coords)
            seg_flat = []
            for pt in exterior_coords[:-1]:
                seg_flat.extend([pt[0], pt[1]])

            # 将这栋建筑添加到最终的 json 列表中
            coco_format["annotations"].append({
                "id": annotation_id,           # 建筑独立编号
                "image_id": gid,               # 对应那是哪张图
                "category_id": 1,              # 类别 (1 = 建筑)
                "segmentation": [seg_flat],    # 多边形精确坐标
                "area": poly.area,             # 像素面积
                "bbox": [xmin, ymin, w, h],    # 回归用的矩形框
                "iscrowd": 0,
                "attributes": {
                    "height": build_height     # 我们自己添加的高度属性
                }
            })
            annotation_id += 1
            
    # 【保存阶段】
    # 1. 保存 32位 浮点 TIFF 掩膜 (机器训练用，人肉眼看是一片黑)
    cv2.imwrite(msk_path, mask_arr)
        
    # 2. 生成一张便于人类检查的【热力图】(高度越高，图像越白亮)
    max_h = np.max(mask_arr) if np.max(mask_arr) > 0 else 0.0
    color_mask = np.zeros((output_image_size, output_image_size, 4), dtype=np.float32)
    color_mask[:, :] = [0, 0, 0, 1]  # 底色纯黑
    
    if max_h > 0:
        valid_mask = mask_arr > 0
        norm_vals = np.power(mask_arr[valid_mask] / max_h, 0.4) # 做一个开根号用来增强视觉对比度
        cmap = plt.get_cmap('gray')
        color_mask[valid_mask] = cmap(norm_vals)
        
    # 如果有些掩码是负数（即高度未知），标为红色方便排查
    unknown_mask = mask_arr < 0.0
    color_mask[unknown_mask] = [1.0, 0.2, 0.2, 1.0]
    
    vis_img = Image.fromarray((color_mask[:, :, :3] * 255).astype(np.uint8))
    vis_img.save(vis_path)
        
    # 3. 最终写入 COCO JSON 文件
    with open(json_path, 'w', encoding='utf-8') as jf:
        json.dump(coco_format, jf, indent=2, ensure_ascii=False)
