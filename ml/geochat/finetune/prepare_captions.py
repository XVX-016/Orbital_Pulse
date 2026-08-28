#!/usr/bin/env python3
"""
BigEarthNet Class Label -> VLM Caption & QA Dataset Converter

Converts BigEarthNet multi-label land-cover classifications into LLaVA/GeoChat
style QA prompt pairs for VLM domain adaptation fine-tuning.

Design Decision Documented:
- BigEarthNet provides multi-label land-cover class lists (e.g. ['Coniferous forest', 'Pastures']).
- We construct natural language captions ("This satellite image shows: {class list}.")
- We paired each caption with a direct remote-sensing VQA prompt ("What land cover types are present in this satellite image?")
- This maps multi-label classification into free-text VLM token generation suitable for autoregressive LLM training.
"""

import os
import sys
import json
import torch
import numpy as np
from PIL import Image

import deeplake
sys.modules['hub'] = deeplake

import gdown
orig_gdown_download = gdown.download
def patched_gdown_download(url=None, output=None, quiet=False, proxy=None, speed=None, use_cookies=True, verify=True, id=None, **kwargs):
    kwargs.pop('fuzzy', None)
    return orig_gdown_download(url=url, output=output, quiet=quiet, proxy=proxy, speed=speed, use_cookies=use_cookies, verify=verify, id=id, **kwargs)
gdown.download = patched_gdown_download

# Add bigearthnet module path
BIGEARTHNET_REPO = os.path.join(os.path.dirname(__file__), "dataset", "bigearthnet")
sys.path.append(BIGEARTHNET_REPO)

def main():
    print("=" * 70)
    print("Preparing BigEarthNet-Mini Captions & VQA Pair Annotations")
    print("=" * 70)

    # 1. Load class list
    class_list_path = os.path.join(BIGEARTHNET_REPO, "bigearthnet", "data", "class_list.json")
    with open(class_list_path, "r") as f:
        class_names = json.load(f)
    print(f"Loaded {len(class_names)} land cover classes from class_list.json.")

    # 2. Setup DataModule
    output_dir = os.path.join(os.path.dirname(__file__), "dataset")
    images_dir = os.path.join(output_dir, "images")
    os.makedirs(images_dir, exist_ok=True)

    from bigearthnet.datamodules.bigearthnet_datamodule import BigEarthNetDataModule
    
    dm = BigEarthNetDataModule(
        dataset_name="bigearthnet-mini",
        dataset_dir=os.path.join(output_dir, "raw_data"),
        batch_size=1,
    )
    print("Preparing and setting up BigEarthNetDataModule ...")
    dm.prepare_data()
    dm.setup()

    datasets = {
        "train": dm.train_dataset,
        "val": dm.valid_dataset,
        "test": dm.test_dataset,
    }

    annotations = {"train": [], "val": [], "test": []}
    total_samples = 0

    for split, ds in datasets.items():
        print(f"\nProcessing {split} split ({len(ds)} samples) ...")
        for idx in range(len(ds)):
            sample = ds[idx]
            if idx == 0:
                print(f"Sample keys: {list(sample.keys())}")
            img_data = sample['data']
            targets = sample['labels']

            if isinstance(img_data, torch.Tensor):
                img_np = img_data.cpu().numpy()
            else:
                img_np = np.array(img_data)

            # Ensure img_np shape is (H, W, 3) uint8
            if img_np.ndim == 3 and img_np.shape[0] == 3:
                img_np = np.transpose(img_np, (1, 2, 0))

            if img_np.dtype != np.uint8:
                if img_np.max() <= 1.0:
                    img_np = (img_np * 255.0).astype(np.uint8)
                else:
                    img_np = img_np.astype(np.uint8)

            # Active classes
            if isinstance(targets, torch.Tensor):
                target_indices = torch.where(targets > 0)[0].tolist()
            else:
                target_indices = np.where(np.array(targets) > 0)[0].tolist()

            present_classes = [class_names[i] for i in target_indices if i < len(class_names)]
            if not present_classes:
                present_classes = ["Unclassified land cover"]

            class_str = ", ".join(present_classes)

            # Save image as PNG
            img_filename = f"{split}_{idx:04d}.png"
            img_path = os.path.join(images_dir, img_filename)
            Image.fromarray(img_np).save(img_path)

            # Create LLaVA / GeoChat formatted annotation entry
            rel_img_path = os.path.join("ml", "geochat", "finetune", "dataset", "images", img_filename)
            entry = {
                "id": f"{split}_{idx:04d}",
                "image": rel_img_path,
                "labels": present_classes,
                "conversations": [
                    {
                        "from": "human",
                        "value": "<image>\nWhat land cover types are present in this satellite image?"
                    },
                    {
                        "from": "gpt",
                        "value": f"This satellite image shows: {class_str}."
                    }
                ]
            }
            annotations[split].append(entry)
            total_samples += 1

    # Save prepared samples JSON
    annot_path = os.path.join(output_dir, "prepared_samples.json")
    with open(annot_path, "w") as f:
        json.dump(annotations, f, indent=2)

    print("\n" + "=" * 70)
    print(f"Dataset preparation complete!")
    print(f"Total samples processed: {total_samples}")
    print(f"  - Train : {len(annotations['train'])}")
    print(f"  - Val   : {len(annotations['val'])}")
    print(f"  - Test  : {len(annotations['test'])}")
    print(f"Annotations saved to: {annot_path}")
    print("=" * 70)

if __name__ == "__main__":
    main()
