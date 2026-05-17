import argparse
import mercantile

def tile_to_lnglat(tile_name):
    """
    Convert tile ID to geographic coordinates and Google Earth link.
    """
    try:
        parts = tile_name.split('_')
        if len(parts) != 3:
            raise ValueError("Tile name must be Z_X_Y.")

        z = int(parts[0])
        x = int(parts[1])
        y = int(parts[2])

        bounds = mercantile.bounds(x, y, z)
        center_lng = (bounds.west + bounds.east) / 2.0
        center_lat = (bounds.north + bounds.south) / 2.0

        print(f"\n================ Tile {tile_name} ================")
        print("🌍 Tile center:")
        print(f"  Longitude (Lng): {center_lng:.6f}")
        print(f"  Latitude  (Lat): {center_lat:.6f}")

        elevation = 600 * (2 ** (16 - z))
        print(f"✅ Google Earth link: https://earth.google.com/web/@{center_lat:.6f},{center_lng:.6f},{elevation:.1f}d")

        print(f"\n📐 Tile bounds:")
        print(f"  West:  {bounds.west:.6f}")
        print(f"  East:  {bounds.east:.6f}")
        print(f"  South: {bounds.south:.6f}")
        print(f"  North: {bounds.north:.6f}")
        print("====================================================\n")

    except Exception as e:
        print(f"❌ Error: {e}.")
        print("Usage: example 16_35073_20905")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert tile ID to geographic coordinates.")
    parser.add_argument('tile', type=str, help="Tile name, e.g. 16_35073_20905")
    args = parser.parse_args()
    tile_to_lnglat(args.tile)
