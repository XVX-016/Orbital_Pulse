#!/usr/bin/env python3
"""
GeoChat QLoRA Domain Adaptation Training Script for BigEarthNet

Loads GeoChat in 4-bit, attaches LoRA adapters to LLM decoder layers,
trains on BigEarthNet-mini land-cover VQA dataset, and saves LoRA weights.

Optimised for 8 GB VRAM GPUs (RTX 4060 Laptop class):
  - Image resolution reduced to 336×336 (from 504) to cut vision activation memory
  - Sequence length capped at 512 tokens
  - LoRA rank=4 (from 8) — fewer adapter params, lighter backward graph
  - Aggressive torch.cuda.empty_cache() between steps
  - Per-step stdout flush so log progress isn't silently buffered

Usage:
    python ml/geochat/finetune/train_qlora.py
"""

import os
import sys
import json
import time
import gc

# Ensure ml/geochat path is accessible for env_check
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from env_check import assert_geochat_env
assert_geochat_env()

import torch
from torch.utils.data import Dataset
from PIL import Image

# Setup paths
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
GEOCHAT_REPO = os.path.join(ROOT_DIR, "ml", "geochat", "GeoChat")
sys.path.insert(0, GEOCHAT_REPO)
sys.path.insert(0, os.path.join(ROOT_DIR, "ml", "geochat"))

# ── Tunables ────────────────────────────────────────────────────────
IMG_SIZE      = 504       # Must stay 504: CLIP vision encoder expects 1297 pos tokens ((504/14)^2 + 1)
MAX_SEQ_LEN   = 512       # Hard cap on token length to limit LLM activation memory
LORA_RANK     = 4         # Lower rank = smaller adapter, less backward VRAM
LORA_ALPHA    = 8         # Conventional α = 2*r
EPOCHS        = 1
GRAD_ACCUM    = 4
LEARNING_RATE = 2e-4
# ────────────────────────────────────────────────────────────────────


def log(msg: str):
    """Print with immediate flush so progress appears in log files."""
    print(msg, flush=True)


def main():
    log("=" * 70)
    log("GeoChat QLoRA Domain Adaptation Training (BigEarthNet-Mini)")
    log("=" * 70)

    # 1. Device and VRAM check
    if not torch.cuda.is_available():
        log("[ERROR] CUDA GPU is required for 4-bit QLoRA fine-tuning.")
        sys.exit(1)

    torch.cuda.reset_peak_memory_stats()
    total_vram = torch.cuda.get_device_properties(0).total_memory / 1024**3
    log(f"GPU Device  : {torch.cuda.get_device_name(0)}")
    log(f"Total VRAM  : {total_vram:.2f} GB")
    log(f"Image size  : {IMG_SIZE}×{IMG_SIZE}")
    log(f"Max seq len : {MAX_SEQ_LEN}")
    log(f"LoRA rank   : {LORA_RANK}")

    # 2. Imports from GeoChat
    from geochat.model.builder import load_pretrained_model
    from geochat.conversation import conv_templates
    from geochat.mm_utils import tokenizer_image_token, get_model_name_from_path
    from geochat.constants import (
        IMAGE_TOKEN_INDEX,
        IGNORE_INDEX,
    )
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training

    MODEL_PATH = os.environ.get("GEOCHAT_MODEL_PATH", "MBZUAI/geochat-7B")
    log(f"\n[1/4] Loading base model (4-bit quantised): {MODEL_PATH} ...")
    t0 = time.time()

    model_name = get_model_name_from_path(MODEL_PATH)
    tokenizer, model, image_processor, context_len = load_pretrained_model(
        model_path=MODEL_PATH,
        model_base=None,
        model_name=model_name,
        load_4bit=True,
        device_map="auto",
    )
    log(f"      Base model loaded in {time.time() - t0:.1f}s")
    log(f"      Peak VRAM after base load: {torch.cuda.max_memory_allocated() / 1024**3:.2f} GB")

    # 3. Setup LoRA Adapters
    log("\n[2/4] Attaching LoRA adapters to LLM decoder layers ...")

    # Freeze vision encoder & projector
    for param in model.get_model().get_vision_tower().parameters():
        param.requires_grad = False
    for param in model.get_model().mm_projector.parameters():
        param.requires_grad = False

    model = prepare_model_for_kbit_training(model)

    peft_config = LoraConfig(
        r=LORA_RANK,
        lora_alpha=LORA_ALPHA,
        target_modules=[
            "q_proj",
            "k_proj",
            "v_proj",
            "o_proj",
            "gate_proj",
            "up_proj",
            "down_proj",
        ],
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
    )

    model = get_peft_model(model, peft_config)
    model.print_trainable_parameters()

    # Configure image resolution — use 336 (CLIP-ViT native) instead of 504
    image_processor.crop_size = {"height": IMG_SIZE, "width": IMG_SIZE}
    image_processor.size = {"shortest_edge": IMG_SIZE}

    # 4. Load dataset
    log("\n[3/4] Preparing dataset ...")
    annot_path = os.path.join(os.path.dirname(__file__), "dataset", "prepared_samples.json")
    with open(annot_path, "r") as f:
        data_json = json.load(f)

    train_entries = data_json["train"]
    log(f"      Loaded {len(train_entries)} training samples from {annot_path}")

    class BigEarthDataset(Dataset):
        def __init__(self, entries):
            self.entries = entries

        def __len__(self):
            return len(self.entries)

        def __getitem__(self, idx):
            entry = self.entries[idx]
            img_full_path = os.path.join(ROOT_DIR, entry["image"])
            image = Image.open(img_full_path).convert("RGB")

            # Preprocess image
            image_tensor = image_processor.preprocess(image, return_tensors="pt")["pixel_values"][0]

            # Build conversation prompt
            conv = conv_templates["llava_v1"].copy()
            human_msg = entry["conversations"][0]["value"]
            gpt_msg = entry["conversations"][1]["value"]

            conv.append_message(conv.roles[0], human_msg)
            conv.append_message(conv.roles[1], gpt_msg)
            full_prompt = conv.get_prompt()

            # Tokenize full prompt
            input_ids = tokenizer_image_token(
                full_prompt, tokenizer, IMAGE_TOKEN_INDEX, return_tensors="pt"
            )

            # Build label targets: mask prompt tokens up to ASSISTANT response
            labels = input_ids.clone()

            conv_human_only = conv_templates["llava_v1"].copy()
            conv_human_only.append_message(conv.roles[0], human_msg)
            conv_human_only.append_message(conv.roles[1], None)
            prompt_human_only = conv_human_only.get_prompt()

            input_ids_human = tokenizer_image_token(
                prompt_human_only, tokenizer, IMAGE_TOKEN_INDEX, return_tensors="pt"
            )
            prompt_len = len(input_ids_human)

            # Mask out human prompt tokens with IGNORE_INDEX (-100)
            labels[:prompt_len] = IGNORE_INDEX

            # ── Truncate to MAX_SEQ_LEN to cap activation memory ──
            if len(input_ids) > MAX_SEQ_LEN:
                input_ids = input_ids[:MAX_SEQ_LEN]
                labels = labels[:MAX_SEQ_LEN]

            return {
                "input_ids": input_ids,
                "labels": labels,
                "images": image_tensor,
            }

    train_dataset = BigEarthDataset(train_entries)

    # 5. Training Loop
    output_dir = os.path.join(os.path.dirname(__file__), "checkpoints", "geochat_qlora_bigearthnet")
    os.makedirs(output_dir, exist_ok=True)

    # Only optimise params that require grad
    trainable_params = [p for p in model.parameters() if p.requires_grad]
    optimizer = torch.optim.AdamW(trainable_params, lr=LEARNING_RATE)
    model.train()

    total_steps = len(train_dataset)
    opt_steps = total_steps // GRAD_ACCUM

    log(f"\n[4/4] Starting QLoRA Training:")
    log(f"      Epochs                : {EPOCHS}")
    log(f"      Batch Size            : 1")
    log(f"      Grad Accumulation     : {GRAD_ACCUM}")
    log(f"      Total Micro-Steps     : {total_steps}")
    log(f"      Total Optim Steps     : {opt_steps}")
    log(f"      Learning Rate         : {LEARNING_RATE}")
    log(f"      Time Limit            : 2 hours per epoch")
    log("-" * 70)

    # Clear any leftover allocations before training loop
    torch.cuda.empty_cache()
    gc.collect()

    start_train_time = time.time()

    for epoch in range(EPOCHS):
        epoch_start_time = time.time()
        running_loss = 0.0
        optimizer.zero_grad(set_to_none=True)

        for step in range(len(train_dataset)):
            step_start = time.time()
            log(f"  [step {step+1}/{total_steps}] loading sample ...", )

            sample = train_dataset[step]
            input_ids = sample["input_ids"].unsqueeze(0).cuda()
            labels = sample["labels"].unsqueeze(0).cuda()
            images = sample["images"].unsqueeze(0).half().cuda()

            seq_len = input_ids.shape[1]
            log(f"  [step {step+1}/{total_steps}] seq_len={seq_len}, forward pass ...")

            # Forward pass — wrapped in autocast and try/except for VRAM & OOM safety
            try:
                with torch.cuda.amp.autocast(dtype=torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16):
                    outputs = model(
                        input_ids=input_ids,
                        labels=labels,
                        images=images,
                    )
                    loss = outputs.loss / GRAD_ACCUM
                loss.backward()
                step_loss = loss.item() * GRAD_ACCUM
                running_loss += step_loss
            except torch.cuda.OutOfMemoryError:
                log(f"  [step {step+1}] *** CUDA OOM! seq_len={seq_len} ***")
                log(f"       Skipping this sample, clearing cache.")
                optimizer.zero_grad(set_to_none=True)
                torch.cuda.empty_cache()
                gc.collect()
                continue

            # Free intermediates before optimizer step
            del outputs, input_ids, labels, images
            torch.cuda.empty_cache()

            if (step + 1) % GRAD_ACCUM == 0 or (step + 1) == total_steps:
                optimizer.step()
                optimizer.zero_grad(set_to_none=True)
                torch.cuda.empty_cache()

                step_time = time.time() - step_start
                avg_step_loss = running_loss / (step + 1)
                vram_gb = torch.cuda.max_memory_allocated() / 1024**3
                log(
                    f"Epoch [{epoch+1}/{EPOCHS}] Step [{step+1}/{total_steps}] | "
                    f"Loss: {step_loss:.4f} | "
                    f"Avg Loss: {avg_step_loss:.4f} | "
                    f"Peak VRAM: {vram_gb:.2f} GB | "
                    f"Step Time: {step_time:.2f}s"
                )

            # Hard time budget safeguard
            elapsed_epoch = time.time() - epoch_start_time
            if elapsed_epoch > 7200:
                log(f"[TIMED OUT] Epoch took > 2 hours ({elapsed_epoch:.1f}s). Halting.")
                break

        log(f"\nEpoch {epoch+1} completed in {time.time() - epoch_start_time:.1f}s.")

    # 6. Save Adapter Checkpoint
    log(f"\nSaving fine-tuned QLoRA adapter weights to: {output_dir}")
    model.save_pretrained(output_dir)
    tokenizer.save_pretrained(output_dir)

    log("\n" + "=" * 70)
    log("QLoRA Training successfully finished!")
    log(f"Total training time : {time.time() - start_train_time:.1f}s")
    log(f"Peak VRAM usage     : {torch.cuda.max_memory_allocated() / 1024**3:.2f} GB")
    log("=" * 70)

if __name__ == "__main__":
    main()

