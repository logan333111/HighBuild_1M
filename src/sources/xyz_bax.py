from urllib.parse import urlencode
from pyproj import Transformer
from .base import BaseSource


class SaoPauloSource(BaseSource):
    def __init__(self):
        super().__init__()
        self.transformer = Transformer.from_crs("EPSG:3857", "EPSG:31983", always_xy=True)

    def get_url_template(self):
        return ""

    def get_zoom_level(self):
        return 19

    def get_headers(self):
        headers = super().get_headers()
        headers["Referer"] = "https://geosampa.prefeitura.sp.gov.br/"
        return headers

    def tile_xyz_to_bbox_3857(self, x, y, z):
        origin_shift = 20037508.342789244
        tile_size = 256
        resolution = (2 * origin_shift) / (tile_size * (2 ** z))
        tile_span = tile_size * resolution

        minx = -origin_shift + x * tile_span
        maxx = -origin_shift + (x + 1) * tile_span
        maxy = origin_shift - y * tile_span
        miny = origin_shift - (y + 1) * tile_span

        return minx, miny, maxx, maxy

    def get_url(self, x, y, z):
        minx_3857, miny_3857, maxx_3857, maxy_3857 = self.tile_xyz_to_bbox_3857(x, y, z)

        minx_31983, miny_31983 = self.transformer.transform(minx_3857, miny_3857)
        maxx_31983, maxy_31983 = self.transformer.transform(maxx_3857, maxy_3857)

        bbox = f"{minx_31983},{miny_31983},{maxx_31983},{maxy_31983}"

        params = {
            "service": "WMS",
            "version": "1.1.1",
            "request": "GetMap",
            "layers": "ORTO_RGB_2020",
            "styles": "",
            "format": "image/jpeg",
            "transparent": "false",
            "srs": "EPSG:31983",
            "width": 256,
            "height": 256,
            "bbox": bbox,
        }

        return "https://raster.geosampa.prefeitura.sp.gov.br/geoserver/geoportal/wms?" + urlencode(params)