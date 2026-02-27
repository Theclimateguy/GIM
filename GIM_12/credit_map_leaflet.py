#!/usr/bin/env python3
import argparse
import csv
import json
from pathlib import Path
from typing import Dict, Tuple


def find_latest_world_log(logs_dir: Path) -> Path:
    if not logs_dir.exists():
        raise FileNotFoundError(f"Logs directory not found: {logs_dir}")
    candidates = [
        p for p in logs_dir.glob("*.csv") if "_t" in p.stem and not p.stem.endswith("_actions") and not p.stem.endswith("_institutions")
    ]
    if not candidates:
        raise FileNotFoundError(f"No world state CSV logs found in: {logs_dir}")
    return max(candidates, key=lambda p: p.stat().st_mtime)


def load_agent_names(agents_csv: Path) -> Dict[str, str]:
    if not agents_csv.exists():
        raise FileNotFoundError(f"Agent CSV not found: {agents_csv}")
    names: Dict[str, str] = {}
    with agents_csv.open(newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            aid = (row.get("id") or "").strip()
            name = (row.get("name") or "").strip()
            if aid and name:
                names[aid] = name
    return names


def load_last_year_ratings(log_path: Path) -> Dict[str, Tuple[int, str, float]]:
    latest_time = None
    rows = []
    with log_path.open(newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                t = int(row.get("time", ""))
            except ValueError:
                continue
            rows.append((t, row))
            if latest_time is None or t > latest_time:
                latest_time = t

    if latest_time is None:
        return {}

    result: Dict[str, Tuple[int, str, float]] = {}
    for t, row in rows:
        if t != latest_time:
            continue
        aid = (row.get("agent_id") or "").strip()
        if not aid:
            continue
        try:
            rating = int(float(row.get("credit_rating", "")))
            risk = float(row.get("credit_risk_score", ""))
        except ValueError:
            continue
        zone = (row.get("credit_zone") or "").strip().lower()
        result[aid] = (rating, zone, risk)
    return result


def build_payload(agent_names: Dict[str, str], ratings: Dict[str, Tuple[int, str, float]]) -> Dict[str, dict]:
    payload = {}
    for aid, (rating, zone, risk) in ratings.items():
        name = agent_names.get(aid)
        if not name or name.lower() == "rest of world":
            continue
        payload[name] = {
            "agent_id": aid,
            "rating": rating,
            "zone": zone,
            "risk": risk,
        }
    return payload


def build_html(
    payload: Dict[str, dict],
    title: str,
    world_geojson: dict,
    leaflet_css: str,
    leaflet_js: str,
    tile_url: str | None = None,
) -> str:
    aliases = {
        "United States of America": "United States",
        "Russian Federation": "Russia",
        "Republic of Korea": "South Korea",
        "Korea, Republic of": "South Korea",
        "Türkiye": "Turkey",
    }

    payload_json = json.dumps(payload, ensure_ascii=False)
    aliases_json = json.dumps(aliases, ensure_ascii=False)
    world_geojson_json = json.dumps(world_geojson, ensure_ascii=False)
    tile_layer_js = ""
    if tile_url:
        tile_layer_js = (
            "L.tileLayer("
            + json.dumps(tile_url)
            + ", {maxZoom: 6, attribution: '&copy; OpenStreetMap contributors'}).addTo(map);"
        )

    return f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\" />
  <title>{title}</title>
  <style>
    {leaflet_css}
    html, body, #map {{ height: 100%; margin: 0; }}
    .legend {{ background: white; padding: 8px 10px; line-height: 1.4; border-radius: 6px; }}
    .swatch {{ display:inline-block; width:12px; height:12px; margin-right:6px; vertical-align:middle; }}
  </style>
</head>
<body>
  <div id=\"map\"></div>
  <script>{leaflet_js}</script>
  <script>
    const ratingData = {payload_json};
    const aliases = {aliases_json};
    const worldGeoJson = {world_geojson_json};

    const map = L.map('map').setView([20, 0], 2);
    {tile_layer_js}

    function resolveName(name) {{
      if (ratingData[name]) return name;
      const alias = aliases[name];
      if (alias && ratingData[alias]) return alias;
      return null;
    }}

    function zoneColor(zone) {{
      if (zone === 'green') return '#3FA34D';
      if (zone === 'yellow') return '#F6C445';
      if (zone === 'red') return '#D94841';
      return '#B9C0C8';
    }}

    function style(feature) {{
      const rawName = feature?.properties?.name || '';
      const resolved = resolveName(rawName);
      const zone = resolved ? ratingData[resolved].zone : null;
      return {{
        fillColor: zoneColor(zone),
        weight: 1,
        opacity: 1,
        color: '#2f2f2f',
        fillOpacity: resolved ? 0.75 : 0.25,
      }};
    }}

    L.geoJSON(worldGeoJson, {{
      style,
      onEachFeature: (feature, layer) => {{
        const rawName = feature?.properties?.name || 'Unknown';
        const resolved = resolveName(rawName);
        if (!resolved) {{
          layer.bindPopup(`<b>${{rawName}}</b><br/>No assigned rating`);
          return;
        }}
        const d = ratingData[resolved];
        layer.bindPopup(
          `<b>${{resolved}}</b><br/>` +
          `Rating (next year): <b>${{d.rating}}</b><br/>` +
          `Zone: <b>${{d.zone}}</b><br/>` +
          `Risk score: ${{(d.risk * 100).toFixed(1)}}%`
        );
      }}
    }}).addTo(map);

    const legend = L.control({{position: 'bottomright'}});
    legend.onAdd = function() {{
      const div = L.DomUtil.create('div', 'legend');
      div.innerHTML = `
        <div><b>Credit Rating Zone</b></div>
        <div><span class=\"swatch\" style=\"background:#3FA34D\"></span>Green (1-12)</div>
        <div><span class=\"swatch\" style=\"background:#F6C445\"></span>Yellow (13-20)</div>
        <div><span class=\"swatch\" style=\"background:#D94841\"></span>Red (21-26)</div>
        <div><span class=\"swatch\" style=\"background:#B9C0C8\"></span>No rating</div>
      `;
      return div;
    }};
    legend.addTo(map);
  </script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Leaflet credit-rating map for final simulation year")
    parser.add_argument("--logs-dir", default="logs")
    parser.add_argument("--agents-csv", default="agent_states.csv")
    parser.add_argument("--log", default=None, help="Explicit world log CSV path")
    parser.add_argument("--output", default=None, help="Output HTML path")
    parser.add_argument("--geojson", default="data/world_countries.geojson", help="Local world GeoJSON path")
    parser.add_argument("--leaflet-css", default="vendor/leaflet/leaflet.css", help="Local Leaflet CSS path")
    parser.add_argument("--leaflet-js", default="vendor/leaflet/leaflet.js", help="Local Leaflet JS path")
    parser.add_argument("--tile-url", default=None, help="Optional tile URL (leave empty for full offline)")
    args = parser.parse_args()

    logs_dir = Path(args.logs_dir).expanduser()
    agents_csv = Path(args.agents_csv).expanduser()
    log_path = Path(args.log).expanduser() if args.log else find_latest_world_log(logs_dir)
    geojson_path = Path(args.geojson).expanduser()
    leaflet_css_path = Path(args.leaflet_css).expanduser()
    leaflet_js_path = Path(args.leaflet_js).expanduser()
    if not geojson_path.exists():
        raise FileNotFoundError(f"GeoJSON file not found: {geojson_path}")
    if not leaflet_css_path.exists():
        raise FileNotFoundError(f"Leaflet CSS not found: {leaflet_css_path}")
    if not leaflet_js_path.exists():
        raise FileNotFoundError(f"Leaflet JS not found: {leaflet_js_path}")

    names = load_agent_names(agents_csv)
    ratings = load_last_year_ratings(log_path)
    payload = build_payload(names, ratings)
    world_geojson = json.loads(geojson_path.read_text(encoding="utf-8"))
    leaflet_css = leaflet_css_path.read_text(encoding="utf-8")
    leaflet_js = leaflet_js_path.read_text(encoding="utf-8")

    if args.output:
        output_path = Path(args.output).expanduser()
    else:
        output_path = log_path.with_name(f"{log_path.stem}_credit_map.html")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    html = build_html(
        payload,
        title=f"Credit Rating Map - {log_path.name}",
        world_geojson=world_geojson,
        leaflet_css=leaflet_css,
        leaflet_js=leaflet_js,
        tile_url=args.tile_url,
    )
    output_path.write_text(html, encoding="utf-8")

    print(f"World log: {log_path}")
    print(f"Countries with rating: {len(payload)}")
    print(f"GeoJSON source: {geojson_path}")
    print(f"Map HTML: {output_path}")


if __name__ == "__main__":
    main()
