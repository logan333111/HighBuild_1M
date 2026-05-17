import math
import os
import random
import shutil
import time
import zipfile
from pathlib import Path

import requests
from PIL import Image

from .base import BaseSource


class HKGSource(BaseSource):
    """
    Hong Kong source backed by the DATA.GOV.HK Digital Orthophoto DOP5000
    GeoTIFF resource.

    DOP5000 is not exposed as a normal XYZ imagery tile endpoint. The CSDI
    service publishes the sheet index and each sheet's public DOWNLOAD_LINK.
    This source keeps the existing project interface by querying the index,
    downloading the needed GeoTIFF sheets into a local cache, and rendering the
    requested Web Mercator grid from those files.
    """

    DATASET_URL = (
        "https://data.gov.hk/en-data/dataset/"
        "hk-landsd-openmap-development-hkms-digital-dop5k"
    )
    TERMS_URL = "https://data.gov.hk/en/terms-and-conditions"
    INDEX_QUERY_URL = (
        "https://portal.csdi.gov.hk/server/rest/services/common/"
        "landsd_rcd_1637306839277_11815/MapServer/0/query"
    )

    WEB_MERCATOR_CRS = "EPSG:3857"
    WGS84_CRS = "EPSG:4326"
    HK80_CRS = "EPSG:2326"

    INDEX_FIELDS = (
        "SHEETNO,YEAR_OF_RELEASE,DATE_OF_PHOTOGRAPH,DOWNLOAD_LINK"
    )
    INDEX_PAGE_SIZE = 2000

    def __init__(self):
        super().__init__()

        repo_root = Path(__file__).resolve().parents[2]
        self.cache_dir = repo_root / "data" / "interim" / "tiles" / "hkg_dop5000"
        self.sheet_cache_dir = self.cache_dir / "sheets"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.sheet_cache_dir.mkdir(parents=True, exist_ok=True)

        self._index_features = None
        self._bounds_index_cache = {}

    def get_url_template(self):
        return self.DATASET_URL

    def get_zoom_level(self):


        return 19

    def get_headers(self):
        headers = super().get_headers()
        headers.update(
            {
                "Accept": "application/json,image/*,*/*",
                "Referer": self.DATASET_URL,
                "User-Agent": (
                    "Mozilla/5.0 (X11; Linux x86_64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
            }
        )
        return headers

    def get_timeout(self):
        return 30

    def get_sheet_download_timeout(self):


        return 3600

    def get_sheet_download_retry_times(self):

        return 50

    def get_compliance_info(self):
        return {
            "verified_for_public_dataset_release": True,
            "redistribution_allowed": True,
            "license_name": "DATA.GOV.HK Terms and Conditions of Use",
            "license_url": self.TERMS_URL,
            "provider": "Lands Department, HKSAR Government",
            "source_url": self.DATASET_URL,
            "attribution": (
                "Digital Orthophoto DOP5000, Lands Department, "
                "HKSAR Government, via DATA.GOV.HK"
            ),
            "notes": (
                "DOP5000 is distributed as DATA.GOV.HK open data. "
                "Generated images should retain source attribution."
            ),
        }

    def _grid_bbox_3857(self, grid):
        minx = self._global_pixel_x_to_mercator_x(grid["global_x_start"])
        maxx = self._global_pixel_x_to_mercator_x(grid["global_x_end"])
        maxy = self._global_pixel_y_to_mercator_y(grid["global_y_start"])
        miny = self._global_pixel_y_to_mercator_y(grid["global_y_end"])
        return minx, miny, maxx, maxy

    def _global_pixel_to_lnglat(self, px, py):
        world_size = self.TILE_SIZE * (2 ** self.zoom_level)
        lng = (px / world_size) * 360.0 - 180.0
        lat_rad = math.atan(math.sinh(math.pi * (1.0 - 2.0 * py / world_size)))
        lat = math.degrees(lat_rad)
        return lng, lat

    def _grid_bbox_4326(self, grid):
        min_lng, max_lat = self._global_pixel_to_lnglat(
            grid["global_x_start"],
            grid["global_y_start"],
        )
        max_lng, min_lat = self._global_pixel_to_lnglat(
            grid["global_x_end"],
            grid["global_y_end"],
        )
        return min_lng, min_lat, max_lng, max_lat

    @staticmethod
    def _bbox_intersects(a, b):
        return not (
            a[2] <= b[0]
            or a[0] >= b[2]
            or a[3] <= b[1]
            or a[1] >= b[3]
        )

    @staticmethod
    def _safe_sheet_name(sheet_no):
        return "".join(
            c if c.isalnum() or c in ("-", "_", ".") else "_"
            for c in sheet_no
        )

    def _request_json(self, params):
        last_error = None
        for attempt in range(self.get_retry_times()):
            try:
                response = requests.get(
                    self.INDEX_QUERY_URL,
                    params=params,
                    headers=self.headers,
                    timeout=self.get_timeout(),
                )
                response.raise_for_status()
                data = response.json()
                if "error" in data:
                    raise RuntimeError(f"CSDI query error: {data['error']}")
                return data
            except (requests.RequestException, ValueError, RuntimeError) as exc:
                last_error = exc
                if attempt < self.get_retry_times() - 1:
                    time.sleep(1.5 * (attempt + 1))

        raise last_error

    def _feature_bbox_4326(self, feature):
        geometry = feature.get("geometry") or {}

        if "rings" in geometry:
            xs = []
            ys = []
            for ring in geometry["rings"]:
                for x, y in ring:
                    xs.append(float(x))
                    ys.append(float(y))
            if xs and ys:
                return min(xs), min(ys), max(xs), max(ys)

        if {"xmin", "ymin", "xmax", "ymax"}.issubset(geometry):
            return (
                float(geometry["xmin"]),
                float(geometry["ymin"]),
                float(geometry["xmax"]),
                float(geometry["ymax"]),
            )

        return None

    def _normalise_index_feature(self, feature, fallback_bbox=None):
        attrs = feature.get("attributes") or {}
        sheet_no = attrs.get("SHEETNO")
        download_link = attrs.get("DOWNLOAD_LINK")
        bbox = self._feature_bbox_4326(feature) or fallback_bbox

        if not sheet_no or not download_link or bbox is None:
            return None

        return {
            "sheet_no": sheet_no,
            "download_link": download_link,
            "year_of_release": attrs.get("YEAR_OF_RELEASE"),
            "date_of_photograph": attrs.get("DATE_OF_PHOTOGRAPH"),
            "bbox_4326": bbox,
        }

    def _load_index_features(self):
        if self._index_features is not None:
            return self._index_features

        features = []
        offset = 0

        while True:
            params = {
                "where": "1=1",
                "outFields": self.INDEX_FIELDS,
                "returnGeometry": "true",
                "outSR": 4326,
                "f": "json",
                "resultOffset": offset,
                "resultRecordCount": self.INDEX_PAGE_SIZE,
            }

            data = self._request_json(params)
            page = data.get("features", [])

            for feature in page:
                item = self._normalise_index_feature(feature)
                if item is not None:
                    features.append(item)

            if not data.get("exceededTransferLimit") or not page:
                break

            offset += len(page)

        self._index_features = features
        self._vprint(f"[hkg dop5000] loaded {len(features)} index features")
        return features

    def _query_index_for_bounds(self, bbox_4326):
        min_lng, min_lat, max_lng, max_lat = bbox_4326
        params = {
            "geometry": f"{min_lng},{min_lat},{max_lng},{max_lat}",
            "geometryType": "esriGeometryEnvelope",
            "inSR": 4326,
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": self.INDEX_FIELDS,
            "returnGeometry": "false",
            "f": "json",
            "resultRecordCount": self.INDEX_PAGE_SIZE,
        }

        data = self._request_json(params)
        matches = []
        for feature in data.get("features", []):
            item = self._normalise_index_feature(feature, fallback_bbox=bbox_4326)
            if item is not None:
                matches.append(item)
        return matches

    def _find_sheets_for_bounds(self, bbox_4326):
        cache_key = tuple(round(value, 8) for value in bbox_4326)
        if cache_key in self._bounds_index_cache:
            return self._bounds_index_cache[cache_key]

        try:
            matches = self._query_index_for_bounds(bbox_4326)
        except Exception as direct_exc:
            self._vprint(f"[hkg dop5000] bbox index query failed: {direct_exc}")
            features = self._load_index_features()
            matches = [
                item
                for item in features
                if self._bbox_intersects(item["bbox_4326"], bbox_4326)
            ]

        unique = {}
        for item in matches:
            unique[item["sheet_no"]] = item

        sheets = [unique[key] for key in sorted(unique)]
        self._bounds_index_cache[cache_key] = sheets
        return sheets

    def _locate_cached_raster(self, sheet_dir):
        for suffix in ("*.tif", "*.tiff", "*.TIF", "*.TIFF"):
            rasters = sorted(sheet_dir.rglob(suffix))
            if rasters:
                return rasters[0]
        return None

    def _locate_cached_archive(self, sheet_dir):
        archives = sorted(sheet_dir.glob("*.zip"))
        if archives:
            return archives[0]
        return None

    def _extract_or_register_download(self, raw_path, sheet_dir, safe_name):
        cached = self._locate_cached_raster(sheet_dir)
        if cached is not None:
            return cached

        if zipfile.is_zipfile(raw_path):
            extract_dir = sheet_dir / "extracted"
            extract_dir.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(raw_path) as zf:
                for member in zf.infolist():
                    if member.is_dir():
                        continue
                    target = extract_dir / Path(member.filename).name
                    with zf.open(member) as source, target.open("wb") as output:
                        shutil.copyfileobj(source, output)
            return self._locate_cached_raster(sheet_dir)

        final_path = sheet_dir / f"{safe_name}.tif"
        os.replace(raw_path, final_path)
        return final_path

    def _validate_zip_file(self, zip_path, sheet_no):
            if not zip_path.exists():
                raise RuntimeError(f"zip file does not exist for {sheet_no}: {zip_path}")

            if zip_path.stat().st_size <= 0:
                raise RuntimeError(f"zip file is empty for {sheet_no}: {zip_path}")

            if not zipfile.is_zipfile(zip_path):
                raise RuntimeError(
                    f"downloaded file is not a valid zip for {sheet_no}: "
                    f"{zip_path}, size={zip_path.stat().st_size}"
                )

            with zipfile.ZipFile(zip_path) as zf:
                bad_member = zf.testzip()
                if bad_member is not None:
                    raise RuntimeError(
                        f"corrupted zip member in {sheet_no}: {bad_member}"
            )

    def _ensure_sheet_raster(self, sheet):
            sheet_no = sheet["sheet_no"]
            safe_name = self._safe_sheet_name(sheet_no)
            sheet_dir = self.sheet_cache_dir / safe_name
            sheet_dir.mkdir(parents=True, exist_ok=True)

            cached = self._locate_cached_raster(sheet_dir)
            if cached is not None:
                return cached

            cached_archive = self._locate_cached_archive(sheet_dir)
            if cached_archive is not None:
                try:
                    self._validate_zip_file(cached_archive, sheet_no)
                    raster_path = self._extract_or_register_download(
                        cached_archive,
                        sheet_dir,
                        safe_name,
                    )
                    if raster_path is not None:
                        return raster_path
                except Exception as exc:
                    self._vprint(
                        f"[hkg dop5000] cached archive invalid {sheet_no}: {exc}"
                    )
                    try:
                        cached_archive.unlink()
                    except OSError:
                        pass


            archive_path = sheet_dir / f"{safe_name}.zip"
            part_path = sheet_dir / f"{safe_name}.zip.part"

            self._vprint(f"[hkg dop5000] downloading {sheet_no} with resume support")

            last_error = None
            last_report_mb = -1

            for attempt in range(self.get_sheet_download_retry_times()):
                try:
                    if attempt == 0:
                        time.sleep(random.uniform(0.5, 1.5))
                    else:
                        wait_sec = min(10 + attempt * 10, 180)
                        self._vprint(
                            f"[hkg dop5000] retry {sheet_no}, "
                            f"attempt={attempt + 1}/"
                            f"{self.get_sheet_download_retry_times()}, "
                            f"sleep={wait_sec}s"
                        )
                        time.sleep(wait_sec)

                    resume_from = part_path.stat().st_size if part_path.exists() else 0

                    headers = dict(self.headers)
                    if resume_from > 0:
                        headers["Range"] = f"bytes={resume_from}-"
                        self._vprint(
                            f"[hkg dop5000] resume {sheet_no} from "
                            f"{resume_from / 1024 / 1024:.2f} MB"
                        )

                    with requests.get(
                        sheet["download_link"],
                        headers=headers,
                        stream=True,
                        timeout=(120, self.get_sheet_download_timeout()),
                    ) as response:
                        response.raise_for_status()

                        content_type = response.headers.get("Content-Type", "")
                        disposition = response.headers.get("Content-Disposition", "")
                        content_length = response.headers.get("Content-Length")
                        content_range = response.headers.get("Content-Range")

                        self._vprint(
                            f"[hkg dop5000] {sheet_no} status={response.status_code} "
                            f"type={content_type} length={content_length} "
                            f"range={content_range} disposition={disposition}"
                        )


                        if resume_from > 0 and response.status_code == 200:
                            self._vprint(
                                f"[hkg dop5000] server ignored Range for {sheet_no}; "
                                f"restart from zero"
                            )
                            part_path.unlink(missing_ok=True)
                            resume_from = 0

                        mode = "ab" if resume_from > 0 and response.status_code == 206 else "wb"

                        with part_path.open(mode) as handle:
                            for chunk in response.iter_content(chunk_size=1024 * 1024):
                                if not chunk:
                                    continue

                                handle.write(chunk)

                                current_size = part_path.stat().st_size
                                current_mb = int(current_size / 1024 / 1024)


                                if current_mb >= last_report_mb + 20:
                                    last_report_mb = current_mb
                                    self._vprint(
                                        f"[hkg dop5000] {sheet_no} downloaded "
                                        f"{current_size / 1024 / 1024:.1f} MB"
                                    )

                    current_size = part_path.stat().st_size if part_path.exists() else 0
                    if current_size == 0:
                        raise RuntimeError(f"empty DOP5000 download for {sheet_no}")


                    try:
                        self._validate_zip_file(part_path, sheet_no)
                    except Exception as zip_exc:
                        last_error = zip_exc
                        self._vprint(
                            f"[hkg dop5000] partial zip not ready {sheet_no}: "
                            f"size={current_size / 1024 / 1024:.2f} MB, error={zip_exc}"
                        )
                        continue

                    os.replace(part_path, archive_path)

                    raster_path = self._extract_or_register_download(
                        archive_path,
                        sheet_dir,
                        safe_name,
                    )

                    if raster_path is None:
                        raise RuntimeError(
                            f"no GeoTIFF found in DOP5000 download {sheet_no}"
                        )

                    self._vprint(
                        f"[hkg dop5000] prepared {sheet_no}: {raster_path}"
                    )

                    return raster_path

                except Exception as exc:
                    last_error = exc


                    current_size = part_path.stat().st_size if part_path.exists() else 0
                    self._vprint(
                        f"[hkg dop5000] download failed {sheet_no} "
                        f"attempt={attempt + 1}/"
                        f"{self.get_sheet_download_retry_times()} "
                        f"bytes={current_size} error={exc}"
                    )

            raise RuntimeError(
                f"DOP5000 sheet download failed after resume retries: "
                f"sheet={sheet_no}, url={sheet['download_link']}, "
                f"last_error={last_error}"
            )
    def _import_rasterio_stack(self):
        try:
            import numpy as np
            import rasterio
            from rasterio.enums import Resampling
            from rasterio.merge import merge
            from rasterio.transform import from_bounds
            from rasterio.warp import reproject, transform_bounds
        except ImportError as exc:
            raise RuntimeError(
                "HKG DOP5000 source needs rasterio and numpy to crop/reproject "
                "GeoTIFF files. Install them in the active environment before "
                "running source=hkg."
            ) from exc

        return np, rasterio, Resampling, merge, from_bounds, reproject, transform_bounds

    def _render_grid_from_rasters(self, grid, raster_paths):
        (
            np,
            rasterio,
            Resampling,
            merge,
            from_bounds,
            reproject,
            transform_bounds,
        ) = self._import_rasterio_stack()

        minx_3857, miny_3857, maxx_3857, maxy_3857 = self._grid_bbox_3857(grid)
        hk80_bounds = transform_bounds(
            self.WEB_MERCATOR_CRS,
            self.HK80_CRS,
            minx_3857,
            miny_3857,
            maxx_3857,
            maxy_3857,
            densify_pts=21,
        )

        datasets = []
        try:
            datasets = [rasterio.open(path) for path in raster_paths]
            if not datasets:
                return None

            first = datasets[0]
            src_crs = first.crs or self.HK80_CRS
            src_nodata = first.nodata
            band_count = min(3, first.count)
            if band_count < 1:
                return None

            indexes = list(range(1, band_count + 1))
            mosaic, mosaic_transform = merge(
                datasets,
                bounds=hk80_bounds,
                indexes=indexes,
                nodata=src_nodata,
                resampling=Resampling.bilinear,
            )

            if mosaic.size == 0:
                return None

            if mosaic.shape[0] == 1:
                mosaic = np.repeat(mosaic, 3, axis=0)
            elif mosaic.shape[0] == 2:
                mosaic = np.concatenate([mosaic, mosaic[:1]], axis=0)
            else:
                mosaic = mosaic[:3]

            pixel_size = int(grid["pixel_size"])
            dst = np.zeros((3, pixel_size, pixel_size), dtype=mosaic.dtype)
            dst_transform = from_bounds(
                minx_3857,
                miny_3857,
                maxx_3857,
                maxy_3857,
                pixel_size,
                pixel_size,
            )

            for band_idx in range(3):
                reproject(
                    source=mosaic[band_idx],
                    destination=dst[band_idx],
                    src_transform=mosaic_transform,
                    src_crs=src_crs,
                    dst_transform=dst_transform,
                    dst_crs=self.WEB_MERCATOR_CRS,
                    resampling=Resampling.bilinear,
                    src_nodata=src_nodata,
                    dst_nodata=0,
                )

            if not np.any(dst):
                return None

            arr = np.nan_to_num(dst.astype("float32", copy=False))
            if arr.max() > 255:
                arr = arr / 257.0 if arr.max() <= 65535 else arr * (255.0 / arr.max())

            rgb = np.moveaxis(np.clip(arr, 0, 255).astype("uint8"), 0, -1)
            return Image.fromarray(rgb, "RGB")

        finally:
            for dataset in datasets:
                dataset.close()

    def fetch_image_for_grid(self, grid):
        bbox_4326 = self._grid_bbox_4326(grid)
        sheets = self._find_sheets_for_bounds(bbox_4326)
        if not sheets:
            self._vprint(f"[hkg dop5000] no sheets for bbox={bbox_4326}")
            return None

        raster_paths = []
        errors = []
        for sheet in sheets:
            try:
                raster_paths.append(self._ensure_sheet_raster(sheet))
            except Exception as exc:
                errors.append(f"{sheet['sheet_no']}: {exc}")
                self._vprint(
                    f"[hkg dop5000] failed to prepare {sheet['sheet_no']}: {exc}"
                )

        if not raster_paths:
            raise RuntimeError(
                "DOP5000 sheets were found, but none could be prepared. "
                + " | ".join(errors)
            )

        image = self._render_grid_from_rasters(grid, raster_paths)
        if image is None:
            raise RuntimeError(
                "DOP5000 raster render returned empty image for sheets: "
                + ", ".join(str(path) for path in raster_paths)
            )

        return image