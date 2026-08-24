# GeoChat-7B Environment Setup & Reproducibility Guide

This guide is the single source of truth for setting up and running 4-bit GeoChat-7B inference from a completely fresh clone.

---

## 1. Repository Setup & Pinned Commit

Clone the official GeoChat repository into `ml/geochat/GeoChat` and checkout the verified working commit:

```bash
# From repository root
mkdir -p ml/geochat
git clone https://github.com/mbzuai-oryx/GeoChat.git ml/geochat/GeoChat
cd ml/geochat/GeoChat
git checkout 4850920e005a849bd224d0ce35aa9db031fa5155
cd ../../..
```

---

## 2. Virtual Environment & Dependency Installation Sequence

> **CRITICAL**: Follow the exact sequence below. Installing dependencies in a generic `pip install -r requirements.txt` order will trigger version resolution conflicts (e.g., DeepSpeed build failures, `huggingface_hub` breakage, or `accelerate` quantization crashes).

### Step A: Create Python 3.10 Virtual Environment
```bash
python3.10 -m venv ml/geochat/venv

# Activate venv
# Linux/macOS:
source ml/geochat/venv/bin/activate
# Windows (PowerShell):
.\ml\geochat\venv\Scripts\Activate.ps1
```

### Step B: Install PyTorch with CUDA 12.1 Support First
```bash
pip install --upgrade pip setuptools wheel
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```

### Step C: Install GeoChat in Editable Mode Without Dependencies
```bash
# Prevents pip from trying to build DeepSpeed from source (which requires CUDA C++ headers)
pip install -e ml/geochat/GeoChat --no-deps
```

### Step D: Install Pinned Inference Requirements
```bash
pip install -r ml/geochat/requirements.txt
```

### Step E: Apply the MPT Import Patch
Apply the automated patch script to fix `transformers` compatibility:
```bash
python ml/geochat/patch_mpt_import.py
```
*(Or verify `ml/geochat/GeoChat/geochat/model/__init__.py` has `GeoChatMPTForCausalLM` wrapped in `try/except ImportError: pass`).*

---

## 3. Automated MPT Import Patch Details

### The Problem
`geochat/model/__init__.py` unconditionally imports `GeoChatMPTForCausalLM`. In modern `transformers`, internal Bloom modeling functions (`_expand_mask`) were refactored, causing `import geochat` to crash with:
`ImportError: cannot import name '_expand_mask' from 'transformers.models.bloom.modeling_bloom'`

### The Fix
The patch wraps the MPT import in a `try/except ImportError: pass` block. Because `MBZUAI/geochat-7B` uses the LLaVA/Vicuna (Llama) backbone, the MPT import is unused for 7B inference.

---

## 4. Summary of Key Runtime Fixes

| Bug / Symptom | Root Cause | Fix & Rationale |
|---|---|---|
| **1. `ValueError: .to is not supported for 4-bit`** | `accelerate > 0.21.0` calls `.to(device)` on quantized models, which `transformers 4.31.0` explicitly forbids. | Pinned `accelerate==0.21.0` to match GeoChat's original dispatch behavior. |
| **2. `RuntimeError: size of tensor a (577) must match tensor b (1297)`** | Default `CLIPImageProcessor` resizes images to 336px (577 patches), but GeoChat extends CLIP to 504px (1297 position embeddings). | Override processor resolution prior to inference: `image_processor.crop_size = {"height": 504, "width": 504}` and `image_processor.size = {"shortest_edge": 504}`. |
| **3. `IndexError: OUT_OF_RANGE: piece id is out of range`** | Calling `tokenizer.batch_decode(output_ids)` on full sequence attempts to decode `IMAGE_TOKEN_INDEX` (`-200`) which is outside SentencePiece vocabulary range. | Slice `output_ids[:, input_token_len:]` to decode only the newly generated token IDs. |

---

## 5. Model Checkpoint Download

- **Model Name**: `MBZUAI/geochat-7B` (LoRA-merged 7B checkpoint)
- **Size**: ~14 GB across 2 shards
- **Storage Location**: Automatically cached in standard HuggingFace cache (`~/.cache/huggingface/hub/models--MBZUAI--geochat-7B/`), **NOT** inside the project repository.
- **First-run behavior**: `test_inference.py` downloads weights automatically via HuggingFace Hub on first launch.

---

## 6. Running Inference & Verification Commands

### Run Standalone Single-Image Test
```bash
python ml/geochat/test_inference.py
```
**Expected Output**:
```text
Model loaded in ~110s.
Peak VRAM after load : 4.44 GB
Question : Describe what you see in this satellite image.
Answer   : In the satellite image, there are <p>some buildings</p> ...
Inference time  : ~14s
Peak VRAM usage : 5.86 GB
```

### Run Multi-Task Benchmark (Grounding, VQA, Captioning)
```bash
python ml/geochat/run_benchmark.py
```
**Expected Output**:
```text
Sample [sample_1_airport] | Task: Visual Grounding -> Found 4 bounding box(es)
Sample [sample_2_agri]    | Task: Presence VQA     -> "Yes, there are agricultural land..."
Sample [sample_3_coastal] | Task: Detailed Caption -> "In the remote sensing image..."
Final Peak VRAM Usage: 5.91 GB
```
