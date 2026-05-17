from sources.base import BaseSource


class AustriaSource(BaseSource):
    def get_zoom_level(self):
        return 18

    def get_url_template(self):


        return (
            "https://mapsneu.wien.gv.at/basemap/"
            "bmaporthofoto30cm/normal/google3857/{z}/{y}/{x}.jpeg"
        )


class ViennaSource(AustriaSource):
    pass