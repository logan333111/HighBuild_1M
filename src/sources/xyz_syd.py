from sources.base import BaseSource


class SydneySource(BaseSource):
    def __init__(self):
        super().__init__()

    def get_url_template(self):


        return "https://maps.six.nsw.gov.au/arcgis/rest/services/public/NSW_Imagery/MapServer/tile/{z}/{y}/{x}"

    def get_zoom_level(self):

        return 19