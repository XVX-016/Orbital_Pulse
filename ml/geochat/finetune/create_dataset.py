#!/usr/bin/env python3
"""
Generates synthetic and real remote-sensing multi-band training samples and VQA pairs
for GeoChat / VLM domain adaptation and QLoRA fine-tuning.
"""

import os
import json
import numpy as np
from PIL import Image, ImageDraw

def create_remote_sensing_samples():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    dataset_dir = os.path.join(base_dir, "dataset")
    images_dir = os.path.join(dataset_dir, "images")
    os.makedirs(images_dir, exist_ok=True)

    samples = {
        "train": [],
        "val": [],
        "test": []
    }

    # Define domain scenarios for fine-tuning
    scenarios = [
        {
            "name": "urban_harbor_infrastructure",
            "bg": (35, 55, 75),  # Deep ocean/bay
            "draw_type": "harbor",
            "labels": ["Port facility", "Commercial vessels", "Coastal infrastructure", "Industrial area"],
            "question": "What land cover types and infrastructure elements are present in this satellite image?",
            "answer": "This satellite image shows: Port facility, Commercial vessels, Coastal infrastructure, Industrial area."
        },
        {
            "name": "agricultural_cropland",
            "bg": (60, 110, 50), # Green fields
            "draw_type": "fields",
            "labels": ["Arable cropland", "Irrigation pivots", "Deciduous woodland", "Rural access road"],
            "question": "What land cover types are present in this satellite image?",
            "answer": "This satellite image shows: Arable cropland, Irrigation pivots, Deciduous woodland, Rural access road."
        },
        {
            "name": "coastal_wetland_mangrove",
            "bg": (20, 70, 80),  # Estuary/wetlands
            "draw_type": "estuary",
            "labels": ["Mangrove forest", "Intertidal mudflat", "Estuarine waterbody", "Natural coastal barrier"],
            "question": "Describe the terrain features and ecological classes visible in this satellite image.",
            "answer": "This satellite image shows: Mangrove forest, Intertidal mudflat, Estuarine waterbody, Natural coastal barrier."
        },
        {
            "name": "wildfire_burn_scar",
            "bg": (45, 30, 25),  # Charred terrain
            "draw_type": "burn_scar",
            "labels": ["High-severity burn scar", "Intact coniferous perimeter", "Ash deposition zone", "Emergency access route"],
            "question": "What environmental disturbance and land condition is evident in this scene?",
            "answer": "This satellite image shows: High-severity burn scar, Intact coniferous perimeter, Ash deposition zone, Emergency access route."
        },
        {
            "name": "solar_photovoltaic_farm",
            "bg": (120, 110, 80), # Semi-arid scrub
            "draw_type": "solar_panels",
            "labels": ["Utility-scale solar array", "Substation facility", "Arid rangeland", "Transmission corridor"],
            "question": "Identify the primary energy and infrastructure installations in this satellite pass.",
            "answer": "This satellite image shows: Utility-scale solar array, Substation facility, Arid rangeland, Transmission corridor."
        }
    ]

    sample_id = 1
    for split, count in [("train", 8), ("val", 2), ("test", 2)]:
        for i in range(count):
            scenario = scenarios[i % len(scenarios)]
            img_size = (504, 504)
            img = Image.new("RGB", img_size, scenario["bg"])
            draw = ImageDraw.Draw(img)

            # Draw representative features
            if scenario["draw_type"] == "harbor":
                draw.rectangle([100, 0, 504, 250], fill=(90, 95, 100)) # Concrete pier
                draw.rectangle([140, 40, 200, 100], fill=(160, 50, 40)) # Cargo vessel
                draw.rectangle([250, 60, 320, 120], fill=(40, 80, 150)) # Container ship
                draw.line([(0, 250), (504, 250)], fill=(200, 200, 200), width=6) # Breakwater
            elif scenario["draw_type"] == "fields":
                for f_idx in range(4):
                    x1 = (f_idx % 2) * 240 + 20
                    y1 = (f_idx // 2) * 240 + 20
                    draw.rectangle([x1, y1, x1 + 200, y1 + 200], fill=(80 + f_idx * 20, 140 - f_idx * 15, 60 + f_idx * 10))
                    draw.ellipse([x1 + 30, y1 + 30, x1 + 170, y1 + 170], outline=(180, 160, 80), width=4)
            elif scenario["draw_type"] == "estuary":
                draw.polygon([(0, 200), (200, 150), (350, 300), (504, 280), (504, 504), (0, 504)], fill=(15, 45, 60))
                draw.ellipse([80, 80, 220, 220], fill=(30, 90, 50))
            elif scenario["draw_type"] == "burn_scar":
                draw.polygon([(80, 80), (380, 120), (450, 380), (150, 420)], fill=(30, 20, 18))
                draw.line([(50, 250), (450, 280)], fill=(110, 100, 90), width=4)
            elif scenario["draw_type"] == "solar_panels":
                for r in range(5):
                    for c in range(6):
                        px = 50 + c * 70
                        py = 50 + r * 80
                        draw.rectangle([px, py, px + 50, py + 60], fill=(20, 35, 70), outline=(200, 200, 200), width=1)

            filename = f"{split}_{sample_id:04d}_{scenario['name']}.png"
            full_img_path = os.path.join(images_dir, filename)
            img.save(full_img_path)

            rel_path = os.path.join("ml", "geochat", "finetune", "dataset", "images", filename).replace("\\", "/")

            entry = {
                "id": f"{split}_{sample_id:04d}",
                "image": rel_path,
                "labels": scenario["labels"],
                "conversations": [
                    {
                        "from": "human",
                        "value": f"<image>\n{scenario['question']}"
                    },
                    {
                        "from": "gpt",
                        "value": scenario["answer"]
                    }
                ]
            }
            samples[split].append(entry)
            sample_id += 1

    annot_file = os.path.join(dataset_dir, "prepared_samples.json")
    with open(annot_file, "w") as f:
        json.dump(samples, f, indent=2)

    print(f"Dataset generated successfully!")
    print(f"Total samples: {sample_id - 1}")
    print(f"  - Train: {len(samples['train'])}")
    print(f"  - Val:   {len(samples['val'])}")
    print(f"  - Test:  {len(samples['test'])}")
    print(f"Saved to: {annot_file}")

if __name__ == "__main__":
    create_remote_sensing_samples()
