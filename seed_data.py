import asyncio
import pandas as pd

from app.db import SessionLocal, engine, Base
from app.models import Product
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
            "CREATE INDEX IF NOT EXISTS product_embedding_hnsw "
            "ON product USING hnsw (embedding vector_cosine_ops)"
        ))
        print("✅ HNSW indeksi oluşturuldu.")

    print("CSV dosyaları yükleniyor...")
    products = pd.read_csv("amazon_products.csv")
    categories = pd.read_csv("amazon_categories.csv")

    print(f"Orijinal ürün sayısı: {len(products)}")
    products = products.dropna(subset=["asin", "title", "category_id"])

    sample_size = min(10000, len(products))
    products = products.sample(n=sample_size, random_state=42)

    df = pd.merge(products, categories, left_on="category_id", right_on="id", how="left")
    df["category_name"] = df["category_name"].fillna("Other")
    df["price"] = df["price"].fillna(0.0)

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

            products_to_insert = [
                Product(
                    sku=item["sku"],
                    title=item["title"],
                    description=item["description"],
                    category=item["category"],
                    price_usd=item["price_usd"],
                    embedding=emb,
                )
                for item, emb in zip(db_products, embeddings)
            ]

            session.add_all(products_to_insert)
            await session.commit()

            total_inserted += len(products_to_insert)
            print(f"  ✅ Eklendi: {total_inserted}/{len(df)}")

    print(f"\n🎉 İşlem tamamlandı! Toplam {total_inserted} ürün veritabanına yüklendi.")

if __name__ == "__main__":
    asyncio.run(seed_data())
