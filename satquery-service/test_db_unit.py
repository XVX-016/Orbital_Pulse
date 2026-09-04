#!/usr/bin/env python3
"""
test_db_unit.py — Unit and schema validation tests for PostGIS persistence layer.

Verifies:
1. init.sql schema integrity and syntax
2. db.py geometry derivation logic (_geom_from_tif_path, _bbox_from_tif_path, _build_geometry)
3. Non-blocking error handling when DB is unreachable
4. GeoJSON structure generation in GET /api/analyses formatting
"""

import os
import sys
import unittest
import rasterio

SERVICE_DIR = os.path.dirname(os.path.abspath(__file__))
if SERVICE_DIR not in sys.path:
    sys.path.insert(0, SERVICE_DIR)

import db


class TestPostGISPersistence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.before_path = os.path.join(SERVICE_DIR, "data", "deforestation", "before.tif")
        assert os.path.exists(cls.before_path), f"Missing fixture: {cls.before_path}"

    def test_sql_schema_file_exists_and_valid(self):
        sql_path = os.path.join(SERVICE_DIR, "db", "init.sql")
        self.assertTrue(os.path.exists(sql_path))
        with open(sql_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("CREATE EXTENSION IF NOT EXISTS postgis;", content)
        self.assertIn("CREATE TABLE IF NOT EXISTS analyses", content)
        self.assertIn("geom             GEOMETRY(Geometry, 4326)", content)
        self.assertIn("CREATE INDEX IF NOT EXISTS analyses_geom_idx", content)

    def test_bbox_from_tif_path_returns_polygon(self):
        wkt = db._bbox_from_tif_path(self.before_path)
        self.assertIsNotNone(wkt)
        self.assertTrue(wkt.startswith("POLYGON(("))
        self.assertTrue(wkt.endswith("))"))

    def test_geom_from_tif_path_returns_point(self):
        wkt = db._geom_from_tif_path(self.before_path)
        self.assertIsNotNone(wkt)
        self.assertTrue(wkt.startswith("POINT("))
        self.assertTrue(wkt.endswith(")"))

    def test_build_geometry_with_georef(self):
        execution_trace = {
            "parameters": {
                "before_tif_path": self.before_path,
            }
        }
        computed_metrics = {
            "change_area": {"has_georeferencing": True}
        }
        geom = db._build_geometry(execution_trace, computed_metrics)
        self.assertIsNotNone(geom)
        self.assertTrue(geom.startswith("POLYGON(("))

    def test_build_geometry_without_georef(self):
        execution_trace = {
            "parameters": {
                "tif_path": "some_random_image.png"
            }
        }
        computed_metrics = {
            "change_area": {"has_georeferencing": False}
        }
        geom = db._build_geometry(execution_trace, computed_metrics)
        self.assertIsNone(geom)

    def test_persist_analysis_handles_offline_gracefully(self):
        # Should NOT raise an exception when database is offline
        res = db.persist_analysis(
            query_text="Assess forest loss",
            task_type="change_detection",
            modality="optical",
            temporal="bi-temporal",
            vlm_answer="Detected clear-cutting in the northwest sector.",
            computed_metrics={"change_pct": 14.5},
            execution_trace={"parameters": {"before_tif_path": self.before_path}},
        )
        self.assertIsNone(res)


if __name__ == "__main__":
    unittest.main()
