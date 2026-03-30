from .base import BaseSource

class NLDSource(BaseSource):
    def get_zoom_level(self):
        # 荷兰 PDOK 支持极高的 Zoom Level，19 级（约 0.3 米）完美兼顾清晰度与下载速度
        return 19

    def get_url_template(self):
        # 荷兰 PDOK 官方高分辨率正射影像 (Actueel_orthoHR) 的 RESTful XYZ 接口
        return "https://service.pdok.nl/hwh/luchtfotorgb/wmts/v1_0/Actueel_orthoHR/EPSG:3857/{z}/{x}/{y}.jpeg"