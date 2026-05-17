#!/usr/bin/env python3


"""
Download exact Overture buildings for São Paulo using the official IBGE municipal boundary and export them as GeoJSON.

This version lists public parquet files with requests before passing HTTPS URLs to DuckDB.
"""

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
import boto3
from botocore import UNSIGNED
from botocore.config import Config
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import duckdb
import requests
from shapely import wkb
from shapely.geometry import mapping, shape
from shapely.ops import unary_union


DEFAULT_MUNICIPIO_CODE = "3550308"
OVERTURE_BUCKET_BASE = "https://overturemaps-us-west-2.s3.us-west-2.amazonaws.com"
OVERTURE_BUCKET = "overturemaps-us-west-2"

def parse_args():
    parser = argparse.ArgumentParser(
        description="Download exact São Paulo buildings from Overture using IBGE boundary."
    )
    parser.add_argument(
        "--release",
        required=True,
        help="Overture release version, e.g. 2025-09-24.0",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Output GeoJSON path",
    )
    parser.add_argument(
        "--municipio-code",
        default=DEFAULT_MUNICIPIO_CODE,
        help="IBGE municipality code, default=3550308 (São Paulo)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=5000,
        help="rows per batch, default=5000",
    )
    return parser.parse_args()


def init_duckdb():
    con = duckdb.connect(database=":memory:")
    con.execute("INSTALL spatial;")
    con.execute("LOAD spatial;")
    con.execute("INSTALL httpfs;")
    con.execute("LOAD httpfs;")
    return con


def build_ibge_boundary_url(municipio_code):
    return (
        "https://servicodados.ibge.gov.br/api/v3/malhas/municipios/"
        f"{municipio_code}"
        "?formato=application/vnd.geo+json&qualidade=minima"
    )


def build_requests_session():
    retry = Retry(
        total=5,
        connect=5,
        read=5,
        backoff_factor=2,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
    )
    session = requests.Session()
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update({"User-Agent": "Mozilla/5.0"})
    return session


SESSION = build_requests_session()


def download_json(url):
    resp = SESSION.get(
        url,
        timeout=(30, 180),
    )
    resp.raise_for_status()
    return resp.json()

def load_boundary_geom(municipio_code, cache_path=None):
    data = None

    if cache_path is not None:
        cache_file = Path(cache_path)
        if cache_file.exists():
            print(f"[INFO] Using local boundary cache: {cache_file}", file=sys.stderr)
            with cache_file.open("r", encoding="utf-8") as f:
                data = json.load(f)

    if data is None:
        url = build_ibge_boundary_url(municipio_code)
        print(f"[INFO] Downloading IBGE boundary: {url}", file=sys.stderr)
        data = download_json(url)

        if cache_path is not None:
            cache_file = Path(cache_path)
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            with cache_file.open("w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
            print(f"[INFO] Cached boundary to: {cache_file}", file=sys.stderr)

    if isinstance(data, dict) and data.get("type") == "FeatureCollection":
        geoms = [shape(feat["geometry"]) for feat in data["features"]]
        geom = unary_union(geoms)
    elif isinstance(data, dict) and data.get("type") == "Feature":
        geom = shape(data["geometry"])
    else:
        raise RuntimeError("Could not parse the GeoJSON boundary returned by IBGE.")

    geom = geom.buffer(0)
    if geom.is_empty:
        raise RuntimeError("IBGE boundary is empty.")

    return geom
def get_public_s3_client():
    return boto3.client(
        "s3",
        region_name="us-west-2",
        config=Config(signature_version=UNSIGNED),
    )


def list_available_releases():
    """
    List visible release prefixes in the public bucket for release troubleshooting.
    """
    s3 = get_public_s3_client()
    paginator = s3.get_paginator("list_objects_v2")

    releases = []
    for page in paginator.paginate(
        Bucket=OVERTURE_BUCKET,
        Prefix="release/",
        Delimiter="/",
    ):
        for item in page.get("CommonPrefixes", []):
            releases.append(item["Prefix"])

    return releases


def list_overture_parquet_urls(release):
    """
    List all building parquet files from public S3 using anonymous boto3 access.
    Check the requested release first, then include visible releases if none are found.
    """
    s3 = get_public_s3_client()
    paginator = s3.get_paginator("list_objects_v2")

    candidate_prefixes = [
        f"release/{release}/theme=buildings/type=building/",
        f"release/{release}/theme=buildings/",
        f"release/{release}/",
    ]

    urls = []

    for prefix in candidate_prefixes:
        print(f"[INFO] Trying prefix: {prefix}", file=sys.stderr)

        local_urls = []
        for page in paginator.paginate(
            Bucket=OVERTURE_BUCKET,
            Prefix=prefix,
        ):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                if key.endswith(".parquet") and "/theme=buildings/" in key:
                    local_urls.append(f"{OVERTURE_BUCKET_BASE}/{key}")

        if local_urls:
            print(f"[INFO] Found parquet files: {len(local_urls)}", file=sys.stderr)
            return local_urls

        print(f"[WARN] Empty prefix: {prefix}", file=sys.stderr)


    releases = list_available_releases()
    raise RuntimeError(
        "No buildings parquet files were found under any candidate prefix.\n"
        f"release={release}\n"
        f"Example visible release prefixes in the public bucket: {releases[:10]}"
    )
def sql_quote(s):
    return "'" + s.replace("'", "''") + "'"


def export_exact_geojson(
    con,
    parquet_urls,
    boundary_wkt,
    bounds,
    output_path,
    batch_size,
):
    minx, miny, maxx, maxy = bounds

    files_sql = ",\n".join(sql_quote(u) for u in parquet_urls)

    sql = f"""
    WITH src AS (
        SELECT
            id,
            height,
            num_floors,
            bbox,
            geometry
        FROM read_parquet([{files_sql}], hive_partitioning=1)
        WHERE bbox.xmin <= ?
          AND bbox.xmax >= ?
          AND bbox.ymin <= ?
          AND bbox.ymax >= ?
    )
    SELECT
        id,
        height,
        num_floors,
        ST_AsWKB(geometry) AS geom_wkb
    FROM src
    WHERE ST_Within(
        ST_Centroid(geometry),
        ST_GeomFromText(?)
    )
    """

    cursor = con.execute(
        sql,
        [
            maxx,
            minx,
            maxy,
            miny,
            boundary_wkt,
        ],
    )

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    count = 0
    first = True

    with out.open("w", encoding="utf-8") as f:
        f.write('{"type":"FeatureCollection","features":[\n')

        while True:
            rows = cursor.fetchmany(batch_size)
            if not rows:
                break

            for row in rows:
                oid, height, num_floors, geom_wkb = row

                if geom_wkb is None:
                    continue

                geom = wkb.loads(geom_wkb)
                if geom.is_empty:
                    continue

                feature = {
                    "type": "Feature",
                    "geometry": mapping(geom),
                    "properties": {
                        "id": oid,
                        "height": height,
                        "num_floors": num_floors,
                    },
                }

                if not first:
                    f.write(",\n")
                json.dump(feature, f, ensure_ascii=False)
                first = False
                count += 1

                if count % 50000 == 0:
                    print(f"[INFO] Wrote {count:,} buildings...", file=sys.stderr)

        f.write("\n]}\n")

    return count


def main():
    args = parse_args()

    print(f"[INFO] Using IBGE municipio code: {args.municipio_code}", file=sys.stderr)
    boundary_cache = str(
    Path(args.output).with_name(f"ibge_boundary_{args.municipio_code}.geojson")
)
    boundary = load_boundary_geom(args.municipio_code, cache_path=boundary_cache)
    bounds = boundary.bounds
    boundary_wkt = boundary.wkt
    print(f"[INFO] Municipality bounds: {bounds}", file=sys.stderr)

    print("[INFO] Listing Overture parquet files...", file=sys.stderr)
    parquet_urls = list_overture_parquet_urls(args.release)
    print(f"[INFO] Parquet file count: {len(parquet_urls)}", file=sys.stderr)

    con = init_duckdb()

    print("[INFO] Starting exact São Paulo building filtering...", file=sys.stderr)
    count = export_exact_geojson(
        con=con,
        parquet_urls=parquet_urls,
        boundary_wkt=boundary_wkt,
        bounds=bounds,
        output_path=args.output,
        batch_size=args.batch_size,
    )

    print(f"[DONE] Output file: {args.output}", file=sys.stderr)
    print(f"[DONE] Building count: {count:,}", file=sys.stderr)


if __name__ == "__main__":
    main()