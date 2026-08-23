# GeoChat Model Architecture Patch

## Overview
When installing the official `GeoChat` repository (`https://github.com/mbzuai-oryx/GeoChat`), loading model builders triggers an `ImportError` when initializing module imports:

```text
ImportError: cannot import name '_expand_mask' from 'transformers.models.bloom.modeling_bloom'
```

## Root Cause
`geochat/model/__init__.py` unconditionally imports `GeoChatMPTForCausalLM` and `GeoChatMPTConfig` alongside `GeoChatLlamaForCausalLM`. 

In modern versions of `transformers` (and even within `4.31.0`), internal utilities in `transformers.models.bloom.modeling_bloom` like `_expand_mask` were refactored or moved, breaking MPT model definitions. Since `MBZUAI/geochat-7B` uses the LLaVA/Vicuna (Llama) backbone rather than MPT, the MPT import is unused for 7B inference but blocks initialization.

## Applied Patch (`c:\Computing\Orbital_Pulse\ml\geochat\GeoChat\geochat\model\__init__.py`)

```diff
--- a/geochat/model/__init__.py
+++ b/geochat/model/__init__.py
@@ -1,2 +1,6 @@
 from .language_model.geochat_llama import GeoChatLlamaForCausalLM, GeoChatConfig
-from .language_model.geochat_mpt import GeoChatMPTForCausalLM, GeoChatMPTConfig
+try:
+    from .language_model.geochat_mpt import GeoChatMPTForCausalLM, GeoChatMPTConfig
+except ImportError:
+    pass
```

## Setup Instructions for Fresh Environment Reproducibility

1. Create a Python 3.10 virtual environment:
   ```bash
   python -m venv ml/geochat/venv
   source ml/geochat/venv/bin/activate  # or ml\geochat\venv\Scripts\activate on Windows
   ```
2. Clone GeoChat repository:
   ```bash
   git clone https://github.com/mbzuai-oryx/GeoChat.git ml/geochat/GeoChat
   ```
3. Apply the patch above to `ml/geochat/GeoChat/geochat/model/__init__.py`.
4. Install requirements:
   ```bash
   pip install -r ml/geochat/requirements.txt
   pip install -e ml/geochat/GeoChat --no-deps
   ```
5. Run inference:
   ```bash
   python ml/geochat/test_inference.py
   ```
