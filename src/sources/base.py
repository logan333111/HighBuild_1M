from abc import ABC, abstractmethod
from PIL import Image
from io import BytesIO
import requests
import time
import random
from concurrent.futures import ThreadPoolExecutor

class BaseSource(ABC):
    def __init__(self):
        self.headers = self.get_headers()
        self.zoom_level = self.get_zoom_level()
        self.url_template = self.get_url_template()

    @abstractmethod
    def get_url_template(self):
        pass

    @abstractmethod
    def get_zoom_level(self):
        pass

    def get_headers(self):
        # Default generic headers
        return {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
        }

    def fetch_image_for_grid(self, grid):
        """Fetch grid image using typical XYZ logic. Subclasses can override if not XYZ."""
        min_tx = grid['global_x_start'] // 256
        max_tx = grid['global_x_end'] // 256
        min_ty = grid['global_y_start'] // 256
        max_ty = grid['global_y_end'] // 256
        
        pixel_size = grid['pixel_size']
        stitched_image = Image.new('RGB', (pixel_size, pixel_size))
        
        def fetch_tile(tx, ty):
            url = self.url_template.format(x=tx, y=ty, z=self.zoom_level)
            time.sleep(random.uniform(0.2, 0.6))
            try:
                response = requests.get(url, headers=self.headers, timeout=10)
                if response.status_code == 200:
                    return (tx, ty, Image.open(BytesIO(response.content)).convert("RGB"))
                elif response.status_code == 429:
                    time.sleep(5)
            except Exception:
                pass
            return (tx, ty, None)

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = []
            for tx in range(min_tx, max_tx + 1):
                for ty in range(min_ty, max_ty + 1):
                    futures.append(executor.submit(fetch_tile, tx, ty))
            
            for future in futures:
                tx, ty, img = future.result()
                if img:
                    paste_x = (tx * 256) - grid['global_x_start']
                    paste_y = (ty * 256) - grid['global_y_start']
                    stitched_image.paste(img, (paste_x, paste_y))
                    
        return stitched_image
