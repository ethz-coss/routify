# Static data overview (backend)

This directory contains the backend's static inputs used at startup and during routing:

- `basemap_admin_level_8.json` (OSM export)
  - Raw OSM data exported via Overpass Turbo.
  - Parsed at startup to build the routing graph.

- `boundary_admin_level_8.geojson` (OSM boundary)
  - GeoJSON FeatureCollection describing the dataset boundary.

- `config_features.json` (routing feature trade‑off config)
  - Self‑generated configuration that defines weight modifiers/trade‑offs per feature and transport mode.
  - Used to bias routing (e.g., prefer/penalize certain highways for walk/bike/drive).

- `altitude_admin_level_8.json` (precomputed per OSM ID)
  - Altitude values mapped to nodes (OSM IDs), used for slope and elevation‑aware routing.

- `green_index_admin_level_8.json` (precomputed per OSM ID)
  - Green index values mapped to ways/nodes, used to bias routes toward greener segments.

- `noise_admin_level_8.json` (precomputed per OSM ID)
  - Noise level values mapped to nodes, used to account for acoustic comfort in routing.

