import asyncio
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.append(str(Path(__file__).parent.parent))

from app.llm import embed
from app.services.search_service import hybrid_search
from app.db import SessionLocal
from app.models import Product
from sqlalchemy import select

async def experiment():
    print("--- Chunking Experiment (Week 2, Thursday) ---")
    
    query = "kırmızı spor ayakkabı bütçem 1000 TL"
    print(f"Sorgu: {query}\n")

    # Embedding query
    query_vector = (await embed([query]))[0]

    # Hybrid Search Test
    results = await hybrid_search(query, query_vector, limit=3)

    print("Hibrit Arama Sonuçları (BM25 + Vector):")
    for p, score in results:
        print(f"- [{p.sku}] {p.title} | Skor: {score:.4f} | Kategori: {p.category}")

    print("\nFarklı Chunk Stratejileri Karşılaştırması:")
    print("1. Raw: Sadece Başlık")
    print("2. Metadata: Kategori + Başlık + Fiyat")
    print("3. Full: Kategori + Başlık + Açıklama + Fiyat")
    
    print("\nNot: Şu anki 'hybrid_search' Başlık + Açıklama kombinasyonunu kullanıyor.")

if __name__ == "__main__":
    asyncio.run(experiment())
