import json
import os
import random
import sys
from bs4 import BeautifulSoup
from sklearn.model_selection import train_test_split

sys.stdout.reconfigure(encoding='utf-8')

# Constants
INPUT_FILE = "data/sample_products.jsonl"
OUTPUT_DIR = "data"
MIN_WORDS_DESCRIPTION = 15
MAX_WORDS_FEATURES = 300

SYSTEM_PROMPT = "You are an expert e-commerce copywriter. Write a compelling, engaging, and professional product description based on the provided title and features."

def clean_html(raw_html: str) -> str:
    """Removes HTML tags and excess whitespace."""
    if not raw_html:
        return ""
    soup = BeautifulSoup(raw_html, "html.parser")
    # get_text with separator to keep formatting somewhat intact
    text = soup.get_text(separator=" ", strip=True)
    # Remove excessive spaces
    return " ".join(text.split())

def truncate_words(text: str, max_words: int) -> str:
    """Truncates text to a maximum number of words."""
    words = text.split()
    if len(words) > max_words:
        return " ".join(words[:max_words]) + "..."
    return text

def format_user_message(title: str, features: list[str]) -> str:
    """Formats the input prompt for the model."""
    user_msg = f"Title: {title.strip()}\n\nFeatures:\n"
    for feat in features:
        clean_feat = clean_html(feat)
        if clean_feat:
            user_msg += f"- {clean_feat}\n"
            
    # Truncate features if they are too long to avoid exceeding context limits
    return truncate_words(user_msg, MAX_WORDS_FEATURES)

def process_data():
    if not os.path.exists(INPUT_FILE):
        print(f"Error: Could not find {INPUT_FILE}")
        return

    print("Loading and cleaning dataset...")
    formatted_dataset = []
    
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        for line in f:
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
                
            title = item.get("title", "")
            features = item.get("features", [])
            descriptions = item.get("description", [])
            
            # Skip if title or description is missing
            if not title or not descriptions:
                continue
                
            # Usually descriptions is a list in this Amazon dataset, join it
            raw_desc = " ".join(descriptions) if isinstance(descriptions, list) else descriptions
            
            # Clean HTML from description
            clean_desc = clean_html(raw_desc)
            
            # Check word count
            word_count = len(clean_desc.split())
            if word_count < MIN_WORDS_DESCRIPTION:
                continue
                
            # Create messages format
            user_content = format_user_message(title, features)
            
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
                {"role": "assistant", "content": clean_desc}
            ]
            
            formatted_dataset.append({"messages": messages})

    print(f"Total high-quality samples after filtering: {len(formatted_dataset)}")
    
    if not formatted_dataset:
        print("No valid samples found!")
        return
        
    # Split the dataset
    # First split: 80% Train, 20% Temp (Val + Test)
    train_data, temp_data = train_test_split(formatted_dataset, test_size=0.20, random_state=42)
    # Second split: 50% Val, 50% Test from the 20% Temp -> 10% Val, 10% Test
    val_data, test_data = train_test_split(temp_data, test_size=0.50, random_state=42)
    
    # Save datasets
    def save_jsonl(data: list, filename: str):
        filepath = os.path.join(OUTPUT_DIR, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            for d in data:
                f.write(json.dumps(d, ensure_ascii=False) + "\n")
                
    save_jsonl(train_data, "train.jsonl")
    save_jsonl(val_data, "val.jsonl")
    save_jsonl(test_data, "test.jsonl")
    
    print("\nDataset successfully split and saved:")
    print(f"📦 Train set (80%): {len(train_data)} samples -> data/train.jsonl")
    print(f"📦 Val set (10%):   {len(val_data)} samples -> data/val.jsonl")
    print(f"📦 Test set (10%):  {len(test_data)} samples -> data/test.jsonl")
    
    # Show a random example
    print("\n" + "="*80)
    print("Example Data Point (from train set):")
    print("="*80)
    example = random.choice(train_data)["messages"]
    for msg in example:
        print(f"\n[{msg['role'].upper()}]:\n{msg['content'][:200]}...")
    print("="*80)

if __name__ == "__main__":
    process_data()
