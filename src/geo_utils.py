import math


def get_meters_per_pixel(zoom, latitude):
    """
    Compute physical resolution in meters per pixel for the given zoom and latitude.
    """
    return (156543.03392 * math.cos(math.radians(latitude))) / (2 ** zoom)


def lnglat_to_global_pixel(lng, lat, zoom):
    """
    Convert longitude and latitude into global Web Mercator pixel coordinates.
    """
    n = 2.0 ** zoom

    pixel_x = ((lng + 180.0) / 360.0) * n * 256.0


    lat_rad = math.radians(lat)
    pixel_y = (1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n * 256.0
    return pixel_x, pixel_y


def generate_city_grid(total_bounds, target_meters, zoom, latitude):
    """
    Generate grid tiles for a city area.

    total_bounds: (min_lng, min_lat, max_lng, max_lat)
    target_meters: tile size in meters
    zoom: zoom level for image resolution
    latitude: center latitude used for scaling
    """
    min_lng, min_lat, max_lng, max_lat = total_bounds


    mpp = get_meters_per_pixel(zoom, latitude)


    step_pixels = int(target_meters / mpp)


    x_start, y_start = lnglat_to_global_pixel(min_lng, max_lat, zoom)
    x_end, y_end = lnglat_to_global_pixel(max_lng, min_lat, zoom)

    grids = []
    grid_id = 0


    y = int(y_start)
    while y < int(y_end):
        x = int(x_start)
        while x < int(x_end):

            grids.append({
                'grid_id': grid_id,
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