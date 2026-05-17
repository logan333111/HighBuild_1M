from .base import BaseSource

class NLDSource(BaseSource):
    def get_zoom_level(self):

        return 19

    def get_url_template(self):

        return "https://service.pdok.nl/hwh/luchtfotorgb/wmts/v1_0/Actueel_orthoHR/EPSG:3857/{z}/{x}/{y}.jpeg"