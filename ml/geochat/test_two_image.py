import os
import time
import torch
from PIL import Image
import requests
from io import BytesIO

from geochat.model.builder import load_pretrained_model
from geochat.conversation import conv_templates, SeparatorStyle
from geochat.mm_utils import tokenizer_image_token, get_model_name_from_path, KeywordsStoppingCriteria
from geochat.constants import IMAGE_TOKEN_INDEX, DEFAULT_IMAGE_TOKEN, DEFAULT_IM_START_TOKEN, DEFAULT_IM_END_TOKEN

MODEL_PATH = os.environ.get("GEOCHAT_MODEL_PATH", "MBZUAI/geochat-7B")

def load_image(url_or_path: str) -> Image.Image:
    if url_or_path.startswith("http"):
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url_or_path, headers=headers, timeout=30)
        resp.raise_for_status()
        img = Image.open(BytesIO(resp.content)).convert("RGB")
    else:
        img = Image.open(url_or_path).convert("RGB")
    return img

def main():
    print("=" * 60)
    print("Testing Two-Image Prompting for GeoChat")
    print("=" * 60)

    # 1. Load model in 4-bit
    model_name = get_model_name_from_path(MODEL_PATH)
    tokenizer, model, image_processor, context_len = load_pretrained_model(
        model_path=MODEL_PATH,
        model_base=None,
        model_name=model_name,
        load_4bit=True,
        device_map="auto"
    )

    # 2. Load two distinct test images
    img1_url = "https://eoimages.gsfc.nasa.gov/images/imagerecords/57000/57723/globe_west_2048.jpg"
    img2_url = "https://eoimages.gsfc.nasa.gov/images/imagerecords/57000/57723/globe_east_2048.jpg" # Different image
    
    print("Loading image 1...")
    image1 = load_image(img1_url)
    print("Loading image 2...")
    image2 = load_image(img2_url)

    # Process images
    image_processor.crop_size = {"height": 504, "width": 504}
    image_processor.size = {"shortest_edge": 504}
    
    tensor1 = image_processor.preprocess(image1, return_tensors="pt")["pixel_values"]
    tensor2 = image_processor.preprocess(image2, return_tensors="pt")["pixel_values"]
    
    # Combine tensors (bs=2, or cat along seq? geochat/llava expects single image tensor per sequence usually, 
    # but we will try concatenating them to pass as a batch of 2 images for the prompt, or shape (2, C, H, W))
    images_tensor = torch.cat([tensor1, tensor2], dim=0)
    if torch.cuda.is_available():
        images_tensor = images_tensor.half().cuda()

    print(f"Image tensor shape: {images_tensor.shape}")

    # 3. Build prompt with two <image> tokens
    qs = f"{DEFAULT_IMAGE_TOKEN}\n{DEFAULT_IMAGE_TOKEN}\nWhat is the difference between the first and the second image?"
    if model.config.mm_use_im_start_end:
        qs = f"{DEFAULT_IM_START_TOKEN}{DEFAULT_IMAGE_TOKEN}{DEFAULT_IM_END_TOKEN}\n{DEFAULT_IM_START_TOKEN}{DEFAULT_IMAGE_TOKEN}{DEFAULT_IM_END_TOKEN}\nWhat is the difference between the first and the second image?"

    conv = conv_templates["llava_v1"].copy()
    conv.append_message(conv.roles[0], qs)
    conv.append_message(conv.roles[1], None)
    prompt = conv.get_prompt()

    input_ids = tokenizer_image_token(prompt, tokenizer, IMAGE_TOKEN_INDEX, return_tensors="pt").unsqueeze(0)
    if torch.cuda.is_available():
        input_ids = input_ids.cuda()

    stop_str = conv.sep if conv.sep_style != SeparatorStyle.TWO else conv.sep2
    stopping_criteria = KeywordsStoppingCriteria([stop_str], tokenizer, input_ids)

    # 4. Generate
    print("Running inference with two images...")
    try:
        with torch.inference_mode():
            output_ids = model.generate(
                input_ids,
                images=images_tensor,
                do_sample=True,
                temperature=0.2,
                max_new_tokens=512,
                use_cache=True,
                stopping_criteria=[stopping_criteria],
            )
        
        input_token_len = input_ids.shape[1]
        generated_ids = output_ids[:, input_token_len:]
        outputs = tokenizer.batch_decode(generated_ids, skip_special_tokens=True)[0].strip()
        print("\nRESULT:")
        print(outputs)
        print("\nSUCCESS: The model accepted two images without crashing.")
    except Exception as e:
        print("\nERROR: The model failed to process two images natively.")
        print(e)

if __name__ == "__main__":
    main()
