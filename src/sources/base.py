import os
import random
import time
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor, as_completed
from io import BytesIO

import numpy as np
import requests
from PIL import Image


class BaseSource(ABC):
    """
    Base class for generic imagery sources.

    Supports two common fetch modes:
    1. xyz               -> standard {z}/{y}/{x} tile services
    2. mapserver_export  -> ArcGIS MapServer export endpoint
    """

    WEB_MERCATOR_HALF_WORLD = 20037508.342789244
    TILE_SIZE = 256

    def __init__(self):
        self.headers = self.get_headers()
        self.zoom_level = self.get_zoom_level()
        self.url_template = self.get_url_template()

    @abstractmethod
    def get_url_template(self):
      return None

    @abstractmethod
    def get_zoom_level(self):
        pass

    def get_headers(self):
        return {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            )
        }

    def get_fetch_mode(self):
        return "xyz"

    def get_timeout(self):
        return 15

    def get_max_workers(self):
        return 4

    def get_retry_times(self):
        return 3

    def get_random_sleep_range(self):
        return 0.1, 0.3

    def get_export_format(self):
        return "png32"

    def get_export_transparent(self):
        return True

    def get_export_extra_params(self):
        return {}

    def get_service_url(self):
        if "/tile/" in self.url_template:
            return self.url_template.split("/tile/")[0]
        return self.url_template

    def get_compliance_info(self):
        return {
            "verified_for_public_dataset_release": False,
            "redistribution_allowed": False,
            "license_name": "UNVERIFIED",
            "license_url": None,
            "provider": None,
            "source_url": self.get_service_url(),
            "attribution": None,
            "notes": (
                "This source has not been audited for public dataset redistribution. "
                "Use only for internal experiments unless you have separately verified its terms."
            ),
        }

    def get_compliance_info_for_bounds(self, bounds_4326):
        del bounds_4326
        return self.get_compliance_info()

    def is_verbose(self):
        return os.environ.get("BH_VERBOSE_DEBUG", "0") == "1"

    def _vprint(self, msg):
        if self.is_verbose():
            print(msg)

    def _build_tile_url(self, tx, ty):
        return self.get_url(tx, ty, self.zoom_level)
    def _resolution_meters_per_pixel(self):
        return (
            2.0 * self.WEB_MERCATOR_HALF_WORLD
        ) / (self.TILE_SIZE * (2 ** self.zoom_level))

    def _global_pixel_x_to_mercator_x(self, px):
        res = self._resolution_meters_per_pixel()
        return px * res - self.WEB_MERCATOR_HALF_WORLD

    def _global_pixel_y_to_mercator_y(self, py):
        res = self._resolution_meters_per_pixel()
        return self.WEB_MERCATOR_HALF_WORLD - py * res

    def get_url(self, x, y, z):
       if self.url_template is None:
            raise NotImplementedError("This source must implement get_url(x, y, z)")
       return self.url_template.format(x=x, y=y, z=z)

    def _fetch_one_tile(self, session, tx, ty):
        url = self._build_tile_url(tx, ty)
        retry_times = self.get_retry_times()
        timeout = self.get_timeout()
        sleep_min, sleep_max = self.get_random_sleep_range()

        self._vprint(f"[tile try] ({tx}, {ty}) -> {url}")

        for attempt in range(retry_times):
            try:
                time.sleep(random.uniform(sleep_min, sleep_max))
                response = session.get(url, timeout=timeout)

                if response.status_code == 200:
                    try:
                        img = Image.open(BytesIO(response.content)).convert("RGB")
                        self._vprint(f"[tile ok] ({tx}, {ty}) status=200")
                        return tx, ty, img, 200
                    except Exception as e:
                        self._vprint(f"[tile decode fail] ({tx}, {ty}) -> {url} | {e}")
                        return tx, ty, None, "decode_fail"

                if response.status_code == 429:
                    backoff = 2 * (attempt + 1)
                    self._vprint(f"[tile 429] ({tx}, {ty}) -> {url} | retry in {backoff}s")
                    time.sleep(backoff)
                    continue

                self._vprint(f"[tile fail] ({tx}, {ty}) status={response.status_code} -> {url}")
                return tx, ty, None, response.status_code

            except requests.RequestException as e:
                self._vprint(f"[tile exc] ({tx}, {ty}) -> {url} | attempt={attempt + 1} | {e}")
                if attempt < retry_times - 1:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                return tx, ty, None, "request_fail"

        return tx, ty, None, "unknown"

    def _fetch_image_for_grid_xyz(self, grid):
        min_tx = grid["global_x_start"] // self.TILE_SIZE
        max_tx = (grid["global_x_end"] - 1) // self.TILE_SIZE
        min_ty = grid["global_y_start"] // self.TILE_SIZE
        max_ty = (grid["global_y_end"] - 1) // self.TILE_SIZE

        pixel_size = grid["pixel_size"]
        stitched_image = Image.new("RGB", (pixel_size, pixel_size), (0, 0, 0))
        success_count = 0

        session = requests.Session()
        session.headers.update(self.headers)

        futures = []
        with ThreadPoolExecutor(max_workers=self.get_max_workers()) as executor:
            for tx in range(min_tx, max_tx + 1):
                for ty in range(min_ty, max_ty + 1):
                    futures.append(executor.submit(self._fetch_one_tile, session, tx, ty))

            for future in as_completed(futures):
                tx, ty, img, status = future.result()
                if img is None:
                    continue

                paste_x = tx * self.TILE_SIZE - grid["global_x_start"]
                paste_y = ty * self.TILE_SIZE - grid["global_y_start"]
                stitched_image.paste(img, (paste_x, paste_y))
                success_count += 1

        if success_count == 0:
            return None

        return stitched_image

    def _fetch_image_for_grid_mapserver_export(self, grid):
        service_url = self.get_service_url().rstrip("/")
        export_url = f"{service_url}/export"

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
            "format": self.get_export_format(),
            "transparent": "true" if self.get_export_transparent() else "false",
            "f": "image",
        }
        params.update(self.get_export_extra_params())

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

                        arr = np.array(img)
                        if arr.ndim == 3 and arr.shape[2] == 4:
                            alpha = arr[:, :, 3]
                            self._vprint(
                                f"[export alpha] min={alpha.min()}, max={alpha.max()}, "
                                f"valid={(alpha > 0).sum()}/{alpha.size}"
                            )

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

    def fetch_image_for_grid(self, grid):
        mode = self.get_fetch_mode()

        if mode == "xyz":
            return self._fetch_image_for_grid_xyz(grid)

        if mode == "mapserver_export":
            return self._fetch_image_for_grid_mapserver_export(grid)

        raise ValueError(f"Unknown fetch mode: {mode}")
