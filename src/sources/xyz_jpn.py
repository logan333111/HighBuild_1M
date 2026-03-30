from .base import BaseSource

class JPNSource(BaseSource):
    def get_zoom_level(self):
        # 日本国土地理院 (GSI) 的全国无缝正射影像最高通常支持到 18 级
        # 18 级的清晰度（约 0.3 米）对于提取建筑高度已经完全足够
        return 18

    def get_url_template(self):
        # GSI Seamless Photo (全国无缝高分辨率正射影像) 官方标准接口
        return "https://cyberjapandata.gsi.go.jp/xyz/seamlessphoto/{z}/{x}/{y}.jpg"