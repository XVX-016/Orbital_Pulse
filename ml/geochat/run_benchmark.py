#!/usr/bin/env python3
"""
Benchmark 3 aerial/remote-sensing samples against GeoChat-7B (4-bit quantized).
Performs Grounding, Presence VQA, and Detailed Captioning tasks.
Saves cropped bounding boxes for visually verifying returned coordinates.
"""

import os
import sys
import time
import re
import json

import torch
from PIL import Image, ImageDraw

MODEL_PATH = os.environ.get("GEOCHAT_MODEL_PATH", "MBZUAI/geochat-7B")

SAMPLES = [
    {
        "id": "sample_1_airport",
        "file": "ml/geochat/eval_samples/sample_1_airport.jpg",
        "question": "Please detect and ground all major infrastructure, buildings, or structures in this aerial view.",
        "ground_truth": "Urban development, roads, building structures, and surrounding spatial layout.",
        "task": "Visual Grounding / Object Detection",
        "question_type": "general"
    },
    {
        "id": "sample_2_agri",
        "file": "ml/geochat/eval_samples/sample_2_agri.jpg",
        "question": "Is there agricultural land, vegetation, or crop field patches present in this aerial image?",
        "ground_truth": "Yes, clear agricultural vegetation, green crop fields, and rural landscape features.",
        "task": "Presence VQA",
        "question_type": "yes_no"
    },
    {
        "id": "sample_3_coastal",
        "file": "ml/geochat/eval_samples/sample_3_coastal.jpg",
        "question": "Provide a detailed description of the landscape, terrain, and environmental features in this remote sensing image.",
        "ground_truth": "Mountainous forest terrain with natural vegetation, mist/fog layer, and scenic landscape.",
        "task": "Detailed Scene Captioning",
        "question_type": "general"
    }
]


def parse_boxes(response_text, img_width, img_height):
    """
    GeoChat outputs normalized coordinates in range [0, 100] enclosed in brackets like:
    {<ymin><xmin><ymax><xmax>|<loc>} or similar formats.
    Extracts all 4-tuples and rescales to original image pixel coordinates.
    """
    pattern = r"\{<(\d+)><(\d+)><(\d+)><(\d+)>"
    matches = re.findall(pattern, response_text)
    boxes = []
    for match in matches:
        ymin_n, xmin_n, ymax_n, xmax_n = map(int, match)
        # Rescale from [0, 100] to image dimensions
        xmin = int((xmin_n / 100.0) * img_width)
        ymin = int((ymin_n / 100.0) * img_height)
        xmax = int((xmax_n / 100.0) * img_width)
        ymax = int((ymax_n / 100.0) * img_height)
        boxes.append((xmin, ymin, xmax, ymax, (xmin_n, ymin_n, xmax_n, ymax_n)))
    return boxes


def crop_and_save_boxes(image_path, boxes, sample_id):
    """
    Crops the image at the predicted bounding box coordinates and draws box overlay
    for visual verification.
    """
    img = Image.open(image_path).convert("RGB")
    out_dir = f"ml/geochat/eval_samples/{sample_id}_grounding"
    os.makedirs(out_dir, exist_ok=True)

    # Save annotated overlay
    overlay_img = img.copy()
    draw = ImageDraw.Draw(overlay_img)
    
    saved_crops = []
    for idx, (xmin, ymin, xmax, ymax, raw_norm) in enumerate(boxes):
        # Draw red box on overlay
        draw.rectangle([xmin, ymin, xmax, ymax], outline="red", width=3)
        
        # Crop region
        crop_box = (max(0, xmin), max(0, ymin), min(img.width, xmax), min(img.height, ymax))
        if crop_box[2] > crop_box[0] and crop_box[3] > crop_box[1]:
            cropped = img.crop(crop_box)
            crop_path = os.path.join(out_dir, f"crop_{idx+1}_norm_{raw_norm[0]}_{raw_norm[1]}_{raw_norm[2]}_{raw_norm[3]}.jpg")
            cropped.save(crop_path)
            saved_crops.append(crop_path)

    overlay_path = os.path.join(out_dir, "annotated_overlay.jpg")
    overlay_img.save(overlay_path)
    return overlay_path, saved_crops


def main():
    from answer_scoring import compute_answer_score

    print("=" * 70)
    print("GeoChat-7B Multi-Task Benchmark (Grounding, Presence VQA, Captioning)")
    print("=" * 70)

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
    print("\nLoading GeoChat model in 4-bit...")
    t0 = time.time()
    tokenizer, model, image_processor, context_len = load_pretrained_model(
        model_path=MODEL_PATH,
        model_base=None,
        model_name=model_name,
        load_4bit=True,
        device_map="auto",
    )
    print(f"Model loaded in {time.time() - t0:.1f}s. Peak VRAM: {torch.cuda.max_memory_allocated() / 1024**3:.2f} GB")

    # Set CLIP image processor resolution to 504px to match GeoChat's interpolated CLIP vision tower
    image_processor.crop_size = {"height": 504, "width": 504}
    image_processor.size = {"shortest_edge": 504}

    results = []

    for s in SAMPLES:
        print("\n" + "-" * 70)
        print(f"Sample [{s['id']}] | Task: {s['task']}")
        print(f"Question: {s['question']}")
        print("-" * 70)

        image = Image.open(s['file']).convert("RGB")
        
        # Build prompt
        if model.config.mm_use_im_start_end:
            qs = DEFAULT_IM_START_TOKEN + DEFAULT_IMAGE_TOKEN + DEFAULT_IM_END_TOKEN + "\n" + s['question']
        else:
            qs = DEFAULT_IMAGE_TOKEN + "\n" + s['question']

        conv = conv_templates["llava_v1"].copy()
        conv.append_message(conv.roles[0], qs)
        conv.append_message(conv.roles[1], None)
        prompt = conv.get_prompt()

        input_ids = tokenizer_image_token(prompt, tokenizer, IMAGE_TOKEN_INDEX, return_tensors="pt").unsqueeze(0).cuda()
        image_tensor = image_processor.preprocess(image, return_tensors="pt")["pixel_values"].half().cuda()

        stop_str = conv.sep if conv.sep_style != SeparatorStyle.TWO else conv.sep2
        keywords = [stop_str]
        stopping_criteria = KeywordsStoppingCriteria(keywords, tokenizer, input_ids)

        t_start = time.time()
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
        infer_time = time.time() - t_start

        # Decode generated tokens only
        input_token_len = input_ids.shape[1]
        generated_ids = output_ids[:, input_token_len:]
        outputs = tokenizer.batch_decode(generated_ids, skip_special_tokens=True)[0].strip()
        if outputs.endswith(stop_str):
            outputs = outputs[:-len(stop_str)].strip()

        # Compute answer score
        score = compute_answer_score(
            prediction=outputs,
            ground_truth=s['ground_truth'],
            question_type=s.get('question_type'),
        )

        print(f"Generated Answer : {outputs}")
        print(f"Ground Truth     : {s['ground_truth']}")
        print(f"Score            : {score}")
        print(f"Inference Time   : {infer_time:.1f}s")

        # Process grounding boxes if present
        boxes = parse_boxes(outputs, image.width, image.height)
        crop_info = []
        if boxes:
            overlay_path, crop_paths = crop_and_save_boxes(s['file'], boxes, s['id'])
            print(f"Found {len(boxes)} bounding box(es). Annotated overlay saved to: {overlay_path}")
            for b_idx, (xmin, ymin, xmax, ymax, raw_norm) in enumerate(boxes):
                print(f"  Box {b_idx+1}: Pixel [xmin={xmin}, ymin={ymin}, xmax={xmax}, ymax={ymax}] | Norm [0-100]: {raw_norm}")
            crop_info = crop_paths

        results.append({
            "id": s['id'],
            "question": s['question'],
            "ground_truth": s['ground_truth'],
            "prediction": outputs,
            "score": score,
            "question_type": s.get('question_type', 'general'),
            "task": s['task'],
            "time": infer_time,
            "boxes": [(b[0], b[1], b[2], b[3]) for b in boxes],
            "crops": crop_info,
        })

    # ── Aggregate summary ────────────────────────────────────────────
    scores = [r['score'] for r in results]
    avg_score = sum(scores) / len(scores) if scores else 0.0

    print("\n" + "=" * 70)
    print("BENCHMARK SCORING SUMMARY")
    print("=" * 70)
    for r in results:
        print(f"  [{r['id']}] Score: {r['score']:.2f}  (type: {r['question_type']})")
    print(f"\n  Aggregate Score : {avg_score:.4f}  ({avg_score * 100:.1f}%)")
    print(f"  Samples Scored  : {len(scores)}")
    print(f"  Final Peak VRAM : {torch.cuda.max_memory_allocated() / 1024**3:.2f} GB")
    print("=" * 70)

    # ── Save results JSON ────────────────────────────────────────────
    results_path = os.path.join("ml", "geochat", "eval_samples", "benchmark_results.json")
    with open(results_path, "w") as f:
        json.dump({"aggregate_score": avg_score, "results": results}, f, indent=2)
    print(f"\nResults saved to: {results_path}")


if __name__ == "__main__":
    main()
