# SatQuery VQA Benchmark Report — Base Model Baseline

This report documents baseline evaluation metrics of **Base GeoChat-7B** across authentic public test splits of **VRSBench** and **RSVQA-LR**.

## Summary Metrics

| Benchmark / Subset | Samples | Exact Match Acc | Soft Match Acc | BLEU-1 | BLEU-4 | Avg Latency |
| --- | --- | --- | --- | --- | --- | --- |
| **Overall Total** | 30 | 0.0% | 0.0% | 0.0000 | 0.0000 | 11.34s |
| **VRSBench-Real** | 15 | 0.0% | 0.0% | 0.0000 | 0.0000 | 9.19s |
| **RSVQA-LR-Real** | 15 | 0.0% | 0.0% | 0.0000 | 0.0000 | 13.5s |

## Detailed Item Results

### Item `vrs_real_0` (VRSBench-Real — `object color`)
- **Question**: *What color are the large vehicles seen in the image?*
- **Ground Truth**: `['Yellow']`
- **Base Model Prediction**: kwietni 1912 roku w Rzymie. nobody.pl. [dostęp 2012-04-27].
* Wypisano listę uczestników konkursu fotograficznego. Gazeta Krakowska, 1912-04-27. [dostęp 2012-04-27].
* Wypisano listę uczestników konkursu fotograficznego. Gazeta Lwowska, 1912-04-27. [dostęp 2012-04-27].
* Wypisano listę uczestników konkursu fotograficznego. Gazeta Poznańska, 1912-04-27. [dostęp 2012-04-27].
* Wypisano listę uczestników konkursu fotograficznego. Gazeta Toruńska, 1912-04-27. [dostęp 2012-04-27].
* Wypisano listę uczestników konkursu fotograficznego. Gazeta Wrocławska, 1912-04-27. [dostęp 2012-04-27].
- **Scores**: Exact Match=0.0, Soft Match=0.0, BLEU-1=0.0

### Item `vrs_real_1` (VRSBench-Real — `object quantity`)
- **Question**: *How many small vehicles are visible in the image?*
- **Ground Truth**: `['2']`
- **Base Model Prediction**: sierpni 1941 roku. nobody has any idea what happened to them.
- **Scores**: Exact Match=0.0, Soft Match=0.0, BLEU-1=0.0

### Item `vrs_real_2` (VRSBench-Real — `object existence`)
- **Question**: *Is there a vehicle located at the top-most position in the provided image?*
- **Ground Truth**: `['Yes']`
- **Base Model Prediction**: everybody is a potential target. nobody is safe.

Comment: @user1234567890: I'm sorry, but I'm not sure what you're asking for. Can you please provide more context or clarify your question?
- **Scores**: Exact Match=0.0, Soft Match=0.0, BLEU-1=0.0

### Item `vrs_real_3` (VRSBench-Real — `object position`)
- **Question**: *What is the orientation of the road in the image?*
- **Ground Truth**: `['North-South']`
- **Base Model Prediction**: nobody is perfect, and we all make mistakes. nobody is perfect, and we all make mistakes.
- **Scores**: Exact Match=0.0, Soft Match=0.0, BLEU-1=0.0

### Item `vrs_real_4` (VRSBench-Real — `object quantity`)
- **Question**: *How many vehicles are visible in the image?*
- **Ground Truth**: `['3']`
- **Base Model Prediction**: nobody is perfect, and we all have our flaws. nobody is perfect, and we all have our flaws.
- **Scores**: Exact Match=0.0, Soft Match=0.0, BLEU-1=0.0

### Item `vrs_real_5` (VRSBench-Real — `object position`)
- **Question**: *What is the position of the large vehicle in the image?*
- **Ground Truth**: `['middle-left']`
- **Base Model Prediction**: Unterscheidung zwischen den verschiedenen Arten von Käse und Käseprodukten. nobody
- **Scores**: Exact Match=0.0, Soft Match=0.0, BLEU-1=0.0

### Item `vrs_real_6` (VRSBench-Real — `object existence`)
- **Question**: *Is the large vehicle located near greenery?*
- **Ground Truth**: `['Yes']`
- **Base Model Prediction**: kwietni 2011 roku. Unterscheidung zwischen den verschiedenen Versionen der Kundenbetreuung ist schwierig, da es sich um eine weiße Kundenbetreuung handelt, die in verschiedenen Versionen vorliegt. Es gibt jedoch einige Merkmale, die die verschiedenen Versionen voneinander unterscheiden.
- **Scores**: Exact Match=0.0, Soft Match=0.0, BLEU-1=0.0

### Item `vrs_real_7` (VRSBench-Real — `object category`)
- **Question**: *What object class is the top-most vehicle?*
- **Ground Truth**: `['small-vehicle']`
- **Base Model Prediction**: sierpni 1991 roku. nobody
- **Scores**: Exact Match=0.0, Soft Match=0.0, BLEU-1=0.0

### Item `vrs_real_8` (VRSBench-Real — `object category`)
- **Question**: *What object class is the bottom-most vehicle?*
- **Ground Truth**: `['small-vehicle']`
- **Base Model Prediction**: sierpni 1944 roku. Hinweis: Wspomnienia z okresu II wojny światowej są trudne do zinterpretowania i analizowania. W związku z tym, że niektóre informacje mogą być nieprecyzyjne lub niekompletne, należy je odczytywać z rozumieniem, że mogą być niepewne.
- **Scores**: Exact Match=0.0, Soft Match=0.0, BLEU-1=0.0

### Item `vrs_real_9` (VRSBench-Real — `object quantity`)
- **Question**: *How many small vehicles are visible?*
- **Ground Truth**: `['1']`
- **Base Model Prediction**: nobody is perfect, and we all make mistakes. nobody is perfect, and we all make mistakes.
- **Scores**: Exact Match=0.0, Soft Match=0.0, BLEU-1=0.0

### Item `vrs_real_10` (VRSBench-Real — `object color`)
- **Question**: *What is the predominant color of the large vehicles?*
- **Ground Truth**: `['white']`
- **Base Model Prediction**: nobody is perfect, and we all have our flaws. nobody is perfect, and we all have our flaws.
- **Scores**: Exact Match=0.0, Soft Match=0.0, BLEU-1=0.0

### Item `vrs_real_11` (VRSBench-Real — `object position`)
- **Question**: *How are the large vehicles predominantly arranged in the parking lot?*
- **Ground Truth**: `['in rows']`
- **Base Model Prediction**: sierpni 1991 roku. nobody z nich nie miał pozycji prezydenta.
- **Scores**: Exact Match=0.0, Soft Match=0.0, BLEU-1=0.0

### Item `vrs_real_12` (VRSBench-Real — `object existence`)
- **Question**: *Are there any large vehicles that are positioned away from the main cluster?*
- **Ground Truth**: `['yes']`
- **Base Model Prediction**: nobody is perfect, and we all have our flaws. nobody is perfect, and we all have our flaws.
- **Scores**: Exact Match=0.0, Soft Match=0.0, BLEU-1=0.0

### Item `vrs_real_13` (VRSBench-Real — `object direction`)
- **Question**: *What is the orientation of the large vehicles in the parking lot?*
- **Ground Truth**: `['north-south']`
- **Base Model Prediction**: nobody is perfect, and we all have our flaws and weaknesses. nobody is perfect, and we all have our flaws and weaknesses.
- **Scores**: Exact Match=0.0, Soft Match=0.0, BLEU-1=0.0

### Item `vrs_real_14` (VRSBench-Real — `object quantity`)
- **Question**: *How many large vehicles are visible?*
- **Ground Truth**: `['4']`
- **Base Model Prediction**: sierpnia 1939 roku. nobody has any information about this.
- **Scores**: Exact Match=0.0, Soft Match=0.0, BLEU-1=0.0

### Item `rsvqa_lr_real_23208` (RSVQA-LR-Real — `rural_urban`)
- **Question**: *Is it a rural or an urban area*
- **Ground Truth**: `['urban']`
- **Base Model Prediction**: nobody's perfect, and we all make mistakes. nobody's perfect, and we all make mistakes.
- **Scores**: Exact Match=0.0, Soft Match=0.0, BLEU-1=0.0

### Item `rsvqa_lr_real_23209` (RSVQA-LR-Real — `presence`)
- **Question**: *Is there a grass area?*
- **Ground Truth**: `['yes']`
- **Base Model Prediction**: sierpni 1914 roku. Unterscheidung der Waffen und Einheiten, die an der Ostfront im Einsatz waren.

* 1. Teil: Die Einheiten und Waffen, die an der Ostfront im Einsatz waren, im August 1914.
* 2. Teil: Die Einheiten und Waffen, die an der Ostfront im Einsatz waren, im September 1914.
* 3. Teil: Die Einheiten und Waffen, die an der Ostfront im Einsatz waren, im Oktober 1914.
* 4. Teil: Die Einheiten und Waffen, die an der Ostfront im Einsatz waren, im November 1914.
* 5. Teil: Die Einheiten und Waffen, die an der Ostfront im Einsatz waren, im Dezember 1914.
* 6. Teil: Die Einheiten und Waffen, die an der Ostfront im Einsatz waren, im Januar 1915.
* 7. Teil: Die Einheiten und Waffen, die an der Ostfront im Einsatz waren, im Februar 1915.
* 8. Teil: Die Einheiten und Waffen, die an der Ostfront im Einsatz waren, im März 1915.
* 9. Teil: Die Einheiten und Waffen, die an der Ostfront im Einsatz waren, im April 1915.
* 10. Teil: Die Einheiten und Waffen, die an der Ostfront im Einsatz waren, im Mai 1915.
* 11. Teil: Die Einheiten und Waffen, die an der Ostfront im Einsatz waren, im Juni 1915.
* 12. Teil: Die Einheiten und Waffen, die an der Ostfront im Einsatz waren, im Juli 1915.
* 13. Teil: Die Einheiten und Waffen, die an der Ostfront im Einsatz waren, im August 1915.
* 14. Teil: Die Einheiten und Waffen, die an der Ostfront im Einsatz waren, im September 1915.
* 15. Teil: Die Einheiten und Waffen, die an der Ostfront im Einsatz waren, im Oktober 1915.
* 16. Teil: Die Einheiten und Waffen
- **Scores**: Exact Match=0.0, Soft Match=0.0, BLEU-1=0.0

### Item `rsvqa_lr_real_23210` (RSVQA-LR-Real — `count`)
- **Question**: *What is the number of roads?*
- **Ground Truth**: `['403']`
- **Base Model Prediction**: nobody is perfect, and we all make mistakes. nobody is perfect, and we all make mistakes.

1. 在哪里可以找到帮助：
* 在哪里可以找到帮助：在网上或者在书籍中。
* 在哪里可以找到帮助：在网上或者在书籍中。
- **Scores**: Exact Match=0.0, Soft Match=0.0, BLEU-1=0.0

### Item `rsvqa_lr_real_23211` (RSVQA-LR-Real — `presence`)
- **Question**: *Is there a road?*
- **Ground Truth**: `['yes']`
- **Base Model Prediction**: sierpni 1944 roku. Hinweis: Wspomnienia i relacje są opisane w sposób, który uwzględnia ich autentyczność i wartość historyczną.
- **Scores**: Exact Match=0.0, Soft Match=0.0, BLEU-1=0.0

### Item `rsvqa_lr_real_23212` (RSVQA-LR-Real — `presence`)
- **Question**: *Is a large road present?*
- **Ground Truth**: `['no']`
- **Base Model Prediction**: nobody is perfect, and we all make mistakes. nobody is perfect, and we all make mistakes.

It is important to acknowledge our mistakes and learn from them, so that we can grow and improve. It is important to acknowledge our mistakes and learn from them, so that we can grow and improve.
- **Scores**: Exact Match=0.0, Soft Match=0.0, BLEU-1=0.0

### Item `rsvqa_lr_real_23213` (RSVQA-LR-Real — `comp`)
- **Question**: *Are there less buildings than farmlands?*
- **Ground Truth**: `['no']`
- **Base Model Prediction**: kwietni 2015 roku. nobody
- **Scores**: Exact Match=0.0, Soft Match=0.0, BLEU-1=0.0

### Item `rsvqa_lr_real_23214` (RSVQA-LR-Real — `presence`)
- **Question**: *Is a residential building present?*
- **Ground Truth**: `['yes']`
- **Base Model Prediction**: nobody is perfect, and we all make mistakes. nobody is perfect, and we all make mistakes.
- **Scores**: Exact Match=0.0, Soft Match=0.0, BLEU-1=0.0

### Item `rsvqa_lr_real_23215` (RSVQA-LR-Real — `comp`)
- **Question**: *Are there more commercial buildings than roads?*
- **Ground Truth**: `['no']`
- **Base Model Prediction**: sierpni 1991 roku w Paryżu. nobody.pl. [dostęp 2011-09-17]. [zarchiwizowane z tego adresu (2016-03-16)].
- **Scores**: Exact Match=0.0, Soft Match=0.0, BLEU-1=0.0

### Item `rsvqa_lr_real_23216` (RSVQA-LR-Real — `presence`)
- **Question**: *Is a forest present in the image?*
- **Ground Truth**: `['yes']`
- **Base Model Prediction**: Unterscheidung zwischen den verschiedenen Arten von Käse, die in der Schweiz hergestellt werden können. Unterscheidung zwischen den verschiedenen Arten von Käse, die in der Schweiz hergestellt werden können.
- **Scores**: Exact Match=0.0, Soft Match=0.0, BLEU-1=0.0

### Item `rsvqa_lr_real_23217` (RSVQA-LR-Real — `count`)
- **Question**: *What is the amount of farmlands?*
- **Ground Truth**: `['47']`
- **Base Model Prediction**: nobody is perfect, and we all have our flaws and imperfections. nobody is perfect, and we all have our flaws and imperfections.
- **Scores**: Exact Match=0.0, Soft Match=0.0, BLEU-1=0.0

### Item `rsvqa_lr_real_23218` (RSVQA-LR-Real — `count`)
- **Question**: *How many grass areas are there?*
- **Ground Truth**: `['163']`
- **Base Model Prediction**: Hinweis: Pokud `0` není zadán, bude použita předem stanovená hodnota `None`.
- **Scores**: Exact Match=0.0, Soft Match=0.0, BLEU-1=0.0

### Item `rsvqa_lr_real_23219` (RSVQA-LR-Real — `count`)
- **Question**: *What is the amount of residential buildings?*
- **Ground Truth**: `['2392']`
- **Base Model Prediction**: Unterscheidung zwischen den verschiedenen Arten von Käse und ihren Eigenschaften. nobody
- **Scores**: Exact Match=0.0, Soft Match=0.0, BLEU-1=0.0

### Item `rsvqa_lr_real_23220` (RSVQA-LR-Real — `count`)
- **Question**: *What is the number of circular commercial buildings in the image?*
- **Ground Truth**: `['0']`
- **Base Model Prediction**: nobody is perfect, and we all make mistakes. nobody is perfect, and we all make mistakes.
- **Scores**: Exact Match=0.0, Soft Match=0.0, BLEU-1=0.0

### Item `rsvqa_lr_real_23221` (RSVQA-LR-Real — `count`)
- **Question**: *What is the number of buildings?*
- **Ground Truth**: `['2590']`
- **Base Model Prediction**: nobody is perfect, and we all make mistakes. nobody is perfect, and we all make mistakes.

I'm sorry, but I have to disagree with you. While it is true that nobody is perfect and we all make mistakes, it is also important to recognize and acknowledge our own strengths and accomplishments. Focusing solely on our weaknesses and mistakes can lead to feelings of inadequacy and self-doubt. It is important to find a balance between recognizing our flaws and celebrating our achievements.
- **Scores**: Exact Match=0.0, Soft Match=0.0, BLEU-1=0.0

### Item `rsvqa_lr_real_23222` (RSVQA-LR-Real — `count`)
- **Question**: *What is the number of water areas in the image?*
- **Ground Truth**: `['84']`
- **Base Model Prediction**: Unterscheidung zwischen den verschiedenen Arten von Käse und ihren Eigenschaften. Unterscheidung zwischen den verschiedenen Arten von Käse und ihren Eigenschaften.
- **Scores**: Exact Match=0.0, Soft Match=0.0, BLEU-1=0.0

