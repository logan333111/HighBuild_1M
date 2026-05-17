import math
import sys
from pathlib import Path

import requests


def lonlat_to_xyz(lon, lat, z):
    lat = max(min(lat, 85.05112878), -85.05112878)
    n = 2 ** z
    x = int((lon + 180.0) / 360.0 * n)
    lat_rad = math.radians(lat)
    y = int(
        (1.0 - math.log(math.tan(lat_rad) + 1.0 / math.cos(lat_rad)) / math.pi)
        / 2.0
        * n
    )
    return x, y


def main():
    if len(sys.argv) < 4:
        print("Usage:")
        print("python src/test_moa_uav_tile_url.py ACCESS_URL CENTER_LON CENTER_LAT")
        sys.exit(1)

    access_url = sys.argv[1].rstrip("/") + "/"
    lon = float(sys.argv[2])
    lat = float(sys.argv[3])

    out_dir = Path("/data2/hgq/BuildingHeight_Dataset/data/raw/twn/moa_uav/test_tiles")
    out_dir.mkdir(parents=True, exist_ok=True)

    headers = {
        "User-Agent": "BuildingHeightDataset/1.0 (+research)"
    }


    for z in [15, 16, 17, 18, 19, 20]:
        x, y = lonlat_to_xyz(lon, lat, z)

        candidates = [
            f"{access_url}{z}/{x}/{y}.png",
            f"{access_url}{z}/{x}/{y}.jpg",
            f"{access_url}{z}/{y}/{x}.png",
            f"{access_url}{z}/{y}/{x}.jpg",
        ]

        print("=" * 80)
        print(f"z={z}, x={x}, y={y}")

        for url in candidates:
            try:
                r = requests.get(url, headers=headers, timeout=30)
                ctype = r.headers.get("Content-Type", "")
                size = len(r.content)

                ok = (
                    r.status_code == 200
                    and (
                        ctype.startswith("image/")
                        or r.content.startswith(b"\x89PNG")
                        or r.content.startswith(b"\xff\xd8")
                    )
                    and size > 100
                )

                print(f"{r.status_code} {size:8d} {ctype:30s} {url}")

                if ok:
                    suffix = ".png" if r.content.startswith(b"\x89PNG") else ".jpg"
                    out = out_dir / f"test_z{z}_x{x}_y{y}{suffix}"
                    out.write_bytes(r.content)
                    print(f"[OK] saved {out}")
                    return

            except Exception as e:
                print(f"ERR {url} {e}")

    print("[FAIL] no valid image tile found")


if __name__ == "__main__":
    main()