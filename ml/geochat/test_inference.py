#!/usr/bin/env python3
"""
GeoChat minimal inference test.
Loads geochat-7B in 4-bit (bitsandbytes), runs one hardcoded image + question,
and reports peak VRAM usage.

Usage (from ml/geochat/ with venv active):
    python test_inference.py

Prerequisites:
    pip install -e GeoChat/
    pip install bitsandbytes accelerate
    HF_MODEL_PATH env var OR edit MODEL_PATH below.
"""

import os
import sys
import time

import torch
from PIL import Image
import requests
from io import BytesIO

# ── Configuration ──────────────────────────────────────────────────────────────
MODEL_PATH = os.environ.get("GEOCHAT_MODEL_PATH", "MBZUAI/geochat-7B")
# A freely-available Sentinel-2 crop patch (agricultural / RGB natural):
TEST_IMAGE_URL = (
    "https://eoimages.gsfc.nasa.gov/images/imagerecords/57000/57723/globe_west_2048.jpg"
)
TEST_QUESTION = "Describe what you see in this satellite image."
# ──────────────────────────────────────────────────────────────────────────────


def load_image(url_or_path: str) -> Image.Image:
    if url_or_path.startswith("http"):
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url_or_path, headers=headers, timeout=30)
        resp.raise_for_status()
        img = Image.open(BytesIO(resp.content)).convert("RGB")
    else:
        img = Image.open(url_or_path).convert("RGB")
    return img


def main() -> None:
    print("=" * 60)
    print(f"Model : {MODEL_PATH}")
    print(f"Image : {TEST_IMAGE_URL}")
    print(f"Query : {TEST_QUESTION}")
    print("=" * 60)

    # ── 1. Check CUDA ─────────────────────────────────────────────────────────
    if not torch.cuda.is_available():
        print("[WARN] CUDA not available — falling back to CPU (no VRAM stats).")
        device_map = "cpu"
        load_in_4bit = False
    else:
        device_map = "auto"
        load_in_4bit = True
        torch.cuda.reset_peak_memory_stats()
        print(f"CUDA device : {torch.cuda.get_device_name(0)}")
        total_vram = torch.cuda.get_device_properties(0).total_memory / 1024**3
        print(f"Total VRAM  : {total_vram:.1f} GB")

    # ── 2. Load image ─────────────────────────────────────────────────────────
    print("\n[1/3] Loading test image …")
    image = load_image(TEST_IMAGE_URL)
    print(f"      Image size : {image.size}")

    # ── 3. Load model ─────────────────────────────────────────────────────────
    # GeoChat ships its own model class in geochat/model/geochat_arch.py.
    # It re-uses LLaVA's loading utilities; we import them from the installed package.
    print("\n[2/3] Loading model (4-bit quantised) …")
    t0 = time.time()

    from geochat.model.builder import load_pretrained_model
    from geochat.conversation import conv_templates, SeparatorStyle
    from geochat.mm_utils import (
        tokenizer_image_token,
        get_model_name_from_path,
        KeywordsStoppingCriteria,
    )
    from geochat.constants import (
        IMAGE_TOKEN_INDEX,
        DEFAULT_IMAGE_TOKEN,
        DEFAULT_IM_START_TOKEN,
        DEFAULT_IM_END_TOKEN,
    )

    model_name = get_model_name_from_path(MODEL_PATH)
    tokenizer, model, image_processor, context_len = load_pretrained_model(
        model_path=MODEL_PATH,
        model_base=None,
        model_name=model_name,
        load_4bit=load_in_4bit,
        device_map=device_map,
    )
    load_time = time.time() - t0
    print(f"      Model loaded in {load_time:.1f}s")

    if torch.cuda.is_available():
        peak_after_load = torch.cuda.max_memory_allocated() / 1024**3
        print(f"      Peak VRAM after load : {peak_after_load:.2f} GB")

    # ── 4. Build prompt ───────────────────────────────────────────────────────
    print("\n[3/3] Running inference …")
    if model.config.mm_use_im_start_end:
        qs = DEFAULT_IM_START_TOKEN + DEFAULT_IMAGE_TOKEN + DEFAULT_IM_END_TOKEN + "\n" + TEST_QUESTION
    else:
        qs = DEFAULT_IMAGE_TOKEN + "\n" + TEST_QUESTION

    conv = conv_templates["llava_v1"].copy()
    conv.append_message(conv.roles[0], qs)
    conv.append_message(conv.roles[1], None)
    prompt = conv.get_prompt()

    input_ids = tokenizer_image_token(
        prompt, tokenizer, IMAGE_TOKEN_INDEX, return_tensors="pt"
    ).unsqueeze(0)

    if torch.cuda.is_available():
        input_ids = input_ids.cuda()

    # GeoChat extends CLIP ViT-L/14 from 336px to 504px via position embedding
    # interpolation (clip_encoder.py). Override the image processor to match.
    image_processor.crop_size = {"height": 504, "width": 504}
    image_processor.size = {"shortest_edge": 504}

    # Process image at 504px
    image_tensor = image_processor.preprocess(image, return_tensors="pt")["pixel_values"]
    if torch.cuda.is_available():
        image_tensor = image_tensor.half().cuda()

    stop_str = conv.sep if conv.sep_style != SeparatorStyle.TWO else conv.sep2
    keywords = [stop_str]
    stopping_criteria = KeywordsStoppingCriteria(keywords, tokenizer, input_ids)

    t1 = time.time()
    with torch.inference_mode():
        output_ids = model.generate(
            input_ids,
            images=image_tensor,
            do_sample=True,
            temperature=0.2,
            max_new_tokens=512,
            use_cache=True,
            stopping_criteria=[stopping_criteria],
        )
    infer_time = time.time() - t1

    # Decode — only the newly generated tokens, not the input prompt
    # (input contains IMAGE_TOKEN_INDEX which is outside sentencepiece vocab)
    input_token_len = input_ids.shape[1]
    n_diff = (output_ids[0, :input_token_len] != input_ids[0]).sum().item()
    if n_diff > 0:
        print(f"      [warn] {n_diff} output tokens differ from input tokens")
    generated_ids = output_ids[:, input_token_len:]
    outputs = tokenizer.batch_decode(generated_ids, skip_special_tokens=True)[0].strip()
    if outputs.endswith(stop_str):
        outputs = outputs[: -len(stop_str)].strip()

    # ── 5. Report ─────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("RESULT")
    print("=" * 60)
    print(f"Question : {TEST_QUESTION}")
    print(f"Answer   : {outputs}")
    print("-" * 60)
    print(f"Inference time  : {infer_time:.1f}s")
    if torch.cuda.is_available():
        peak_vram = torch.cuda.max_memory_allocated() / 1024**3
        print(f"Peak VRAM usage : {peak_vram:.2f} GB")
    print("=" * 60)


if __name__ == "__main__":
    main()
