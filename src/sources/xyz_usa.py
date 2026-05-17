from io import BytesIO
import random
import time

import requests
from PIL import Image

from .base import BaseSource


class USASource(BaseSource):
    SERVICE_URL = (
        "https://imagery.nationalmap.gov/arcgis/rest/services/"
        "USGSNAIPImagery/ImageServer"
    )
    DATASET_URL = (
        "https://www.usgs.gov/centers/eros/science/"
        "usgs-eros-archive-aerial-photography-national-agriculture-imagery-program-naip"
    )
    LICENSE_URL = "https://www.usa.gov/publicdomain/label/1.0/"

    def get_zoom_level(self):


        return 18

    def get_fetch_mode(self):
        return "imageserver_export"

    def get_url_template(self):
        return self.SERVICE_URL

    def get_service_url(self):
        return self.SERVICE_URL

    def get_timeout(self):
        return 30

    def get_retry_times(self):
        return 5

    def get_random_sleep_range(self):
        return 0.2, 0.6

    def get_headers(self):
        headers = super().get_headers()
        headers.update({
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Referer": "https://apps.nationalmap.gov/viewer/"
        })
        return headers

    def get_compliance_info(self):
        return {
            "verified_for_public_dataset_release": True,
            "redistribution_allowed": True,
            "license_name": "Public Domain / U.S. Government Work",
            "license_url": self.LICENSE_URL,
            "provider": "USGS / USDA Farm Service Agency",
            "source_url": self.SERVICE_URL,
            "dataset_url": self.DATASET_URL,
            "attribution": "USGS, USDA, The National Map: Orthoimagery",
            "notes": (
                "The USGS NAIP Imagery service states that The National Map "
                "Downloader provides free downloads of public-domain NAIP "
                "compressed orthoimagery for the conterminous United States."
            ),
        }

    def fetch_image_for_grid(self, grid):
        service_url = self.get_service_url().rstrip("/")
        export_url = f"{service_url}/exportImage"
        pixel_size = int(grid["pixel_size"])

        minx = self._global_pixel_x_to_mercator_x(grid["global_x_start"])
        maxx = self._global_pixel_x_to_mercator_x(grid["global_x_end"])
        maxy = self._global_pixel_y_to_mercator_y(grid["global_y_start"])
        miny = self._global_pixel_y_to_mercator_y(grid["global_y_end"])

        params = {
            "bbox": f"{minx},{miny},{maxx},{maxy}",
            "bboxSR": 3857,
            "imageSR": 3857,
            "size": f"{pixel_size},{pixel_size}",
            "format": "jpgpng",
            "transparent": "false",
            "renderingRule": '{"rasterFunction":"NaturalColor"}',
            "f": "image",
        }

        retry_times = self.get_retry_times()
        timeout = self.get_timeout()
        sleep_min, sleep_max = self.get_random_sleep_range()

        self._vprint(
            f"[naip exportImage] url={export_url} bbox={params['bbox']} "
            f"size={params['size']}"
        )

        session = requests.Session()
        session.headers.update(self.headers)

        for attempt in range(retry_times):
            try:
                time.sleep(random.uniform(sleep_min, sleep_max))
                response = session.get(export_url, params=params, timeout=timeout)

                if response.status_code == 200:
                    try:
                        img = Image.open(BytesIO(response.content)).convert("RGB")
                        self._vprint(f"[naip exportImage ok] mode={img.mode}, size={img.size}")
                        return img
                    except Exception as exc:
                        self._vprint(f"[naip decode fail] {response.url} | {exc}")
                        return None

                if response.status_code == 429:
                    backoff = 2 * (attempt + 1)
                    self._vprint(
                        f"[naip 429] retry in {backoff}s | {response.url}"
                    )
                    time.sleep(backoff)
                    continue

                self._vprint(
                    f"[naip exportImage fail] status={response.status_code} -> "
                    f"{response.url}"
                )
                return None

            except requests.RequestException as exc:
                self._vprint(f"[naip exportImage exc] attempt={attempt + 1} | {exc}")
                if attempt < retry_times - 1:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                return None

        return None
