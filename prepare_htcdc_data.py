import os
import glob
import cv2
import shutil
import numpy as np
import sys
import geopandas as gpd

# 将 src 加入环境变量以便调用 geo_utils 和 config
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))
from geo_utils import generate_city_grid
import config

def prepare_data_spatial_east_west():
    base_dir = "/data2/hgq/BuildingHeight_Dataset/data/processed"
    out_dir = "/data2/hgq/BuildingHeight_Dataset/htcdc_data"
    
    os.makedirs(os.path.join(out_dir, "image"), exist_ok=True)
    os.makedirs(os.path.join(out_dir, "ndsm"), exist_ok=True)
    os.makedirs(os.path.join(out_dir, "mask"), exist_ok=True)
    
    # 【需求1】只测试 HKG_Core
    city = "HKG_Core"
    
    img_dir = os.path.join(base_dir, "images", city)
    mask_dir = os.path.join(base_dir, "masks", city, "masks")
    
    if not os.path.exists(mask_dir):
        print(f"Directory {mask_dir} does not exist!")
        return
        
    imgs = glob.glob(os.path.join(img_dir, "*.jpg"))
    
    # 【需求2】为了实现自东向西划分，我们需要真实的空间坐标
    # 我们可以通过重新运行一次网格生成系统，拿到 gid 到 X 坐标的映射表
    geojson_path = f"/data2/hgq/BuildingHeight_Dataset/data/raw/{city}.geojson"
    gdf = gpd.read_file(geojson_path)
    if gdf.crs != "EPSG:4326":
        gdf = gdf.to_crs("EPSG:4326")
    minx, miny, maxx, maxy = gdf.total_bounds
    center_lat = (miny + maxy) / 2.0
    
    zoom_level = 19 # 根据香港图像的名字如 grid_00000_z19
    # 从 config 中读取物理尺度
    grids = generate_city_grid((minx, miny, maxx, maxy), config.TARGET_METERS, zoom_level, center_lat)
    
    # 将网格ID映射到真实的地图像素 X 坐标 (经度方向)
    gid_to_x = {g['grid_id']: g['global_x_start'] for g in grids}
    
    # 组合成带有空间信息的对象列表
    scene_infos = []
    
    for img_path in imgs:
        basename = os.path.basename(img_path).replace(".jpg", "")
        # 解析如 grid_00000_z19 提取出 gid = 0
        gid_str = basename.split('_')[1]
        gid = int(gid_str)
        
        mask_path = os.path.join(mask_dir, basename + ".tiff")
        
        if os.path.exists(mask_path):
            scene_name = f"{city}_{basename}"
            scene_infos.append({
                'scene_name': scene_name,
                'img_path': img_path,
                'mask_path': mask_path,
                'x_coord': gid_to_x.get(gid, 0) # 获取其空间东-西坐标
            })

    # 【核心：自东向西排序】
    # x_coord 的数值越大代表越偏东边，越小代表越偏西边。
    # 既然要求自东向西切分，那我们就把所有瓦片按照 X 坐标【从大到小】(降序)进行排序！
    scene_infos.sort(key=lambda item: item['x_coord'], reverse=True)
    
    train_scenes = []
    val_scenes = []
    test_scenes = []
    
    # 保存所有有效的图片与标签
    for item in scene_infos:
        scene_name = item['scene_name']
        img_path = item['img_path']
        mask_path = item['mask_path']
        
        out_img_path = os.path.join(out_dir, "image", f"{scene_name}_IMG.tif")
        out_ndsm_path = os.path.join(out_dir, "ndsm", f"{scene_name}_AGL.tif")
        out_b_mask_path = os.path.join(out_dir, "mask", f"{scene_name}_BLG.tif")
        
        # 真正写入硬盘 (利用库自带解码器读取原图，然后转存)
        if not os.path.exists(out_img_path):
            # 1. 它是如何把 jpg 变成 tif 的？
            # 答：利用 cv2 的重编码机制。cv2 先把 jpg 解析为 numpy 内存矩阵；
            #    随后 cv2.imwrite() 遇到 ".tif" 后缀，会自动把 numpy 矩阵按标准 TIFF 格式存入硬盘，这就完成了无损转换！
            img = cv2.imread(img_path)
            cv2.imwrite(out_img_path, img)      # 存出来的就是实打实的 .tif 图片格式
            
            # 2. 复制高度图
            shutil.copy(mask_path, out_ndsm_path)
            
            # 3. 生成只包含 0 和 255 的纯二值建筑掩膜
            height_mask = cv2.imread(mask_path, cv2.IMREAD_UNCHANGED)
            if height_mask is not None:
                b_mask = (height_mask > 0).astype(np.uint8) * 255
                cv2.imwrite(out_b_mask_path, b_mask)
                
    # 按照比例割分 (从东往西切：最东端80%给train, 中部西侧10%给val, 最西端10%给test)
    total = len(scene_infos)
    train_idx = int(0.8 * total)
    val_idx = int(0.9 * total)
    
    train_scenes = [s['scene_name'] for s in scene_infos[:train_idx]]
    val_scenes = [s['scene_name'] for s in scene_infos[train_idx:val_idx]]
    test_scenes = [s['scene_name'] for s in scene_infos[val_idx:]]
    
    split_dir = os.path.join(out_dir, "splits")
    os.makedirs(split_dir, exist_ok=True)
    
    with open(os.path.join(split_dir, "train.txt"), "w") as f:
        f.write("\n".join(train_scenes))
    with open(os.path.join(split_dir, "val.txt"), "w") as f:
        f.write("\n".join(val_scenes))
    with open(os.path.join(split_dir, "test.txt"), "w") as f:
        f.write("\n".join(test_scenes))
        
    print(f"Dataset spatial preparation complete for HKG_Core (East to West cut)!")
    print(f"Train (East 80%): {len(train_scenes)}")
    print(f"Val (Mid-West 10%): {len(val_scenes)}")
    print(f"Test (Far-West 10%): {len(test_scenes)}")

if __name__ == '__main__':
    prepare_data_spatial_east_west()
