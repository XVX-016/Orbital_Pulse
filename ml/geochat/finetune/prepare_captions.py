import os
import json
from datasets import load_dataset

def main():
    print("Loading jerpint/bigearthnet from HuggingFace Datasets...")
    dataset = load_dataset("jerpint/bigearthnet")
    
    print(dataset)
    
    out_dir = os.path.dirname(os.path.abspath(__file__))
    out_file = os.path.join(out_dir, "bigearthnet_vqa.json")
    
    vqa_data = []
    
    # We will format the data into LLaVA/GeoChat expected JSON format
    # which usually looks like:
    # {
    #   "id": "...", 
    #   "image": "path/to/image",
    #   "conversations": [
    #       {"from": "human", "value": "<image>\nWhat land cover types are present?"},
    #       {"from": "gpt", "value": "This satellite image shows: ..."}
    #   ]
    # }
    
    print("Processing dataset...")
    # Process train split
    for i, item in enumerate(dataset['train']):
        # item typically has 'image' (PIL) and 'labels' or 'labels_str'
        # We need to save the image locally
        img = item['image']
        img_name = f"train_{i}.jpg"
        img_path = os.path.join(out_dir, "images", img_name)
        
        os.makedirs(os.path.dirname(img_path), exist_ok=True)
        img.save(img_path)
        
        # Get labels
        if 'labels' in item and isinstance(item['labels'], list):
            labels = ", ".join(item['labels'])
        else:
            labels = str(item.get('labels', 'unknown'))
            
        vqa_data.append({
            "id": f"train_{i}",
            "image": f"images/{img_name}",
            "conversations": [
                {
                    "from": "human",
                    "value": "<image>\nWhat land cover types are present in this satellite image?"
                },
                {
                    "from": "gpt",
                    "value": f"This satellite image shows the following land cover types: {labels}."
                }
            ]
        })
        
    with open(out_file, 'w') as f:
        json.dump(vqa_data, f, indent=2)
        
    print(f"Saved {len(vqa_data)} samples to {out_file}")

if __name__ == "__main__":
    main()
