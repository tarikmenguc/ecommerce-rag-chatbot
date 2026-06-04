import json
import os
import sys

# Paths
INPUT_META = r"C:\Users\tarik\Desktop\dataset\meta_Beauty_and_Personal_Care.jsonl"
INPUT_REVIEWS = r"C:\Users\tarik\Desktop\dataset\Beauty_and_Personal_Care.jsonl"

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
OUTPUT_META = os.path.join(OUTPUT_DIR, "sample_products.jsonl")
OUTPUT_REVIEWS = os.path.join(OUTPUT_DIR, "sample_reviews.jsonl")

TARGET_PRODUCT_COUNT = 5000

def ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path)

def extract_products():
    print(f"Step 1: Extracting top {TARGET_PRODUCT_COUNT} products from {INPUT_META}...")
    ensure_dir(OUTPUT_DIR)
    
    selected_asins = set()
    product_count = 0
    
    with open(INPUT_META, 'r', encoding='utf-8') as fin, \
         open(OUTPUT_META, 'w', encoding='utf-8') as fout:
        
        for line in fin:
            if not line.strip(): continue
            try:
                item = json.loads(line)
            except:
                continue
            
            # Check for required fields for RAG
            has_title = bool(item.get("title"))
            description = item.get("description", [])
            features = item.get("features", [])
            
            # We want products that have at least some descriptive text
            # description or features lists usually contain strings. 
            has_desc = isinstance(description, list) and len(description) > 0 and any(len(str(d)) > 10 for d in description)
            has_feat = isinstance(features, list) and len(features) > 0 and any(len(str(f)) > 10 for f in features)
            
            if has_title and (has_desc or has_feat):
                fout.write(line)
                selected_asins.add(item.get("parent_asin"))
                product_count += 1
                
                if product_count % 500 == 0:
                    print(f"  -> Extracted {product_count} products...")
                
                if product_count >= TARGET_PRODUCT_COUNT:
                    break
                    
    print(f"Done! Successfully extracted {product_count} products.")
    return selected_asins

def extract_reviews(selected_asins):
    print(f"\nStep 2: Extracting reviews for the {len(selected_asins)} selected products from {INPUT_REVIEWS}...")
    print("  (This might take a few minutes as we scan the 11GB file line-by-line)")
    
    review_count = 0
    lines_scanned = 0
    
    with open(INPUT_REVIEWS, 'r', encoding='utf-8') as fin, \
         open(OUTPUT_REVIEWS, 'w', encoding='utf-8') as fout:
        
        for line in fin:
            lines_scanned += 1
            if lines_scanned % 1_000_000 == 0:
                print(f"  -> Scanned {lines_scanned:,} lines, found {review_count:,} matching reviews...")
                
            if not line.strip(): continue
            try:
                item = json.loads(line)
            except:
                continue
                
            if item.get("parent_asin") in selected_asins:
                fout.write(line)
                review_count += 1

    print(f"Done! Successfully extracted {review_count} reviews.")

if __name__ == "__main__":
    if not os.path.exists(INPUT_META) or not os.path.exists(INPUT_REVIEWS):
        print("Error: Input files not found. Please check paths.")
        sys.exit(1)
        
    asins = extract_products()
    if asins:
        extract_reviews(asins)
    else:
        print("No products found matching criteria.")
