# 全球建筑高度数据集 (Building Height Dataset) - 高分辨率影像拉取工具

为了确保数据集的合规性并获得极高的物理分辨率（亚米级），本项目不提供直接的卫星影像打包下载。
取而代之的是，我们根据全球不同国家/地区的免费开放数据政策，分别编写了专属的高分辨率航空影像下载器。

您需要提供自己关心的具有建筑高度属性的 GeoJSON 边界文件，并对应所属国家运行特定的下载脚本。

## 依赖安装
```bash
pip install geopandas rioxarray rasterio shapely mercantile Pillow requests
```

## 各国家/地区影像源提取指南

目前原生集成支持了全球 3 个具有顶级开源测绘数据的代表性国家/地区，所有提取的影像自动配置为标准 `EPSG:3857` 投影，并完美裁切贴合输入的 GeoJSON 边界框。

您可以使用一套统一的接口 `--source` 进行随时切换调用：

### 🇺🇸 1. 美国 (USA) - NAIP 0.6m
拉取区域对应的高清 0.6米 影像：
```bash
python src/download_image.py --geojson data/raw/your_usa_city.geojson --source usa
```

### 🇫🇷 2. 法国 (France) - IGN 0.2m
拉取最高等级 0.2米 惊人细节的影像：
```bash
python src/download_image.py --geojson data/raw/your_france_city.geojson --source fra
```

### 🇳🇿 3. 新西兰 (New Zealand) - LINZ 0.3m
```bash
python src/download_image.py --geojson data/raw/your_nzl_city.geojson --source nzl
```

> ⚠️ **性能说明**: 这个脚本对读取超大 GeoJSON 做了首级边界快速提取优化，无论几百 MB 的 `geojson` 都能在单张秒级请求完瓦片。在提取最终影像（精裁切）这一步，才会进行详细形状提取。

> ⚠️ **注意**: 请确保输入的 GeoJSON 的空间几何体存在且具有正确的经纬度 (EPSG:4326/WGS84) 投影信息。
