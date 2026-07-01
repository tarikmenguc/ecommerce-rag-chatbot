import os
import sys
import json
import asyncio

# Fix Windows console emoji/unicode encoding errors
sys.stdout.reconfigure(encoding='utf-8')

from dotenv import load_dotenv
from huggingface_hub import AsyncInferenceClient

load_dotenv()

HF_TOKEN = os.getenv("HF_TOKEN")

# Models to evaluate
MODELS = {
    "Llama-3.1-8B": "meta-llama/Meta-Llama-3.1-8B-Instruct",
    "Qwen-2.5-7B": "Qwen/Qwen2.5-7B-Instruct",
    "Mistral-7B": "mistralai/Mistral-7B-Instruct-v0.3"
}

PROMPT_TEMPLATE = """You are an expert e-commerce copywriter. 
Write a compelling product description based on the provided title and features.
Keep it engaging, professional, and highlight the main benefits.

Title: {title}

Features:
{features}

Product Description:"""

async def evaluate_models():
    if not HF_TOKEN:
        print("ERROR: HF_TOKEN is not set in your .env file.")
        print("Please create a free HuggingFace account, go to Settings -> Access Tokens, create a 'Read' token, and add HF_TOKEN=... to your .env file.")
        return

    print("Loading 2 random samples from the dataset...\n")
    samples = []
    with open("data/sample_products.jsonl", "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if i in [0, 4]: # Just picking two specific ones for consistency
                samples.append(json.loads(line))
            if i > 5:
                break

    client = AsyncInferenceClient(token=HF_TOKEN)

    for sample in samples:
        title = sample.get("title", "")
        features = "\n".join(f"- {feat}" for feat in sample.get("features", []))
        prompt = PROMPT_TEMPLATE.format(title=title, features=features)
        
        print("="*80)
        print(f" PRODUCT: {title[:80]}...")
        print("="*80)

        for model_name, model_id in MODELS.items():
            print(f"\n MODEL: {model_name} ({model_id})")
            print("-" * 40)
            try:
                messages = [
                    {"role": "user", "content": prompt}
                ]
                response = await client.chat_completion(
                    model=model_id,
                    messages=messages,
                    max_tokens=200,
                    temperature=0.7
                )
                output = response.choices[0].message.content.strip()
                print(output)
            except Exception as e:
                print(f"Failed to generate: {e}")
            print("\n")

if __name__ == "__main__":
    asyncio.run(evaluate_models())
