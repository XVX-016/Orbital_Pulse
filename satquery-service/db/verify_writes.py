#!/usr/bin/env python3
"""Verification script: confirms analysis rows are landing in PostGIS.

Run after triggering a few queries through the Analyze UI:
    python satquery-service/db/verify_writes.py

Connects using the same DATABASE_URL as the service (env or default).
"""

import os
import sys
import json
import psycopg2
import psycopg2.extras

DATABASE_URL = os.environ.get(
    "SATQUERY_DATABASE_URL",
    "postgresql://orbital_user:orbital_password@localhost:5432/orbital_db",
)

SEP = "─" * 72

def main():
    print(SEP)
    print("SatQuery AI — PostGIS write verification")
    print(f"DSN: {DATABASE_URL}")
    print(SEP)

    try:
        conn = psycopg2.connect(DATABASE_URL)
    except Exception as e:
        print(f"\n❌  Could not connect: {e}")
        print("\nMake sure the postgis container is running:")
        print("    docker compose up postgis -d")
        sys.exit(1)

    with conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:

            # 1. Total row count
            cur.execute("SELECT COUNT(*) AS total FROM analyses;")
            total = cur.fetchone()["total"]
            print(f"\n{'✅' if total > 0 else '⚠️ '} Total rows in analyses: {total}")

            if total == 0:
                print("\n  No rows yet. Run a query through the Analyze UI and try again.")
                return

            # 2. Recent 5 rows
            cur.execute("""
                SELECT
                    id,
                    created_at,
                    task_type,
                    modality,
                    LEFT(query_text, 70) AS query_preview,
                    LEFT(vlm_answer, 60) AS answer_preview,
                    computed_metrics IS NOT NULL AS has_metrics,
                    ST_AsText(geom)       AS geom_wkt
                FROM analyses
                ORDER BY created_at DESC
                LIMIT 5;
            """)
            rows = cur.fetchall()

            print(f"\n{'Last'} {len(rows)} row(s):\n")
            for row in rows:
                print(f"  id={row['id']}  task={row['task_type']}  modality={row['modality']}")
                print(f"  created_at : {row['created_at']}")
                print(f"  query      : {row['query_preview']!r}")
                print(f"  answer     : {row['answer_preview']!r}")
                print(f"  metrics    : {'present' if row['has_metrics'] else 'null'}")
                print(f"  geom       : {row['geom_wkt'] or 'NULL (no georef)'}")
                print()

            # 3. Geometry stats
            cur.execute("""
                SELECT
                    COUNT(*) FILTER (WHERE geom IS NOT NULL) AS with_geom,
                    COUNT(*) FILTER (WHERE geom IS NULL)     AS without_geom,
                    COUNT(*) FILTER (WHERE GeometryType(geom) = 'POINT')   AS points,
                    COUNT(*) FILTER (WHERE GeometryType(geom) = 'POLYGON') AS polygons
                FROM analyses;
            """)
            gs = cur.fetchone()
            print(SEP)
            print(f"Geometry summary:")
            print(f"  Georeferenced rows : {gs['with_geom']}")
            print(f"  Non-georef rows    : {gs['without_geom']}")
            print(f"  Points             : {gs['points']}")
            print(f"  Bbox polygons      : {gs['polygons']}")

            # 4. Spot-check: make sure PostGIS extension is active
            cur.execute("SELECT PostGIS_Full_Version() AS v;")
            postgis_ver = cur.fetchone()["v"].split("POSTGIS=")[1].split()[0]
            print(f"\n✅  PostGIS version  : {postgis_ver}")

    print(SEP)
    print("Verification complete.\n")


if __name__ == "__main__":
    main()
