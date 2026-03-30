from .base import BaseSource

class TWNSource(BaseSource):
    def __init__(self):
        # NLSC API 完全开源免费，不需要传任何 Token 或参数
        super().__init__()

    def get_url_template(self):
        # PHOTO2 是 NLSC 的官方「正射影像圖」圖層
        # 注意：WMTS 標準的路徑通常是 {z}/{y}/{x} (TileRow/TileCol)，如果切出來的圖錯位了，可以換成 {z}/{x}/{y} 試試
        return "https://wmts.nlsc.gov.tw/wmts/PHOTO2/default/GoogleMapsCompatible/{z}/{y}/{x}"

    def get_zoom_level(self):
        # 台灣都會區的正射影像通常支援到 Zoom Level 19 (約 0.15 米解析度)
        return 19