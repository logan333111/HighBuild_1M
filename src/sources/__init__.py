from importlib import import_module


_SOURCE_SPECS = {
    "usa": (".xyz_usa", "USASource"),
    "fra": (".xyz_fra", "FRASource"),
    "jpn": (".xyz_jpn", "JPNSource"),
    "nld": (".xyz_nld", "NLDSource"),
    "hkg": (".xyz_hkg", "HKGSource"),
    "twn": (".xyz_twn", "TWNSource"),
    "deu": (".xyz_deu", "GermanySource"),
    "syd": (".xyz_syd", "SydneySource"),
    "mel": (".xyz_mel", "MelbourneSource"),
    "bax": (".xyz_bax", "SaoPauloSource"),
    "van": (".xyz_can", "VancouverSource"),
    "tor": (".xyz_can", "TorontoSource"),
    "dam": (".xyz_dam", "DenmarkSDFISource"),
    "afr": (".xyz_afr", "CapeTownSource"),


    "aut": (".xyz_aut", "AustriaSource"),
    "vie": (".xyz_aut", "ViennaSource"),
}


def get_source(source_name):
    source_name = source_name.lower().strip()

    if source_name not in _SOURCE_SPECS:
        raise ValueError(
            f"❌ Unsupported imagery source: {source_name}. "
            f"Available: {list(_SOURCE_SPECS.keys())}"
        )

    module_name, class_name = _SOURCE_SPECS[source_name]

    try:
        module = import_module(module_name, __name__)
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            f"Source module or dependency for {source_name} is unavailable: {exc.name}"
        ) from exc

    return getattr(module, class_name)()