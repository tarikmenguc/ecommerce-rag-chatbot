from __future__ import annotations

from sqlalchemy import select
from app.models import Product
from app.db import SessionLocal
from rank_bm25 import BM25Okapi

async def vector_search(query_embedding: list[float], limit: int = 5):
    """Sadece vektör benzerliğine göre arama yapar."""
    async with SessionLocal() as session:
        # <=> operatörü mesafeyi verir, 1'den çıkarınca benzerlik olur.
        stmt = (
            select(Product, (1 - Product.embedding.cosine_distance(query_embedding)).label("similarity"))
            .order_by(Product.embedding.cosine_distance(query_embedding))
            .limit(limit)
        )
        result = await session.execute(stmt)
        return [(row[0], float(row[1])) for row in result.all()]

async def hybrid_search(query: str, query_embedding: list[float], limit: int = 5):
    """Hem anahtar kelime (BM25) hem de anlam (Vector) araması yapar."""
    async with SessionLocal() as session:
        # 1. Veritabanındaki tüm ürünleri getir
        stmt = select(Product)
        result = await session.execute(stmt)
        all_products = result.scalars().all()
        
        if not all_products:
            return []

        # 2. Vektör Benzerlik Skorlarını Hesapla
        # (Basitlik için burada manuel hesaplıyoruz, pgvector veritabanında daha hızlıdır)
        def get_sim(a, b):
            dot = sum(x*y for x, y in zip(a, b))
            norm_a = sum(x*x for x in a)**0.5
            norm_b = sum(x*x for x in b)**0.5
            return dot / (norm_a * norm_b)
        
        vector_scores = [get_sim(query_embedding, p.embedding) for p in all_products]
        
        # 3. BM25 (Kelime) Skorlarını Hesapla
        corpus = [f"{p.title} {p.description}".lower().split() for p in all_products]
        bm25 = BM25Okapi(corpus)
        bm25_scores = bm25.get_scores(query.lower().split())
        
        # 4. Skorları Normalize Et (0 ile 1 arasına getir)
        def normalize(scores):
            low, high = min(scores), max(scores)
            if high == low: return [1.0] * len(scores)
            return [(s - low) / (high - low) for s in scores]
        
        v_norm = normalize(vector_scores)
        b_norm = normalize(bm25_scores)
        
        # 5. İkisini Birleştir (%50 + %50)
        combined = []
        for i in range(len(all_products)):
            final_score = (0.5 * v_norm[i]) + (0.5 * b_norm[i])
            combined.append((all_products[i], final_score))
            
        # En yüksek skora göre sırala
        combined.sort(key=lambda x: x[1], reverse=True)
        return combined[:limit]
