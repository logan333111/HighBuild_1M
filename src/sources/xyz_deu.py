import time
import random
import requests
import io
from PIL import Image
from sources.base import BaseSource


class GermanySource(BaseSource):
    def __init__(self):
        super().__init__()

    def get_url_template(self):
        return "dynamic_router_mode"

    def get_zoom_level(self):
        return 19

    def get_compliance_info(self):
        return {
            "verified_for_public_dataset_release": False,
            "redistribution_allowed": False,
            "license_name": "PARTIALLY_VERIFIED",
            "license_url": None,
            "provider": "German state open-data providers",
            "source_url": None,
            "attribution": None,
            "notes": (
                "Germany routes to different state services. Compliance must be checked "
                "against the concrete state endpoint for the requested bounds."
            ),
        }

    def get_compliance_info_for_bounds(self, bounds_4326):
        min_lng, min_lat, max_lng, max_lat = bounds_4326
        center_lng = (min_lng + max_lng) / 2.0
        center_lat = (min_lat + max_lat) / 2.0
        state_config = self._get_state_wms_config(center_lng, center_lat)

        if not state_config:
            return {
                "verified_for_public_dataset_release": False,
                "redistribution_allowed": False,
                "license_name": "UNSUPPORTED",
                "license_url": None,
                "provider": None,
                "source_url": None,
                "attribution": None,
                "notes": (
                    "The requested bounds are outside the supported German source regions. "
                    "Only Frankfurt, Munich, and Berlin regions are supported."
                ),
            }

        if state_config["state_id"] == "berlin_brandenburg":
            return {
                "verified_for_public_dataset_release": True,
                "redistribution_allowed": True,
                "license_name": "Datenlizenz Deutschland - Namensnennung - Version 2.0",
                "license_url": "https://www.govdata.de/dl-de/by-2-0",
                "provider": "Landesvermessung und Geobasisinformation Brandenburg",
                "source_url": state_config["url"],
                "attribution": (
                    "© GeoBasis-DE/LGB, dl-de/by-2-0; "
                    "© Geoportal Berlin, dl-de/by-2-0 (Daten geändert)"
                ),
                "notes": (
                    "Verified against the official BB-BE DOP20c service metadata. "
                    "Berlin data requires the additional Geoportal Berlin attribution."
                ),
            }

        return {
            "verified_for_public_dataset_release": False,
            "redistribution_allowed": False,
            "license_name": "UNVERIFIED_STATE_LICENSE",
            "license_url": None,
            "provider": state_config.get("provider"),
            "source_url": state_config["url"],
            "attribution": None,
            "notes": (
                "This German state endpoint may be open data, but its redistribution notice "
                "has not been audited in this codebase yet."
            ),
        }

    def _get_state_wms_config(self, center_lng, center_lat):
        """
        German imagery source router for the three city sources used by this dataset:

          1. Frankfurt / Frankfurt
             - State: Hesse / Hesse
             - Layer: he_dop20_rgb

          2. Munich / Munich
             - State: Bavaria / Bavaria
             - Layer: by_dop20c

          3. Berlin / Berlin
             - Region: Berlin-Brandenburg / Berlin-Brandenburg
             - Layer: bebb_dop20c

        WMS version and BBOX axis order:
          - WMS 1.1.1:
            SRS=EPSG:4326
            BBOX = min_lon,min_lat,max_lon,max_lat

          - WMS 1.3.0 + EPSG:4326:
            CRS=EPSG:4326
            BBOX = min_lat,min_lon,max_lat,max_lon

          - WMS 1.3.0 + EPSG:3857:
            CRS=EPSG:3857
            BBOX = minx,miny,maxx,maxy
        """


        if 7.5 < center_lng < 10.5 and 49.0 < center_lat < 51.7:
            return {
                "state_id": "hesse",
                "provider": "Land Hessen",
                "url": "https://www.gds-srv.hessen.de/cgi-bin/lika-services/ogc-free-images.ows",
                "layer": "he_dop20_rgb",
                "wms_version": "1.1.1",
                "request_crs": "EPSG:4326",
            }


        elif 8.8 < center_lng < 14.0 and 47.0 < center_lat < 50.6:
            return {
                "state_id": "bavaria",
                "provider": "Bayern",
                "url": "https://geoservices.bayern.de/od/wms/dop/v1/dop20",
                "layer": "by_dop20c",
                "wms_version": "1.1.1",
                "request_crs": "EPSG:4326",
            }


        elif 11.2 < center_lng < 14.8 and 51.3 < center_lat < 53.6:
            return {
                "state_id": "berlin_brandenburg",
                "provider": "Landesvermessung und Geobasisinformation Brandenburg",
                "url": "https://isk.geobasis-bb.de/mapproxy/dop20c/service/wms",
                "layer": "bebb_dop20c",
                "wms_version": "1.3.0",
                "request_crs": "EPSG:3857",
                "styles": "",
            }


        return None

    def fetch_image_for_grid(self, grid):
        """
        Build WMS parameters dynamically and adapt to each state service version and BBOX axis order.
        """
        import math

        def pixel2deg(px, py, zoom):
            n = 256.0 * (2 ** zoom)
            lon = (px / n) * 360.0 - 180.0
            lat_rad = math.atan(math.sinh(math.pi * (1 - 2 * py / n)))
            lat = math.degrees(lat_rad)
            return lon, lat

        min_lng, max_lat = pixel2deg(
            grid["global_x_start"],
            grid["global_y_start"],
            self.zoom_level,
        )
        max_lng, min_lat = pixel2deg(
            grid["global_x_end"],
            grid["global_y_end"],
            self.zoom_level,
        )

        minx_3857 = self._global_pixel_x_to_mercator_x(grid["global_x_start"])
        maxx_3857 = self._global_pixel_x_to_mercator_x(grid["global_x_end"])
        maxy_3857 = self._global_pixel_y_to_mercator_y(grid["global_y_start"])
        miny_3857 = self._global_pixel_y_to_mercator_y(grid["global_y_end"])

        center_lng = (min_lng + max_lng) / 2.0
        center_lat = (min_lat + max_lat) / 2.0

        state_config = self._get_state_wms_config(center_lng, center_lat)
        if not state_config:
            raise ValueError(
                f"Coordinate ({center_lng:.4f}, {center_lat:.4f}) is outside the supported German city source regions."
                "Currently only Frankfurt, Munich, and Berlin are supported."
            )


        wms_version = state_config.get("wms_version", "1.1.1")
        request_crs = state_config.get("request_crs", "EPSG:4326")

        if request_crs == "EPSG:3857":
            bbox_str = f"{minx_3857},{miny_3857},{maxx_3857},{maxy_3857}"
            srs_key = "CRS" if wms_version == "1.3.0" else "SRS"

        elif wms_version == "1.3.0":


            bbox_str = f"{min_lat},{min_lng},{max_lat},{max_lng}"
            srs_key = "CRS"

        else:


            bbox_str = f"{min_lng},{min_lat},{max_lng},{max_lat}"
            srs_key = "SRS"

        params = {
            "SERVICE": "WMS",
            "VERSION": wms_version,
            "REQUEST": "GetMap",
            "FORMAT": "image/jpeg",
            "TRANSPARENT": "FALSE",
            "LAYERS": state_config["layer"],
            "STYLES": state_config.get("styles", ""),
            "WIDTH": "1024",
            "HEIGHT": "1024",
            srs_key: request_crs,
            "BBOX": bbox_str,
        }

        time.sleep(random.uniform(1.0, 2.5))

        try:
            response = requests.get(
                state_config["url"],
                params=params,
                headers=self.headers,
                timeout=60,
            )

            if response.status_code == 200:
                content_type = response.headers.get("Content-Type", "").lower()

                if (
                    "xml" in content_type
                    or "text" in content_type
                    or b"ServiceException" in response.content[:100]
                ):
                    print(f"\n❌ [WMS service error]: {response.text[:300]}")
                    print(f"🔗 Check URL: {response.url}")
                    return None

                return Image.open(io.BytesIO(response.content)).convert("RGB")

            elif response.status_code == 429:
                print("\n⚠️ Rate limited; sleeping for 30 seconds...")
                time.sleep(30)
                return None

            else:
                print(f"\n❌ [HTTP {response.status_code} error]: {response.text[:300]}")
                print(f"🔗 Failed request URL: {response.url}")
                return None

        except Exception as e:
            print(f"\n❌ [Network failure]: {e}")
            return None