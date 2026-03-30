import argparse
import mercantile

def tile_to_lnglat(tile_name):
    """
    【瓦片探索器小工具】
    因为我们在测试或者看日志的时候，经常只能看到一些类似 16_35073_20905 这样的代号（Z_X_Y 瓦片号）。
    你看到这个号，根本不知道它到底代表地球上的什么地方。
    这个脚本就是帮你把这串神秘代号翻译成“人话”(经纬度)，并且直接生成一个 Google Earth 的传送门，点击就能飞过去看！
    """
    try:
        # 把类似 "16_35073_20905" 拆开，分别拿到 Z(缩放级), X(列号), Y(行号)
        parts = tile_name.split('_')
        if len(parts) != 3:
            raise ValueError("需要 Z_X_Y 三个部分，用下划线连接哦~")
        
        z = int(parts[0])
        x = int(parts[1])
        y = int(parts[2])

        # mercantile 是处理网络地图的标准库，我们可以直接用它查出这个瓦片的经纬度外框
        bounds = mercantile.bounds(x, y, z)
        
        # 算出这个框的正中心，也就是经度(lng)和纬度(lat)
        center_lng = (bounds.west + bounds.east) / 2.0
        center_lat = (bounds.north + bounds.south) / 2.0
        
        print(f"\n================ 瓦片 {tile_name} ================")
        print(f"🌍 这块瓦片的中心点位于:")
        print(f"  经度 (Lng): {center_lng:.6f}")
        print(f"  纬度 (Lat): {center_lat:.6f}")
        
        # 为了让你在 Google Earth 点进去看的时候高度正合适，根据 Z 级别简单估算一下相机高度
        elevation = 600 * (2 ** (16 - z))
        
        # 【彩蛋】这个链接可以直接在浏览器打开，谷歌地球会自动飞到这个地点，超级爽
        print(f"✅ Google Earth 直达传送门 (点击直达): https://earth.google.com/web/@{center_lat:.6f},{center_lng:.6f},{elevation:.1f}d")
        
        print(f"\n📐 瓦片的绝对物理边界框是:")
        print(f"  最西边 (West):  {bounds.west:.6f}")
        print(f"  最东边 (East):  {bounds.east:.6f}")
        print(f"  最南边 (South): {bounds.south:.6f}")
        print(f"  最北边 (North): {bounds.north:.6f}")
        print("====================================================\n")

    except Exception as e:
        print(f"❌ 哎呀，出错了: {e}。 \n正确用法是这样的: 比如想查 16级的，X是35073，Y是20905，你就输入 16_35073_20905")

if __name__ == "__main__":
    # 解析你在命令行(黑框框)里输入的字
    parser = argparse.ArgumentParser(description="这是一个把瓦片神秘代号翻译成地球真实经纬度的小魔法棒~")
    parser.add_argument('tile', type=str, help="请输入瓦片名称，例如: 16_35073_20905")
    args = parser.parse_args()
    
    # 启动转换
    tile_to_lnglat(args.tile)
