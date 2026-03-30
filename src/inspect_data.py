import cv2
import json
import os
import sys

def inspect(tile_name):
    """
    【数据质检探针工具】
    作用：由于模型使用的 TIFF 掩膜图是一片纯黑的32位浮点图，人类用肉眼无法打开直接看有没有高度，
    这个脚本就是帮你一键读取 TIFF 和 JSON，然后把里头隐藏的内容打印出来给你过目，确保生成的没错。
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    tiff_path = os.path.join(base_dir, 'data', 'processed', 'masks', f'{tile_name}.tiff')
    json_path = os.path.join(base_dir, 'data', 'processed', 'coco_json', f'{tile_name}.json')

    print(f"================ 检查瓦片: {tile_name} ================")

    # =============== 1. 检查 TIFF 掩膜部分 ===============
    if not os.path.exists(tiff_path):
        print(f"❌ 找不到 TIFF 文件: {tiff_path}")
    else:
        # 读取 TIFF (cv2.IMREAD_UNCHANGED 是为了不让 OpenCV 自作主张转成8位图，保留原有的小数数组)
        mask = cv2.imread(tiff_path, cv2.IMREAD_UNCHANGED)
        print(f"✅ TIFF 形状: {mask.shape}, 数据类型: {mask.dtype}")
        
        # 找出所有非零的像素点 (即这个像素有房子的位置)
        nonzero_pixels = mask[mask > 0]
        if len(nonzero_pixels) == 0:
            print("ℹ️ 该瓦片 TIFF 中没有建筑 (全为0). 这是平地或者是海。")
        else:
            print(f"📍 发现 {len(nonzero_pixels)} 个建筑像素。")
            # 打印前 10 个像素的高度数值，让我们看看究竟是多少米
            print(f"📏 前 10 个非零像素的高度真实数值 (米): {nonzero_pixels[:10].tolist()}")

    print("\n---------------------------------------------------------")

    # =============== 2. 检查 JSON 标注部分 ===============
    if not os.path.exists(json_path):
        print(f"❌ 找不到 JSON 文件: {json_path}")
    else:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        print(f"✅ JSON 包含 {len(data['annotations'])} 个独立的建筑实例标注。")
        if len(data['annotations']) > 0:
            print("📝 第一个建筑示例的内容 (COCO Instance 标准格式):")
            sample = data['annotations'][0]
            # 为了防止打印出来的坐标直接霸屏，我们只抽取前8个坐标数字展示
            sample_coords = sample['segmentation'][0]
            sample['segmentation'] = [sample_coords[:8] + ["... 此处省略太长不打印了"]]
            print(json.dumps(sample, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    # 如果用户没有带任何参数，就提示一下正确用法
    if len(sys.argv) < 2:
        print("用法: conda run -n bh_env python src/inspect_data.py <你想检查的瓦片名称>")
        print("例如: conda run -n bh_env python src/inspect_data.py hznu/masks/grid_00000_z18")
    else:
        inspect(sys.argv[1])
