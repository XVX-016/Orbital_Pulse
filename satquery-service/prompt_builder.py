"""Scenario-aware instruction construction for GeoChat requests."""


def build_geochat_prompt(scenario_preset: str | None, user_query: str) -> str:
    """Return a model prompt while retaining the user's original question verbatim."""
    query = (user_query or "").strip()
    preset = (scenario_preset or "").strip().lower()
    templates = {
        "deforestation": (
            "[VQA] Perform a bi-temporal satellite change analysis. Describe canopy loss, "
            "spectral variance, and degraded zones. Distinguish observed evidence from uncertainty.\n"
        ),
        "grounding": (
            "[grounding] Detect relevant structures, describe their spatial layout, and return "
            "bounding coordinates for each grounded object.\n"
        ),
        "sar_inundation": (
            "[VQA] Analyze SAR flood inundation using backscatter variation and identify terrain "
            "likely submerged versus unchanged. State uncertainty from speckle or layover.\n"
        ),
        "optical_sar_fusion": (
            "[VQA] Cross-correlate optical spectral observations with SAR backscatter and "
            "double-bounce signatures. Explain where modalities agree or disagree.\n"
        ),
    }
    return templates.get(preset, "[grounding] ") + (query if preset not in templates else "User request: " + query)
