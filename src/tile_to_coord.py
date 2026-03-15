import argparse
import mercantile

def tile_to_lnglat(tile_name):
    try:
        parts = tile_name.split('_')
        if len(parts) != 3:
            raise ValueError("需要 Z_X_Y 三个部分")
        
        z = int(parts[0])
        x = int(parts[1])
        y = int(parts[2])

        # 使用 mercantile 获取该瓦片的边界
        bounds = mercantile.bounds(x, y, z)
        
        # 计算中心点的经纬度
        center_lng = (bounds.west + bounds.east) / 2.0
        center_lat = (bounds.north + bounds.south) / 2.0
        
        print(f"\n================ 瓦片 {tile_name} ================")
        print(f"🌍 瓦片中心点经纬度:")
        print(f"  经度 (Lng): {center_lng:.6f}")
        print(f"  纬度 (Lat): {center_lat:.6f}")
        # 直接给定一个相对固定的舒服的相机高度，或者按照 16 级给出 500-800 的建议值
        elevation = 600 * (2 ** (16 - z))
        print(f"✅ Google Earth 直达链接: https://earth.google.com/web/@{center_lat:.6f},{center_lng:.6f},{elevation:.1f}d")
        
        print(f"\n📐 瓦片物理边界:")
        print(f"  西边界 (West):  {bounds.west:.6f}")
        print(f"  东边界 (East):  {bounds.east:.6f}")
        print(f"  南边界 (South): {bounds.south:.6f}")
        print(f"  北边界 (North): {bounds.north:.6f}")
        print("====================================================\n")

    except Exception as e:
        print(f"❌ 错误: {e}。 请使用格式 Z_X_Y (例如: 16_35073_20905)")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="转换瓦片名称为经纬度信息")
    parser.add_argument('tile', type=str, help="瓦片名称，例如: 16_35073_20905")
    args = parser.parse_args()
    
    tile_to_lnglat(args.tile)
