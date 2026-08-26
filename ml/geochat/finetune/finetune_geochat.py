import os
import time
import json
import torch
from torch.utils.data import Dataset
from PIL import Image
from transformers import Trainer, TrainingArguments
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training

# Use the existing GeoChat utilities
from geochat.model.builder import load_pretrained_model
from geochat.conversation import conv_templates
from geochat.mm_utils import tokenizer_image_token
from geochat.constants import IMAGE_TOKEN_INDEX, DEFAULT_IMAGE_TOKEN, DEFAULT_IM_START_TOKEN, DEFAULT_IM_END_TOKEN
from geochat.mm_utils import get_model_name_from_path

# ── Configuration ──────────────────────────────────────────────────────────────
MODEL_PATH = os.environ.get("GEOCHAT_MODEL_PATH", "MBZUAI/geochat-7B")
DATA_FILE = os.path.join(os.path.dirname(__file__), "bigearthnet_vqa.json")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "checkpoints")
# ──────────────────────────────────────────────────────────────────────────────

class GeoChatDataset(Dataset):
    def __init__(self, data_path, tokenizer, image_processor, model_config):
        with open(data_path, 'r') as f:
            self.data = json.load(f)
        self.tokenizer = tokenizer
        self.image_processor = image_processor
        self.model_config = model_config
        self.base_dir = os.path.dirname(data_path)

    def __len__(self):
        return len(self.data)

    def __getitem__(self, idx):
        item = self.data[idx]
        image_path = os.path.join(self.base_dir, item['image'])
        image = Image.open(image_path).convert("RGB")
        
        # Process image
        self.image_processor.crop_size = {"height": 504, "width": 504}
        self.image_processor.size = {"shortest_edge": 504}
        image_tensor = self.image_processor.preprocess(image, return_tensors="pt")["pixel_values"][0]

        # Construct prompt
        conv = conv_templates["llava_v1"].copy()
        
        human_val = item['conversations'][0]['value']
        gpt_val = item['conversations'][1]['value']
        
        # Format the image token appropriately
        if self.model_config.mm_use_im_start_end:
            human_val = human_val.replace("<image>", DEFAULT_IM_START_TOKEN + DEFAULT_IMAGE_TOKEN + DEFAULT_IM_END_TOKEN)
        else:
            human_val = human_val.replace("<image>", DEFAULT_IMAGE_TOKEN)
            
        conv.append_message(conv.roles[0], human_val)
        conv.append_message(conv.roles[1], gpt_val)
        
        prompt = conv.get_prompt()
        
        input_ids = tokenizer_image_token(prompt, self.tokenizer, IMAGE_TOKEN_INDEX, return_tensors="pt")
        
        # Create labels (for simplicity in this minimal script, we supervise on the whole sequence. 
        # A proper implementation would mask the human prompt, but this is a scoped demo)
        labels = input_ids.clone()

        return {
            "input_ids": input_ids,
            "labels": labels,
            "images": image_tensor.half() # Need half precision for memory
        }

def collate_fn(batch):
    # Pad sequences
    input_ids = [item['input_ids'] for item in batch]
    labels = [item['labels'] for item in batch]
    images = [item['images'] for item in batch]
    
    # Very basic padding for demonstration
    max_len = max(len(ids) for ids in input_ids)
    
    padded_input_ids = []
    padded_labels = []
    for ids, lbl in zip(input_ids, labels):
        pad_len = max_len - len(ids)
        padded_input_ids.append(torch.cat([ids, torch.zeros(pad_len, dtype=torch.long)]))
        padded_labels.append(torch.cat([lbl, torch.full((pad_len,), -100, dtype=torch.long)]))
        
    return {
        "input_ids": torch.stack(padded_input_ids),
        "labels": torch.stack(padded_labels),
        "images": torch.stack(images)
    }

def main():
    print("=" * 60)
    print("Setting up QLoRA domain adaptation for GeoChat")
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

    # 2. Setup LoRA
    # Target language model layers. Usually q_proj, v_proj in Llama.
    model = prepare_model_for_kbit_training(model)
    config = LoraConfig(
        r=16,
        lora_alpha=32,
        target_modules=["q_proj", "v_proj"],
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM"
    )
    model = get_peft_model(model, config)
    model.print_trainable_parameters()

    # 3. Load Dataset
    dataset = GeoChatDataset(DATA_FILE, tokenizer, image_processor, model.config)
    print(f"Loaded {len(dataset)} training samples.")

    # 4. Train
    training_args = TrainingArguments(
        output_dir=OUTPUT_DIR,
        per_device_train_batch_size=1, # Keep small for 8GB VRAM
        gradient_accumulation_steps=4,
        learning_rate=2e-4,
        num_train_epochs=1,
        logging_steps=5,
        save_strategy="epoch",
        optim="paged_adamw_32bit",
        fp16=True,
        remove_unused_columns=False, # Required because we use 'images' custom arg
        max_steps=20 # Hard cap for time budget just to ensure it finishes quickly for the test
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=dataset,
        data_collator=collate_fn
    )

    print("Starting fine-tuning... (hardcapped to 20 steps to fit time budget)")
    trainer.train()
    
    print("Saving adapter...")
    model.save_pretrained(OUTPUT_DIR)
    print("Done!")

if __name__ == "__main__":
    main()
