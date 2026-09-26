"""Eyeball-verification harness for mining_monitor (Prompt 5).

Runs the specialist against the REAL ingested Jharia / Joda Sentinel-2 series
and prints everything needed to sanity-check the reported km² by eye:

  • which two real scenes were compared, their dates and cloud cover
  • the land-cover bare-ground share on each date
  • the derived expansion in km², and the analysed area it came from
  • a plausibility audit that flags physically implausible numbers
  • the thumbnail URLs of both scenes, so the before/after imagery can be
    opened and the number checked against what is actually visible

This is a REPORTING harness, not a pass/fail unit test: the plan explicitly
asks for a human eyeball check. It exits non-zero only when the pipeline
itself fails or produces a physically impossible figure.

    docker compose exec satquery-service python test_mining_monitor.py
"""

import sys

from mining_monitor import (
    EXPANSION_THRESHOLD_KM2,
    EXPANSION_THRESHOLD_PP,
    analyse_expansion,
    evaluate_region,
    select_scene_pair,
)
from mining_regions import MINING_REGIONS


def audit(metrics) -> list:
    """Flag numbers that cannot be physically right."""
    problems = []
    area = metrics.get("analysed_area_km2")
    exp = metrics.get("expansion_km2")
    delta = metrics.get("bare_ground_delta_pp")

    if area is None:
        problems.append("analysed_area_km2 is None — geotransform was not usable")
    elif not (10.0 < area < 5000.0):
        problems.append(f"analysed_area_km2={area} is outside a sane window for a ~20-40km ROI")

    if exp is not None and area is not None and abs(exp) > area:
        problems.append(f"expansion_km2={exp} exceeds the analysed area {area} — impossible")

    if delta is not None and abs(delta) > 100.0:
        problems.append(f"bare_ground_delta_pp={delta} is outside [-100,100] — impossible")

    for key in ("before_cloud_cover_pct", "after_cloud_cover_pct"):
        cc = metrics.get(key)
        if cc is not None and cc > 60.0:
            problems.append(f"{key}={cc}% exceeds the 60% gate — NDBI unreliable")
    return problems


def main() -> int:
    print("=" * 78)
    print("Mining expansion specialist — real Jharia / Joda imagery")
    print("=" * 78)
    print(f"Thresholds: expansion >= {EXPANSION_THRESHOLD_KM2} km²  "
          f"OR bare-share rise >= {EXPANSION_THRESHOLD_PP} pp")

    hard_failures = []
    analysed = 0

    for region in MINING_REGIONS:
        print(f"\n{'─' * 78}")
        print(f"{region['display_name']}")
        print(f"{'─' * 78}")

        pair = select_scene_pair(region)
        if pair is None:
            print("  SKIP: no usable low-cloud scene pair in the catalog.")
            continue
        before, after = pair

        print(f"  BEFORE  {before['scene_id']}")
        print(f"          date={before['datetime'][:10]}  cloud={before['cloud_cover']}%")
        print(f"          thumb={before.get('thumbnail_url')}")
        print(f"  AFTER   {after['scene_id']}")
        print(f"          date={after['datetime'][:10]}  cloud={after['cloud_cover']}%")
        print(f"          thumb={after.get('thumbnail_url')}")

        print("\n  Reading real COG windows (5 bands x 2 dates)...")
        metrics = analyse_expansion(region, before, after)
        if metrics is None:
            print("  FAIL: could not analyse this pair (COG read failed).")
            hard_failures.append(f"{region['name']}: analyse_expansion returned None")
            continue

        analysed += 1
        print("\n  DETERMINISTIC RESULT")
        print(f"    analysed area          : {metrics['analysed_area_km2']} km²")
        print(f"    bare ground before     : {metrics['bare_ground_pct_before']}%")
        print(f"    bare ground after      : {metrics['bare_ground_pct_after']}%")
        print(f"    delta                  : {metrics['bare_ground_delta_pp']} pp")
        print(f"    => EXPANSION           : {metrics['expansion_km2']} km²")
        print(f"    spectral change        : {metrics['spectral_change_pct']}%")
        print(f"    newly-bare outside bdy : {metrics['newly_bare_outside_boundary_pct']}%")
        print(f"    boundary area          : {metrics.get('boundary_area_km2')} km²")
        print(f"    => NEW BARE INSIDE BDY : {metrics.get('expansion_inside_boundary_km2')} km²  <-- primary signal")

        problems = audit(metrics)
        if problems:
            print("\n  PLAUSIBILITY PROBLEMS:")
            for p in problems:
                print(f"    ✗ {p}")
            hard_failures.extend(f"{region['name']}: {p}" for p in problems)
        else:
            print("\n    ✓ figures are within physically plausible bounds")

        verdict = evaluate_region(region)
        if verdict:
            print(f"\n  ALERT WOULD FIRE: severity={verdict['severity']}")
            print(f"    triggers: {verdict['computed_metrics']['triggers']}")
        else:
            print("\n  No alert (below all thresholds).")

        print(f"\n  CAVEAT CARRIED WITH THE NUMBER:")
        print(f"    boundary_is_approximate = {metrics['boundary_is_approximate']}")
        print(f"    {metrics['boundary_caveat']}")

        print("\n  >>> EYEBALL CHECK: open both thumbnails above and confirm the")
        print(f"  >>> reported {metrics['expansion_km2']} km² of new bare ground is")
        print("  >>> consistent with visible excavation/spoil growth between the dates.")

    print("\n" + "=" * 78)
    if analysed == 0:
        print("FAIL: no region could be analysed.")
        return 1
    if hard_failures:
        print("FAIL: implausible or broken results:")
        for f in hard_failures:
            print(f"  ✗ {f}")
        return 1
    print(f"Pipeline OK on {analysed} region(s). Numbers are plausible;")
    print("the km² figures still require the human eyeball check described above.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
