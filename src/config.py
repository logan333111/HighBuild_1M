import os

"""
Global configuration file.
Adjust default paths, resolution, and tile settings here.
"""


TARGET_METERS = 256


HD_ZOOM_LEVEL = 18


OUTPUT_IMAGE_SIZE = 1024


DOWNLOAD_THREADS = 16


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


RAW_DATA_DIR = os.path.join(BASE_DIR, 'data', 'raw')


PROCESSED_DIR = os.path.join(BASE_DIR, 'data', 'processed')
IMAGES_DIR = os.path.join(PROCESSED_DIR, 'images')
MASKS_DIR = os.path.join(PROCESSED_DIR, 'masks')
COCO_DIR = os.path.join(PROCESSED_DIR, 'coco_json')


TILE_CACHE_DIR = os.path.join(BASE_DIR, 'data', 'interim', 'tiles')


os.makedirs(IMAGES_DIR, exist_ok=True)
os.makedirs(MASKS_DIR, exist_ok=True)
os.makedirs(COCO_DIR, exist_ok=True)
os.makedirs(TILE_CACHE_DIR, exist_ok=True)