import asyncio
import json
import os
import sys
import time

from sqlalchemy import text
from app.db import engine, SessionLocal, Base
from app.models import Product, ProductChunk

# --- Configuration ---
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
PRODUCTS_FILE = os.path.join(DATA_DIR, "sample_products.jsonl")
EMBEDDED_CHUNKS_FILE = os.path.join(DATA_DIR, "embedded_chunks.jsonl")
BATCH_SIZE = 500

async def recreate_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS product_chunk_embedding_hnsw "
            "ON product_chunk USING hnsw (embedding vector_cosine_ops)"
        ))

async def main():
    print("Starting V2 Database Seeding from Colab Embeddings...")
    start_time = time.time()

    if not os.path.exists(PRODUCTS_FILE):
        print(f"❌ Error: {PRODUCTS_FILE} is missing.")
        sys.exit(1)
        
    if not os.path.exists(EMBEDDED_CHUNKS_FILE):
        print(f"❌ Error: Could not find {EMBEDDED_CHUNKS_FILE}!")
        print("Please download it from Google Colab and place it in the data/ folder.")
        sys.exit(1)

    print("\nStep 1: Recreating database tables...")
    await recreate_tables()
    print("  ✅ Tables created + HNSW index on product_chunk.embedding")

    print(f"\nStep 2: Loading Products from {PRODUCTS_FILE}...")
    product_rows = {}
    with open(PRODUCTS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip(): continue
            try:
                raw = json.loads(line)
                asin = raw.get("parent_asin")
                if not asin or asin in product_rows: continue
                
                title = (raw.get("title") or "Unknown")[:512]
                category = " > ".join(raw.get("categories", [])) or raw.get("category", "Unknown")
                price = raw.get("price")
                rating = raw.get("average_rating", 0.0)
                
                product_rows[asin] = Product(
                    sku=asin,
                    title=title,
                    category=category,
                    price_usd=float(price) if price else 0.0,
                    avg_rating=float(rating) if rating else 0.0
                )
            except Exception:
                continue

    async with SessionLocal() as session:
        session.add_all(list(product_rows.values()))
        await session.commit()
    print(f"  ✅ Inserted {len(product_rows):,} products into Product table.")

    print(f"\nStep 3: Loading embedded chunks from {EMBEDDED_CHUNKS_FILE}...")
    chunk_batch = []
    total_inserted = 0

    async with SessionLocal() as session:
        with open(EMBEDDED_CHUNKS_FILE, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip(): continue
                record = json.loads(line)
                
                # Check if product exists in our DB (it should)
                if record.get("sku") not in product_rows:
                    continue
                    
                chunk = ProductChunk(
                    product_sku=record["sku"],
                    chunk_type=record["type"],
                    chunk_index=record["index"],
                    content=record["content"],
                    embedding=record["embedding"]
                )
                chunk_batch.append(chunk)
                
                if len(chunk_batch) >= BATCH_SIZE:
                    session.add_all(chunk_batch)
                    await session.commit()
                    total_inserted += len(chunk_batch)
                    print(f"    Inserted {total_inserted:,} chunks...")
                    chunk_batch.clear()

            if chunk_batch:
                session.add_all(chunk_batch)
                await session.commit()
                total_inserted += len(chunk_batch)
                print(f"    Inserted {total_inserted:,} chunks...")

    print(f"\n✅ Seeding complete in {time.time() - start_time:.1f} seconds!")
    print(f"Summary:")
    print(f"  Products: {len(product_rows):,}")
    print(f"  Chunks  : {total_inserted:,}")

if __name__ == "__main__":
    asyncio.run(main())
