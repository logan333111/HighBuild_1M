from sources.base import BaseSource
import os


class DenmarkSDFISource(BaseSource):
    def get_zoom_level(self):
        return 18

    def get_fetch_mode(self):
        return "xyz"

    def get_url_template(self):
        api_key = os.environ.get("SDFI_API_KEY", "").strip()
        if not api_key:
            raise ValueError(
                "SDFI_API_KEY is not set. Run: export SDFI_API_KEY='your_api_key'"
            )

        return (
            "https://wmts.datafordeler.dk/GeoDanmarkOrto/orto_foraar_webm/1.0.0/WMTS"
            f"?apikey={api_key}"
            "&SERVICE=WMTS"
            "&REQUEST=GetTile"
            "&VERSION=1.0.0"
            "&STYLE=default"
            "&FORMAT=image/jpeg"
            "&TILEMATRIXSET=DFD_GoogleMapsCompatible"
            "&TILEMATRIX={z}"
            "&TILEROW={y}"
            "&TILECOL={x}"
            "&Layer=orto_foraar_webm"
        )