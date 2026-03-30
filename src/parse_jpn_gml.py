import geopandas as gpd
import pandas as pd
import os
import glob
import subprocess

def process_citygml():
    gml_dir = "data/raw/osaka_citygml/udx/bldg/"
    output_file = "data/raw/Japan_Osaka_buildings_full.geojson"
    temp_json = "data/raw/temp_chunk.json"
    
    gml_files = glob.glob(os.path.join(gml_dir, "*.gml"))
    if not gml_files:
        print(f"❌ 找不到 GML 文件！")
        return
        
    print(f"🚀 开始强力提炼 {len(gml_files)} 个大阪数据块...")
    gdf_list = []
    
    for i, file in enumerate(gml_files):
        print(f"⏳ 处理进度: {i+1}/{len(gml_files)} -> {os.path.basename(file)}")
        try:
            # 核心修正：加入 -nlt POLYGON
            subprocess.run([
                "ogr2ogr", "-f", "GeoJSON", temp_json, file,
                "-dim", "2",
                "-nlt", "POLYGON",
                "-skipfailures",
                "-select", "measuredHeight"
            ], check=True, stderr=subprocess.DEVNULL) # 隐藏烦人的警告
            
            gdf = gpd.read_file(temp_json)
            if 'measuredHeight' in gdf.columns:
                gdf = gdf.rename(columns={'measuredHeight': 'height'})
                gdf['height'] = pd.to_numeric(gdf['height'], errors='coerce')
                gdf = gdf.dropna(subset=['height', 'geometry']) # 确保形状和高度都在
                gdf = gdf[gdf['height'] > 0]
                gdf_list.append(gdf[['height', 'geometry']])
                print(f"  ✅ 成功捕获 {len(gdf)} 栋建筑！")
            
            if os.path.exists(temp_json):
                os.remove(temp_json)
        except Exception:
            continue
            
    if not gdf_list:
        print("😭 仍然无法提取。请尝试运行: sudo apt install gdal-bin")
        return
        
    print("\n🔄 正在合并并保存最终文件...")
    final_gdf = pd.concat(gdf_list, ignore_index=True).to_crs(epsg=4326)
    final_gdf.to_file(output_file, driver='GeoJSON')
    print(f"🎉 成功！大阪真值已保存: {output_file}")
    print(f"📊 总计收获: {len(final_gdf)} 栋高精度建筑！")

if __name__ == "__main__":
    process_citygml()