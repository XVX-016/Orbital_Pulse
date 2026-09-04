#!/usr/bin/env python3
"""
test_geospatial_metrics.py — Unit tests for pure, deterministic geospatial metrics.

Uses real Sentinel-2 before/after GeoTIFF pairs from data/deforestation/ as fixtures,
verifying:
  1. compute_ndvi_coverage: Standard NDVI calculation, thresholding, and hand-checked ranges.
  2. compute_area_from_bbox: Bounding box real-world area calculation using geotransform resolution,
     with explicit None return for unreferenced inputs.
  3. compute_change_area: Bi-temporal pixel spectral difference thresholding and real-world area scaling.
  4. compute_landcover_breakdown: Spectral classification into water/vegetation/builtup/other percentages.
"""

import os
import sys
import unittest
import numpy as np
import rasterio

# Ensure satquery-service root is in sys.path
SERVICE_DIR = os.path.dirname(os.path.abspath(__file__))
if SERVICE_DIR not in sys.path:
    sys.path.insert(0, SERVICE_DIR)

from geospatial_metrics import (
    compute_ndvi_coverage,
    compute_area_from_bbox,
    compute_change_area,
    compute_landcover_breakdown,
    get_pixel_dimensions_meters,
)


class TestGeospatialMetrics(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Load real Sentinel-2 deforestation before/after GeoTIFF fixtures."""
        cls.before_path = os.path.join(SERVICE_DIR, "data", "deforestation", "before.tif")
        cls.after_path = os.path.join(SERVICE_DIR, "data", "deforestation", "after.tif")

        assert os.path.exists(cls.before_path), f"Fixture missing: {cls.before_path}"
        assert os.path.exists(cls.after_path), f"Fixture missing: {cls.after_path}"

        with rasterio.open(cls.before_path) as src:
            cls.before_bands = src.read()
            cls.before_transform = src.transform
            cls.width = src.width
            cls.height = src.height
            cls.crs = src.crs

        with rasterio.open(cls.after_path) as src:
            cls.after_bands = src.read()
            cls.after_transform = src.transform

    def test_fixture_integrity(self):
        """Verify the loaded fixtures conform to expected 6-band 224x224 shape."""
        self.assertEqual(self.before_bands.shape, (6, 224, 224))
        self.assertEqual(self.after_bands.shape, (6, 224, 224))
        self.assertEqual(self.width, 224)
        self.assertEqual(self.height, 224)
        self.assertIsNotNone(self.before_transform)

    def test_compute_ndvi_coverage_ranges(self):
        """Verify NDVI coverage on real Sentinel-2 before/after pairs with hand-checked ranges."""
        # Red is band 2, NIR is band 3 (HLS ordering)
        before_ndvi = compute_ndvi_coverage(self.before_bands, red_band_idx=2, nir_band_idx=3)
        after_ndvi = compute_ndvi_coverage(self.after_bands, red_band_idx=2, nir_band_idx=3)

        # 1. Returned dictionary keys
        for res in (before_ndvi, after_ndvi):
            self.assertIn("vegetation_pct", res)
            self.assertIn("mean_ndvi", res)
            self.assertIn("min_ndvi", res)
            self.assertIn("max_ndvi", res)
            self.assertIn("vegetated_pixel_count", res)
            self.assertIn("total_pixels", res)
            self.assertEqual(res["total_pixels"], 224 * 224)

        # 2. Hand-checked expected ranges for before image:
        # Before image has water/river and cleared regions: vegetation% ~ 88.74%, mean_ndvi ~ 0.624
        self.assertGreaterEqual(before_ndvi["vegetation_pct"], 85.0)
        self.assertLessEqual(before_ndvi["vegetation_pct"], 92.0)
        self.assertAlmostEqual(before_ndvi["vegetation_pct"], 88.74, places=1)
        self.assertGreater(before_ndvi["mean_ndvi"], 0.60)
        self.assertLess(before_ndvi["mean_ndvi"], 0.65)

        # 3. Hand-checked expected ranges for after image:
        # After image has 100% vegetation coverage (>0.2) and higher mean NDVI ~ 0.717
        self.assertEqual(after_ndvi["vegetation_pct"], 100.0)
        self.assertGreater(after_ndvi["mean_ndvi"], 0.70)
        self.assertLess(after_ndvi["mean_ndvi"], 0.75)

        # 4. Verified distinction between the two dates:
        # The two dates exhibit significant vegetative difference (before has non-vegetated patches)
        self.assertNotEqual(before_ndvi["vegetation_pct"], after_ndvi["vegetation_pct"])
        self.assertGreater(before_ndvi["total_pixels"] - before_ndvi["vegetated_pixel_count"], 5000)

    def test_compute_ndvi_synthetic_deterministic(self):
        """Verify NDVI arithmetic on simple, known synthetic numbers."""
        # Shape: (6, 2, 2)
        # Pixel 0,0: NIR=3000, Red=1000 -> NDVI = (3000-1000)/(3000+1000) = 2000/4000 = 0.5 (>0.2 -> veg)
        # Pixel 0,1: NIR=1000, Red=3000 -> NDVI = (1000-3000)/(1000+3000) = -2000/4000 = -0.5 (not veg)
        # Pixel 1,0: NIR=1200, Red=1000 -> NDVI = 200/2200 = 0.0909 (not veg)
        # Pixel 1,1: NIR=4000, Red=1000 -> NDVI = 3000/5000 = 0.6 (>0.2 -> veg)
        synthetic = np.zeros((6, 2, 2), dtype=np.float32)
        synthetic[2] = [[1000, 3000], [1000, 1000]]  # Red
        synthetic[3] = [[3000, 1000], [1200, 4000]]  # NIR

        res = compute_ndvi_coverage(synthetic, red_band_idx=2, nir_band_idx=3)
        self.assertEqual(res["total_pixels"], 4)
        self.assertEqual(res["vegetated_pixel_count"], 2)
        self.assertEqual(res["vegetation_pct"], 50.0)
        expected_mean = (0.5 + (-0.5) + (200.0 / 2200.0) + 0.6) / 4.0
        self.assertAlmostEqual(res["mean_ndvi"], round(expected_mean, 4), places=3)

    def test_compute_area_from_bbox_with_and_without_georeferencing(self):
        """Verify bounding box area computation with real geotransform vs unreferenced None."""
        # 1. Unreferenced / plain upload -> MUST return None explicitly
        box_norm = [10, 10, 50, 50]  # 40% x 40%
        none_res = compute_area_from_bbox(
            box_normalized=box_norm,
            geotransform=None,
            image_width=self.width,
            image_height=self.height,
        )
        self.assertIsNone(none_res, "Unreferenced imagery must return None explicitly without fabricating scale")

        # 2. Real geotransform from Sentinel-2 fixture
        geo_res = compute_area_from_bbox(
            box_normalized=[0, 0, 100, 100],  # Full scene 100% x 100%
            geotransform=self.before_transform,
            image_width=self.width,
            image_height=self.height,
        )
        self.assertIsNotNone(geo_res)
        self.assertEqual(geo_res["pixel_count"], 224 * 224)
        # Sentinel-2 ~2.56 km across, ~8.0 km² total scene area
        self.assertGreater(geo_res["area_km2"], 7.0)
        self.assertLess(geo_res["area_km2"], 9.0)
        self.assertAlmostEqual(geo_res["area_km2"], 8.0, places=0)

        # 3. Quarter-area sub-box [0, 0, 50, 50] -> should be 1/4 of total scene area
        sub_res = compute_area_from_bbox(
            box_normalized=[0, 0, 50, 50],
            geotransform=self.before_transform,
            image_width=self.width,
            image_height=self.height,
        )
        self.assertIsNotNone(sub_res)
        self.assertAlmostEqual(sub_res["area_km2"], geo_res["area_km2"] / 4.0, places=2)

    def test_compute_change_area(self):
        """Verify bi-temporal change detection metrics between before and after GeoTIFFs."""
        # 1. With geotransform
        change_res = compute_change_area(
            before_bands=self.before_bands,
            after_bands=self.after_bands,
            geotransform=self.before_transform,
            threshold=0.15,
        )
        self.assertEqual(change_res["total_pixels"], 224 * 224)
        self.assertGreater(change_res["changed_pixels"], 0)
        self.assertGreater(change_res["change_pct"], 20.0)
        self.assertLess(change_res["change_pct"], 35.0)
        self.assertIsNotNone(change_res["changed_area_km2"])
        self.assertGreater(change_res["changed_area_km2"], 1.5)
        self.assertLess(change_res["changed_area_km2"], 3.0)

        # 2. Without geotransform -> areas must be None, but pixel metrics valid
        unref_change = compute_change_area(
            before_bands=self.before_bands,
            after_bands=self.after_bands,
            geotransform=None,
            threshold=0.15,
        )
        self.assertEqual(unref_change["changed_pixels"], change_res["changed_pixels"])
        self.assertEqual(unref_change["change_pct"], change_res["change_pct"])
        self.assertIsNone(unref_change["changed_area_km2"])
        self.assertIsNone(unref_change["changed_area_m2"])

        # 3. Zero-change sanity check (identical images)
        identical_res = compute_change_area(
            before_bands=self.before_bands,
            after_bands=self.before_bands,
            geotransform=self.before_transform,
            threshold=0.15,
        )
        self.assertEqual(identical_res["changed_pixels"], 0)
        self.assertEqual(identical_res["change_pct"], 0.0)
        self.assertEqual(identical_res["changed_area_km2"], 0.0)

    def test_compute_landcover_breakdown(self):
        """Verify spectral landcover classification on real Sentinel-2 before/after pairs."""
        before_lc = compute_landcover_breakdown(self.before_bands)
        after_lc = compute_landcover_breakdown(self.after_bands)

        # Percentages sum to 100%
        for lc in (before_lc, after_lc):
            total_pct = lc["water_pct"] + lc["vegetation_pct"] + lc["builtup_pct"] + lc["other_pct"]
            self.assertAlmostEqual(total_pct, 100.0, places=1)
            self.assertEqual(lc["total_pixels"], 224 * 224)

        # Before image has river water presence (~9.85%)
        self.assertGreater(before_lc["water_pct"], 5.0)
        self.assertLess(before_lc["water_pct"], 15.0)
        self.assertAlmostEqual(before_lc["water_pct"], 9.85, places=1)
        self.assertAlmostEqual(before_lc["vegetation_pct"], 88.74, places=1)

        # After image has 0% water and 100% vegetation
        self.assertEqual(after_lc["water_pct"], 0.0)
        self.assertEqual(after_lc["vegetation_pct"], 100.0)


if __name__ == "__main__":
    unittest.main()
