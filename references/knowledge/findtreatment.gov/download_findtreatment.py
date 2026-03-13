import requests
import pandas as pd
import time

BASE_URL = "https://findtreatment.gov/locator/exportsAsJson/v2"

params = {
    "page": 1,
    "pageSize": 2000
}

all_rows = []

while True:
    response = requests.get(BASE_URL, params=params, timeout=30)
    response.raise_for_status()
    data = response.json()

    rows = data.get("rows", [])
    all_rows.extend(rows)

    current_page = data.get("page", 1)
    total_pages = data.get("totalPages", 1)

    print(f"Downloaded page {current_page} of {total_pages} - {len(rows)} rows")

    if current_page >= total_pages:
        break

    params["page"] += 1
    time.sleep(0.2)

df = pd.json_normalize(all_rows, sep="_")
df.to_csv("findtreatment_facilities.csv", index=False, encoding="utf-8-sig")

print(f"Done. Saved {len(df)} facilities to findtreatment_facilities.csv")