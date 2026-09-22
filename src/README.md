# Source

This folder builds `../dashboard.html`. Day to day, run **`python3 run.py`** from the project root.

To download fresh data from the Chicago Data Portal (`--refresh`), copy **`../.env.example`** to **`../.env`** and add your portal credentials. See the root **README** or **START_HERE.html**.

| Path | Purpose |
|---|---|
| `build_dashboard.py` | HTML template and write step |
| `dashboard.js` | Page switch, jump palette, ordinance charts and table |
| `glance.js` | All-funds river, takeaways, filters |
| `app.css` | Styles |
| `data/` | Cached CSVs (`*.parquet` is a local cache; not required) |
| `pipeline/config.py` | Budget year and Data Portal dataset IDs |
| `pipeline/published_glance.py` | Optional official Overview totals, keyed by year |
| `pipeline/classifications.py` | Fund types and department → function map |
| `pipeline/fetch_data.py` | Socrata download |
| `pipeline/glance.py` | Glance payload (numbers, takeaways, YoY, copy) |
| `pipeline/dashboard_logic.py` | Ordinance views, charts, stories |
| `notebooks/try.ipynb` | Exploratory analysis |

```bash
# From project root
python3 run.py
python3 run.py --refresh
python3 run.py --no-open

# From this folder
python3 build_dashboard.py
python3 -m pipeline.fetch_data
```
