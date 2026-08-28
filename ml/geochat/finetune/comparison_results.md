# GeoChat QLoRA Domain Adaptation — Before vs After Comparison

This report documents the performance evaluation of **GeoChat-7B Base Model** vs **GeoChat-7B + BigEarthNet QLoRA Adapter** across evaluation satellite patches.

## Sample: `sample_1_airport`

**Question**: *What land cover types and infrastructure elements are present in this satellite image?*

| Base GeoChat-7B Model | Fine-Tuned QLoRA Adapter (BigEarthNet) |
| --- | --- |
| In this satellite image, there are two bridges, one at the center and another at the top right. The center bridge is a large bridge, while the top right bridge is smaller. There are also two buildings, one at the top right and another at the top left. The top right building is taller than the top left building. Additionally, there are two roads, one at the top right and another at the top left. The top right road is longer than the top left road. The land cover types present in the image include buildings, roads, and a bridge. | This satellite image shows: Bridge, Harbor, Road. |

---

## Sample: `sample_2_agri`

**Question**: *What land cover types are present in this satellite image?*

| Base GeoChat-7B Model | Fine-Tuned QLoRA Adapter (BigEarthNet) |
| --- | --- |
| The land cover types present in this satellite image are trees, buildings, and a road. | This satellite image shows: Broad-leaved forest, Mixed forest. |

---

## Sample: `sample_3_coastal`

**Question**: *Describe the land cover and terrain features visible in this satellite image.*

| Base GeoChat-7B Model | Fine-Tuned QLoRA Adapter (BigEarthNet) |
| --- | --- |
| The land cover in this satellite image is a mix of grassy fields, trees, and mountains. There are also two roads visible, one at the bottom right and another at the top right. The terrain features include hills, mountains, and a valley. The presence of trees and mountains suggests a diverse and possibly rugged landscape. | This satellite image shows: Coniferous forest, Land principally occupied by agriculture, with significant areas of natural vegetation, Mixed forest, Transitional woodland/shrub. |

---

