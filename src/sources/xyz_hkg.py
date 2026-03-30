from .base import BaseSource

class HKGSource(BaseSource):
    def __init__(self):
        # 香港的公共 API 不需要密钥，直接空参初始化
        super().__init__()

    def get_url_template(self):
        # 香港地政总署官方公开的 WGS84 高清影像 XYZ 服务
        return "https://mapapi.geodata.gov.hk/gs/api/v1.0.0/xyz/imagery/WGS84/{z}/{x}/{y}.png"

    def get_zoom_level(self):
        # 香港的航空图极为清晰，最高支持到 Zoom Level 19 (约 0.15米分辨率)
        return 19