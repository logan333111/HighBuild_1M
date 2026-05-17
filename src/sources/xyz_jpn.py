from .base import BaseSource

class JPNSource(BaseSource):
    def get_zoom_level(self):


        return 18

    def get_url_template(self):

        return "https://cyberjapandata.gsi.go.jp/xyz/seamlessphoto/{z}/{x}/{y}.jpg"