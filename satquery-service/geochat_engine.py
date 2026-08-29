"""
GeoChat-7B Model Service Singleton.
Loads 4-bit GeoChat once at service startup and exposes standard inference.
"""

import os
import sys
import time
import logging
from typing import Dict, Any, Tuple, Optional, List
import torch
from PIL import Image

logger = logging.getLogger(__name__)

# Ensure ml/geochat/GeoChat (the actual GeoChat model package) is on sys.path.
# grounding_parser.py lives alongside this file in satquery-service/ and is
# imported as a normal sibling module — no cross-directory path hacks needed.
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
GEOCHAT_PATH = os.path.join(REPO_ROOT, "ml", "geochat", "GeoChat")

if GEOCHAT_PATH not in sys.path:
    sys.path.insert(0, GEOCHAT_PATH)

from grounding_parser import parse_geochat_grounding

# Singleton model storage
_GEOCHAT_TOKENIZER = None
_GEOCHAT_MODEL = None
_GEOCHAT_IMAGE_PROCESSOR = None
_GEOCHAT_LOADED = False
_GEOCHAT_LOAD_TIME = 0.0


def init_geochat_model(model_path: str = "MBZUAI/geochat-7B") -> bool:
    """Loads GeoChat-7B in 4-bit mode once during service startup."""
    global _GEOCHAT_TOKENIZER, _GEOCHAT_MODEL, _GEOCHAT_IMAGE_PROCESSOR, _GEOCHAT_LOADED, _GEOCHAT_LOAD_TIME

    if _GEOCHAT_LOADED:
        return True

    logger.info("Initializing GeoChat-7B 4-bit model in satquery-service...")
    t0 = time.time()

    try:
        from geochat.model.builder import load_pretrained_model
        from geochat.mm_utils import get_model_name_from_path

        model_name = get_model_name_from_path(model_path)
        tokenizer, model, image_processor, context_len = load_pretrained_model(
            model_path=model_path,
            model_base=None,
            model_name=model_name,
            load_4bit=True,
            device_map="auto",
        )

        # Set CLIP image processor resolution to 504px to match GeoChat's interpolated CLIP vision tower
        image_processor.crop_size = {"height": 504, "width": 504}
        image_processor.size = {"shortest_edge": 504}

        _GEOCHAT_TOKENIZER = tokenizer
        _GEOCHAT_MODEL = model
        _GEOCHAT_IMAGE_PROCESSOR = image_processor
        _GEOCHAT_LOADED = True
        _GEOCHAT_LOAD_TIME = time.time() - t0

        peak_vram = torch.cuda.max_memory_allocated() / 1024**3 if torch.cuda.is_available() else 0.0
        logger.info(f"GeoChat-7B loaded successfully in {_GEOCHAT_LOAD_TIME:.1f}s. Peak VRAM: {peak_vram:.2f} GB")
        return True

    except Exception as e:
        logger.error(f"Failed to load GeoChat-7B model: {e}", exc_info=True)
        _GEOCHAT_LOADED = False
        return False


def is_geochat_loaded() -> bool:
    return _GEOCHAT_LOADED


def run_geochat_inference(
    image: Image.Image,
    query: str,
    mode: str = "vqa",
) -> Tuple[str, Optional[list], float]:
    """
    Executes inference over a PIL Image and natural language query.

    Args:
        image: PIL Image to analyze.
        query: Natural language question or instruction.
        mode: One of 'vqa' (default), 'grounding', or 'refer'.
              'grounding' prepends [grounding] to trigger bbox coordinate tokens.
              'refer' wraps object name with [refer]<p>...</p> for referring expression.

    Returns: (generated_text_answer, parsed_visual_evidence_list, inference_duration_seconds)
    """
    if not _GEOCHAT_LOADED:
        raise RuntimeError("GeoChat model is not loaded in satquery-service.")

    from geochat.conversation import conv_templates, SeparatorStyle
    from geochat.mm_utils import tokenizer_image_token, KeywordsStoppingCriteria, process_images_demo
    from geochat.constants import (
        IMAGE_TOKEN_INDEX,
        DEFAULT_IMAGE_TOKEN,
        DEFAULT_IM_START_TOKEN,
        DEFAULT_IM_END_TOKEN,
    )

    t_start = time.time()

    # Apply GeoChat task-specific prompt prefixes
    if mode == "grounding":
        effective_query = "[grounding] " + query
    elif mode == "refer":
        effective_query = "[refer] Give me the location of <p> " + query + " </p>"
    else:
        effective_query = query

    # Format prompt with special image tokens
    if getattr(_GEOCHAT_MODEL.config, "mm_use_im_start_end", False):
        qs = DEFAULT_IM_START_TOKEN + DEFAULT_IMAGE_TOKEN + DEFAULT_IM_END_TOKEN + "\n" + effective_query
    else:
        qs = DEFAULT_IMAGE_TOKEN + "\n" + effective_query

    conv = conv_templates["v1"].copy() if "v1" in conv_templates else conv_templates["llava_v1"].copy()
    conv.append_message(conv.roles[0], qs)
    conv.append_message(conv.roles[1], None)
    prompt = conv.get_prompt()

    input_ids = tokenizer_image_token(prompt, _GEOCHAT_TOKENIZER, IMAGE_TOKEN_INDEX, return_tensors="pt").unsqueeze(0)
    if torch.cuda.is_available():
        input_ids = input_ids.cuda()

    # Use GeoChat official process_images_demo for exact CLIP aspect ratio padding & normalization
    image_tensor = process_images_demo([image], _GEOCHAT_IMAGE_PROCESSOR)
    if torch.cuda.is_available():
        image_tensor = image_tensor.half().cuda()

    stop_str = conv.sep if conv.sep_style != SeparatorStyle.TWO else conv.sep2
    keywords = [stop_str]
    stopping_criteria = KeywordsStoppingCriteria(keywords, _GEOCHAT_TOKENIZER, input_ids)

    with torch.inference_mode():
        output_ids = _GEOCHAT_MODEL.generate(
            input_ids,
            images=image_tensor,
            do_sample=False,
            max_new_tokens=128,
            use_cache=True,
            stopping_criteria=[stopping_criteria],
        )

    duration = time.time() - t_start

    # Decode generated token sequence only
    input_token_len = input_ids.shape[1]
    generated_ids = output_ids[:, input_token_len:]
    outputs = _GEOCHAT_TOKENIZER.batch_decode(generated_ids, skip_special_tokens=True)[0].strip()
    if outputs.endswith(stop_str):
        outputs = outputs[:-len(stop_str)].strip()

    # Parse visual grounding evidence if bounding box tokens exist
    visual_evidence = parse_geochat_grounding(outputs, img_width=image.width, img_height=image.height)

    return outputs, visual_evidence, duration


def run_geochat_multi_image_inference(
    images: List[Image.Image],
    query: str,
) -> Tuple[str, Optional[list], float]:
    """
    Executes native multi-image bi-temporal inference over multiple PIL Images and a comparison query.

    Args:
        images: List of PIL Images (e.g. [before_image, after_image]).
        query: Change detection / comparative VQA prompt.

    Returns: (generated_text_answer, parsed_visual_evidence_list, inference_duration_seconds)
    """
    if not _GEOCHAT_LOADED:
        raise RuntimeError("GeoChat model is not loaded in satquery-service.")

    if not images or len(images) == 0:
        raise ValueError("At least one image must be provided for multi-image inference.")

    from geochat.conversation import conv_templates, SeparatorStyle
    from geochat.mm_utils import tokenizer_image_token, KeywordsStoppingCriteria, process_images_demo
    from geochat.constants import (
        IMAGE_TOKEN_INDEX,
        DEFAULT_IMAGE_TOKEN,
        DEFAULT_IM_START_TOKEN,
        DEFAULT_IM_END_TOKEN,
    )

    t_start = time.time()

    # Format multi-image prompt
    use_im_start_end = getattr(_GEOCHAT_MODEL.config, "mm_use_im_start_end", False)
    image_token_str = (
        DEFAULT_IM_START_TOKEN + DEFAULT_IMAGE_TOKEN + DEFAULT_IM_END_TOKEN
        if use_im_start_end
        else DEFAULT_IMAGE_TOKEN
    )

    if len(images) == 1:
        qs = image_token_str + "\n" + query
    else:
        prompt_parts = []
        for idx in range(len(images)):
            prompt_parts.append(f"Image {idx + 1}: {image_token_str}")
        prompt_parts.append(query)
        qs = "\n".join(prompt_parts)

    conv = conv_templates["v1"].copy() if "v1" in conv_templates else conv_templates["llava_v1"].copy()
    conv.append_message(conv.roles[0], qs)
    conv.append_message(conv.roles[1], None)
    prompt = conv.get_prompt()

    input_ids = tokenizer_image_token(prompt, _GEOCHAT_TOKENIZER, IMAGE_TOKEN_INDEX, return_tensors="pt").unsqueeze(0)
    if torch.cuda.is_available():
        input_ids = input_ids.cuda()

    # Process and stack all image tensors using process_images_demo
    images_stacked = process_images_demo(images, _GEOCHAT_IMAGE_PROCESSOR)
    if torch.cuda.is_available():
        images_stacked = images_stacked.half().cuda()

    stop_str = conv.sep if conv.sep_style != SeparatorStyle.TWO else conv.sep2
    keywords = [stop_str]
    stopping_criteria = KeywordsStoppingCriteria(keywords, _GEOCHAT_TOKENIZER, input_ids)

    with torch.inference_mode():
        output_ids = _GEOCHAT_MODEL.generate(
            input_ids,
            images=images_stacked,
            do_sample=False,
            max_new_tokens=128,
            use_cache=True,
            stopping_criteria=[stopping_criteria],
        )

    duration = time.time() - t_start

    input_token_len = input_ids.shape[1]
    generated_ids = output_ids[:, input_token_len:]
    outputs = _GEOCHAT_TOKENIZER.batch_decode(generated_ids, skip_special_tokens=True)[0].strip()
    if outputs.endswith(stop_str):
        outputs = outputs[:-len(stop_str)].strip()

    # Parse visual grounding evidence from generated output using dimensions of first image
    ref_img = images[0]
    visual_evidence = parse_geochat_grounding(outputs, img_width=ref_img.width, img_height=ref_img.height)

    return outputs, visual_evidence, duration

