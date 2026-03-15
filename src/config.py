import os

# ================= 核心参数 =================
# 数据源选择: 'GOOGLE_MAPS', 'ESRI_MAPS', 或 'GEE'
# 'GOOGLE_MAPS' - 最高清，做科研实验首选 (XYZ瓦片拼接)，细节极佳
# 'ESRI_MAPS'   - 极高清，作为 Google Maps 的完美平替方案
# 'GEE'         - 独立合规版本 (临时XYZ瓦片服务拼接法，平滑插值，视野一致)
DATA_SOURCE = 'ESRI_MAPS'
# 每张输出图片代表的真实物理街区大小（单位：米）
TARGET_METERS = 256  

# 强制使用的高清缩放级别 (推荐 17 或 18)
# 17 级: ~1.2m/像素, 下载快，适合快速测试
# 18 级: ~0.6m/像素, 非常清晰，适合正式数据集
HD_ZOOM_LEVEL = 18

# 切图后的输出分辨率 (像素 x 像素)
OUTPUT_IMAGE_SIZE = 1024

# 多线程下载的并发线程数
DOWNLOAD_THREADS = 16

# ================= 路径配置 =================
# 获取当前项目的根目录 (也就是 BuildingHeight_Dataset 文件夹)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 原始数据路径
RAW_DATA_DIR = os.path.join(BASE_DIR, 'data', 'raw')

# 输出数据集的路径
PROCESSED_DIR = os.path.join(BASE_DIR, 'data', 'processed')
IMAGES_DIR = os.path.join(PROCESSED_DIR, 'images')
MASKS_DIR = os.path.join(PROCESSED_DIR, 'masks')
COCO_DIR = os.path.join(PROCESSED_DIR, 'coco_json')

# 瓦片缓存目录（避免重复下载）
TILE_CACHE_DIR = os.path.join(BASE_DIR, 'data', 'interim', 'tiles')

# 确保输出文件夹存在
os.makedirs(IMAGES_DIR, exist_ok=True)
os.makedirs(MASKS_DIR, exist_ok=True)
os.makedirs(COCO_DIR, exist_ok=True)
os.makedirs(TILE_CACHE_DIR, exist_ok=True)

# ================= 数据源 URL 配置 =================
# Google 卫星图无密钥瓦片接口
TILE_URL_GOOGLE = "https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}"

# ESRI 卫星图无密钥瓦片接口 (0.5m 分辨率级别)
TILE_URL_ESRI = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"

# 动态决定使用的 URL
if DATA_SOURCE == 'GOOGLE_MAPS':
    TILE_URL = TILE_URL_GOOGLE
elif DATA_SOURCE == 'ESRI_MAPS':
    TILE_URL = TILE_URL_ESRI
else:
    # GEE 会在代码里动态生成
    TILE_URL = ""