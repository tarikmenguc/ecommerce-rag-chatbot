import os
import asyncio
import httpx
import pandas as pd
from datasets import Dataset
from ragas import evaluate
from ragas.metrics import faithfulness, answer_relevancy
from rich.console import Console

console = Console()

API_URL = "http://localhost:8000/search"
HEADERS = {"X-API-Key": "tarik-proje"}

# 10 Sample Synthetic Queries
EVAL_DATA = [
    {"query": "Kuru ciltler için en iyi nemlendirici hangisidir?", "expected_aspects": ["nemlendirici", "kuru cilt", "hyalüronik asit"]},
    {"query": "Yağlı saçlar için hangi şampuanı önerirsiniz?", "expected_aspects": ["şampuan", "yağlı saç"]},
    {"query": "Göz altı torbaları nasıl geçer?", "expected_aspects": ["göz altı torbası", "krem", "serum"]},
    {"query": "Siyah nokta temizleyici maske tavsiyesi?", "expected_aspects": ["siyah nokta", "maske", "kil"]},
    {"query": "Vegan ve cruelty-free makyaj fırçası seti var mı?", "expected_aspects": ["vegan", "cruelty-free", "fırça"]},
]

async def fetch_rag_response(query: str):
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(API_URL, json={"query": query, "top_k": 3}, headers=HEADERS)
        if resp.status_code == 200:
            data = resp.json()
            return data["answer"], [hit["title"] for hit in data["hits"]]
        return "", []

async def main():
    console.print("[bold]RAGAS Evaluation Started...[/bold]")
    
    questions = []
    answers = []
    contexts = []
    ground_truths = []
    
    for item in EVAL_DATA:
        query = item["query"]
        console.print(f"Fetching: {query}")
        answer, hits = await fetch_rag_response(query)
        
        questions.append(query)
        answers.append(answer)
        contexts.append(hits)
        ground_truths.append(item["expected_aspects"])
        
    data = {
        "question": questions,
        "answer": answers,
        "contexts": contexts,
        "ground_truth": ground_truths
    }
    
    dataset = Dataset.from_dict(data)
    
    # Langfuse Integration
    if os.environ.get("LANGFUSE_PUBLIC_KEY") and os.environ.get("LANGFUSE_SECRET_KEY"):
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        # Ragas automatically picks up Langfuse traces via Langchain setup or manual handler
    
    console.print("[bold yellow]Running Ragas metrics (Faithfulness & Answer Relevancy)...[/bold yellow]")
    
    try:
        result = evaluate(
            dataset,
            metrics=[faithfulness, answer_relevancy],
            raise_exceptions=False
        )
        
        df = result.to_pandas()
        console.print("\n[bold green]Evaluation Results:[/bold green]")
        console.print(df[["question", "faithfulness", "answer_relevancy"]])
        console.print(f"\n[bold]Average Faithfulness:[/bold] {df['faithfulness'].mean():.2f}")
        console.print(f"[bold]Average Answer Relevancy:[/bold] {df['answer_relevancy'].mean():.2f}")
    except Exception as e:
        console.print(f"[bold red]Evaluation failed:[/bold red] {e}")
        console.print("Make sure OPENAI_API_KEY is set in your environment as Ragas uses OpenAI for metrics by default.")

if __name__ == "__main__":
    asyncio.run(main())
