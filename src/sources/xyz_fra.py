from .base import BaseSource

class FRASource(BaseSource):
    def get_zoom_level(self):
        return 19

    def get_url_template(self):
        return "https://data.geopf.fr/wmts?SERVICE=WMTS&VERSION=1.0.0&REQUEST=GetTile&LAYER=ORTHOIMAGERY.ORTHOPHOTOS&STYLE=normal&FORMAT=image/jpeg&TILEMATRIXSET=PM&TILEMATRIX={z}&TILEROW={y}&TILECOL={x}"

    def get_headers(self):
        headers = super().get_headers()

        headers['Referer'] = 'https://www.geoportail.gouv.fr/'
        return headers
