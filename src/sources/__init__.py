from .xyz_usa import USASource
from .xyz_fra import FRASource
from .xyz_jpn import JPNSource
from .xyz_nld import NLDSource
from .xyz_chn import TiandituSource
from .xyz_hkg import HKGSource
from .xyz_twn import TWNSource


def get_source(source_name):
    sources = {
        'usa': USASource,
        'fra': FRASource,
        'jpn': JPNSource,
        'nld': NLDSource,
        'chn': TiandituSource,
        'hkg': HKGSource,
        'twn': TWNSource
    }
    if source_name not in sources:
        raise ValueError(f"❌ 不支持的影像源: {source_name}. Available: {list(sources.keys())}")
    return sources[source_name]()
