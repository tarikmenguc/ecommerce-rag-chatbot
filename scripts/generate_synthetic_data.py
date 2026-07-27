import os
import json
import ollama

# Configuration
INPUT_FILE = "data/train.jsonl"
OUTPUT_FILE = "data/synthetic_train_ollama.jsonl"
MODEL_NAME = "llama3.1" 

SYSTEM_PROMPT = """You are one of the world's best and highest-paid e-commerce copywriters and marketing experts. Your task is to transform raw, technical product descriptions into high-converting, compelling, and fluent marketing copy. You must strictly adhere to the following rules:

1. ABSOLUTE LOYALTY TO PRODUCT FACTS & CATEGORY (ZERO HALLUCINATION): Never delete, alter, or over-simplify specific technical terms, patented ingredients, scientific explanations, or unique selling propositions (USPs) from the original text; weave them naturally into the copy. NEVER add any feature, promise, ingredient, or industry jargon that is not explicitly stated in the original text (e.g., do not use salon/hairdresser terms for a supermarket product; do not use luxury/premium terms for an entry-level product). Enrich the text ONLY within the boundaries of the product's actual identity, segment, and tone.
2. AVOID AI CLICHÉS (AUTHENTICITY): DO NOT use insincere and overused AI buzzwords such as "ultimate", "elevate", "without compromise", "transform your routine", "delve", or "testament". Instead, build striking, clear, dynamic, and direct action sentences that resonate with the target audience.
3. TARGET AUDIENCE & CATEGORY MATCH (TONE CONTROL): Do not position every product like a luxury perfume. Adjust your tone according to the product's specific sub-category. For example, use a reassuring, medical, and clean tone for an anti-dandruff shampoo, but use a stylish and masculine tone for a styling wax.
4. STRONG HOOK & CLEAR CTA: Instead of a boring introduction, start with a powerful hook that directly addresses the reader's problem or desire. End the text with a natural, non-exaggerated Call to Action (CTA).
5. NO CONVERSATIONAL FILLER: Return ONLY the final product description. Do NOT include any introductory sentences like "Here is a rewritten product description" or "Sure, here you go." Just output the copy.

CRITICAL: The final product description MUST be written in ENGLISH. Target length: 80-150 words. To reach this word count without inventing new features, use marketing psychology: expand on the customer's pain points, elaborate on the emotional benefits of the existing features, and build a stronger narrative around what is already provided."""

def get_processed_count():
    if not os.path.exists(OUTPUT_FILE):
        return 0
    with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
        return sum(1 for _ in f)

def generate_description(prompt_text):
    try:
        response = ollama.chat(model=MODEL_NAME, messages=[
            {'role': 'system', 'content': SYSTEM_PROMPT},
            {'role': 'user', 'content': prompt_text}
        ])
        return response['message']['content'].strip()
    except Exception as e:
        print(f"    [Ollama Error] {e}")
        return None

def main():
    print(f"Starting Knowledge Distillation Pipeline using Local Model: {MODEL_NAME}")
    
    if not os.path.exists(INPUT_FILE):
        print(f"Error: {INPUT_FILE} not found.")
        return
        
    processed = get_processed_count()
    print(f"Found {processed} already processed items. Resuming from index {processed}.")
    
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()
        
    total_lines = len(lines)
    remaining_lines = lines[processed:]
    
    if not remaining_lines:
        print("All items processed!")
        return

    with open(OUTPUT_FILE, "a", encoding="utf-8") as out_f:
        for i, line in enumerate(remaining_lines):
            current_idx = processed + i + 1
            
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
                
            messages = item.get("messages", [])
            user_msg = next((m["content"] for m in messages if m["role"] == "user"), None)
            
            if not user_msg:
                continue
                
            print(f"Processing [{current_idx}/{total_lines}] via {MODEL_NAME}...")
            
            new_desc = generate_description(user_msg)
            
            if new_desc:
                # Reconstruct the messages format for SFT
                new_messages = [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_msg},
                    {"role": "assistant", "content": new_desc}
                ]
                
                out_f.write(json.dumps({"messages": new_messages}, ensure_ascii=False) + "\n")
                out_f.flush()

    print("Pipeline Finished!")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--pilot":
        with open(INPUT_FILE, "r", encoding="utf-8") as f:
            item = json.loads(f.readline())
            user_msg = next((m["content"] for m in item["messages"] if m["role"] == "user"), None)
            old_desc = next((m["content"] for m in item["messages"] if m["role"] == "assistant"), "No original description found.")
            
        print(f"=== OLLAMA ({MODEL_NAME}) PILOT TEST ===")
        print(f"\n[USER INPUT]:\n{user_msg}")
        print(f"\n[ESKİ AÇIKLAMA (BEFORE)]:\n{old_desc}")
        print("\n[GENERATING NEW DESCRIPTION WITH LOCAL LLAMA...]")
        
        new_desc = generate_description(user_msg)
        print(f"\n[YENİ LOKAL AÇIKLAMA (AFTER)]:\n{new_desc}")
    else:
        main()
