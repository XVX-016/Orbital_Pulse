#!/usr/bin/env python3
"""
GeoChat Multi-Image Test Script
Tests whether GeoChat can natively process two images in a single prompt.

Usage:
    python ml/geochat/test_two_image.py
"""

import os
import sys
import time

# Ensure ml/geochat path is accessible for env_check
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from env_check import assert_geochat_env
assert_geochat_env()

import torch
from PIL import Image

def main():
    print("=" * 70)
    print("GeoChat Multi-Image Input Test")
    print("=" * 70)

    # 1. Setup CUDA / Device
    if not torch.cuda.is_available():
        print("[ERROR] CUDA is required for GeoChat 4-bit inference test.")
        sys.exit(1)

    device_map = "auto"
    load_in_4bit = True
    torch.cuda.reset_peak_memory_stats()
    print(f"CUDA device : {torch.cuda.get_device_name(0)}")

    # 2. Load model using exact setup from test_inference.py
    MODEL_PATH = os.environ.get("GEOCHAT_MODEL_PATH", "MBZUAI/geochat-7B")
    print(f"\n[1/3] Loading GeoChat model: {MODEL_PATH} ...")
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
    print(f"      Model loaded in {time.time() - t0:.1f}s")
    print(f"      Peak VRAM after load: {torch.cuda.max_memory_allocated() / 1024**3:.2f} GB")

    # 3. Load 2 test images
    img1_path = os.path.join("ml", "geochat", "eval_samples", "sample_1_airport.jpg")
    img2_path = os.path.join("ml", "geochat", "eval_samples", "sample_3_coastal.jpg")

    print(f"\n[2/3] Loading test images:")
    print(f"      Image 1 (Airport): {img1_path}")
    print(f"      Image 2 (Coastal): {img2_path}")

    img1 = Image.open(img1_path).convert("RGB")
    img2 = Image.open(img2_path).convert("RGB")

    image_processor.crop_size = {"height": 504, "width": 504}
    image_processor.size = {"shortest_edge": 504}

    tensor1 = image_processor.preprocess(img1, return_tensors="pt")["pixel_values"][0]
    tensor2 = image_processor.preprocess(img2, return_tensors="pt")["pixel_values"][0]

    # Batch/stack image tensors
    # Shape: (2, 3, 504, 504)
    images_stacked = torch.stack([tensor1, tensor2], dim=0).half().cuda()
    print(f"      Stacked image tensor shape: {images_stacked.shape}")

    # 4. Construct Multi-Image Prompt
    print(f"\n[3/3] Running multi-image inference test ...")
    
    question = "What is different between Image 1 and Image 2? Describe what you see in both images."
    
    if model.config.mm_use_im_start_end:
        im1_tok = DEFAULT_IM_START_TOKEN + DEFAULT_IMAGE_TOKEN + DEFAULT_IM_END_TOKEN
        im2_tok = DEFAULT_IM_START_TOKEN + DEFAULT_IMAGE_TOKEN + DEFAULT_IM_END_TOKEN
    else:
        im1_tok = DEFAULT_IMAGE_TOKEN
        im2_tok = DEFAULT_IMAGE_TOKEN

    prompt_content = f"Image 1: {im1_tok}\nImage 2: {im2_tok}\n{question}"

    conv = conv_templates["llava_v1"].copy()
    conv.append_message(conv.roles[0], prompt_content)
    conv.append_message(conv.roles[1], None)
    prompt = conv.get_prompt()

    print(f"\n--- Constructed Prompt ---")
    print(prompt)
    print("--------------------------")

    input_ids = tokenizer_image_token(
        prompt, tokenizer, IMAGE_TOKEN_INDEX, return_tensors="pt"
    ).unsqueeze(0).cuda()

    num_img_tokens = (input_ids == IMAGE_TOKEN_INDEX).sum().item()
    print(f"Number of <image> tokens in input_ids: {num_img_tokens}")

    stop_str = conv.sep if conv.sep_style != SeparatorStyle.TWO else conv.sep2
    keywords = [stop_str]
    stopping_criteria = KeywordsStoppingCriteria(keywords, tokenizer, input_ids)

    # Run forward / generation
    start_time = time.time()
    try:
        with torch.inference_mode():
            output_ids = model.generate(
                input_ids,
                images=images_stacked,
                do_sample=True,
                temperature=0.2,
                max_new_tokens=256,
                stopping_criteria=[stopping_criteria],
            )

        output_token_len = output_ids.shape[1] - input_ids.shape[1]
        outputs = tokenizer.batch_decode(
            output_ids[:, input_ids.shape[1]:], skip_special_tokens=True
        )[0].strip()

        print(f"\n=== GENERATION RESULT ===")
        print(f"Time taken : {time.time() - start_time:.2f}s")
        print(f"Peak VRAM  : {torch.cuda.max_memory_allocated() / 1024**3:.2f} GB")
        print(f"Output text:\n{outputs}")
        print("=========================")

    except Exception as e:
        print(f"\n[EXCEPTION CAUGHT DURING GENERATION]")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
