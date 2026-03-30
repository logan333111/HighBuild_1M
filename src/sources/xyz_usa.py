from .base import BaseSource

class USASource(BaseSource):
    def get_zoom_level(self):
        return 18
        
    def get_url_template(self):
        return "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
