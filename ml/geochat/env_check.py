"""
Environment validation utility for GeoChat-7B scripts.
Enforces pinned dependencies (transformers==4.31.0, accelerate==0.21.0) to prevent
silent degradation or quantized model loading bugs.
"""

import sys

EXPECTED_TRANSFORMERS = "4.31.0"
EXPECTED_ACCELERATE = "0.21.0"


def assert_geochat_env():
    """Asserts that transformers and accelerate match the exact pinned environment versions."""
    try:
        import transformers
        import accelerate
    except ImportError as e:
        raise RuntimeError(
            f"GeoChat environment check failed: missing required package ({e}). "
            f"Are you running via the pinned venv? (e.g. ml/geochat/venv/Scripts/python.exe)"
        ) from e

    tf_ver = transformers.__version__
    acc_ver = accelerate.__version__

    if tf_ver != EXPECTED_TRANSFORMERS or acc_ver != EXPECTED_ACCELERATE:
        raise RuntimeError(
            f"Wrong environment for GeoChat!\n"
            f"  Expected: transformers=={EXPECTED_TRANSFORMERS}, accelerate=={EXPECTED_ACCELERATE}\n"
            f"  Got:      transformers=={tf_ver}, accelerate=={acc_ver}\n\n"
            f"Running with unpinned transformers/accelerate versions causes 4-bit weight loading "
            f"and multimodal projection to silently collapse into fallback text.\n"
            f"Please run your script using the pinned virtual environment interpreter:\n"
            f"  ml\\geochat\\venv\\Scripts\\python.exe <script_path>"
        )


if __name__ == "__main__":
    assert_geochat_env()
    print("GeoChat environment assertion passed cleanly.")
