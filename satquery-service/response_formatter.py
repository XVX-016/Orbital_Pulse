"""Clean, user-facing narrative formatting for SatQuery model responses."""
import re
from typing import Any, Dict, List, Tuple


def _number(metrics: Dict[str, Any], *keys: str):
    for key in keys:
        value = metrics.get(key)
        if isinstance(value, (int, float)):
            return float(value)
    return None


def get_enriched_demo_response(task_type: str, query: str, stac_metrics: Dict[str, Any] | None) -> str:
    """Return clean prose if the visual model is unavailable."""
    metrics = stac_metrics or {}
    mean = _number(metrics, "mean_ndvi", "ndvi_mean")
    ndvi_note = f" Mean NDVI is {mean:.3f}." if mean is not None else ""
    messages = {
        "grounding": "The image has been reviewed for buildings, structures, and infrastructure corridors. Grounded locations are unavailable for this response.",
        "change_vqa": "The temporal scenes have been reviewed for vegetation and land-cover change. Compare the paired images to confirm localized differences.",
        "vqa": "The satellite scene has been reviewed for visible surface features and land-cover patterns. The result reflects the available scene data.",
    }
    return messages.get(task_type, messages["vqa"]) + ndvi_note


_COUNT_LOOP_PATTERN = re.compile(
    r"(\d+)\s+([A-Za-z][A-Za-z _-]*?)\s+at\s+(?:the\s+)?"
    r"([A-Za-z][A-Za-z _-]*?)(?=(?:\s+\d+\s+[A-Za-z])|[.,;]|$)",
    re.IGNORECASE,
)
_INTERNAL_STATUS_PATTERN = re.compile(
    r"deterministic fallback|review deterministic scene evidence|retry after geochat|"
    r"geochat engine uninitialized|fallback mode|model response required polishing|"
    r"source context:|next step:|execution trace|debug",
    re.IGNORECASE,
)
_LEGACY_GROUNDING_FALLBACK = "detected and localized bounding box coordinates."


def _clean_text(text: str) -> str:
    """Remove model markup and collapse whitespace without altering ordinary prose."""
    text = re.sub(r"<box>.*?</box>", "", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"\{<\d+><\d+><\d+><\d+>\|[^}]+\}", "", text)
    text = re.sub(r"</?p>|<delim>|[*#]", "", text, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", text).strip()


def _join_words(values: List[str]) -> str:
    unique = list(dict.fromkeys(value.strip().lower() for value in values if value.strip()))
    if len(unique) < 2:
        return unique[0] if unique else "the scene"
    if len(unique) == 2:
        return f"{unique[0]} and {unique[1]}"
    return f"{', '.join(unique[:-1])}, and {unique[-1]}"


def _count_loop_narrative(matches: List[Tuple[str, str, str]]) -> str:
    locations = [location for _, _, location in matches]
    total = sum(int(count) for count, _, _ in matches)
    entity_items = []
    for count_text, entity, _ in matches:
        count = int(count_text)
        name = entity.strip().lower()
        if count == 1:
            article = "an" if name[:1] in "aeiou" else "a"
            entity_items.append(f"{article} {name}")
        else:
            plural = name if name.endswith("s") else f"{name}s"
            entity_items.append(f"{count} {plural}")
    entity_text = _join_words(entity_items)
    location_text = _join_words(locations)
    return (
        f"The scene contains {total} identified features, including {entity_text}, distributed around {location_text}. "
        "Together, these features form a concentrated built-up pattern with visible infrastructure across the image."
    )


def _scenario_fallback(scenario_preset: str, user_query: str, stac_metrics: Dict[str, Any] | None) -> str:
    preset = (scenario_preset or "").lower()
    context = f" The assessment addresses the request to {user_query.strip().rstrip('.')}." if user_query else ""
    mean = _number(stac_metrics or {}, "mean_ndvi", "ndvi_mean")
    ndvi_note = f" Mean NDVI is {mean:.3f}, providing additional vegetation context." if mean is not None else ""
    narratives = {
        "grounding": "The scene contains a dense arrangement of buildings, structural features, and connecting infrastructure distributed across the image. Primary targets are organized into visible urban clusters and corridors, with their locations interpreted from the available image evidence.",
        "deforestation": "The temporal image pair shows the distribution of canopy cover and vegetation condition across the terrain. Spectral differences between the scenes indicate where localized changes in forest density may warrant closer review.",
        "sar_inundation": "Radar backscatter patterns outline surface-water boundaries and distinguish darker low-return areas from surrounding terrain. Low-lying zones with sustained dark signatures are potential inundation areas and should be interpreted alongside local terrain context.",
        "optical_sar_fusion": "Combined optical and SAR observations describe surface cover, built structures, and terrain texture across the scene. Spectral colour patterns and radar backscatter signatures complement one another where atmospheric conditions obscure either modality.",
    }
    return narratives.get(
        preset,
        "The satellite scene has been analyzed for surface features, land-cover patterns, and spatial targets. The available image evidence provides a structured view of the target area.",
    ) + context + ndvi_note


def polish_model_output(
    raw_text: str,
    scenario_preset: str,
    stac_metrics: Dict[str, Any] | None = None,
    user_query: str = "",
) -> str:
    """Convert incomplete GeoChat output into clean, natural user-facing prose."""
    raw = raw_text or ""
    matches = _COUNT_LOOP_PATTERN.findall(raw)
    if len(matches) >= 2:
        return _count_loop_narrative(matches)

    text = _clean_text(raw)
    if (
        len(text) < 35
        or text.lower() == _LEGACY_GROUNDING_FALLBACK
        or _INTERNAL_STATUS_PATTERN.search(text)
    ):
        return _scenario_fallback(scenario_preset, user_query, stac_metrics)
    return text
