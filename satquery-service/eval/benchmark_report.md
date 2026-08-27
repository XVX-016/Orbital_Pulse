# SatQuery VQA Evaluation Report — Self-Authored Sanity-Check Baseline

> [!IMPORTANT]
> **DISCLAIMER**: The evaluation below uses **self-authored sanity-check questions** generated against local sample imagery (`ml/geochat/eval_samples/`). These results are strictly internal pipeline sanity checks and MUST NOT be cited or presented as official VRSBench or RSVQA-LR benchmark scores.

## Summary Metrics

| Benchmark / Subset | Samples | Exact Match Acc | Soft Match Acc | BLEU-1 | BLEU-4 | Avg Latency |
| --- | --- | --- | --- | --- | --- | --- |
| **Overall Total** | 10 | 0.0% | 80.0% | 0.0194 | 0.0000 | 4.3s |
| **SanityCheck-VQA** | 5 | 0.0% | 60.0% | 0.0389 | 0.0000 | 5.0s |
| **SanityCheck-RSVQA** | 5 | 0.0% | 100.0% | 0.0000 | 0.0000 | 3.59s |

## Detailed Item Results

### Item `sanity_vqa_001` (SanityCheck-VQA — `presence`)
- **Question**: *Is there an airport runway present in this satellite image?*
- **Ground Truth**: `['yes', 'Yes']`
- **Base Model Prediction**: No, there is no airport runway present in this satellite image.
- **Scores**: Exact Match=0.0, Soft Match=1.0, BLEU-1=0.0

### Item `sanity_vqa_002` (SanityCheck-VQA — `land_cover`)
- **Question**: *What is the primary land cover classification of this area?*
- **Ground Truth**: `['agricultural', 'farmland', 'fields']`
- **Base Model Prediction**: The primary land cover classification of this area is a mix of grasslands, trees, and mountains. The presence of a single building and a road suggests some human activity, but the overall landscape is predominantly natural.
- **Scores**: Exact Match=0.0, Soft Match=0.0, BLEU-1=0.0

### Item `sanity_vqa_003` (SanityCheck-VQA — `identification`)
- **Question**: *What type of facility is located along the shoreline?*
- **Ground Truth**: `['port', 'harbor', 'maritime port']`
- **Base Model Prediction**: There is a single groundtrackfield located along the shoreline.
- **Scores**: Exact Match=0.0, Soft Match=0.0, BLEU-1=0.0

### Item `sanity_vqa_004` (SanityCheck-VQA — `spatial`)
- **Question**: *Where are the rocky hills located relative to the water?*
- **Ground Truth**: `['adjacent to water', 'along the coastline']`
- **Base Model Prediction**: The rocky hills are located close to the water.
- **Scores**: Exact Match=0.0, Soft Match=1.0, BLEU-1=0.1111

### Item `sanity_vqa_005` (SanityCheck-VQA — `presence`)
- **Question**: *Are there industrial dock cranes present in this rural scene?*
- **Ground Truth**: `['no', 'No']`
- **Base Model Prediction**: No, there are no industrial dock cranes present in this rural scene.
- **Scores**: Exact Match=0.0, Soft Match=1.0, BLEU-1=0.0833

### Item `sanity_rsvqa_001` (SanityCheck-RSVQA — `presence`)
- **Question**: *Are there buildings present in this image?*
- **Ground Truth**: `['yes']`
- **Base Model Prediction**: Yes, there are buildings present in the image.
- **Scores**: Exact Match=0.0, Soft Match=1.0, BLEU-1=0.0

### Item `sanity_rsvqa_002` (SanityCheck-RSVQA — `count`)
- **Question**: *How many main bridge structures are visible in the scene?*
- **Ground Truth**: `['2', 'two']`
- **Base Model Prediction**: There are two main bridge structures visible in the scene.
- **Scores**: Exact Match=0.0, Soft Match=1.0, BLEU-1=0.0

### Item `sanity_rsvqa_003` (SanityCheck-RSVQA — `land_cover`)
- **Question**: *What is the dominant land cover category?*
- **Ground Truth**: `['coastal', 'natural vegetation', 'water']`
- **Base Model Prediction**: The dominant land cover category is mountains.
- **Scores**: Exact Match=0.0, Soft Match=1.0, BLEU-1=0.0

### Item `sanity_rsvqa_004` (SanityCheck-RSVQA — `comparison`)
- **Question**: *Are there more vegetated fields than urban buildings?*
- **Ground Truth**: `['yes']`
- **Base Model Prediction**: Yes, there are more vegetated fields than urban buildings in the image.
- **Scores**: Exact Match=0.0, Soft Match=1.0, BLEU-1=0.0

### Item `sanity_rsvqa_005` (SanityCheck-RSVQA — `presence`)
- **Question**: *Is water present in this satellite image?*
- **Ground Truth**: `['yes']`
- **Base Model Prediction**: Yes, water is present in the image, as there are two harbors and a ship present in the water.
- **Scores**: Exact Match=0.0, Soft Match=1.0, BLEU-1=0.0
