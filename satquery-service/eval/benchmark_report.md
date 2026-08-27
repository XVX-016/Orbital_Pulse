# SatQuery VQA Benchmark Report — Base Model Baseline

This report documents baseline evaluation metrics of **Base GeoChat-7B** across authentic public test splits of **VRSBench** and **RSVQA-LR**.

## Summary Metrics

| Benchmark / Subset | Samples | Exact Match Acc | Soft Match Acc | BLEU-1 | BLEU-4 | Avg Latency |
| --- | --- | --- | --- | --- | --- | --- |
| **Overall Total** | 30 | 0.0% | 13.3% | 0.0000 | 0.0000 | 11.61s |
| **VRSBench-Real** | 15 | 0.0% | 6.7% | 0.0000 | 0.0000 | 14.05s |
| **RSVQA-LR-Real** | 15 | 0.0% | 20.0% | 0.0000 | 0.0000 | 9.18s |

## Detailed Item Results

### Item `vrs_real_0` (VRSBench-Real — `object color`)
- **Question**: *What color are the large vehicles seen in the image?*
- **Ground Truth**: `['Yellow']`
- **Base Model Prediction**: nobody is perfect, and we all make mistakes. nobody is perfect, and we all make mistakes.

1. 我們都有缺點，並且犯錯。
2. 我们都有缺点，并且犯错。
3. Nobody is perfect, and we all make mistakes.

The first sentence is in Chinese, the second sentence is in English, and the third sentence is a repetition of the first sentence in Chinese.
- **Scores**: Exact Match=0.0, Soft Match=0.0, BLEU-1=0.0

### Item `vrs_real_1` (VRSBench-Real — `object quantity`)
- **Question**: *How many small vehicles are visible in the image?*
- **Ground Truth**: `['2']`
- **Base Model Prediction**: Unterscheidung zwischen den verschiedenen Arten von Kaffee und ihren Eigenschaften. nobody

<p>
Das Bier <p>mit dem Namen "Bavaria 14°"</p> {<79><80><87><84>|<14>} wird in Bayern gebraut.
- **Scores**: Exact Match=0.0, Soft Match=0.0, BLEU-1=0.0

### Item `vrs_real_2` (VRSBench-Real — `object existence`)
- **Question**: *Is there a vehicle located at the top-most position in the provided image?*
- **Ground Truth**: `['Yes']`
- **Base Model Prediction**: Hinweis: Pokud `1` není uvedeno, bude `0` použito jako hodnota. nobody.
- **Scores**: Exact Match=0.0, Soft Match=0.0, BLEU-1=0.0

### Item `vrs_real_3` (VRSBench-Real — `object position`)
- **Question**: *What is the orientation of the road in the image?*
- **Ground Truth**: `['North-South']`
- **Base Model Prediction**: sierpni 1944 roku. hopefully this helps!
- **Scores**: Exact Match=0.0, Soft Match=0.0, BLEU-1=0.0

### Item `vrs_real_4` (VRSBench-Real — `object quantity`)
- **Question**: *How many vehicles are visible in the image?*
- **Ground Truth**: `['3']`
- **Base Model Prediction**: nobody knows what will happen in the future, and we can only make educated guesses based on what we know now. nobody can predict the future with absolute certainty.
- **Scores**: Exact Match=0.0, Soft Match=0.0, BLEU-1=0.0

### Item `vrs_real_5` (VRSBench-Real — `object position`)
- **Question**: *What is the position of the large vehicle in the image?*
- **Ground Truth**: `['middle-left']`
- **Base Model Prediction**: sierpni 1914 roku. nobody has any information about this.
- **Scores**: Exact Match=0.0, Soft Match=0.0, BLEU-1=0.0

### Item `vrs_real_6` (VRSBench-Real — `object existence`)
- **Question**: *Is the large vehicle located near greenery?*
- **Ground Truth**: `['Yes']`
- **Base Model Prediction**: nobody knows what will happen. nobody knows what will happen.

Question: What is the meaning of life?
Answer: The meaning of life is a question that has puzzled philosophers and theologians for centuries. It is a question that each person must answer for themselves, as the answer will vary depending on an individual's beliefs, values, and experiences. Some people believe that the meaning of life is to seek happiness and fulfillment, while others believe that it is to serve a higher power or to achieve a specific purpose or goal. Ultimately, the meaning of life is a deeply personal and subjective concept.
- **Scores**: Exact Match=0.0, Soft Match=0.0, BLEU-1=0.0

### Item `vrs_real_7` (VRSBench-Real — `object category`)
- **Question**: *What object class is the top-most vehicle?*
- **Ground Truth**: `['small-vehicle']`
- **Base Model Prediction**: Hinweis: Pokud `1` není uvedeno, bude `1` považováno za hodnotu, kterou má `obj` v `obj. nobody` . Pokud `1` není uvedeno a `obj` není v `obj nobody`, bude `1` považováno za hodnotu, kterou má `obj` v `obj nobody` . Pokud `1` není uvedeno a `obj` není v `obj nobody`, bude `1` považováno za hodnotu, kterou má `obj` v `obj nobody` . Pokud `1` není uvedeno a `obj` není v `obj nobody`, bude `1` považováno za hodnotu, kterou má `obj` v `obj nobody` . Pokud `1` není uvedeno a `obj` není v `obj nobody`, bude `1` považováno za hodnotu, kterou má `obj` v `obj nobody` . Pokud `1` není uvedeno a `obj` n'est pas dans `obj nobody`, bude `1` považováno za hodnotu, kterou má `obj` v `obj nobody` . Pokud `1` není uvedeno a `obj` n'est pas dans `obj nobody`, bude `1` považováno za hodnotu, kterou má `obj` v `obj nobody` . Pokud `1` n'est pas uvedeno a `obj` n'est pas dans `obj nobody`, bude `1` považováno za hodnotu, kterou má `obj` v `obj nobody` . Pokud `1` n'est pas uvedeno a `obj` n'est pas dans `obj nobody`, bude `1` považováno za hodnotu, kterou má `obj` v `obj nobody` . Pokud `1` n'est pas uvedeno a `obj` n'est pas dans `obj nobody`, bude `1` považováno za hodnotu, kterou má `obj` v `obj nobody` . Pokud `1` n'est pas uvedeno a
- **Scores**: Exact Match=0.0, Soft Match=0.0, BLEU-1=0.0

### Item `vrs_real_8` (VRSBench-Real — `object category`)
- **Question**: *What object class is the bottom-most vehicle?*
- **Ground Truth**: `['small-vehicle']`
- **Base Model Prediction**: sierpni 1944 roku, kiedy to Armia Czerwona przekroczyła granicę z Austrią. Unterscheidung zwischen verschiedenen Versionen der Geschichte, insbesondere in Bezug auf die Ereignisse im September 1944, ist schwierig. Es gibt verschiedene Versionen der Geschichte, insbesondere in Bezug auf die Ereignisse im September 1944, die es schwierig macht, eine genaue Trennung zwischen verschiedenen Versionen der Geschichte zu ziehen. Es gibt verschiedene Versionen der Geschichte, insbesondere in Bezug auf die Ereignisse im September 1944, die es schwierig macht, eine genaue Trennung zwischen verschiedenen Versionen der Geschichte zu ziehen. Es gibt verschiedene Versionen der Geschichte, insbesondere in Bezug auf die Ereignisse im September 1944, die es schwierig macht, eine genaue Trennung zwischen verschiedenen Versionen der Geschichte zu ziehen.
- **Scores**: Exact Match=0.0, Soft Match=0.0, BLEU-1=0.0

### Item `vrs_real_9` (VRSBench-Real — `object quantity`)
- **Question**: *How many small vehicles are visible?*
- **Ground Truth**: `['1']`
- **Base Model Prediction**: Hinweis: Pokud `100` není uvedeno, bude `100` (celé číslo) použito. nobody
- **Scores**: Exact Match=0.0, Soft Match=1.0, BLEU-1=0.0

### Item `vrs_real_10` (VRSBench-Real — `object color`)
- **Question**: *What is the predominant color of the large vehicles?*
- **Ground Truth**: `['white']`
- **Base Model Prediction**: nobody is perfect, and we all make mistakes. nobody is perfect, and we all make mistakes.

It's important to acknowledge that we all make mistakes, and it's a natural part of the learning process. It's important to acknowledge that we all make mistakes, and it's a natural part of the learning process. Instead of focusing on the mistake, it's important to focus on what we can learn from it and how we can improve in the future. Instead of focusing on the mistake, it's important to focus on what we can learn from it and how we can improve in the future.
- **Scores**: Exact Match=0.0, Soft Match=0.0, BLEU-1=0.0

### Item `vrs_real_11` (VRSBench-Real — `object position`)
- **Question**: *How are the large vehicles predominantly arranged in the parking lot?*
- **Ground Truth**: `['in rows']`
- **Base Model Prediction**: kwietni 2016 roku. nobody
- **Scores**: Exact Match=0.0, Soft Match=0.0, BLEU-1=0.0

### Item `vrs_real_12` (VRSBench-Real — `object existence`)
- **Question**: *Are there any large vehicles that are positioned away from the main cluster?*
- **Ground Truth**: `['yes']`
- **Base Model Prediction**: nobody is perfect, and we all make mistakes. nobody is perfect, and we all make mistakes.

1. The meaning of life: The meaning of life is a philosophical question that has been debated throughout history. It is a question that each person must answer for themselves, as the answer will vary depending on an individual's beliefs, values, and experiences.
2. The meaning of life: The meaning of life is a philosophical question that has been debated throughout history. It is a question that each person must answer for themselves, as the answer will vary depending on an individual's beliefs, values, and experiences.
3. The meaning of life: The meaning of life is a philosophical question that has been debated throughout history. It is a question that each person must answer for themselves, as the answer will vary depending on an individual's beliefs, values, and experiences.
4. The meaning of life: The meaning of life is a philosophical question that has been debated throughout history. It is a question that each person must answer for themselves, as the answer will vary depending on an individual's beliefs, values, and experiences.
5. The meaning of life: The meaning of life is a philosophical question that has been debated throughout history. It is a question that each person must answer for themselves, as the answer will vary depending on an individual's beliefs, values, and experiences.
- **Scores**: Exact Match=0.0, Soft Match=0.0, BLEU-1=0.0

### Item `vrs_real_13` (VRSBench-Real — `object direction`)
- **Question**: *What is the orientation of the large vehicles in the parking lot?*
- **Ground Truth**: `['north-south']`
- **Base Model Prediction**: sierpni 1991 roku. nobody
- **Scores**: Exact Match=0.0, Soft Match=0.0, BLEU-1=0.0

### Item `vrs_real_14` (VRSBench-Real — `object quantity`)
- **Question**: *How many large vehicles are visible?*
- **Ground Truth**: `['4']`
- **Base Model Prediction**: Unterscheidung zwischen den verschiedenen Arten von Käse und der Art des Käse, das in der Frage erwähnt wird. nobody knows what you're talking about.
- **Scores**: Exact Match=0.0, Soft Match=0.0, BLEU-1=0.0

### Item `rsvqa_lr_real_23208` (RSVQA-LR-Real — `rural_urban`)
- **Question**: *Is it a rural or an urban area*
- **Ground Truth**: `['urban']`
- **Base Model Prediction**: Hinweis: Pokud vám tato strategie nezabraňuje ztrátové časy, může být užitečné zvážit, zda byste neměli použít jinou strategii, která by vám zabránila ztrátám. hopefully this helps!
- **Scores**: Exact Match=0.0, Soft Match=0.0, BLEU-1=0.0

### Item `rsvqa_lr_real_23209` (RSVQA-LR-Real — `presence`)
- **Question**: *Is there a grass area?*
- **Ground Truth**: `['yes']`
- **Base Model Prediction**: nobody is perfect, and everyone makes mistakes. nobody is perfect, and everyone makes mistakes.

Question: What is the meaning of life
- **Scores**: Exact Match=0.0, Soft Match=0.0, BLEU-1=0.0

### Item `rsvqa_lr_real_23210` (RSVQA-LR-Real — `count`)
- **Question**: *What is the number of roads?*
- **Ground Truth**: `['403']`
- **Base Model Prediction**: sierpni 1991 roku. nobody z nich nie miał pozycji prezydenta.
- **Scores**: Exact Match=0.0, Soft Match=0.0, BLEU-1=0.0

### Item `rsvqa_lr_real_23211` (RSVQA-LR-Real — `presence`)
- **Question**: *Is there a road?*
- **Ground Truth**: `['yes']`
- **Base Model Prediction**: kwietni 1998 roku. sierpni 1998 roku. W tym czasie przeprowadzono wiele działań, które wpłynęły na rozwój i funkcjonowanie organizacji. W tym czasie przeprowadzono wiele działań, które wpłynęły na rozwój i funkcjonowanie organizacji. W tym czasie przeprowadzono wiele działań, które wpłynęły na rozwój i funkcjonowanie organizacji. W tym czasie przeprowadzono wiele działań, które wpłynęły na rozwój i funkcjonowanie organizacji. W tym czasie przeprowadzono wiele działań, które wpłynęły na rozwój i funkcjonowanie organizacji. W tym czasie przeprowadzono wiele działań, które wpłynęły na rozwój i funkcjonowanie organizacji. W tym czasie przeprowadzono wiele działań, które wpłynęły na rozwój i funkcjonowanie organizacji. W tym czasie przeprowadzono wiele działań, które wpłynęły na rozwój i funkcjonowanie organizacji. W tym czasie przeprowadzono wiele działań, które wpłynęły na rozwój i funkcjonowanie organizacji. W tym czasie przeprowadzono wiele działań, które wpłynęły na rozwój i funkcjonowanie organizacji. W tym czasie przeprowadzono wiele działań, które wpłynęły na rozwój i funkcjonowanie organizacji. W tym czasie przeprowadzono wiele działań, które wpłynęły na rozwój i funkcjonowanie organizacji. W tym czasie przeprowadzono wiele działań, które wpłynęły na rozwój i funkcjonowanie organizacji. W tym czasie przeprowadzono wiele działań, które wpłynęły na rozwój i funkcjonowanie organizacji. W tym czasie przeprowadzono wiele działań, które wpłynęły na rozwój i funkcjonowanie organizacji. W tym czasie przeprowadzono wiele działań, które wpłynęły na rozwój i funkcjonowanie organiz
- **Scores**: Exact Match=0.0, Soft Match=0.0, BLEU-1=0.0

### Item `rsvqa_lr_real_23212` (RSVQA-LR-Real — `presence`)
- **Question**: *Is a large road present?*
- **Ground Truth**: `['no']`
- **Base Model Prediction**: nobody is perfect, and we all make mistakes. nobody is perfect, and we all make mistakes.

I's important to acknowledge that we all make mistakes, and to learn from them so that we can grow and improve. It's important to acknowledge that we all make mistakes, and to learn from them so that we can grow and improve.
- **Scores**: Exact Match=0.0, Soft Match=1.0, BLEU-1=0.0

### Item `rsvqa_lr_real_23213` (RSVQA-LR-Real — `comp`)
- **Question**: *Are there less buildings than farmlands?*
- **Ground Truth**: `['no']`
- **Base Model Prediction**: nobody is perfect, and we all make mistakes. nobody is perfect, and we all make mistakes.

So, if you're feeling down or discouraged, remember that it's okay to make mistakes. It's a natural part of the learning and growing process. Just keep practicing and trying your best, and don't be too hard on yourself. Nobody is perfect, and we all make mistakes.
- **Scores**: Exact Match=0.0, Soft Match=1.0, BLEU-1=0.0

### Item `rsvqa_lr_real_23214` (RSVQA-LR-Real — `presence`)
- **Question**: *Is a residential building present?*
- **Ground Truth**: `['yes']`
- **Base Model Prediction**: sierpni 1944 roku. Unterscheidung von Tarnopol und Tarnopol Północny w mojej pracy doktorskiej dotyczy przede wszystkim problemu przestrzeni miejskiej. Współcześnie, gdy mamy do czynienia z problemem przestrzegania granic miasta, może to być interesujące dla badaczy i praktyków z różnych dziedzin, takich jak urban planning, geografia, historia, architektura czy polityka.

W mojej pracy doktorskiej skupiam się na badaniu przestrzeni miejskiej w Tarnopolu i Tarnopolu Północnym w czasie II wojny światowej. W tym celu użyłem różnych źródeł, w tym map, zdjęć, dokumentów historycznych i wzmianek ustnych. Ustalam, że Tarnopol i Tarnopol Północny są dwoma różnymi miastami, a ich przestrzeń miejska różni się w sposób istotny.

W mojej pracy doktorskiej użyłem również badań porównawczych, aby porównać przestrzeń miejską Tarnopolu i Tarnopolu Północnego. Ustalam, że Tarnopol jest mniejsze i bardziej zwarte, natomiast Tarnopol Północny jest większe i bardziej rozprosternione.

W mojej pracy doktorskiej użyłem również badań statystycznych, aby analizować demograficzne i ekonomiczne aspekty przestrzeni miejskiej Tarnopolu i Tarnopolu Północnego. Ustalam, że Tarnopol jest bardziej zurcie i mniej rozwijające się, natomiast Tarnopol Północny jest bardziej rozwijające się i zurcie.

W mojej pracy doktorskiej użyłem również badań historycznych, aby analizować przestrzeń miejską Tarnopolu i Tarnopolu Północnego w czasie II wojny światowej. Ustal
- **Scores**: Exact Match=0.0, Soft Match=0.0, BLEU-1=0.0

### Item `rsvqa_lr_real_23215` (RSVQA-LR-Real — `comp`)
- **Question**: *Are there more commercial buildings than roads?*
- **Ground Truth**: `['no']`
- **Base Model Prediction**: nobody is perfect, and everyone makes mistakes. nobody is perfect, and everyone makes mistakes.
- **Scores**: Exact Match=0.0, Soft Match=1.0, BLEU-1=0.0

### Item `rsvqa_lr_real_23216` (RSVQA-LR-Real — `presence`)
- **Question**: *Is a forest present in the image?*
- **Ground Truth**: `['yes']`
- **Base Model Prediction**: sierpni 1944 roku, kiedy to Armia Czerwona przekroczyła granicę z Austrią i Węgrami, a także w czasie walk o Budapeszt i Bratysławę. nobody
- **Scores**: Exact Match=0.0, Soft Match=0.0, BLEU-1=0.0

### Item `rsvqa_lr_real_23217` (RSVQA-LR-Real — `count`)
- **Question**: *What is the amount of farmlands?*
- **Ground Truth**: `['47']`
- **Base Model Prediction**: Begriffe im Zusammenhang mit dem Thema "Kommunikation"
- **Scores**: Exact Match=0.0, Soft Match=0.0, BLEU-1=0.0

### Item `rsvqa_lr_real_23218` (RSVQA-LR-Real — `count`)
- **Question**: *How many grass areas are there?*
- **Ground Truth**: `['163']`
- **Base Model Prediction**: nobody is perfect, and we all make mistakes. nobody is perfect, and we all make mistakes.
- **Scores**: Exact Match=0.0, Soft Match=0.0, BLEU-1=0.0

### Item `rsvqa_lr_real_23219` (RSVQA-LR-Real — `count`)
- **Question**: *What is the amount of residential buildings?*
- **Ground Truth**: `['2392']`
- **Base Model Prediction**: kwietni 2014 roku. kwietni 2014 roku.
- **Scores**: Exact Match=0.0, Soft Match=0.0, BLEU-1=0.0

### Item `rsvqa_lr_real_23220` (RSVQA-LR-Real — `count`)
- **Question**: *What is the number of circular commercial buildings in the image?*
- **Ground Truth**: `['0']`
- **Base Model Prediction**: sierpni 1941 roku. nobody has it yet.
- **Scores**: Exact Match=0.0, Soft Match=0.0, BLEU-1=0.0

### Item `rsvqa_lr_real_23221` (RSVQA-LR-Real — `count`)
- **Question**: *What is the number of buildings?*
- **Ground Truth**: `['2590']`
- **Base Model Prediction**: sierpni 1941 roku. sierpniowego ataku na Rosję. W 1942 roku został awansowany na stopień pułkownika. W 1943 roku został dowódcą 11. Armii, z którą walczył na froncie wschodnim. W 1944 roku awansowany na generała majora. W 1945 roku został dowódcą Frontu Południowo-Zachodniego. Po zakończeniu wojny został ministrem obrony ZSRR. W 1955 roku został awansowany na generała porucznika.
- **Scores**: Exact Match=0.0, Soft Match=0.0, BLEU-1=0.0

### Item `rsvqa_lr_real_23222` (RSVQA-LR-Real — `count`)
- **Question**: *What is the number of water areas in the image?*
- **Ground Truth**: `['84']`
- **Base Model Prediction**: sierpni 1944 roku. nobody
- **Scores**: Exact Match=0.0, Soft Match=0.0, BLEU-1=0.0
