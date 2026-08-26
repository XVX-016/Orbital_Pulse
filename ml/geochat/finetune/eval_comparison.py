#!/usr/bin/env python3
"""
Before/After Comparison Evaluator for GeoChat QLoRA Domain Adaptation

Runs 3 evaluation images through both:
  1. Un-adapted Base GeoChat-7B Model
  2. QLoRA Fine-Tuned GeoChat Adapter

Saves comparative results side-by-side in Markdown & JSON formats.

Usage:
    python ml/geochat/finetune/eval_comparison.py
"""

import os
import sys
import json
import time
import torch
from PIL import Image

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
GEOCHAT_REPO = os.path.join(ROOT_DIR, "ml", "geochat", "GeoChat")
sys.path.insert(0, GEOCHAT_REPO)
sys.path.insert(0, os.path.join(ROOT_DIR, "ml", "geochat"))

def run_inference_on_samples(model, tokenizer, image_processor, eval_samples, model_label):
    from geochat.conversation import conv_templates, SeparatorStyle
    from geochat.mm_utils import tokenizer_image_token, KeywordsStoppingCriteria
    from geochat.constants import (
        IMAGE_TOKEN_INDEX,
        DEFAULT_IMAGE_TOKEN,
        DEFAULT_IM_START_TOKEN,
        DEFAULT_IM_END_TOKEN,
    )

    results = {}
    print(f"\n--- Running evaluation with [{model_label}] ---")

    for sample_name, sample_info in eval_samples.items():
        img_path = sample_info["path"]
        question = sample_info["question"]
        print(f"Processing sample: {sample_name} ...")

        image = Image.open(img_path).convert("RGB")
        image_processor.crop_size = {"height": 504, "width": 504}
        image_processor.size = {"shortest_edge": 504}
        image_tensor = image_processor.preprocess(image, return_tensors="pt")["pixel_values"].half().cuda()

        if model.config.mm_use_im_start_end:
            qs = DEFAULT_IM_START_TOKEN + DEFAULT_IMAGE_TOKEN + DEFAULT_IM_END_TOKEN + "\n" + question
        else:
            qs = DEFAULT_IMAGE_TOKEN + "\n" + question

        conv = conv_templates["llava_v1"].copy()
        conv.append_message(conv.roles[0], qs)
        conv.append_message(conv.roles[1], None)
        prompt = conv.get_prompt()

        input_ids = tokenizer_image_token(
            prompt, tokenizer, IMAGE_TOKEN_INDEX, return_tensors="pt"
        ).unsqueeze(0).cuda()

        stop_str = conv.sep if conv.sep_style != SeparatorStyle.TWO else conv.sep2
        stopping_criteria = KeywordsStoppingCriteria([stop_str], tokenizer, input_ids)

        t0 = time.time()
        with torch.inference_mode():
            output_ids = model.generate(
                input_ids=input_ids,
                images=image_tensor,
                do_sample=True,
                temperature=0.2,
                max_new_tokens=200,
                stopping_criteria=[stopping_criteria],
            )

        outputs = tokenizer.batch_decode(
            output_ids[:, input_ids.shape[1]:], skip_special_tokens=True
        )[0].strip()
        
        elapsed = time.time() - t0
        print(f"  [{model_label}] Response ({elapsed:.1f}s): {outputs[:100]}...")
        results[sample_name] = outputs

    return results

def main():
    print("=" * 70)
    print("GeoChat QLoRA Before / After Comparison Evaluation")
    print("=" * 70)

    if not torch.cuda.is_available():
        print("[ERROR] CUDA is required for evaluation.")
        sys.exit(1)

    from geochat.model.builder import load_pretrained_model
    from geochat.mm_utils import get_model_name_from_path
    from peft import PeftModel

    eval_dir = os.path.join(ROOT_DIR, "ml", "geochat", "eval_samples")
    eval_samples = {
        "sample_1_airport": {
            "path": os.path.join(eval_dir, "sample_1_airport.jpg"),
            "question": "What land cover types and infrastructure elements are present in this satellite image?",
        },
        "sample_2_agri": {
            "path": os.path.join(eval_dir, "sample_2_agri.jpg"),
            "question": "What land cover types are present in this satellite image?",
        },
        "sample_3_coastal": {
            "path": os.path.join(eval_dir, "sample_3_coastal.jpg"),
            "question": "Describe the land cover and terrain features visible in this satellite image.",
        },
    }

    MODEL_PATH = os.environ.get("GEOCHAT_MODEL_PATH", "MBZUAI/geochat-7B")
    ADAPTER_PATH = os.path.join(os.path.dirname(__file__), "checkpoints", "geochat_qlora_bigearthnet")

    print("\n[1/3] Loading Base Model (4-bit quantised) ...")
    model_name = get_model_name_from_path(MODEL_PATH)
    tokenizer, base_model, image_processor, context_len = load_pretrained_model(
        model_path=MODEL_PATH,
        model_base=None,
        model_name=model_name,
        load_4bit=True,
        device_map="auto",
    )

    # 1. Run Base Model Evaluation
    base_results = run_inference_on_samples(base_model, tokenizer, image_processor, eval_samples, "Base Model")

    # 2. Attach LoRA Adapter and Run Fine-Tuned Model Evaluation
    print(f"\n[2/3] Loading QLoRA Adapter weights from: {ADAPTER_PATH} ...")
    ft_model = PeftModel.from_pretrained(base_model, ADAPTER_PATH)
    
    ft_results = run_inference_on_samples(ft_model, tokenizer, image_processor, eval_samples, "Fine-Tuned Adapter")

    # 3. Format Side-by-Side Outputs
    print("\n[3/3] Generating Side-by-Side Comparison Report ...")
    
    comparison_data = []
    for sample_name, sample_info in eval_samples.items():
        entry = {
            "sample": sample_name,
            "question": sample_info["question"],
            "base_response": base_results[sample_name],
            "fine_tuned_response": ft_results[sample_name],
        }
        comparison_data.append(entry)

    # Save JSON report
    json_path = os.path.join(os.path.dirname(__file__), "comparison_results.json")
    with open(json_path, "w") as f:
        json.dump(comparison_data, f, indent=2)

    # Save Markdown report
    md_path = os.path.join(os.path.dirname(__file__), "comparison_results.md")
    with open(md_path, "w") as f:
        f.write("# GeoChat QLoRA Domain Adaptation — Before vs After Comparison\n\n")
        f.write("This report documents the performance evaluation of **GeoChat-7B Base Model** vs **GeoChat-7B + BigEarthNet QLoRA Adapter** across evaluation satellite patches.\n\n")
        
        for item in comparison_data:
            f.write(f"## Sample: `{item['sample']}`\n\n")
            f.write(f"**Question**: *{item['question']}*\n\n")
            f.write("| Base GeoChat-7B Model | Fine-Tuned QLoRA Adapter (BigEarthNet) |\n")
            f.write("| --- | --- |\n")
            f.write(f"| {item['base_response'].replace('|', '-')} | {item['fine_tuned_response'].replace('|', '-')} |\n\n")
            f.write("---\n\n")

    print("=" * 70)
    print("Comparison Evaluation Completed!")
    print(f"JSON Report saved to : {json_path}")
    print(f"Markdown Report saved to: {md_path}")
    print("=" * 70)

if __name__ == "__main__":
    main()
