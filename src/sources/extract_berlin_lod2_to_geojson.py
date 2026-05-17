import os
import zipfile
import xml.etree.ElementTree as ET
import geopandas as gpd
from shapely.geometry import Polygon, mapping
import json
import uuid

BASE_DIR = "/data2/hgq/BuildingHeight_Dataset/data/raw/germany/berlin"
OUT_PATH = os.path.join(BASE_DIR, "berlin_all_buildings_height.geojson")

ns = {
    "core": "http://www.opengis.net/citygml/1.0",
    "bldg": "http://www.opengis.net/citygml/building/1.0",
    "gml": "http://www.opengis.net/gml",
    "gen": "http://www.opengis.net/citygml/generics/1.0",
}

def parse_poslist_3d(text):
    vals = list(map(float, text.strip().split()))
    coords = []
    for i in range(0, len(vals), 3):
        coords.append((vals[i], vals[i + 1], vals[i + 2]))
    return coords

def find_best_horizontal_polygon(elem):
    poslists = elem.findall(".//gml:posList", ns)
    if not poslists:
        return None, None

    best_poly = None
    best_z = None
    best_area = 0.0

    for p in poslists:
        if p.text is None:
            continue

        try:
            coords3d = parse_poslist_3d(p.text)
        except Exception:
            continue

        if len(coords3d) < 4:
            continue

        zs = [c[2] for c in coords3d]


        if max(zs) - min(zs) > 0.5:
            continue

        coords2d = [(c[0], c[1]) for c in coords3d]

        try:
            poly = Polygon(coords2d)
        except Exception:
            continue

        if (not poly.is_valid) or poly.is_empty or poly.area <= 1:
            continue

        z0 = sum(zs) / len(zs)


        if best_poly is None:
            best_poly = poly
            best_z = z0
            best_area = poly.area
        else:
            if (z0 < best_z - 0.01) or (abs(z0 - best_z) < 0.01 and poly.area > best_area):
                best_poly = poly
                best_z = z0
                best_area = poly.area

    return best_poly, best_z

def extract_from_xml(xml_path):
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
    except Exception as e:
        print(f"[SKIP] XML parse failed: {xml_path} | {e}")
        return []

    records = []


    for b in root.findall(".//bldg:Building", ns):
        gml_id = b.attrib.get("{http://www.opengis.net/gml}id", str(uuid.uuid4()))

        mh = b.find(".//bldg:measuredHeight", ns)
        if mh is None or mh.text is None:
            continue

        try:
            height = float(mh.text)
        except Exception:
            continue

        poly, base_z = find_best_horizontal_polygon(b)
        if poly is None:
            continue

        records.append({
            "id": gml_id,
            "height": height,
            "base_z": base_z,
            "geometry": poly,
            "xml_file": os.path.basename(xml_path),
        })

    return records

def unzip_all_zips(base_dir):
    zip_files = [f for f in os.listdir(base_dir) if f.lower().endswith(".zip")]
    zip_files.sort()

    print(f"Found {len(zip_files)} zip files")

    for zf in zip_files:
        zip_path = os.path.join(base_dir, zf)
        folder_name = os.path.splitext(zf)[0]
        extract_dir = os.path.join(base_dir, folder_name)

        if os.path.isdir(extract_dir):

            continue

        try:
            with zipfile.ZipFile(zip_path, "r") as z:
                z.extractall(extract_dir)
            print(f"[EXTRACT] {zf}")
        except Exception as e:
            print(f"[SKIP] Extraction failed: {zf} | {e}")

def collect_all_xmls(base_dir):
    xml_paths = []
    for root, _, files in os.walk(base_dir):
        for f in files:
            if f.lower().endswith(".xml"):
                xml_paths.append(os.path.join(root, f))
    xml_paths.sort()
    return xml_paths

def main():
    unzip_all_zips(BASE_DIR)

    xml_paths = collect_all_xmls(BASE_DIR)
    print(f"Found {len(xml_paths)} XML files")

    all_records = []
    total_xml = 0

    for xml_path in xml_paths:
        total_xml += 1
        recs = extract_from_xml(xml_path)
        all_records.extend(recs)
        print(f"[{total_xml}/{len(xml_paths)}] {os.path.basename(xml_path)} -> {len(recs)} buildings")

    if len(all_records) == 0:
        print("No buildings were extracted.")
        return

    gdf = gpd.GeoDataFrame(all_records, geometry="geometry", crs="EPSG:25833")
    gdf = gdf.to_crs(epsg=4326)

    features = []
    for _, row in gdf.iterrows():
        geom = row["geometry"]
        minx, miny, maxx, maxy = geom.bounds

        features.append({
            "type": "Feature",
            "properties": {
                "id": row["id"],
                "height": float(row["height"]),
                "base_z": float(row["base_z"]),
                "bbox": {
                    "xmin": minx,
                    "xmax": maxx,
                    "ymin": miny,
                    "ymax": maxy
                },
                "is_estimated_height": False,
                "source": "Berlin LoD2",
                "xml_file": row["xml_file"]
            },
            "geometry": mapping(geom)
        })

    geojson = {
        "type": "FeatureCollection",
        "features": features
    }

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(geojson, f, ensure_ascii=False)

    print("\n==============================")
    print(f"Saved: {OUT_PATH}")
    print(f"Total buildings: {len(features)}")
    print("==============================")

if __name__ == "__main__":
    main()