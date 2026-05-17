# HighBuild-1M Dataset Toolkit

HighBuild-1M is a dataset preparation toolkit for single-view building height estimation. It takes building footprint GeoJSON files with height attributes, downloads high-resolution aerial or orthophoto imagery from regional public sources, and generates aligned 1024x1024 image tiles, floating-point height masks, visualization masks, and COCO-style building annotations.

The repository does not package third-party imagery directly. Instead, each imagery source is implemented as a downloader under `src/sources/`, so dataset generation can be run against the relevant public provider for each city or region.

## Main Workflow

- `src/main.py` is the primary entry point.
- Input data should be a GeoJSON file containing building geometries in `EPSG:4326` or a CRS that can be reprojected to `EPSG:4326`.
- Each generated grid covers `256m x 256m` and is rendered as a `1024x1024` image by default.
- Outputs are written under `data/processed/`.
- Downloaded source tiles are cached under `data/interim/tiles/`.

## Requirements

Install dependencies with:

```bash
pip install -r requirements.txt
```

Spatial packages such as `geopandas`, `rasterio`, `pyproj`, and `shapely` may require GDAL, GEOS, and PROJ system libraries. A conda environment is usually the most reliable setup for these dependencies.

## Basic Usage

```bash
python src/main.py \
  --geojson data/raw/your_city_Filtered.geojson \
  --source usa \
  --prefilter_grids_by_buildings \
  --prefilter_pad_pixels 32
```

Useful options:

- `--source`: imagery source key.
- `--sample_rate`: randomly process a fraction of grids for quick testing.
- `--prefilter_grids_by_buildings`: skip grids that do not intersect building geometry.
- `--prefilter_pad_pixels`: expand the prefilter bounds to avoid dropping edge buildings.
- `--debug_grid_mode first|center`: process a single grid for debugging.
- `--debug_grid_id <id>`: process one explicit grid id.
- `--debug_save_rejected`: save rejected tiles for inspection.

Run the full CLI help with:

```bash
python src/main.py --help
```

## Supported Imagery Sources

Common source keys currently implemented in `src/sources/` include:

| Key | Region |
| --- | --- |
| `usa` | United States |
| `fra` | France |
| `jpn` | Japan |
| `nld` | Netherlands |
| `hkg` | Hong Kong |
| `deu` | Germany |
| `syd` | Sydney, Australia |
| `mel` | Melbourne, Australia |
| `afr` | Cape Town, South Africa |
| `bax` | Sao Paulo, Brazil |
| `van` | Vancouver, Canada |
| `tor` | Toronto, Canada |
| `dam` | Denmark |
| `aut` | Austria |

Use `python src/main.py --help` as the source of truth for sources exposed by the CLI. New source classes can be added under `src/sources/` and registered in `src/sources/__init__.py`.

## Output Structure

For an input file named `data/raw/my_city_Filtered.geojson`, outputs are placed in:

```text
data/processed/
  images/my_city_Filtered/
  masks/my_city_Filtered/
    masks/
    viz/
  coco_json/my_city_Filtered/
    checkpoint_gid.txt
    process_log.txt
```

Output files include:

- JPEG image tiles.
- TIFF height masks with floating-point height values.
- PNG visualization masks for manual QA.
- COCO JSON annotations containing building bounding boxes, segmentations, height values, and estimated-height flags when available.

## Utility Scripts

Several helper scripts are included for dataset preparation and QA:

- `src/clean_processed_dataset.py`: remove unpaired samples, clip invalid annotations, and delete low-valid-pixel samples.
- `src/stat_city_dataset.py`: summarize per-city image, mask, COCO, and building-height counts.
- `src/generate_benchmark_splits.py`: generate benchmark train/val/test manifests and split reports.
- `src/remove_unknown_height_buildings.py`: filter unknown-height buildings from source data.
- `src/sources/download_berlin.py`: download Berlin LoD2 source archives.
- `src/sources/extract_berlin_lod2_to_geojson.py`: extract Berlin LoD2 building heights into GeoJSON.
- `src/sources/download_overture_sao_paulo_exact.py`: export exact Sao Paulo Overture buildings using the IBGE boundary.

## Data Notes

- Building heights should be stored in a `height` property when possible.
- Estimated heights may be marked with `is_estimated_height`.
- Missing or invalid heights are treated as unknown by the processing code.
- Keep source GeoJSON files in `data/raw/` and processed outputs in `data/processed/`.
- Check each imagery provider's license before redistributing generated imagery or derived datasets.

## Citation

If your research uses HighBuild-1M, please cite:

```bibtex
@article{highbuild1m2026,
  title={HighBuild-1M: A Multi-continental High-resolution Benchmark Dataset for Single-view Building Height Estimation},
  author={Anonymous Authors},
  journal={NeurIPS Datasets and Benchmarks Track},
  year={2026}
}
```
