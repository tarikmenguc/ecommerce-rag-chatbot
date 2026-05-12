import asyncio
import sys
from pathlib import Path

# Proje kök dizinini Python yoluna ekle
sys.path.append(str(Path(__file__).parent.parent))

from app.llm import embed
from app.services.search_service import hybrid_search

# Test edilecek 20 sorgu
TEST_QUERIES = [
    "Black suitcase", "Travel luggage", "Small carry-on",
    "Luggage under $150", "28-inch checked bag", "Hard shell suitcase",
    "Lightweight travel bag", "Cheap backpack",
    "Durable suitcase for long trips", "Best bag for business",
    "Safe luggage with TSA lock", "Waterproof travel bag",
    "Compact bag for laptop", "Best spinner wheels",
    "Samsonite suitcase", "Expandable luggage",
    "Arctic Silver bag", "Carry-on with wheels",
    "TSA approved bag", "Black travel luggage"
]

async def start_eval():
    print("=== Pazar Günü Değerlendirme Başladı ===\n")
    
    for i, query in enumerate(TEST_QUERIES, 1):
        print(f"Sorgu {i}: {query}")
        
        # 1. Metni sayıya çevir (Embedding)
        vectors = await embed([query])
        
        # 2. Hibrit Arama yap
        hits = await hybrid_search(query, vectors[0], limit=5)
        
        # 3. Sonuçları ekrana bas
        for rank, (product, score) in enumerate(hits, 1):
            print(f"  {rank}. {product.title[:60]}... (Skor: {score:.2f})")
        
        print("-" * 30)

    print("\nDeğerlendirme bitti. Şimdi bu sonuçlara göre Precision@5 puanlarını verebilirsin.")

if __name__ == "__main__":
    asyncio.run(start_eval())
