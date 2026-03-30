import ee
import os
import requests

# 1. 认证与初始化 Earth Engine (首次运行需取消注释下一行进行网页授权)
# ee.Authenticate()
ee.Initialize()

def download_compliant_satellite_image(roi_bbox, output_path, resolution=1.0):
    """
    根据给定的经纬度边界，合规下载高分辨率影像。
    以完全开源的 NAIP 数据集 (0.6m 分辨率) 为例。
    
    参数:
    roi_bbox: list, [最小经度, 最小纬度, 最大经度, 最大纬度]
    output_path: str, 保存图像的本地路径 (如 './data/image_001.zip')
    resolution: float, 下载的像素分辨率 (米/像素)
    """
    print(f"正在处理区域: {roi_bbox}...")
    
    # 将边界框转换为 GEE 的几何对象
    roi = ee.Geometry.Rectangle(roi_bbox)

    # 2. 选取合规的高分辨率开源数据集 (例如 NAIP)
    # 您也可以根据研究需求替换为 Sentinel-2 (10m) 或其他公开的高分商业数据集入口
    dataset = ee.ImageCollection('USDA/NAIP/DOQQ') \
                .filterBounds(roi) \
                .filterDate('2020-01-01', '2021-12-31') 

    # 检查区域内是否有数据
    if dataset.size().getInfo() == 0:
        print("警告：该时间段/区域内无开源影像覆盖。")
        return

    # 3. 图像融合与裁剪 (将多张影像拼接并精准裁剪到目标框)
    # 取中位数可以有效过滤掉偶发的噪点
    image = dataset.median().clip(roi)

    # 4. 生成一次性下载链接
    try:
        download_url = image.getDownloadURL({
            'scale': resolution,  # 分辨率，数值越小越清晰，但文件越大
            'crs': 'EPSG:4326',   # 标准 WGS84 坐标系
            'region': roi,
            'format': 'GEO_TIFF'  # 遥感标准的带坐标系图像格式
        })
        print("下载链接生成成功，正在拉取数据...")
        
        # 5. 下载并写入本地
        response = requests.get(download_url, stream=True)
        if response.status_code == 200:
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=1024):
                    if chunk:
                        f.write(chunk)
            print(f"✅ 成功保存至: {output_path}\n")
        else:
            print(f"❌ 下载失败，状态码: {response.status_code}\n")
            
    except Exception as e:
        print(f"发生错误: {e}")

if __name__ == '__main__':
    # 示例：准备您的数据集标注文件中的坐标列表 (通常可以从 CSV 中遍历读取)
    # 这里我们以旧金山市区的一个包含密集建筑的街区为例
    dataset_rois = [
        {"id": "sf_block_01", "bbox": [-122.405, 37.785, -122.395, 37.795]},
        {"id": "sf_block_02", "bbox": [-122.415, 37.790, -122.405, 37.800]}
    ]
    
    os.makedirs('./satellite_dataset', exist_ok=True)
    
    # 遍历下载
    for item in dataset_rois:
        save_path = f"./satellite_dataset/{item['id']}.zip"
        # 下载 1米 分辨率的影像 (您可以修改为0.6来测试极限分辨率)
        download_compliant_satellite_image(item['bbox'], save_path, resolution=0.6)
