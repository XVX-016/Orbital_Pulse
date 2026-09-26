"""INSAT-3DR thermal-IR (TIR-1, 10.8 µm) ingestion from MOSDAC (Track B, Prompt 7).

Pulls real INSAT imager frames from MOSDAC (SAC-ISRO), converts TIR-1 counts to
brightness temperature with the LUT shipped inside each file, clips them to the
weather regions in weather_regions.py and stores per-region arrays + statistics
together with everything needed to trace each value back to the archive.

MOSDAC API — endpoints and request shapes are taken from MOSDAC's own client
(mdapi.py, https://www.mosdac.gov.in/software/mdapi.zip):
    search   GET  https://mosdac.gov.in/apios/datasets.json   (no auth)
    token    POST https://mosdac.gov.in/download_api/gettoken  {"username","password"}
    download GET  https://mosdac.gov.in/download_api/download?id=<record id>  Bearer
    refresh  POST https://mosdac.gov.in/download_api/refresh-token {"refresh_token"}
    logout   POST https://mosdac.gov.in/download_api/logout  {"username"}
Rules from the MOSDAC manual that this module respects:
    • 3 consecutive failed logins lock the account for 1 hour → on the first 401
      we stop and never retry until the process is restarted.
    • ≤ 5000 files/day/user and ≤ 100 records per search page.

DEFAULT PRODUCT
    3RIMG_L1C_ASIA_MER — INSAT-3DR imager L1C, Mercator Asia sector (~24 MB per
    frame) instead of the ~437 MB full-disk L1B.  Override with INSAT_DATASET_ID
    (e.g. 3SIMG_L1C_ASIA_MER for INSAT-3DS, or 3RIMG_L1B_STD for full disk).
    INSAT-3D (3DIMG_*) returns "Data unavailable" for 2026 dates.

VERIFICATION GATE (Prompt 7 → Prompt 8)
    Each stored frame gets automatic provenance checks (identifier timestamp ==
    archive timestamp, HDF5 acquisition attributes agree, BT physically
    plausible, geolocation resolved).  That is necessary but not sufficient:
    storm_risk.py stays disabled until a human has run

        python insat_ingest.py verify            # prints raw values + exact calls
        python insat_ingest.py confirm <frame_id> --note "checked on MOSDAC browser"

    after cross-checking the printed identifier/timestamp against MOSDAC's
    archive browser.  Nothing here produces a placeholder or mock value: if a
    step cannot be done for real, it raises.

CLI
    python insat_ingest.py search  [--hours 6]          # archive listing, no login
    python insat_ingest.py ingest  [--hours 6] [--max-files 6] [--keep-raw]
    python insat_ingest.py inspect <file.h5>            # dump HDF5 structure
    python insat_ingest.py verify  [--region NAME] [--limit 4]
    python insat_ingest.py confirm <frame_id> --note "..."
"""

import argparse
import asyncio
import hashlib
import json
import logging
import math
import os
import re
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

import db as analysis_db
from weather_regions import WEATHER_REGIONS

logger = logging.getLogger(__name__)

SEARCH_URL = "https://mosdac.gov.in/apios/datasets.json"
TOKEN_URL = "https://mosdac.gov.in/download_api/gettoken"
DOWNLOAD_URL = "https://mosdac.gov.in/download_api/download"
REFRESH_URL = "https://mosdac.gov.in/download_api/refresh-token"
LOGOUT_URL = "https://mosdac.gov.in/download_api/logout"

DATASET_ID = os.environ.get("INSAT_DATASET_ID", "3RIMG_L1C_ASIA_MER")
DATA_DIR = os.environ.get("INSAT_DATA_DIR", os.path.join("data", "insat"))
USER_AGENT = "SatQuery/1.0 (+insat_ingest)"

# Physically possible TIR-1 brightness temperatures.  The coldest tropical
# overshooting tops reach ~180 K; the hottest land surfaces ~330 K.
BT_MIN_K = 170.0
BT_MAX_K = 340.0
# Brightness-temperature thresholds reported in the per-region statistics:
# 235 K is the conventional cold-cloud / convective-cloud threshold,
# 221 K marks deep convection (both widely used with 10.8 µm IR).
COLD_CLOUD_K = 235.0
DEEP_CONVECTION_K = 221.0
EARTH_RADIUS_M = 6378137.0

_IDENT_RE = re.compile(r"^3[A-Z]IMG_(\d{2}[A-Z]{3}\d{4})_(\d{4})_")


class MosdacError(RuntimeError):
    pass


class MosdacAuthError(MosdacError):
    """Credentials rejected.  Never retried: 3 failures lock the account."""


class GeolocationError(RuntimeError):
    pass


# Set once a login is rejected, so the daemon stops trying (lockout safety).
_AUTH_DISABLED_REASON: Optional[str] = None


def _requests():
    try:
        import requests
        return requests
    except ImportError as e:  # pragma: no cover
        raise MosdacError("The 'requests' package is required for MOSDAC access") from e


def identifier_time(identifier: str) -> Optional[datetime]:
    """3RIMG_20SEP2026_2345_L1C_... → 2026-09-20T23:45Z."""
    m = _IDENT_RE.match(identifier or "")
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1) + m.group(2), "%d%b%Y%H%M").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _parse_iso(s: str) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


# ─── MOSDAC client ────────────────────────────────────────────────────────────

class MosdacClient:
    def __init__(self, username: Optional[str] = None, password: Optional[str] = None):
        self.username = username if username is not None else os.environ.get("MOSDAC_USERNAME", "")
        self.password = password if password is not None else os.environ.get("MOSDAC_PASSWORD", "")
        self.access_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self.req = _requests()

    # Search needs no credentials.
    def search(
        self,
        dataset_id: str,
        start: datetime,
        end: datetime,
        max_records: int = 100,
    ) -> Tuple[List[Dict[str, Any]], List[str]]:
        """Archive entries for [start, end], newest first, plus the exact URLs called."""
        entries: List[Dict[str, Any]] = []
        urls: List[str] = []
        start_index = 1
        while len(entries) < max_records:
            params = {
                "datasetId": dataset_id,
                "startTime": start.strftime("%Y-%m-%d"),
                "endTime": end.strftime("%Y-%m-%d"),
                "count": str(min(100, max_records - len(entries))),
                "startIndex": str(start_index),
            }
            r = self.req.get(SEARCH_URL, params=params, timeout=60, headers={"User-Agent": USER_AGENT})
            urls.append(r.url)
            try:
                body = r.json()
            except ValueError:
                raise MosdacError(f"MOSDAC search returned non-JSON (HTTP {r.status_code}) for {r.url}")
            if r.status_code != 200 or "entries" not in body:
                msg = body.get("message") if isinstance(body, dict) else body
                if isinstance(msg, list) and msg and "unavailable" in str(msg[0]).lower():
                    break  # no files for that window — a real, empty answer
                raise MosdacError(f"MOSDAC search failed (HTTP {r.status_code}): {msg} [{r.url}]")
            page = body.get("entries") or []
            entries.extend(page)
            if len(page) == 0 or start_index + len(page) > int(body.get("totalResults", 0)):
                break
            start_index += len(page)

        # The API filters by DATE; narrow to the requested instant window here.
        out = []
        for e in entries:
            t = _parse_iso(e.get("updated", "")) or identifier_time(e.get("identifier", ""))
            if t and start <= t <= end:
                out.append(e)
        out.sort(key=lambda e: e.get("updated", ""), reverse=True)
        return out, urls

    def login(self) -> None:
        global _AUTH_DISABLED_REASON
        if _AUTH_DISABLED_REASON:
            raise MosdacAuthError(_AUTH_DISABLED_REASON)
        if not self.username or not self.password:
            raise MosdacAuthError(
                "MOSDAC_USERNAME / MOSDAC_PASSWORD are not set. Register at "
                "https://www.mosdac.gov.in/ and add both to the service environment."
            )
        r = self.req.post(
            TOKEN_URL,
            json={"username": self.username, "password": self.password},
            timeout=60,
            headers={"User-Agent": USER_AGENT},
        )
        if r.status_code in (400, 401):
            try:
                err = r.json().get("error")
            except ValueError:
                err = r.text[:200]
            _AUTH_DISABLED_REASON = (
                f"MOSDAC rejected the credentials (HTTP {r.status_code}: {err}). Login attempts are "
                "now DISABLED for this process — MOSDAC locks an account for 1 hour after 3 "
                "consecutive failures. Fix the credentials and restart."
            )
            raise MosdacAuthError(_AUTH_DISABLED_REASON)
        if r.status_code == 503:
            raise MosdacError(f"MOSDAC is under maintenance: {r.text[:200]}")
        r.raise_for_status()
        body = r.json()
        self.access_token = body.get("access_token")
        self.refresh_token = body.get("refresh_token")
        if not self.access_token:
            raise MosdacError("MOSDAC token response had no access_token")

    def _refresh(self) -> None:
        r = self.req.post(REFRESH_URL, json={"refresh_token": self.refresh_token}, timeout=60)
        r.raise_for_status()
        body = r.json()
        self.access_token = body.get("access_token")
        self.refresh_token = body.get("refresh_token")

    def download(self, record_id: str, dest_dir: str) -> Dict[str, Any]:
        """Stream one archive file to dest_dir; returns path, bytes, sha256, headers."""
        if not self.access_token:
            self.login()
        for attempt in (1, 2):
            r = self.req.get(
                DOWNLOAD_URL,
                params={"id": record_id},
                headers={"Authorization": f"Bearer {self.access_token}", "User-Agent": USER_AGENT},
                stream=True,
                timeout=120,
            )
            if r.status_code == 401 and attempt == 1:
                code = ""
                try:
                    code = r.json().get("code", "")
                except ValueError:
                    pass
                if code in ("INVALID_TOKEN", "NO_ACCESS_TOKEN") and self.refresh_token:
                    self._refresh()
                    continue
            if r.status_code != 200:
                try:
                    detail = r.json()
                except ValueError:
                    detail = r.text[:300]
                raise MosdacError(f"MOSDAC download of id={record_id} failed (HTTP {r.status_code}): {detail}")
            break

        cd = r.headers.get("Content-Disposition", "")
        m = re.search(r'filename="?([^";]+)"?', cd)
        filename = m.group(1) if m else f"{record_id}.h5"
        path = os.path.join(dest_dir, os.path.basename(filename))
        sha = hashlib.sha256()
        size = 0
        with open(path, "wb") as fh:
            for chunk in r.iter_content(chunk_size=1 << 20):
                if chunk:
                    fh.write(chunk)
                    sha.update(chunk)
                    size += len(chunk)
        expected = int(r.headers.get("Content-Length", 0) or 0)
        if expected and expected != size:
            raise MosdacError(f"Truncated download for id={record_id}: {size} of {expected} bytes")
        return {
            "path": path,
            "filename": filename,
            "bytes": size,
            "sha256": sha.hexdigest(),
            # The token is deliberately NOT recorded.
            "request": f"GET {DOWNLOAD_URL}?id={record_id}  (Authorization: Bearer <token>)",
        }

    def logout(self) -> None:
        if not self.username or not self.access_token:
            return
        try:
            self.req.post(LOGOUT_URL, json={"username": self.username}, timeout=10)
        except Exception as e:
            logger.debug("MOSDAC logout failed (non-fatal): %s", e)
        self.access_token = None


# ─── HDF5 reading ─────────────────────────────────────────────────────────────

def _attr_value(v: Any) -> Any:
    if isinstance(v, bytes):
        return v.decode("utf-8", "replace").strip()
    if isinstance(v, np.ndarray):
        if v.size == 1:
            return _attr_value(v.reshape(-1)[0])
        if v.dtype.kind in "SO":
            return [_attr_value(x) for x in v.reshape(-1)[:32]]
        return v.reshape(-1)[:32].tolist()
    if isinstance(v, np.generic):
        return v.item()
    return v


def _attrs(obj) -> Dict[str, Any]:
    return {k: _attr_value(v) for k, v in obj.attrs.items()}


def inspect_h5(path: str) -> str:
    """Human-readable dump of every dataset (shape/dtype/attrs) and global attrs."""
    import h5py
    lines = [f"FILE {path}", "GLOBAL ATTRIBUTES:"]
    with h5py.File(path, "r") as f:
        for k, v in _attrs(f).items():
            lines.append(f"  {k} = {v}")
        lines.append("DATASETS:")

        def visit(name, obj):
            if isinstance(obj, h5py.Dataset):
                lines.append(f"  {name}  shape={obj.shape} dtype={obj.dtype}")
                for k, v in _attrs(obj).items():
                    lines.append(f"      @{k} = {v}")
        f.visititems(visit)
    return "\n".join(lines)


def _scaled(ds) -> np.ndarray:
    """Apply CF-style _FillValue / scale_factor / add_offset."""
    a = _attrs(ds)
    arr = ds[...].astype(np.float64)
    fill = a.get("_FillValue")
    if fill is not None:
        arr = np.where(arr == float(fill if not isinstance(fill, list) else fill[0]), np.nan, arr)
    scale = a.get("scale_factor")
    offset = a.get("add_offset")
    if scale is not None:
        arr = arr * float(scale if not isinstance(scale, list) else scale[0])
    if offset is not None:
        arr = arr + float(offset if not isinstance(offset, list) else offset[0])
    return arr


def _squeeze2d(arr: np.ndarray) -> np.ndarray:
    arr = np.squeeze(arr)
    if arr.ndim != 2:
        raise GeolocationError(f"expected a 2-D image, got shape {arr.shape}")
    return arr


def _find_attr(attrs: Dict[str, Any], *names: str) -> Optional[float]:
    low = {k.lower(): v for k, v in attrs.items()}
    for n in names:
        v = low.get(n.lower())
        if v is None:
            continue
        if isinstance(v, list):
            v = v[0]
        try:
            return float(v)
        except (TypeError, ValueError):
            continue
    return None


def _mercator_y(lat_deg: float) -> float:
    return EARTH_RADIUS_M * math.log(math.tan(math.pi / 4 + math.radians(lat_deg) / 2))


def _inv_mercator_lat(y: np.ndarray) -> np.ndarray:
    return np.degrees(2 * np.arctan(np.exp(y / EARTH_RADIUS_M)) - np.pi / 2)


def read_tir1(path: str) -> Dict[str, Any]:
    """Read TIR-1 brightness temperature and geolocation from an INSAT imager file.

    Returns {"bt": 2-D K (NaN = fill), "counts": 2-D raw counts, "lut": 1-D,
             "lat": 1-D (rows) or 2-D, "lon": 1-D (cols) or 2-D,
             "geoloc_method": str, "attrs": global attributes, "geoloc_checks": {...}}
    Raises GeolocationError if geolocation cannot be resolved from the file
    itself — it never guesses a grid.
    """
    import h5py

    with h5py.File(path, "r") as f:
        gattrs = _attrs(f)
        if "IMG_TIR1" not in f or "IMG_TIR1_TEMP" not in f:
            raise GeolocationError(
                "File lacks IMG_TIR1 / IMG_TIR1_TEMP; run `inspect` on it. Keys: " + ", ".join(list(f.keys())[:40])
            )
        counts_ds = f["IMG_TIR1"]
        counts = _squeeze2d(counts_ds[...]).astype(np.int64)
        lut = np.asarray(f["IMG_TIR1_TEMP"][...], dtype=np.float64).reshape(-1)
        fill = _attrs(counts_ds).get("_FillValue")
        fill = None if fill is None else int(fill if not isinstance(fill, list) else fill[0])

        valid = (counts >= 0) & (counts < lut.size)
        if fill is not None:
            valid &= counts != fill
        bt = np.full(counts.shape, np.nan)
        bt[valid] = lut[counts[valid]]
        bt[(bt < BT_MIN_K - 50) | (bt > BT_MAX_K + 50)] = np.nan  # LUT sentinel entries

        checks: Dict[str, Any] = {}
        H, W = counts.shape

        if "Latitude" in f and "Longitude" in f and np.squeeze(f["Latitude"][...]).shape == (H, W):
            lat = _squeeze2d(_scaled(f["Latitude"]))
            lon = _squeeze2d(_scaled(f["Longitude"]))
            method = "latlon_2d_datasets"
        else:
            left = _find_attr(gattrs, "left_longitude", "Left_Longitude", "west_longitude")
            right = _find_attr(gattrs, "right_longitude", "Right_Longitude", "east_longitude")
            upper = _find_attr(gattrs, "upper_latitude", "Upper_Latitude", "north_latitude")
            lower = _find_attr(gattrs, "lower_latitude", "Lower_Latitude", "south_latitude")
            if None in (left, right, upper, lower):
                raise GeolocationError(
                    "No 2-D Latitude/Longitude and no corner-bound attributes; cannot geolocate. "
                    "Run `python insat_ingest.py inspect <file>` and extend read_tir1()."
                )
            if right < left:
                right += 360.0
            lon = left + (np.arange(W) + 0.5) * (right - left) / W
            y_top, y_bot = _mercator_y(upper), _mercator_y(lower)
            ys = y_top + (np.arange(H) + 0.5) * (y_bot - y_top) / H
            lat = _inv_mercator_lat(ys)
            method = "mercator_from_corner_attrs"
            # Cross-check against the file's own Y axis if it has one.
            if "Y" in f:
                try:
                    yv = np.asarray(_scaled(f["Y"])).reshape(-1)
                    if yv.size == H:
                        lat_from_y = _inv_mercator_lat(yv)
                        checks["lat_vs_Y_axis_max_diff_deg"] = float(np.nanmax(np.abs(lat_from_y - lat)))
                except Exception as e:
                    checks["lat_vs_Y_axis_error"] = str(e)
            checks["bounds"] = {"left": left, "right": right, "upper": upper, "lower": lower}

    return {
        "bt": bt,
        "counts": counts,
        "lut": lut,
        "lat": lat,
        "lon": lon,
        "geoloc_method": method,
        "attrs": gattrs,
        "geoloc_checks": checks,
    }


def clip_to_bbox(img: Dict[str, Any], bbox: List[float]) -> Optional[Dict[str, np.ndarray]]:
    """Rectangular subset of bt/counts/lat/lon covering bbox, or None if outside."""
    w, s, e, n = bbox
    lat, lon = img["lat"], img["lon"]
    if lat.ndim == 1:
        rows = np.where((lat >= s) & (lat <= n))[0]
        cols = np.where((lon >= w) & (lon <= e))[0]
        if rows.size == 0 or cols.size == 0:
            return None
        r0, r1, c0, c1 = rows.min(), rows.max() + 1, cols.min(), cols.max() + 1
        sub_lat = np.repeat(lat[r0:r1, None], c1 - c0, axis=1)
        sub_lon = np.repeat(lon[None, c0:c1], r1 - r0, axis=0)
    else:
        inside = (lat >= s) & (lat <= n) & (lon >= w) & (lon <= e)
        if not inside.any():
            return None
        rr, cc = np.where(inside)
        r0, r1, c0, c1 = rr.min(), rr.max() + 1, cc.min(), cc.max() + 1
        sub_lat = lat[r0:r1, c0:c1]
        sub_lon = lon[r0:r1, c0:c1]
    return {
        "bt": img["bt"][r0:r1, c0:c1].astype(np.float32),
        "counts": img["counts"][r0:r1, c0:c1],
        "lat": sub_lat.astype(np.float32),
        "lon": sub_lon.astype(np.float32),
        "window": [int(r0), int(r1), int(c0), int(c1)],
    }


def pixel_area_km2(lat: np.ndarray, lon: np.ndarray) -> float:
    """Mean pixel area of a (near-)regular lat/lon grid subset, in km²."""
    if lat.shape[0] < 2 or lat.shape[1] < 2:
        return float("nan")
    dlat = float(np.nanmedian(np.abs(np.diff(lat, axis=0))))
    dlon = float(np.nanmedian(np.abs(np.diff(lon, axis=1))))
    mean_lat = math.radians(float(np.nanmean(lat)))
    km_per_deg = 111.32
    return (dlat * km_per_deg) * (dlon * km_per_deg * math.cos(mean_lat))


def region_stats(sub: Dict[str, np.ndarray]) -> Dict[str, Any]:
    bt = sub["bt"]
    v = bt[np.isfinite(bt)]
    area = pixel_area_km2(sub["lat"], sub["lon"])
    if v.size == 0:
        return {"valid_pixels": 0, "pixel_area_km2": area}
    return {
        "valid_pixels": int(v.size),
        "total_pixels": int(bt.size),
        "pixel_area_km2": round(area, 3),
        "bt_min_k": round(float(v.min()), 2),
        "bt_p05_k": round(float(np.percentile(v, 5)), 2),
        "bt_p10_k": round(float(np.percentile(v, 10)), 2),
        "bt_mean_k": round(float(v.mean()), 2),
        "bt_max_k": round(float(v.max()), 2),
        "cold_cloud_frac_lt235k": round(float((v < COLD_CLOUD_K).mean()), 4),
        "deep_convection_frac_lt221k": round(float((v < DEEP_CONVECTION_K).mean()), 4),
    }


def raw_sample(sub: Dict[str, np.ndarray], lut: np.ndarray) -> Dict[str, Any]:
    """Centre 3×3 of raw counts with their LUT brightness temperatures."""
    H, W = sub["bt"].shape
    r, c = H // 2, W // 2
    r0, c0 = max(0, r - 1), max(0, c - 1)
    counts = sub["counts"][r0:r0 + 3, c0:c0 + 3]
    return {
        "centre_row_col_in_file": [sub["window"][0] + r, sub["window"][2] + c],
        "centre_lat": round(float(sub["lat"][r, c]), 4),
        "centre_lon": round(float(sub["lon"][r, c]), 4),
        "counts_3x3": counts.tolist(),
        "bt_k_3x3": [[round(float(lut[x]), 2) if 0 <= x < lut.size else None for x in row] for row in counts],
        "lut_size": int(lut.size),
    }


def _acq_times_from_attrs(attrs: Dict[str, Any]) -> Dict[str, str]:
    """Every global attribute that looks like an acquisition date/time."""
    return {
        k: str(v) for k, v in attrs.items()
        if isinstance(k, str) and "acq" in k.lower() and ("time" in k.lower() or "date" in k.lower())
    }


def _parse_attr_time(attrs: Dict[str, Any]) -> Optional[datetime]:
    """Best-effort parse of the HDF5 acquisition timestamp (formats vary by product)."""
    acq = _acq_times_from_attrs(attrs)
    date_s = next((v for k, v in acq.items() if "date" in k.lower()), None)
    time_s = next((v for k, v in acq.items() if "time" in k.lower() and "date" not in k.lower()), None)
    candidates = []
    if date_s and time_s:
        candidates.append(f"{date_s} {time_s}")
    candidates.extend(acq.values())
    for c in candidates:
        # Pull a date (20SEP2026 / 20-SEP-2026 / 2026-09-20) and a time
        # (23:45:01 / 2345) out of whatever layout the product uses.
        c = c.strip().upper()
        d = (re.search(r"\d{2}-?[A-Z]{3}-?\d{4}", c) or re.search(r"\d{4}-\d{2}-\d{2}", c))
        t = re.search(r"(\d{2}):?(\d{2})(?::?(\d{2}))?(?!\d)", c[d.end():] if d else c)
        if not d or not t:
            continue
        ds = d.group(0).replace("-", "")
        date_fmt = "%Y%m%d" if ds[:4].isdigit() else "%d%b%Y"
        try:
            base = datetime.strptime(ds, date_fmt)
        except ValueError:
            continue
        return base.replace(
            hour=int(t.group(1)), minute=int(t.group(2)), second=int(t.group(3) or 0), tzinfo=timezone.utc
        )
    return None


def automatic_checks(entry: Dict[str, Any], img: Dict[str, Any], stats: Dict[str, Any]) -> Dict[str, Any]:
    """Provenance and plausibility checks recorded with every frame."""
    ident_t = identifier_time(entry.get("identifier", ""))
    archive_t = _parse_iso(entry.get("updated", ""))
    attr_t = _parse_attr_time(img["attrs"])
    checks: Dict[str, Any] = {
        "identifier_time": ident_t.isoformat() if ident_t else None,
        "archive_updated": archive_t.isoformat() if archive_t else None,
        "archive_dcDate": entry.get("dcDate"),
        "h5_acquisition_attrs": _acq_times_from_attrs(img["attrs"]),
        "h5_acquisition_parsed": attr_t.isoformat() if attr_t else None,
        "geoloc_method": img["geoloc_method"],
        **img.get("geoloc_checks", {}),
    }
    failures = []
    if not ident_t or not archive_t or abs((ident_t - archive_t).total_seconds()) > 120:
        failures.append("identifier timestamp does not match archive 'updated' timestamp")
    if attr_t and archive_t and abs((attr_t - archive_t).total_seconds()) > 1800:
        failures.append("HDF5 acquisition attribute is >30 min from the archive timestamp")
    if stats.get("valid_pixels", 0) < 16:
        failures.append("fewer than 16 valid TIR-1 pixels in the region")
    else:
        if stats["bt_min_k"] < BT_MIN_K or stats["bt_max_k"] > BT_MAX_K:
            failures.append(
                f"brightness temperature outside physical range [{BT_MIN_K}, {BT_MAX_K}] K "
                f"(min {stats['bt_min_k']}, max {stats['bt_max_k']})"
            )
    if checks.get("lat_vs_Y_axis_max_diff_deg", 0) > 0.1:
        failures.append("latitude grid disagrees with the file's Y axis by >0.1°")
    checks["failures"] = failures
    checks["passed"] = not failures
    return checks


# ─── Ingest pipeline ──────────────────────────────────────────────────────────

def ingest(
    hours: float = 6.0,
    max_files: int = 6,
    keep_raw: bool = False,
    dataset_id: str = DATASET_ID,
    regions: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """Download the newest frames within `hours` and store every region clip.

    Returns a summary per stored (frame, region).  Raises on auth failure.
    """
    regions = regions or [r for r in WEATHER_REGIONS if r.get("insat_monitored")]
    client = MosdacClient()
    end = datetime.now(timezone.utc)
    start = end - timedelta(hours=hours)
    entries, search_urls = client.search(dataset_id, start, end, max_records=100)
    logger.info("INSAT: %d archive entries for %s in the last %.1f h", len(entries), dataset_id, hours)

    # One file per distinct acquisition minute (the archive sometimes lists
    # 01:44 and 01:45 twice); skip files already stored for every region.
    seen_times = set()
    todo = []
    for e in entries:
        t = e.get("updated")
        if t in seen_times:
            continue
        seen_times.add(t)
        if all(analysis_db.insat_frame_exists(e["identifier"], r["name"]) for r in regions):
            continue
        todo.append(e)
        if len(todo) >= max_files:
            break

    if not todo:
        logger.info("INSAT: nothing new to download.")
        return []

    os.makedirs(DATA_DIR, exist_ok=True)
    stored: List[Dict[str, Any]] = []
    tmpdir = tempfile.mkdtemp(prefix="insat_", dir=DATA_DIR)
    try:
        client.login()
        for e in reversed(todo):  # oldest first, so frames land in time order
            dl = client.download(e["id"], tmpdir)
            try:
                img = read_tir1(dl["path"])
            except Exception:
                logger.error("INSAT: could not read %s; structure follows:\n%s", dl["filename"], inspect_h5(dl["path"]))
                raise
            acquired = _parse_iso(e["updated"]) or identifier_time(e["identifier"])
            for region in regions:
                sub = clip_to_bbox(img, region["bbox"])
                if sub is None:
                    logger.warning("INSAT: %s does not cover region %s", e["identifier"], region["name"])
                    continue
                stats = region_stats(sub)
                checks = automatic_checks(e, img, stats)
                rdir = os.path.join(DATA_DIR, region["name"])
                os.makedirs(rdir, exist_ok=True)
                array_path = os.path.join(rdir, e["identifier"].replace(".h5", ".npz"))
                np.savez_compressed(array_path, bt=sub["bt"], lat=sub["lat"], lon=sub["lon"])
                row = {
                    "dataset_id": dataset_id,
                    "identifier": e["identifier"],
                    "record_id": str(e["id"]),
                    "region_name": region["name"],
                    "acquired_at": acquired,
                    "search_url": search_urls[0] if search_urls else None,
                    "download_request": dl["request"],
                    "archive_link": e.get("enclosureLink"),
                    "file_sha256": dl["sha256"],
                    "file_bytes": dl["bytes"],
                    "h5_attrs": {k: v for k, v in img["attrs"].items() if not isinstance(v, (list, dict)) or len(str(v)) < 500},
                    "geoloc_method": img["geoloc_method"],
                    "raw_sample": raw_sample(sub, img["lut"]),
                    "stats": stats,
                    "array_path": array_path,
                    "auto_checks": checks,
                    "auto_checks_passed": checks["passed"],
                }
                frame_id = analysis_db.insert_insat_frame(row)
                stored.append({"id": frame_id, **{k: row[k] for k in ("identifier", "region_name", "auto_checks_passed")}, "stats": stats})
                logger.info(
                    "INSAT: stored frame %s for %s (id=%s, checks %s)",
                    e["identifier"], region["name"], frame_id, "passed" if checks["passed"] else checks["failures"],
                )
            if keep_raw:
                os.replace(dl["path"], os.path.join(DATA_DIR, dl["filename"]))
            else:
                os.remove(dl["path"])
    finally:
        client.logout()
        try:
            for fn in os.listdir(tmpdir):
                os.remove(os.path.join(tmpdir, fn))
            os.rmdir(tmpdir)
        except OSError:
            pass
    return stored


def load_frame_arrays(frame: Dict[str, Any]) -> Dict[str, np.ndarray]:
    with np.load(frame["array_path"]) as z:
        return {"bt": z["bt"], "lat": z["lat"], "lon": z["lon"]}


def credentials_configured() -> bool:
    return bool(os.environ.get("MOSDAC_USERNAME") and os.environ.get("MOSDAC_PASSWORD"))


def auth_disabled_reason() -> Optional[str]:
    return _AUTH_DISABLED_REASON


# ─── Daemon ───────────────────────────────────────────────────────────────────

async def insat_daemon() -> None:
    """Poll MOSDAC every INSAT_POLL_MINUTES (default 30, the imager cadence),
    ingest new frames, then run the convective-risk alert check over the
    weather regions.  Idle (with a log line) until credentials are configured."""
    loop = asyncio.get_event_loop()
    interval = max(5.0, float(os.environ.get("INSAT_POLL_MINUTES", "30"))) * 60
    await asyncio.sleep(5)
    if not credentials_configured():
        logger.warning(
            "INSAT daemon idle: MOSDAC_USERNAME / MOSDAC_PASSWORD not set. Track B severe-weather "
            "monitoring needs a MOSDAC account (https://www.mosdac.gov.in/)."
        )
        return
    while True:
        try:
            await loop.run_in_executor(None, ingest)
        except MosdacAuthError as e:
            logger.error("INSAT daemon stopped: %s", e)
            return
        except Exception as e:
            logger.error("INSAT ingest cycle failed (will retry next cycle): %s", e)
        try:
            from stac_catalog import run_alert_checks
            import storm_risk
            await loop.run_in_executor(
                None,
                lambda: run_alert_checks(rois=WEATHER_REGIONS, checks=[storm_risk.storm_risk_check]),
            )
        except Exception as e:
            logger.warning("Convective alert pass failed (non-fatal): %s", e)
        await asyncio.sleep(interval)


# ─── CLI ──────────────────────────────────────────────────────────────────────

def _print_frame(f: Dict[str, Any]) -> None:
    s = f.get("stats") or {}
    raw = f.get("raw_sample") or {}
    ch = f.get("auto_checks") or {}
    print(f"\n── frame id={f['id']}  region={f['region_name']}")
    print(f"   identifier      : {f['identifier']}  (MOSDAC record id {f['record_id']})")
    print(f"   acquired_at     : {f['acquired_at']}")
    print(f"   archive dcDate  : {ch.get('archive_dcDate')}")
    print(f"   h5 acquisition  : {ch.get('h5_acquisition_attrs')}")
    print(f"   search call     : GET {f['search_url']}")
    print(f"   download call   : {f['download_request']}")
    print(f"   archive page    : {f['archive_link']}")
    print(f"   file sha256     : {f['file_sha256']}  ({f['file_bytes']} bytes)")
    print(f"   geolocation     : {f['geoloc_method']}")
    print(f"   raw centre pixel: file row/col {raw.get('centre_row_col_in_file')} at "
          f"{raw.get('centre_lat')}N {raw.get('centre_lon')}E")
    print(f"   raw counts 3x3  : {raw.get('counts_3x3')}")
    print(f"   LUT BT (K) 3x3  : {raw.get('bt_k_3x3')}")
    print(f"   region BT (K)   : min {s.get('bt_min_k')}  p10 {s.get('bt_p10_k')}  mean {s.get('bt_mean_k')}  "
          f"max {s.get('bt_max_k')}  cold<235K {s.get('cold_cloud_frac_lt235k')}")
    print(f"   automatic checks: {'PASSED' if f['auto_checks_passed'] else 'FAILED ' + str(ch.get('failures'))}")
    print(f"   manual check    : {f['manually_verified_at'] or 'NOT YET CONFIRMED'}"
          f"{'  — ' + f['manually_verified_note'] if f.get('manually_verified_note') else ''}")


def main(argv: Optional[List[str]] = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    s1 = sub.add_parser("search"); s1.add_argument("--hours", type=float, default=6)
    s1.add_argument("--dataset", default=DATASET_ID)
    s2 = sub.add_parser("ingest"); s2.add_argument("--hours", type=float, default=6)
    s2.add_argument("--max-files", type=int, default=6); s2.add_argument("--keep-raw", action="store_true")
    s2.add_argument("--dataset", default=DATASET_ID)
    s3 = sub.add_parser("inspect"); s3.add_argument("path")
    s4 = sub.add_parser("verify"); s4.add_argument("--region"); s4.add_argument("--limit", type=int, default=4)
    s5 = sub.add_parser("confirm"); s5.add_argument("frame_id", type=int); s5.add_argument("--note", required=True)
    a = p.parse_args(argv)

    if a.cmd == "search":
        end = datetime.now(timezone.utc)
        entries, urls = MosdacClient().search(a.dataset, end - timedelta(hours=a.hours), end)
        for u in urls:
            print(f"GET {u}")
        print(f"{len(entries)} file(s) for {a.dataset} in the last {a.hours} h:")
        for e in entries:
            print(f"  {e['updated']}  id={e['id']}  {e['identifier']}")
        return 0

    if a.cmd == "ingest":
        stored = ingest(hours=a.hours, max_files=a.max_files, keep_raw=a.keep_raw, dataset_id=a.dataset)
        print(f"Stored {len(stored)} (frame, region) row(s).")
        for s in stored:
            print(f"  id={s['id']} {s['identifier']} {s['region_name']} checks={'ok' if s['auto_checks_passed'] else 'FAILED'}"
                  f" BT min/mean={s['stats'].get('bt_min_k')}/{s['stats'].get('bt_mean_k')} K")
        print("\nNext: `python insat_ingest.py verify`, cross-check on MOSDAC, then `confirm <id>`.")
        return 0

    if a.cmd == "inspect":
        print(inspect_h5(a.path))
        return 0

    if a.cmd == "verify":
        frames = analysis_db.get_insat_frames(region_name=a.region, limit=a.limit)
        if not frames:
            print("No INSAT frames stored yet. Run `python insat_ingest.py ingest` first.")
            return 1
        print("=" * 78)
        print("INSAT VERIFICATION GATE — raw values and the exact calls that produced them")
        print("=" * 78)
        for f in frames:
            _print_frame(f)
        print("\nManual step: open https://www.mosdac.gov.in/ (Catalog → INSAT-3DR Imager), find the")
        print("identifier above, confirm the file exists with that acquisition time, then run:")
        print("  python insat_ingest.py confirm <frame_id> --note \"<what you checked>\"")
        print(f"\nGate state for {DATASET_ID}: "
              f"{'OPEN (manually verified)' if analysis_db.insat_pipeline_verified(DATASET_ID) else 'CLOSED — storm_risk.py will not run'}")
        return 0

    if a.cmd == "confirm":
        f = analysis_db.get_insat_frame(a.frame_id)
        if not f:
            print(f"No frame with id {a.frame_id}.")
            return 1
        if not f["auto_checks_passed"]:
            print(f"Frame {a.frame_id} FAILED its automatic checks: {(f.get('auto_checks') or {}).get('failures')}")
            print("It cannot be used to open the verification gate.")
            return 1
        analysis_db.confirm_insat_frame(a.frame_id, a.note)
        print(f"Frame {a.frame_id} ({f['identifier']}) confirmed. Gate for {f['dataset_id']} is now OPEN.")
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
