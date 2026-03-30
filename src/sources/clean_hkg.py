import os
import glob
import numpy as np
from PIL import Image
from tqdm import tqdm

print("🧹 开始扫描并清理全黑背景数据 (大阪)...")

# 直接使用你提供的绝对路径
base_image_dir = "/data2/hgq/BuildingHeight_Dataset/data/processed/images/Japan_Osaka_buildings_full"
base_mask_root = "/data2/hgq/BuildingHeight_Dataset/data/processed/masks/Japan_Osaka_buildings_full"
base_json_dir = "/data2/hgq/BuildingHeight_Dataset/data/processed/coco_json/Japan_Osaka_buildings_full"

# 根据 main.py 的逻辑，细化具体的子目录
masks_dir = os.path.join(base_mask_root, "masks")  # 存放 .tiff 的地方
viz_dir = os.path.join(base_mask_root, "viz")      # 存放 _vis.png 的地方

# 获取所有生成的 tiff 掩码文件
mask_files = glob.glob(os.path.join(masks_dir, "*.tiff"))

if not mask_files:
    print("❌ 未找到任何掩码文件，请检查路径是否正确。")
else:
    print(f"📦 共找到 {len(mask_files)} 张掩码图，开始质检...")
    remove_count = 0
    for mask_path in tqdm(mask_files, desc="🔍 扫描黑图中..."):
        try:
            # 读取掩码并转为 numpy 数组
            mask_array = np.array(Image.open(mask_path))
            
            # 🛑 核心判断：如果最大值为 0，说明整张图全黑（没有任何建筑）
            if np.max(mask_array) == 0:
                # 获取文件的基础名称，比如 grid_00001_z19
                base_name = os.path.basename(mask_path).replace(".tiff", "")
                
                # 构造所有关联文件的绝对路径
                related_files = [
                    mask_path,                                         # 删除黑白掩码 .tiff
                    os.path.join(base_image_dir, f"{base_name}.jpg"),  # 删除卫星图 .jpg
                    os.path.join(viz_dir, f"{base_name}_vis.png"),     # 删除彩色可视化 _vis.png
                    os.path.join(base_json_dir, f"{base_name}.json")   # 删除标签 .json
                ]
                
                # 物理删除
                for file_path in related_files:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                
                remove_count += 1
        except Exception as e:
            pass

    print(f"🎉 大扫除完毕！共无情删除了 {remove_count} 组毫无价值的全黑背景数据。")