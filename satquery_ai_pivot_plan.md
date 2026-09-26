# SatQuery AI Pivot: Recovery & Continuation Plan

## Phase 0 — Shared Foundation (Do First, Everything Else Depends on It)

### Prompt 1 — PostGIS Alerting Schema + Generic Daemon Hook
* **Task:** Create table `monitoring_alerts`: `id`, `region_name`, `alert_type` (`'land_change'` | `'severe_weather'`), `severity` (`'info'` | `'warning'` | `'critical'`), `computed_metrics` (JSONB), `geom` (Geometry, 4326), `timestamp`, `acknowledged` (boolean). Add indexes on `timestamp DESC` and a GIST index on `geom`. Extend the existing STAC ingestion daemon so that after each poll cycle, for any ROI flagged `monitored: true`, it calls a pluggable alert-check function (signature: takes recent scene/metric data, returns `None` or a structured alert dict) and inserts a row if triggered. Add `GET /api/alerts` returning recent alerts as GeoJSON.
* **Verification:** Insert one manual test alert via the endpoint, confirm it's retrievable via a direct `psql` query **AND** via the API — both, not just one.

### Prompt 2 — One-Command Startup Script
* **Task:** Write `start.ps1` and `start.sh`: 
  1. `docker compose up -d` for `satquery-service` + PostGIS, 
  2. Activate the GeoChat venv and launch inference in the background, 
  3. Poll `GET /health` until `geochat_loaded: true`, with a 90s timeout that fails loudly rather than hanging silently, 
  4. Print a single "System Ready" banner with URLs.
* **Verification:** Run the script from a completely fresh terminal (no manually-activated venv, no already-running containers) and confirm it works unattended.

### Prompt 3 — Dashboard Reorg + Deterministic Output Composer
* **Task:** Move the Auditable Execution Trace card from the main Analyze results panel into a separate `/audit` route, linked via a small badge (not deleted — PS-26167 requires it to exist somewhere). Build a template-based composer combining GeoChat's answer with deterministic metrics (NDVI, change area, landcover) into one readable paragraph — string composition only, no second LLM call.
* **Verification:** Run the composer against two different real image pairs with genuinely different NDVI/landcover numbers and confirm the output values actually differ between them — the earlier version had a bug where two different metrics both rendered the same number; explicitly test for that not recurring.

---

## Track A — Mining/Land Monitoring

### Prompt 4 — Data Sourcing
* **Task:** Pull real Sentinel-2 time series (via the existing Earth Search STAC pipeline) for two known Indian mining regions — Jharia Coalfield (Dhanbad, Jharkhand) and Joda Iron Ore (Keonjhar, Odisha), at least 3-4 dates per region spanning several weeks. If no official lease-boundary GIS file is available, digitize an approximate boundary polygon from public imagery/reporting and label it explicitly as an approximation in code comments and any UI display — this caveat must be user-visible, not just known internally.

### Prompt 5 — Mining Alert-Check Specialist
* **Task:** Build `mining_monitor.py` reusing the existing `compute_landcover_breakdown()` / `compute_change_area()` functions (don't reimplement) to detect bare-soil/excavation expansion between successive scenes. Register as an alert-check function from Prompt 1. Trigger on expansion exceeding a configurable threshold or extending outside the boundary polygon.
* **Verification:** Run against the real ingested Jharia/Joda time series and manually sanity-check the reported $	ext{km}^2$ expansion against what's visible in the actual before/after imagery — eyeball it, don't just trust the number.

### Prompt 6 — Land Monitoring Dashboard
* **Task:** Add `/land-monitoring`: map view of monitored regions, latest status, triggered alerts, with the boundary-approximation caveat visibly displayed per region.

---

## Track B — Severe Weather Monitoring

### Prompt 7 — MOSDAC Data Pipeline (Verify Real Access Before Building Anything on Top)
* **Task:** Register for MOSDAC access and build `insat_ingest.py` to pull real INSAT-3D/3DR thermal IR (Channel TIR-1, 10.8$\mu$m) frames for a target region. 
* **Verification Gate (Mandatory before Prompt 8 starts):** Confirm the retrieved brightness temperature values trace to an actual MOSDAC archive timestamp for the claimed date — print the raw values and the exact API call/timestamp used, and manually cross-check against MOSDAC's own archive browser. Do not proceed to the risk-detection module until this is confirmed genuinely live, not a placeholder/mock value.

### Prompt 8 — Convective Risk Detection
* **Task:** Build `storm_risk.py`: compute cloud-top cooling rate ($\mathrm{d}T_B/\mathrm{d}t$) across consecutive real thermal frames, threshold against published convective-development criteria (start conservative — real severe cooling events are typically single-digit $	ext{K}/15	ext{min}$, not extreme outlier values; treat any reading beyond $\sim -10	ext{K}/15	ext{min}$ as suspicious and worth re-verifying against Prompt 7's raw data before trusting it). Output "elevated convective development risk," never a precise strike/location prediction. Register as a second alert-check function.

### Prompt 9 — Citation Check for Regional Statistics
* **Task:** Before publishing any specific regional lightning fatality/flash-density figures (e.g., for Mayurbhanj/Chota Nagpur), find and link the exact CROPC/LRIC or IMD report containing those specific numbers for that specific region — the organization (CROPC) is confirmed real, but region-specific figures need their own direct citation, not inference from the organization's existence. If the exact regional figures can't be pinned to a specific published report, use a broader, directly-citable national or state-level statistic instead.

### Prompt 10 — Severe Weather Dashboard
* **Task:** Add `/weather-monitoring`: map view of monitored regions, current risk status, historical alert log, styled consistently with the Track A dashboard.

---

## Final Integration

1. Confirm both alert types flow through the shared `/api/alerts` endpoint correctly.
2. Update About page + pitch materials to reflect the **reactive $
ightarrow$ proactive** pivot.
3. Full rehearsal, ideally demoing a live-triggered alert rather than only an on-demand query.


