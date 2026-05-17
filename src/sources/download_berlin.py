import os
import re
import time
import requests


download_dir = "/data2/hgq/BuildingHeight_Dataset/data/raw/germany/berlin/"
os.makedirs(download_dir, exist_ok=True)

atom_url = "https://gdi.berlin.de/data/a_lod2/atom/0.atom"

print(f"Opening data catalog: {atom_url}")

try:
    response = requests.get(atom_url, timeout=30)
except Exception as e:
    print(f"Failed to fetch catalog: {e}")
    exit()

if response.status_code == 200:
    zip_links = re.findall(r'href="(https://[^"]+\.zip)"', response.text)
    zip_links = list(set(zip_links))
    print(f"[INFO] Found {len(zip_links)} data archives.")


    for i, link in enumerate(zip_links, 1):
        filename = link.split("/")[-1]
        filepath = os.path.join(download_dir, filename)


        if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
            print(f"[{i}/{len(zip_links)}] File already complete, skipping: {filename}")
            continue

        print(f"[{i}/{len(zip_links)}] Downloading: {filename} ...")


        max_retries = 3
        for attempt in range(max_retries):
            try:

                with requests.get(link, stream=True, timeout=30) as r:
                    r.raise_for_status()
                    with open(filepath, 'wb') as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)

                break
            except Exception as e:
                print(f"  ⚠️ Attempt {attempt + 1} failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(3)
                else:
                    print(f"  ❌ Failed permanently, skipping file: {filename}")

                    if os.path.exists(filepath):
                        os.remove(filepath)


        time.sleep(1)

    print("\n✅ All Berlin 3D building downloads finished.")
else:
    print(f"Request failed with status code: {response.status_code}")