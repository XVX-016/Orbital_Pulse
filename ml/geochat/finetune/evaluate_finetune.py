import os
import torch
import json
from PIL import Image
import requests
from io import BytesIO

from geochat.model.builder import load_pretrained_model
from geochat.conversation import conv_templates, SeparatorStyle
from geochat.mm_utils import tokenizer_image_token, get_model_name_from_path, KeywordsStoppingCriteria
from geochat.constants import IMAGE_TOKEN_INDEX, DEFAULT_IMAGE_TOKEN, DEFAULT_IM_START_TOKEN, DEFAULT_IM_END_TOKEN
from peft import PeftModel

MODEL_PATH = os.environ.get("GEOCHAT_MODEL_PATH", "MBZUAI/geochat-7B")
ADAPTER_PATH = os.path.join(os.path.dirname(__file__), "checkpoints")

def load_image(url_or_path: str) -> Image.Image:
    if url_or_path.startswith("http"):
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url_or_path, headers=headers, timeout=30)
        resp.raise_for_status()
        img = Image.open(BytesIO(resp.content)).convert("RGB")
    else:
        img = Image.open(url_or_path).convert("RGB")
    return img

def generate_answer(model, tokenizer, image_processor, image, question):
    image_processor.crop_size = {"height": 504, "width": 504}
    image_processor.size = {"shortest_edge": 504}
    
    image_tensor = image_processor.preprocess(image, return_tensors="pt")["pixel_values"]
    if torch.cuda.is_available():
        image_tensor = image_tensor.half().cuda()

    if model.config.mm_use_im_start_end:
        qs = DEFAULT_IM_START_TOKEN + DEFAULT_IMAGE_TOKEN + DEFAULT_IM_END_TOKEN + "\n" + question
    else:
        qs = DEFAULT_IMAGE_TOKEN + "\n" + question

    conv = conv_templates["llava_v1"].copy()
    conv.append_message(conv.roles[0], qs)
    conv.append_message(conv.roles[1], None)
    prompt = conv.get_prompt()

    input_ids = tokenizer_image_token(prompt, tokenizer, IMAGE_TOKEN_INDEX, return_tensors="pt").unsqueeze(0)
    if torch.cuda.is_available():
        input_ids = input_ids.cuda()

    stop_str = conv.sep if conv.sep_style != SeparatorStyle.TWO else conv.sep2
    stopping_criteria = KeywordsStoppingCriteria([stop_str], tokenizer, input_ids)

    with torch.inference_mode():
        output_ids = model.generate(
            input_ids,
            images=image_tensor,
            do_sample=False, # Use greedy for deterministic comparison
            temperature=0.0,
            max_new_tokens=512,
            use_cache=True,
            stopping_criteria=[stopping_criteria],
        )

    input_token_len = input_ids.shape[1]
    generated_ids = output_ids[:, input_token_len:]
    outputs = tokenizer.batch_decode(generated_ids, skip_special_tokens=True)[0].strip()
    if outputs.endswith(stop_str):
        outputs = outputs[: -len(stop_str)].strip()
    return outputs

def main():
    print("=" * 60)
    print("Evaluating Base vs Fine-tuned Model")
    print("=" * 60)

    # 1. Load Base Model
    print("Loading base model in 4-bit...")
    model_name = get_model_name_from_path(MODEL_PATH)
    tokenizer, model, image_processor, context_len = load_pretrained_model(
        model_path=MODEL_PATH,
        model_base=None,
        model_name=model_name,
        load_4bit=True,
        device_map="auto"
    )

    # 2. Get Test Images
    test_urls = [
        "https://eoimages.gsfc.nasa.gov/images/imagerecords/57000/57723/globe_west_2048.jpg",
        "https://eoimages.gsfc.nasa.gov/images/imagerecords/144000/144574/venice_oli_2019056_lrg.jpg",
    ]
    test_question = "What land cover types are present in this satellite image?"
    
    results = []

    print("\n--- Running Base Model ---")
    for i, url in enumerate(test_urls):
        print(f"Processing image {i+1}...")
        img = load_image(url)
        ans = generate_answer(model, tokenizer, image_processor, img, test_question)
        results.append({
            "image": url,
            "base_answer": ans
        })

    # 3. Load LoRA Adapter
    print("\nLoading fine-tuned adapter...")
    if not os.path.exists(ADAPTER_PATH):
        print(f"WARNING: Adapter path {ADAPTER_PATH} not found. Did you run the fine-tuning script?")
    else:
        model = PeftModel.from_pretrained(model, ADAPTER_PATH)
        print("Adapter loaded successfully.")

        print("\n--- Running Fine-Tuned Model ---")
        for i, url in enumerate(test_urls):
            print(f"Processing image {i+1}...")
            img = load_image(url)
            ans = generate_answer(model, tokenizer, image_processor, img, test_question)
            results[i]["finetuned_answer"] = ans

    # 4. Save and Print Results
    out_file = os.path.join(os.path.dirname(__file__), "evaluation_results.json")
    with open(out_file, "w") as f:
        json.dump(results, f, indent=2)

    print("\n" + "=" * 60)
    print("EVALUATION RESULTS")
    print("=" * 60)
    for i, res in enumerate(results):
        print(f"Image {i+1}: {res['image']}")
        print(f"Base Model:       {res.get('base_answer', 'N/A')}")
        print(f"Fine-Tuned Model: {res.get('finetuned_answer', 'N/A')}")
        print("-" * 60)
    print(f"Results saved to {out_file}")

if __name__ == "__main__":
    main()
