from sources.base import BaseSource


class MelbourneSource(BaseSource):
    def __init__(self):
        super().__init__()

    def get_url_template(self):


        return "https://gisags.melbourne.vic.gov.au/server_wa/rest/services/AerialImageryWGS84/AerialImage2020_WGS84/MapServer/tile/{z}/{y}/{x}"

    def get_zoom_level(self):

        return 19

