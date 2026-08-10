import asyncio
import pandas as pd

from app.db import SessionLocal, engine, Base
from app.models import Product, ProductChunk
from app.config import get_settings
from app.llm import embed
from sqlalchemy import text

settings = get_settings()

async def seed_data():
    print("Eski tablolar silinip yeniden oluşturuluyor...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
        # HNSW indeksi — Cosine Distance için optimize (1024 boyut)
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS product_chunk_embedding_hnsw "
            "ON product_chunk USING hnsw (embedding vector_cosine_ops)"
        ))
        print("✅ HNSW indeksi oluşturuldu.")

    print("CSV dosyaları yükleniyor...")
    products = pd.read_csv("amazon_products.csv")
    categories = pd.read_csv("amazon_categories.csv")

    print(f"Orijinal ürün sayısı: {len(products)}")
    products = products.dropna(subset=["asin", "title", "category_id"])

    # Premium filtreler: Fiyatı 0'dan büyük, 4+ yıldızlı ve en az 50 yorumlu ürünler
    products["price"] = pd.to_numeric(products["price"], errors="coerce").fillna(0.0)
    products["stars"] = pd.to_numeric(products["stars"], errors="coerce").fillna(0.0)
    products["reviews"] = pd.to_numeric(products["reviews"], errors="coerce").fillna(0)
    
    products = products[(products["price"] > 0) & (products["stars"] >= 4.0) & (products["reviews"] >= 50)]
    print(f"Premium kriterleri sağlayan ürün sayısı: {len(products)}")

    # En popüler 50.000 ürünü (yorum sayısına göre) seç
    sample_size = min(50000, len(products))
    products = products.sort_values(by="reviews", ascending=False).head(sample_size)

    df = pd.merge(products, categories, left_on="category_id", right_on="id", how="left")
    df["category_name"] = df["category_name"].fillna("Other")

    print(f"Toplam {len(df)} ürün vektörize edilecek.")
    print(f"Model yükleniyor: {settings.default_embed_model} (Bu işlem ilk seferde model indireceği için biraz sürebilir)...")

    # Limit yok, o yüzden batch boyutunu büyütebiliriz.
    batch_size = 500
    total_inserted = 0

    async with SessionLocal() as session:
        for start_idx in range(0, len(df), batch_size):
            batch = df.iloc[start_idx: start_idx + batch_size]

            db_products = []
            texts_to_embed = []

            for _, row in batch.iterrows():
                title = str(row["title"])[:512]
                category = str(row["category_name"])[:128]
                price = float(row["price"])
                description = f"Category: {category} | Product: {title}"
                texts_to_embed.append(description)
                db_products.append({
                    "sku": str(row["asin"]),
                    "title": title,
                    "description": description,
                    "category": category,
                    "price_usd": price,
                })

            print(f"Batch {start_idx//batch_size + 1}/{len(df)//batch_size + 1} işleniyor ({len(batch)} ürün)...")
            
            try:
                embeddings = await embed(texts_to_embed)
            except Exception as e:
                print(f"Embedding hatası (batch {start_idx}): {e}")
                continue

            products_to_insert = []
            for item, emb in zip(db_products, embeddings):
                prod = Product(
                    sku=item["sku"],
                    title=item["title"],
                    category=item["category"],
                    price_usd=item["price_usd"],
                )
                chunk = ProductChunk(
                    product=prod,
                    chunk_type="metadata",
                    chunk_index=0,
                    content=item["description"],
                    embedding=emb
                )
                products_to_insert.append(prod)
                products_to_insert.append(chunk)

            session.add_all(products_to_insert)
            await session.commit()

            total_inserted += len(products_to_insert)
            print(f"  ✅ Eklendi: {total_inserted}/{len(df)}")

    print(f"\n🎉 İşlem tamamlandı! Toplam {total_inserted} ürün veritabanına yüklendi.")

if __name__ == "__main__":
    asyncio.run(seed_data())
