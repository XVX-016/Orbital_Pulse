# SatQuery VQA Benchmark Report — Base Model Baseline

This report documents the baseline evaluation metrics of **Base GeoChat-7B** across public test subsets of **VRSBench** and **RSVQA-LR**.

## Summary Metrics

| Benchmark Split | Samples | Exact Match Acc | Soft Match Acc | BLEU-1 | BLEU-4 | Avg Latency |
| --- | --- | --- | --- | --- | --- | --- |
| **Overall Total** | 10 | 0.0% | 80.0% | 0.0194 | 0.0000 | 4.3s |
| **VRSBench** | 5 | 0.0% | 60.0% | 0.0389 | 0.0000 | 5.0s |
| **RSVQA-LR** | 5 | 0.0% | 100.0% | 0.0000 | 0.0000 | 3.59s |

## Detailed Item Results

### Item `vrs_001` (VRSBench — `presence`)
- **Question**: *Is there an airport runway present in this satellite image?*
- **Ground Truth**: `['yes', 'Yes']`
- **Base Model Prediction**: No, there is no airport runway present in this satellite image.
- **Scores**: Exact Match=0.0, Soft Match=1.0, BLEU-1=0.0

### Item `vrs_002` (VRSBench — `land_cover`)
- **Question**: *What is the primary land cover classification of this area?*
- **Ground Truth**: `['agricultural', 'farmland', 'fields']`
- **Base Model Prediction**: The primary land cover classification of this area is a mix of grasslands, trees, and mountains. The presence of a single building and a road suggests some human activity, but the overall landscape is predominantly natural.
- **Scores**: Exact Match=0.0, Soft Match=0.0, BLEU-1=0.0

### Item `vrs_003` (VRSBench — `identification`)
- **Question**: *What type of facility is located along the shoreline?*
- **Ground Truth**: `['port', 'harbor', 'maritime port']`
- **Base Model Prediction**: There is a single groundtrackfield located along the shoreline.
- **Scores**: Exact Match=0.0, Soft Match=0.0, BLEU-1=0.0

### Item `vrs_004` (VRSBench — `spatial`)
- **Question**: *Where are the rocky hills located relative to the water?*
- **Ground Truth**: `['adjacent to water', 'along the coastline']`
- **Base Model Prediction**: The rocky hills are located close to the water.
- **Scores**: Exact Match=0.0, Soft Match=1.0, BLEU-1=0.1111

### Item `vrs_005` (VRSBench — `presence`)
- **Question**: *Are there industrial dock cranes present in this rural scene?*
- **Ground Truth**: `['no', 'No']`
- **Base Model Prediction**: No, there are no industrial dock cranes present in this rural scene.
- **Scores**: Exact Match=0.0, Soft Match=1.0, BLEU-1=0.0833

### Item `rsvqa_lr_001` (RSVQA-LR — `presence`)
- **Question**: *Are there buildings present in this image?*
- **Ground Truth**: `['yes']`
- **Base Model Prediction**: Yes, there are buildings present in the image.
- **Scores**: Exact Match=0.0, Soft Match=1.0, BLEU-1=0.0

### Item `rsvqa_lr_002` (RSVQA-LR — `count`)
- **Question**: *How many main bridge structures are visible in the scene?*
- **Ground Truth**: `['2', 'two']`
- **Base Model Prediction**: There are two main bridge structures visible in the scene.
- **Scores**: Exact Match=0.0, Soft Match=1.0, BLEU-1=0.0

### Item `rsvqa_lr_003` (RSVQA-LR — `land_cover`)
- **Question**: *What is the dominant land cover category?*
- **Ground Truth**: `['coastal', 'natural vegetation', 'water']`
- **Base Model Prediction**: The dominant land cover category is mountains.
- **Scores**: Exact Match=0.0, Soft Match=1.0, BLEU-1=0.0

### Item `rsvqa_lr_004` (RSVQA-LR — `comparison`)
- **Question**: *Are there more vegetated fields than urban buildings?*
- **Ground Truth**: `['yes']`
- **Base Model Prediction**: Yes, there are more vegetated fields than urban buildings in the image.
- **Scores**: Exact Match=0.0, Soft Match=1.0, BLEU-1=0.0

### Item `rsvqa_lr_005` (RSVQA-LR — `presence`)
- **Question**: *Is water present in this satellite image?*
- **Ground Truth**: `['yes']`
- **Base Model Prediction**: Yes, water is present in the image, as there are two harbors and a ship present in the water.
- **Scores**: Exact Match=0.0, Soft Match=1.0, BLEU-1=0.0

