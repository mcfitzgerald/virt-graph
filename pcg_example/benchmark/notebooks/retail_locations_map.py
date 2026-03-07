"""Generate an interactive map of all PCG retail locations."""

import psycopg
import folium
from folium.plugins import MarkerCluster
from pathlib import Path

conn_str = "postgresql://postgres:postgres@localhost:5432/erp_db"

with psycopg.connect(conn_str) as conn:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT name, city, lat, lon, store_format, channel FROM retail_locations ORDER BY id"
        )
        rows = cur.fetchall()

# Center on US
m = folium.Map(location=[39.5, -98.35], zoom_start=4, tiles="CartoDB positron")

cluster = MarkerCluster(name="Retail Locations").add_to(m)

for name, city, lat, lon, store_format, channel in rows:
    folium.CircleMarker(
        location=[float(lat), float(lon)],
        radius=3,
        color="#e74c3c",
        fill=True,
        fill_opacity=0.7,
        popup=f"<b>{name}</b><br>{city}<br>Format: {store_format}<br>Channel: {channel}",
    ).add_to(cluster)

out = Path(__file__).parent / "retail_locations_map.html"
m.save(str(out))
print(f"Map saved to {out} ({len(rows):,} locations)")
