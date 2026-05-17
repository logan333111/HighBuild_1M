from io import BytesIO
import random
import time

import requests
from PIL import Image
from pyproj import CRS, Transformer

from sources.base import BaseSource


class CapeTownSource(BaseSource):
    def get_zoom_level(self):
        return 18

    def get_fetch_mode(self):
        return "mapserver_export"

    def get_url_template(self):
        return (
            "https://cityimg.capetown.gov.za/erdas-iws/esri/"
            "GeoSpatial%20Datasets/rest/services/"
            "Aerial%20Imagery_Aerial%20Imagery%202024/MapServer"
        )

    def get_service_url(self):
        return (
            "https://cityimg.capetown.gov.za/erdas-iws/esri/"
            "GeoSpatial%20Datasets/rest/services/"
            "Aerial%20Imagery_Aerial%20Imagery%202024/MapServer"
        )

    def get_timeout(self):
        return 30

    def get_retry_times(self):
        return 5

    def get_random_sleep_range(self):
        return 0.3, 0.8

    def fetch_image_for_grid(self, grid):
        service_url = self.get_service_url().rstrip("/")
        export_url = f"{service_url}/export"
        pixel_size = int(grid["pixel_size"])


        minx_3857 = self._global_pixel_x_to_mercator_x(grid["global_x_start"])
        maxx_3857 = self._global_pixel_x_to_mercator_x(grid["global_x_end"])
        maxy_3857 = self._global_pixel_y_to_mercator_y(grid["global_y_start"])
        miny_3857 = self._global_pixel_y_to_mercator_y(grid["global_y_end"])


        cape_lo19 = CRS.from_proj4(
            "+proj=tmerc +lat_0=0 +lon_0=19 +k=1 "
            "+x_0=0 +y_0=0 +ellps=WGS84 +units=m +no_defs"
        )
        transformer = Transformer.from_crs("EPSG:3857", cape_lo19, always_xy=True)

        minx_srv, miny_srv = transformer.transform(minx_3857, miny_3857)
        maxx_srv, maxy_srv = transformer.transform(maxx_3857, maxy_3857)

        xmin = min(minx_srv, maxx_srv)
        xmax = max(minx_srv, maxx_srv)
        ymin = min(miny_srv, maxy_srv)
        ymax = max(miny_srv, maxy_srv)

        params = {
            "bbox": f"{xmin},{ymin},{xmax},{ymax}",
            "bboxSR": 20482,
            "imageSR": 20482,
            "size": f"{pixel_size},{pixel_size}",
            "format": "png24",
            "transparent": "true",
            "f": "image",
        }

        retry_times = self.get_retry_times()
        timeout = self.get_timeout()
        sleep_min, sleep_max = self.get_random_sleep_range()

        self._vprint(
            f"[export] url={export_url} bbox={params['bbox']} size={params['size']}"
        )

        session = requests.Session()
        session.headers.update(self.headers)

        for attempt in range(retry_times):
            try:
                time.sleep(random.uniform(sleep_min, sleep_max))
                response = session.get(export_url, params=params, timeout=timeout)

                if response.status_code == 200:
                    try:
                        img = Image.open(BytesIO(response.content))
                        self._vprint(f"[export img] mode={img.mode}, size={img.size}")

                        if img.mode != "RGBA":
                            img = img.convert("RGBA")

                        self._vprint("[export ok] status=200")
                        return img
                    except Exception as e:
                        self._vprint(f"[export decode fail] {response.url} | {e}")
                        return None

                if response.status_code == 429:
                    backoff = 2 * (attempt + 1)
                    self._vprint(f"[export 429] retry in {backoff}s | {response.url}")
                    time.sleep(backoff)
                    continue

                self._vprint(f"[export fail] status={response.status_code} -> {response.url}")
                return None

            except requests.RequestException as e:
                self._vprint(f"[export exc] attempt={attempt + 1} | {e}")
                if attempt < retry_times - 1:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                return None

        return None