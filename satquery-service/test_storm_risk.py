#!/usr/bin/env python3
"""
test_storm_risk.py — Unit tests for the Track B INSAT pipeline math.

The arrays and HDF5 files built here are TEST FIXTURES for the arithmetic and
parsing only.  They never reach the database or the alert path; real alerts
come exclusively from MOSDAC frames that passed the Prompt 7 gate.

Verifies:
1. Cooling rate is normalised to K/15 min and restricted to below-freezing tops
2. Thresholds: −4 K/15 min → info, −8 sustained → warning, never critical
3. Regional rates beyond −10 K/15 min are capped at info and flagged for re-verification
4. Pairs outside 10–45 min and mismatched grids are refused
5. read_tir1 converts counts through the in-file LUT and geolocates both
   L1B-style (2-D lat/lon) and L1C Mercator (corner attributes) layouts
6. Automatic provenance checks catch a timestamp mismatch
"""

import os
import sys
import tempfile
import unittest

import numpy as np

SERVICE_DIR = os.path.dirname(os.path.abspath(__file__))
if SERVICE_DIR not in sys.path:
    sys.path.insert(0, SERVICE_DIR)

import storm_risk
import insat_ingest


def _grid(n=20):
    lat, lon = np.meshgrid(np.linspace(22.0, 23.0, n), np.linspace(85.0, 86.0, n), indexing="ij")
    return lat.astype(np.float32), lon.astype(np.float32)


def _frame(ident, t):
    return {"identifier": ident, "acquired_at": t}


def _arrays(bt):
    lat, lon = _grid(bt.shape[0])
    return {"bt": bt.astype(np.float32), "lat": lat, "lon": lon}


PIXEL_KM2 = 16.0  # ~4 km INSAT TIR pixel


class TestCoolingMath(unittest.TestCase):
    def test_rate_normalised_to_15_minutes(self):
        before = _arrays(np.full((20, 20), 260.0))
        after = _arrays(np.full((20, 20), 250.0))       # −10 K over 30 min
        step = storm_risk.cooling_step(before, after, 30.0, PIXEL_KM2)
        self.assertAlmostEqual(step["regional_rate_k_per_15min"], -5.0, places=3)

    def test_warm_tops_are_ignored(self):
        before = _arrays(np.full((20, 20), 300.0))
        after = _arrays(np.full((20, 20), 285.0))       # strong cooling but above freezing
        step = storm_risk.cooling_step(before, after, 30.0, PIXEL_KM2)
        self.assertEqual(step["below_freezing_pixels"], 0)
        self.assertIsNone(step["regional_rate_k_per_15min"])

    def test_grid_mismatch_refused(self):
        before = _arrays(np.full((20, 20), 260.0))
        after = _arrays(np.full((20, 20), 250.0))
        after["lat"] = after["lat"] + 0.5
        self.assertFalse(storm_risk.cooling_step(before, after, 30.0, PIXEL_KM2)["usable"])


class TestAssessment(unittest.TestCase):
    T = ["2026-05-10T09:15:00+00:00", "2026-05-10T09:45:00+00:00", "2026-05-10T10:15:00+00:00"]

    def _run(self, bts, times=None):
        times = times or self.T[: len(bts)]
        frames = [_frame(f"F{i}", t) for i, t in enumerate(times)]
        return storm_risk.assess(frames, [_arrays(b) for b in bts], PIXEL_KM2)

    def test_no_cooling_no_risk(self):
        r = self._run([np.full((20, 20), 250.0)] * 3)
        self.assertEqual(r["status"], "no_elevated_risk")
        self.assertIsNone(r["risk"])

    def test_weak_growth_is_info(self):
        # −12 K over 30 min = −6 K/15 min on a 10×10 patch (1600 km²)
        a = np.full((20, 20), 280.0); b = a.copy(); b[:10, :10] = 262.0
        c = b.copy(); c[:10, :10] = 250.0
        r = self._run([b, c], self.T[1:])
        self.assertEqual(r["status"], "elevated")
        self.assertEqual(r["severity"], "info")
        self.assertEqual(r["risk"], storm_risk.RISK_LABEL)

    def test_strong_sustained_is_warning_never_critical(self):
        a = np.full((20, 20), 272.0)
        b = a.copy(); b[:10, :10] = 254.0   # −9 K/15 min
        c = b.copy(); c[:10, :10] = 236.0   # −9 K/15 min again
        r = self._run([a, b, c])
        self.assertTrue(r["sustained_over_two_steps"])
        self.assertEqual(r["severity"], "warning")

    def test_suspicious_rate_capped_and_flagged(self):
        a = np.full((20, 20), 270.0)
        b = a.copy(); b[:, :] = 230.0        # −20 K/15 min: implausible
        r = self._run([a, b], self.T[:2])
        self.assertEqual(r["status"], "needs_reverification")
        self.assertEqual(r["severity"], "info")
        self.assertTrue(r["suspicious_rate"])
        self.assertIn("insat_ingest.py verify", r["reverify"])

    def test_small_area_does_not_flag(self):
        a = np.full((20, 20), 270.0)
        b = a.copy(); b[0, :3] = 240.0       # 3 pixels ≈ 48 km² < 150 km²
        r = self._run([a, b], self.T[:2])
        self.assertNotEqual(r.get("status"), "elevated")

    def test_pairs_outside_window_skipped(self):
        a = np.full((20, 20), 270.0); b = np.full((20, 20), 240.0)
        r = self._run([a, b], ["2026-05-10T09:00:00+00:00", "2026-05-10T11:00:00+00:00"])
        self.assertEqual(r["status"], "insufficient_data")


class TestInsatParsing(unittest.TestCase):
    def setUp(self):
        try:
            import h5py  # noqa: F401
        except ImportError:
            self.skipTest("h5py not installed")
        self.tmp = tempfile.mkdtemp()

    def _lut(self):
        return np.linspace(330.0, 180.0, 1024)   # count 0 → 330 K, 1023 → 180 K

    def test_l1c_mercator_corner_attrs(self):
        import h5py
        path = os.path.join(self.tmp, "l1c.h5")
        counts = np.zeros((1, 40, 50), dtype=np.uint16); counts[0, 10, 20] = 1023
        with h5py.File(path, "w") as f:
            f.attrs["left_longitude"] = 80.0; f.attrs["right_longitude"] = 90.0
            f.attrs["upper_latitude"] = 25.0; f.attrs["lower_latitude"] = 20.0
            f.attrs["Acquisition_Date"] = b"10MAY2026"; f.attrs["Acquisition_Time_in_GMT"] = b"0915"
            d = f.create_dataset("IMG_TIR1", data=counts); d.attrs["_FillValue"] = np.uint16(0)
            f.create_dataset("IMG_TIR1_TEMP", data=self._lut())
        img = insat_ingest.read_tir1(path)
        self.assertEqual(img["geoloc_method"], "mercator_from_corner_attrs")
        self.assertAlmostEqual(float(img["bt"][10, 20]), 180.0, places=3)
        self.assertTrue(np.isnan(img["bt"][0, 0]))          # fill value masked
        self.assertTrue(20.0 < img["lat"][-1] < img["lat"][0] < 25.0)
        sub = insat_ingest.clip_to_bbox(img, [84.0, 21.0, 86.0, 23.0])
        self.assertIsNotNone(sub)
        self.assertTrue(np.all((sub["lon"] >= 84.0) & (sub["lon"] <= 86.0)))
        t = insat_ingest._parse_attr_time(img["attrs"])
        self.assertEqual(t.isoformat(), "2026-05-10T09:15:00+00:00")

    def test_l1b_latlon_datasets(self):
        import h5py
        path = os.path.join(self.tmp, "l1b.h5")
        lat, lon = _grid(30)
        with h5py.File(path, "w") as f:
            f.create_dataset("IMG_TIR1", data=np.full((1, 30, 30), 512, dtype=np.uint16))
            f.create_dataset("IMG_TIR1_TEMP", data=self._lut())
            la = f.create_dataset("Latitude", data=(lat * 100).astype(np.int16)); la.attrs["scale_factor"] = 0.01
            lo = f.create_dataset("Longitude", data=(lon * 100).astype(np.int16)); lo.attrs["scale_factor"] = 0.01
        img = insat_ingest.read_tir1(path)
        self.assertEqual(img["geoloc_method"], "latlon_2d_datasets")
        self.assertAlmostEqual(float(img["lat"][0, 0]), 22.0, places=2)

    def test_no_geolocation_raises(self):
        import h5py
        path = os.path.join(self.tmp, "bad.h5")
        with h5py.File(path, "w") as f:
            f.create_dataset("IMG_TIR1", data=np.zeros((1, 5, 5), dtype=np.uint16))
            f.create_dataset("IMG_TIR1_TEMP", data=self._lut())
        with self.assertRaises(insat_ingest.GeolocationError):
            insat_ingest.read_tir1(path)


class TestProvenanceChecks(unittest.TestCase):
    STATS = {"valid_pixels": 400, "bt_min_k": 210.0, "bt_max_k": 300.0}

    def _img(self, attrs):
        return {"attrs": attrs, "geoloc_method": "mercator_from_corner_attrs", "geoloc_checks": {}}

    def test_identifier_time(self):
        t = insat_ingest.identifier_time("3RIMG_25SEP2026_1645_L1C_ASIA_MER_V01R00.h5")
        self.assertEqual(t.isoformat(), "2026-09-25T16:45:00+00:00")

    def test_matching_times_pass(self):
        e = {"identifier": "3RIMG_25SEP2026_1645_L1C_ASIA_MER_V01R00.h5", "updated": "2026-09-25T16:45:00Z"}
        c = insat_ingest.automatic_checks(e, self._img({"Acquisition_Date": "25SEP2026", "Acquisition_Time_in_GMT": "1645"}), self.STATS)
        self.assertTrue(c["passed"], c["failures"])

    def test_timestamp_mismatch_fails(self):
        e = {"identifier": "3RIMG_25SEP2026_1645_L1C_ASIA_MER_V01R00.h5", "updated": "2026-09-24T10:00:00Z"}
        c = insat_ingest.automatic_checks(e, self._img({}), self.STATS)
        self.assertFalse(c["passed"])

    def test_implausible_bt_fails(self):
        e = {"identifier": "3RIMG_25SEP2026_1645_L1C_ASIA_MER_V01R00.h5", "updated": "2026-09-25T16:45:00Z"}
        c = insat_ingest.automatic_checks(e, self._img({}), {"valid_pixels": 400, "bt_min_k": 90.0, "bt_max_k": 300.0})
        self.assertFalse(c["passed"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
