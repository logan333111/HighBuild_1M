from .base import BaseSource

class TiandituSource(BaseSource):
    def __init__(self):
        # 初始化基础属性
        self.tk = "826eb39a5ec1fcb3384218dc1ea99da4" 
        # 绝不瞎传参数了，直接空调用
        super().__init__()

    # 老师规定的必答题 1：返回下载链接模板
    def get_url_template(self):
        return f"https://t0.tianditu.gov.cn/DataServer?T=img_w&x={{x}}&y={{y}}&l={{z}}&tk={self.tk}"

    # 老师规定的必答题 2：返回地图清晰度级别
    def get_zoom_level(self):
        return 18