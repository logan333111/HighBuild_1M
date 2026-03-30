import math

# 【地理信息大管家】
# 所有的地理经纬度和像素坐标之间的数学换算都在这里
# 因为地球是圆的，但图片是平的，所以我们需要墨卡托投影把它压平计算

def get_meters_per_pixel(zoom, latitude):
    """
    【计算物理分辨率】
    计算在给定的缩放级别 (zoom) 和当前的地球维度 (latitude) 下，
    这张图片里的 1 个像素，代表真实世界里的多少米？
    
    原理：你在赤道（维度0）看和在极地看，同样一个1024x1024的瓦片覆盖的物理面积是不一样大的。
    返回值例子: 0.597米/像素 (代表这非常高清，车道线都能看见)
    """
    return (156543.03392 * math.cos(math.radians(latitude))) / (2 ** zoom)


def lnglat_to_global_pixel(lng, lat, zoom):
    """
    【经纬度 转换 全球绝对像素】
    就像一个超大的 2D 游戏地图，我们把整个世界铺平，假设整个世界图片非常大。
    这个函数用来问：在当前的放大倍数 (zoom) 下，给定的经度(lng)和纬度(lat)，在这个超大图片上的 X 和 Y 坐标是多少？
    """
    n = 2.0 ** zoom
    # 经度比较简单，线性映射过去 (-180 到 180 -> 0 到 整个世界的宽度)
    pixel_x = ((lng + 180.0) / 360.0) * n * 256.0
    
    # 纬度比较复杂，因为墨卡托投影越往两极拉伸越大，所以用反双曲正弦和平移来算
    lat_rad = math.radians(lat)
    pixel_y = (1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n * 256.0
    return pixel_x, pixel_y


def generate_city_grid(total_bounds, target_meters, zoom, latitude):
    """
    【城市网格划分器】
    当你想处理一个巨大的城市(比如有75万栋房子的哥本哈根)，你不可能一次性把它全塞进内存。
    所以我们要把它像切豆腐一样，切成一个个比如 256米 x 256米 的小方块，这叫做“网格 (Grid)”。
    每一个网格会生成一张 1024x1024 像素的图片和对应标签。
    
    参数:
        total_bounds: (最西经度, 最南纬度, 最东经度, 最北纬度) 整个城市的包干范围
        target_meters: 每一个豆腐块的真实物理长宽，比如 256 米
        zoom: 你要用的影像清晰度 (清晰度不同，网格在图片上的占比像素也不同)
        latitude: 中心点的纬度，用来校准比例的
    """
    min_lng, min_lat, max_lng, max_lat = total_bounds
    
    # 首先问一下，当前这个城市纬度下，1个像素等于多少米
    mpp = get_meters_per_pixel(zoom, latitude)
    
    # 知道了 1个像素等于 mpp 米，那么你想切 256 米的块，那这个块在全局地图上应该是多少个像素？
    # step_pixels = 256 / 0.597 = 428 像素
    step_pixels = int(target_meters / mpp)
    
    # 获取城市左上角和右下角在全球大地图上的绝对像素位置
    x_start, y_start = lnglat_to_global_pixel(min_lng, max_lat, zoom)  # 左上点
    x_end, y_end = lnglat_to_global_pixel(max_lng, min_lat, zoom)      # 右下点
    
    grids = []
    grid_id = 0
    
    # 开始切豆腐！从最上面的一排开始往下切 (y 轴)
    y = int(y_start)
    while y < int(y_end):
        # 每一排里面从左到右切 (x 轴)
        x = int(x_start)
        while x < int(x_end):
            # 将切下来的每一个网格的数据装起来，做成任务包交给后面的模块
            grids.append({
                'grid_id': grid_id,                 # 这个网格的专属流水号
                'global_x_start': x,                # 这个网格在全球地图上从哪儿开始 (X)
                'global_y_start': y,                # 这个网格在全球地图上从哪儿开始 (Y)
                'global_x_end': x + step_pixels,    # 到哪儿结束 (X)
                'global_y_end': y + step_pixels,    # 到哪儿结束 (Y)
                'pixel_size': step_pixels,          # 这个网格在拼图画板上该画多大
            })
            grid_id += 1
            x += step_pixels # 往右移动一个步长
        y += step_pixels # 处理完一行，往下移动一行
    
    # 最终返回所有切好的任务包
    return grids