import os
import sys
import argparse
import geopandas as gpd
from PIL import Image

# 把 src 目录加入 Python 搜索路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sources import get_source
from dataset_engine import generate_labels_for_grid
import geo_utils
import config

def main():
    """
    【工业级数据集生成主程序】
    增加了针对超大规模数据（如 56万建筑）的断点哨兵机制。
    """
    
    # 1. 设置命令行参数
    parser = argparse.ArgumentParser(description="按物理尺度切割并生成 1024x1024 遥感影像与建筑掩码数据集")
    parser.add_argument("--geojson", type=str, required=True, help="输入的 geojson 边界文件")
    parser.add_argument("--source", type=str, required=True, choices=['usa', 'fra', 'nzl', 'jpn', 'nld','chn','hkg','twn'], 
                        help="手动指定数据源")
    args = parser.parse_args()

    geojson_path = args.geojson
    source_name = args.source

    # 路径准备
    item_id = os.path.splitext(os.path.basename(geojson_path))[0]
    out_img_dir = os.path.join(config.IMAGES_DIR, item_id)
    out_msk_root = os.path.join(config.MASKS_DIR, item_id)
    out_json_dir = os.path.join(config.COCO_DIR, item_id)
    
    os.makedirs(out_img_dir, exist_ok=True)
    os.makedirs(out_msk_root, exist_ok=True)
    os.makedirs(out_json_dir, exist_ok=True)

    # --- 哨兵机制：定义断点文件路径 ---
    checkpoint_path = os.path.join(out_json_dir, "checkpoint_gid.txt")

    print(f"📍 正在启动任务: {item_id} | 影像源: {source_name.upper()}")

    # 2. 加载数据并计算 BBOX
    gdf = gpd.read_file(geojson_path)
    if gdf.crs != "EPSG:4326":
        gdf = gdf.to_crs("EPSG:4326")
    
    minx, miny, maxx, maxy = gdf.total_bounds
    center_lat = (miny + maxy) / 2.0
    
    print("🚀 初始化影像源及网格系统...")
    source_obj = get_source(source_name)
    zoom_level = source_obj.zoom_level

    # 3. 切分物理网格
    grids = geo_utils.generate_city_grid((minx, miny, maxx, maxy), config.TARGET_METERS, zoom_level, center_lat)
    total_grids = len(grids)
    print(f"🗺️ 城市总计被切分为 {total_grids} 个训练网格。")

    # --- 哨兵机制：读取上次进度 ---
    start_gid = 0
    if os.path.exists(checkpoint_path):
        with open(checkpoint_path, "r") as f:
            try:
                start_gid = int(f.read().strip())
                print(f"🔄 发现断点！将跳过前 {start_gid} 个已确认网格，直接从 GID {start_gid} 开始...")
            except:
                start_gid = 0

    # 使用 tqdm 进度条
    try:
        from tqdm import tqdm
        grid_iter = tqdm(grids, desc=f"📦 {item_id}", unit="grid")
    except ImportError:
        grid_iter = grids

    # 4. 核心处理循环
    for grid in grid_iter:
        gid = grid['grid_id']
        
        # 1️⃣ 哨兵校验：如果 gid 小于断点，直接跳过计算
        if gid < start_gid:
            continue
        
        # 路径准备
        img_path = os.path.join(out_img_dir, f"grid_{gid:05d}_z{zoom_level}.jpg")
        out_mask_subdir = os.path.join(out_msk_root, 'masks')
        out_viz_subdir = os.path.join(out_msk_root, 'viz')
        os.makedirs(out_mask_subdir, exist_ok=True)
        os.makedirs(out_viz_subdir, exist_ok=True)

        msk_path = os.path.join(out_mask_subdir, f"grid_{gid:05d}_z{zoom_level}.tiff")
        vis_path = os.path.join(out_viz_subdir, f"grid_{gid:05d}_z{zoom_level}_vis.png")
        json_path = os.path.join(out_json_dir, f"grid_{gid:05d}_z{zoom_level}.json")

        # 2️⃣ 文件级校验：如果文件已在磁盘，跳过（双重保险）
        if os.path.exists(img_path) and os.path.exists(msk_path) and os.path.exists(json_path):
            continue

        try:
            # 获取影像
            grid_img = source_obj.fetch_image_for_grid(grid)
            if not grid_img:
                grid_img = Image.new('RGB', (grid['pixel_size'], grid['pixel_size']))
            
            final_img = grid_img.resize((config.OUTPUT_IMAGE_SIZE, config.OUTPUT_IMAGE_SIZE), Image.Resampling.LANCZOS)
            final_img.save(img_path, quality=95)

            # 生成标签 (TIFF/JSON)
           # ... 前面是生成标签的代码 ...
            generate_labels_for_grid(
                grid=grid,
                gdf=gdf,
                zoom_level=zoom_level,
                output_image_size=config.OUTPUT_IMAGE_SIZE,
                img_path=img_path,
                msk_path=msk_path,
                vis_path=vis_path,
                json_path=json_path,
                gid=gid
            )

            # 🛑 --- 新增：日本数据“全黑掩码”拦截与“毁尸灭迹”机制 --- 🛑
            if source_name == 'jpn':
                import numpy as np
                # 读取刚刚生成的掩码图
                if os.path.exists(msk_path):
                    msk_array = np.array(Image.open(msk_path))
                    # 检查是否全黑
                    if np.max(msk_array) == 0:
                        # 如果全黑，立刻删除刚才保存的 jpg, tiff, png 和 json
                        for p in [img_path, msk_path, vis_path, json_path]:
                            if os.path.exists(p):
                                os.remove(p)
                        # 直接跳入下一个循环，不执行后面的更新 checkpoint 操作
                        # 这样终端也不会显得太乱
                        continue 
            # 🛑 ---------------------------------------------------- 🛑

            # 3️⃣ 哨兵更新：每成功处理一个（或每10个）网格，更新一次 checkpoint
            with open(checkpoint_path, "w") as f:
                f.write(str(gid))
            
            # ... 后面是 except Exception as e ...

        except Exception as e:
            print(f"\n❌ 处理网格 {gid} 时发生意外错误: {e}")
            # 遇到单图错误不中断大任务，继续跑下一个
            continue

    print(f"\n✨ {item_id} 任务全部完成！数据保存在 {config.DATA_DIR}")

if __name__ == "__main__":
    main()