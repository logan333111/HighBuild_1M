import cv2
import json
import os
import sys

def inspect(tile_name):
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    tiff_path = os.path.join(base_dir, 'data', 'processed', 'masks', f'{tile_name}.tiff')
    json_path = os.path.join(base_dir, 'data', 'processed', 'coco_json', f'{tile_name}.json')

    print(f"================ 检查瓦片: {tile_name} ================")

    if not os.path.exists(tiff_path):
        print(f"❌ 找不到 TIFF 文件: {tiff_path}")
    else:
        # 读取 TIFF (cv2.IMREAD_UNCHANGED 保留原有的 float 数组)
        mask = cv2.imread(tiff_path, cv2.IMREAD_UNCHANGED)
        print(f"✅ TIFF 形状: {mask.shape}, 数据类型: {mask.dtype}")
        
        # 找出所有非零的像素点 (即有建筑的地方)
        nonzero_pixels = mask[mask > 0]
        if len(nonzero_pixels) == 0:
            print("ℹ️ 该瓦片 TIFF 中没有建筑 (全为0).")
        else:
            print(f"📍 发现 {len(nonzero_pixels)} 个建筑像素。")
            # 打印前 10 个像素的值看看高度是不是对的
            print(f"📏 前 10 个非零像素的高度值 (Y): {nonzero_pixels[:10].tolist()}")

    print("\n---------------------------------------------------------")

    if not os.path.exists(json_path):
        print(f"❌ 找不到 JSON 文件: {json_path}")
    else:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        print(f"✅ JSON 包含 {len(data['annotations'])} 个独立的建筑实例标注。")
        if len(data['annotations']) > 0:
            print("📝 第一个建筑示例的内容 (COCO Instance):")
            sample = data['annotations'][0]
            # 为了打印好看，省略全部的坐标，只打印前8个数字
            sample_coords = sample['segmentation'][0]
            sample['segmentation'] = [sample_coords[:8] + ["... omitted for brevity"]]
            print(json.dumps(sample, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: conda run -n bh_env python src/inspect_data.py <tile_name>")
        print("例如: conda run -n bh_env python src/inspect_data.py 16_54694_27211")
    else:
        inspect(sys.argv[1])
