import os
import json
import time
import httpx
import asyncio
import pandas as pd
from dotenv import load_dotenv
from google import genai
from google.genai import types
import random

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

API_URL = "http://localhost:8000/description/generate"

async def call_gemini(title, features):
    prompt = f"{title} için kısa, esprili ve çok ikna edici bir ürün açıklaması yazar mısın?"
    if features:
        prompt += f"\nÜrün özellikleri: {features}"
    
    start = time.time()
    def _do_call():
        return client.models.generate_content(
            model="gemini-3.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction="You are an expert e-commerce copywriter. Write in Turkish.",
                temperature=0.3
            )
        )
    
    resp = await asyncio.to_thread(_do_call)
    latency = time.time() - start
    
    try:
        in_tok = resp.usage_metadata.prompt_token_count
        out_tok = resp.usage_metadata.candidates_token_count
    except:
        in_tok = 0
        out_tok = 0
        
    cost = (in_tok / 1000000) * 0.075 + (out_tok / 1000000) * 0.300
    
    return {
        "model": "gemini-3.5-flash",
        "description": resp.text,
        "latency": latency,
        "tokens_in": in_tok,
        "tokens_out": out_tok,
        "cost_usd": cost
    }

async def call_llama(title, features):
    start = time.time()
    
    payload = {
        "product_name": title,
        "features": features
    }
    
    async with httpx.AsyncClient() as hc:
        res = await hc.post(API_URL, json=payload, timeout=60.0)
        res.raise_for_status()
        data = res.json()
        
    latency = time.time() - start
    
    return {
        "model": "ecommerce-llama3",
        "description": data["description"],
        "latency": latency,
        "tokens_in": 0, 
        "tokens_out": len(data["description"].split()), 
        "cost_usd": 0.0
    }

def extract_title_and_features(content):
    parts = content.split("\n\nFeatures:\n")
    title = parts[0].replace("Title: ", "").strip()
    features = parts[1].strip() if len(parts) > 1 else ""
    return title, features

async def evaluate_product(product):
    title, features = extract_title_and_features(product["user"])
    
    gemini_task = asyncio.create_task(call_gemini(title, features))
    llama_task = asyncio.create_task(call_llama(title, features))
    
    try:
        gemini_res, llama_res = await asyncio.gather(gemini_task, llama_task)
    except Exception as e:
        print(f"Error evaluating product: {e}")
        return None
        
    return {
        "title": title,
        "features": features,
        "gemini_desc": gemini_res["description"],
        "gemini_latency": gemini_res["latency"],
        "gemini_cost": gemini_res["cost_usd"],
        "llama_desc": llama_res["description"],
        "llama_latency": llama_res["latency"],
        "llama_cost": llama_res["cost_usd"]
    }

async def main():
    print("Loading test data...")
    products = []
    with open("data/test.jsonl", "r", encoding="utf-8") as f:
        for line in f:
            obj = json.loads(line)
            user_msg = next(m["content"] for m in obj["messages"] if m["role"] == "user")
            products.append({"user": user_msg})
            
    random.seed(42)
    sample_size = min(25, len(products))
    test_products = random.sample(products, sample_size)
    
    print(f"Starting A/B test on {sample_size} products...")
    
    results = []
    for i, p in enumerate(test_products):
        print(f"Processing product {i+1}/{sample_size}...")
        res = await evaluate_product(p)
        if res:
            results.append(res)
            
    df = pd.DataFrame(results)
    
    print("\n--- A/B TEST RESULTS ---")
    print(f"Average Gemini Latency: {df['gemini_latency'].mean():.2f}s")
    print(f"Average Llama-3 Latency: {df['llama_latency'].mean():.2f}s")
    print(f"Total Gemini Cost: ${df['gemini_cost'].sum():.4f}")
    print(f"Total Llama Cost: ${df['llama_cost'].sum():.4f}")
    
    df.to_csv("data/ab_test_results.csv", index=False)
    print("\nResults saved to data/ab_test_results.csv")

if __name__ == "__main__":
    asyncio.run(main())
