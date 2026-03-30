import os

"""
【总控台：配置文件】
这是项目的全局配置文件。你要改默认路径、改分辨率、改每次要多大多清晰的图，都在这里调，不需要去别的代码里翻找。
"""

# ================= 核心参数区 =================

# 你希望最终每张要生成训练用的正方形图片，里面代表世界上多长多宽的距离？
# 比如 256 就代表：每张图片覆盖一个 256米 x 256米的真实城市街区。
TARGET_METERS = 256  

# 【强制使用的高清缩放级别】
# 不同的卫星服务商，级别不一样：
# 比如 美国 NAIP 支持 18 级 (约0.6米/像素，非常清晰)
# 法国 IGN 支持 19 级 (约0.2米/像素，可以看清车道线)
HD_ZOOM_LEVEL = 18

# 最终提供给深度学习模型训练用的统一图片分辨率 (宽 x 高)
# 无论原本瓦片是多大，最后都会缩放成 1024x1024 像素的完美正方形
OUTPUT_IMAGE_SIZE = 1024

# 多线程并发下载瓦片时的速度（如果服务商屏蔽严格，可以在源插件里调低）
DOWNLOAD_THREADS = 16

# ================= 目录路径大管家 =================

# 自动获取当前项目所在的绝对路径根目录 (找 BuildingHeight_Dataset 文件夹)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 原始数据路径 (你把下好的 GeoJSON 放这里)
RAW_DATA_DIR = os.path.join(BASE_DIR, 'data', 'raw')

# 【加工后的模型成品数据集】都会自动分门别类地存在这里
PROCESSED_DIR = os.path.join(BASE_DIR, 'data', 'processed')
IMAGES_DIR = os.path.join(PROCESSED_DIR, 'images')         # 这里存卫星图 (.jpg)
MASKS_DIR = os.path.join(PROCESSED_DIR, 'masks')           # 这里存高度的矩阵图 (.tiff) 及给人看的预览图 (.png)
COCO_DIR = os.path.join(PROCESSED_DIR, 'coco_json')        # 这里存实例分割的坐标点和轮廓框 (.json)

# 下载瓦片的临时中转站（防断网，如果下了一半网断了，下次还能直接用缓存不用重下）
TILE_CACHE_DIR = os.path.join(BASE_DIR, 'data', 'interim', 'tiles')

# 每次跑代码前，如果这些存放输出的文件夹不存在，就自动帮你建好
os.makedirs(IMAGES_DIR, exist_ok=True)
os.makedirs(MASKS_DIR, exist_ok=True)
os.makedirs(COCO_DIR, exist_ok=True)
os.makedirs(TILE_CACHE_DIR, exist_ok=True)