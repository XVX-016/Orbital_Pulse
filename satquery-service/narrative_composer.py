"""Deterministic narrative composer for SatQuery AI.

Combines the VLM's qualitative answer with the independently computed
geospatial metrics into one readable paragraph.

DESIGN CONSTRAINT — this module performs **string composition only**.  It makes
no model call, no network call and no I/O.  Given the same inputs it always
produces the same output, so a narrative can be regenerated and diffed offline.

─── Why each metric family gets its own clause builder ───────────────────────
`compute_ndvi_coverage()` and `compute_landcover_breakdown()` BOTH return a key
literally named `vegetation_pct`, carrying two different numbers:

    ndvi["vegetation_pct"]       → % pixels above the sparse-NDVI threshold
    landcover["vegetation_pct"]  → % pixels classified vegetation by the
                                   multi-band land-cover rules

Flattening the metric families into a single dict (`{**ndvi, **landcover}`)
silently drops one and renders the survivor twice — two distinct metrics showing
an identical number.  Every clause builder below therefore receives ONLY its own
sub-dict and never sees a merged namespace.  test_narrative_composer.py asserts
this stays true.
"""

from typing import Any, Dict, List, Optional

# Land-cover class keys as emitted by compute_landcover_breakdown(), paired with
# the wording used in prose.
LANDCOVER_LABELS = [
    ("vegetation_pct", "vegetation"),
    ("water_pct", "water"),
    ("builtup_pct", "built-up or bare ground"),
    ("other_pct", "unclassified"),
]


def _fmt_pct(value: Any, digits: int = 1) -> Optional[str]:
    """Render a percentage, or None when the value is absent/non-numeric."""
    if value is None or isinstance(value, bool):
        return None
    try:
        return f"{float(value):.{digits}f}%"
    except (TypeError, ValueError):
        return None


def _fmt_num(value: Any, digits: int = 3) -> Optional[str]:
    """Render a plain number, or None when absent/non-numeric."""
    if value is None or isinstance(value, bool):
        return None
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return None


def _clean_answer(answer: Optional[str]) -> str:
    """Strip markdown emphasis and collapse whitespace from the model answer."""
    if not answer:
        return ""
    text = str(answer).replace("**", "").replace("*", "")
    text = " ".join(text.split())
    return text.strip()


def _ensure_sentence(text: str) -> str:
    """Guarantee terminal punctuation so clauses concatenate cleanly."""
    text = text.strip()
    if text and text[-1] not in ".!?":
        text += "."
    return text


def _ndvi_clause(label: str, ndvi: Optional[Dict[str, Any]]) -> Optional[str]:
    """One sentence about NDVI vegetation coverage.

    Reads ONLY the ndvi sub-dict — see the module docstring on key collisions.
    """
    if not isinstance(ndvi, dict):
        return None

    mean_ndvi = _fmt_num(ndvi.get("mean_ndvi"), 3)
    sparse = _fmt_pct(ndvi.get("vegetation_pct_sparse", ndvi.get("vegetation_pct")))
    dense = _fmt_pct(ndvi.get("vegetation_pct_dense"))

    if mean_ndvi is None and sparse is None:
        return None

    parts: List[str] = []
    if mean_ndvi is not None:
        parts.append(f"a mean NDVI of {mean_ndvi}")
    if sparse is not None:
        parts.append(f"{sparse} of pixels vegetated at the sparse threshold")
    if dense is not None:
        parts.append(f"{dense} at the dense threshold")

    prefix = f"{label} NDVI analysis reports" if label else "NDVI analysis reports"
    return _ensure_sentence(f"{prefix} {', '.join(parts)}")


def _landcover_clause(label: str, lc: Optional[Dict[str, Any]]) -> Optional[str]:
    """One sentence about the land-cover class breakdown.

    Reads ONLY the landcover sub-dict.  Its `vegetation_pct` is a DIFFERENT
    measurement from the NDVI clause's, and is deliberately attributed to
    "land-cover classification" so the two are never confused in prose.
    """
    if not isinstance(lc, dict):
        return None

    shares: List[str] = []
    dominant_key: Optional[str] = None
    dominant_val = float("-inf")

    for key, word in LANDCOVER_LABELS:
        rendered = _fmt_pct(lc.get(key))
        if rendered is None:
            continue
        shares.append(f"{rendered} {word}")
        try:
            numeric = float(lc.get(key))
        except (TypeError, ValueError):
            continue
        if numeric > dominant_val:
            dominant_val = numeric
            dominant_key = word

    if not shares:
        return None

    prefix = f"{label} land-cover classification" if label else "Land-cover classification"
    sentence = f"{prefix} splits the scene into {', '.join(shares)}"
    if dominant_key is not None:
        sentence += f", making {dominant_key} the dominant class"
    return _ensure_sentence(sentence)


def _ndvi_delta_clause(
    before_ndvi: Optional[Dict[str, Any]],
    after_ndvi: Optional[Dict[str, Any]],
) -> Optional[str]:
    """One sentence quantifying the before→after shift in mean NDVI."""
    if not isinstance(before_ndvi, dict) or not isinstance(after_ndvi, dict):
        return None
    try:
        before_val = float(before_ndvi.get("mean_ndvi"))
        after_val = float(after_ndvi.get("mean_ndvi"))
    except (TypeError, ValueError):
        return None

    delta = after_val - before_val
    direction = "a decline" if delta < 0 else "an increase" if delta > 0 else "no net change"
    if delta == 0:
        return _ensure_sentence(
            f"Mean NDVI is unchanged between the two dates at {before_val:.3f}"
        )
    return _ensure_sentence(
        f"Mean NDVI moved from {before_val:.3f} to {after_val:.3f}, "
        f"{direction} of {abs(delta):.3f}"
    )


def _change_clause(sc: Optional[Dict[str, Any]]) -> Optional[str]:
    """One sentence about thresholded spectral change between two dates.

    Accepts both `change_pct` (as compute_change_area returns it) and the
    `changed_pct` spelling used by some callers; likewise for the area key.
    """
    if not isinstance(sc, dict):
        return None

    pct_value = sc.get("change_pct", sc.get("changed_pct"))
    pct = _fmt_pct(pct_value, 2)
    area_value = sc.get("changed_area_km2", sc.get("change_area_km2"))
    area = _fmt_num(area_value, 3)
    georef = sc.get("georeferenced", sc.get("has_georeferencing"))

    if pct is None and area is None:
        return None

    sentence = "Pixel-level spectral differencing flags "
    if pct is not None:
        sentence += f"{pct} of the scene as changed"
    else:
        sentence += "a changed region"

    if area is not None:
        sentence += f", covering {area} km²"
    elif georef is False:
        sentence += ", though the imagery carries no geotransform so the change cannot be expressed in km²"

    return _ensure_sentence(sentence)


def _object_clause(objects: Optional[List[Dict[str, Any]]]) -> Optional[str]:
    """One sentence summarising grounded object footprints."""
    if not isinstance(objects, list) or not objects:
        return None

    described: List[str] = []
    for obj in objects:
        if not isinstance(obj, dict):
            continue
        label = obj.get("label") or "object"
        area = _fmt_num(obj.get("area_km2"), 4)
        described.append(f"{label} ({area} km²)" if area is not None else str(label))

    if not described:
        return None

    noun = "footprint" if len(described) == 1 else "footprints"
    return _ensure_sentence(
        f"Grounding localised {len(described)} {noun}: {', '.join(described)}"
    )


def compose_narrative(
    answer: Optional[str],
    computed_metrics: Optional[Dict[str, Any]],
    task_type: Optional[str] = None,
) -> str:
    """Compose the model answer and deterministic metrics into one paragraph.

    Args:
        answer:           the VLM's qualitative response (may be empty).
        computed_metrics: the metrics dict from the controller (may be None).
        task_type:        optional task label used for the closing attribution.

    Returns:
        A single paragraph.  When no metrics are available the cleaned model
        answer is returned unchanged, with an explicit note that nothing
        independent corroborates it.
    """
    lead = _clean_answer(answer)
    metrics = computed_metrics if isinstance(computed_metrics, dict) else {}

    clauses: List[str] = []

    # Single-image task: one NDVI family and one land-cover family, kept apart.
    clauses.append(_ndvi_clause("", metrics.get("ndvi")))
    clauses.append(_landcover_clause("", metrics.get("landcover")))

    # Bi-temporal task: each date keeps its own labelled clause.
    clauses.append(_ndvi_clause("Before-date", metrics.get("before_ndvi")))
    clauses.append(_ndvi_clause("After-date", metrics.get("after_ndvi")))
    clauses.append(_ndvi_delta_clause(metrics.get("before_ndvi"), metrics.get("after_ndvi")))
    clauses.append(_landcover_clause("Before-date", metrics.get("before_landcover")))
    clauses.append(_landcover_clause("After-date", metrics.get("after_landcover")))
    clauses.append(_change_clause(metrics.get("spectral_change")))

    # Grounding task.
    clauses.append(_object_clause(metrics.get("object_areas")))

    supporting = [c for c in clauses if c]

    if not supporting:
        if not lead:
            return "No model answer and no deterministic metrics are available for this request."
        return _ensure_sentence(lead) + (
            " No deterministic geospatial metrics were computed for this request, "
            "so nothing independently corroborates the statement above."
        )

    body = " ".join(supporting)

    if not lead:
        return (
            "The model returned no usable answer, so the following rests entirely on "
            f"deterministic pixel measurements. {body}"
        )

    task_suffix = f" ({task_type})" if task_type else ""
    return (
        f"{_ensure_sentence(lead)} "
        f"Independently of that answer, deterministic pixel analysis{task_suffix} finds the following. "
        f"{body}"
    )
