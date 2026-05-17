from sources.base import BaseSource

class VancouverSource(BaseSource):
    def get_zoom_level(self):


        return 18

    def get_url_template(self):


        return "https://tiles.arcgis.com/tiles/qrcTTRTwUoS8N47o/arcgis/rest/services/Orthophotos_2022/MapServer/tile/{z}/{y}/{x}"

class TorontoSource(BaseSource):
    def get_zoom_level(self):
        return 18

    def get_url_template(self):
        return "https://gis.toronto.ca/arcgis/rest/services/basemap/cot_ortho_2023_color_10cm/MapServer"

    def get_fetch_mode(self):
        return "mapserver_export"

    def get_service_url(self):
        return "https://gis.toronto.ca/arcgis/rest/services/basemap/cot_ortho_2023_color_10cm/MapServer"

