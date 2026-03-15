import math

def get_meters_per_pixel(zoom, latitude):
    """
    计算在给定 zoom 级别和当地纬度下，每一个像素代表多少物理米。
    公式来源：Web 墨卡托投影标准。
    """
    return (156543.03392 * math.cos(math.radians(latitude))) / (2 ** zoom)


def lnglat_to_global_pixel(lng, lat, zoom):
    """
    将经纬度转换为全球绝对像素坐标 (基于指定 zoom 级别)。
    原点在世界地图左上角 (经度 -180, 纬度 ~85.05)。
    返回 (pixel_x, pixel_y) 浮点数。
    """
    n = 2.0 ** zoom
    pixel_x = ((lng + 180.0) / 360.0) * n * 256.0
    lat_rad = math.radians(lat)
    pixel_y = (1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n * 256.0
    return pixel_x, pixel_y


def generate_city_grid(total_bounds, target_meters, zoom, latitude):
    """
    将城市的总边界框按 target_meters 步长切分为均匀的网格。
    
    参数:
        total_bounds: (min_lng, min_lat, max_lng, max_lat) 整个数据集的地理边界
        target_meters: 每个网格代表的物理宽度 (米)
        zoom: 当前使用的缩放级别
        latitude: 用于计算每像素代表多少米的参考纬度
    
    返回:
        grids: list of dict, 每个元素包含该网格的边界和像素信息
    """
    min_lng, min_lat, max_lng, max_lat = total_bounds
    mpp = get_meters_per_pixel(zoom, latitude)
    
    # 步长：target_meters 对应多少像素 (这就是每个网格在拼接画布上的像素宽/高)
    step_pixels = int(target_meters / mpp)
    
    # 把整个城市的左上角和右下角转换为全球像素坐标
    x_start, y_start = lnglat_to_global_pixel(min_lng, max_lat, zoom)  # 左上
    x_end, y_end = lnglat_to_global_pixel(max_lng, min_lat, zoom)      # 右下
    
    grids = []
    grid_id = 0
    
    # 按 step_pixels 步长逐行逐列切网格
    y = int(y_start)
    while y < int(y_end):
        x = int(x_start)
        while x < int(x_end):
            grids.append({
                'grid_id': grid_id,
                # 全局像素坐标的左上角和右下角
                'global_x_start': x,
                'global_y_start': y,
                'global_x_end': x + step_pixels,
                'global_y_end': y + step_pixels,
                'pixel_size': step_pixels,
            })
            grid_id += 1
            x += step_pixels
        y += step_pixels
    
    return grids