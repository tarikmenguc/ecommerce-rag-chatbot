"""
Dataset Inspection Script — Amazon Reviews 2023
Çalıştır: python inspect_dataset.py
Çıktıyı Claude'a yapıştır.
"""

import os
import json
import gzip
import glob
import sys
from pathlib import Path
from collections import Counter

# ── Ayarlar ──────────────────────────────────────────────────────────────────
DATASET_DIR = r"C:\Users\tarik\Desktop\dataset"
SAMPLE_ROWS = 3       # Her dosyadan kaç örnek satır gösterilsin
REVIEW_SAMPLE = 5000  # RAM'e çekilecek max review satırı (hız için)
META_SAMPLE   = 5000  # RAM'e çekilecek max meta satırı

# ── Yardımcı fonksiyonlar ─────────────────────────────────────────────────────

def file_size_mb(path: str) -> float:
    return os.path.getsize(path) / 1024 / 1024


def open_file(path: str):
    """Hem .jsonl hem .jsonl.gz dosyaları açar."""
    if path.endswith(".gz"):
        return gzip.open(path, "rt", encoding="utf-8")
    return open(path, "r", encoding="utf-8")


def read_jsonl_sample(path: str, n: int) -> list[dict]:
    rows = []
    with open_file(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
            if len(rows) >= n:
                break
    return rows


def count_lines(path: str) -> int:
    """Dosyanın toplam satır sayısını sayar (büyük dosyalar için yavaş ama doğru)."""
    count = 0
    with open_file(path) as f:
        for _ in f:
            count += 1
    return count


def analyze_field(rows: list[dict], field: str) -> dict:
    """Bir alanın null oranı, tip dağılımı ve örnek değerlerini döner."""
    values = [r.get(field) for r in rows]
    non_null = [v for v in values if v is not None]
    null_count = len(values) - len(non_null)

    types = Counter(type(v).__name__ for v in non_null)

    # Metin alanlarında uzunluk istatistiği
    text_lengths = []
    if field in ("text", "description", "features", "title"):
        for v in non_null:
            if isinstance(v, str):
                text_lengths.append(len(v))
            elif isinstance(v, list):
                text_lengths.append(sum(len(str(x)) for x in v))

    result = {
        "null_count": null_count,
        "null_pct": round(null_count / len(values) * 100, 1) if values else 0,
        "types": dict(types),
    }
    if text_lengths:
        result["text_len_avg"] = round(sum(text_lengths) / len(text_lengths))
        result["text_len_max"] = max(text_lengths)
        result["text_len_min"] = min(text_lengths)
    return result


def print_separator(char="─", width=70):
    print(char * width)


# ── Ana analiz ────────────────────────────────────────────────────────────────

def main():
    dataset_path = Path(DATASET_DIR)
    if not dataset_path.exists():
        print(f"[HATA] Klasör bulunamadı: {DATASET_DIR}")
        sys.exit(1)

    # 1. Klasör içeriği
    print_separator("═")
    print("  DATASET KLASÖR İÇERİĞİ")
    print_separator("═")
    all_files = sorted(dataset_path.rglob("*"))
    for f in all_files:
        if f.is_file():
            size = file_size_mb(str(f))
            print(f"  {f.relative_to(dataset_path)!s:<55}  {size:>8.1f} MB")
    print()

    # 2. Her dosyayı ayrı ayrı analiz et
    jsonl_files = list(dataset_path.rglob("*.jsonl")) + list(dataset_path.rglob("*.jsonl.gz"))

    if not jsonl_files:
        # .json uzantılı da dene
        jsonl_files = list(dataset_path.rglob("*.json")) + list(dataset_path.rglob("*.json.gz"))

    if not jsonl_files:
        print("[UYARI] .jsonl / .json dosyası bulunamadı. Klasördeki tüm dosyaları listeleyelim:")
        for f in all_files:
            if f.is_file():
                print(f"  {f}")
        return

    for fpath in jsonl_files:
        fpath_str = str(fpath)
        fname = fpath.name
        print_separator("═")
        print(f"  DOSYA: {fpath.relative_to(dataset_path)}")
        print_separator("═")
        print(f"  Boyut : {file_size_mb(fpath_str):.1f} MB")

        # Satır sayısı (büyük dosyalarda bu yavaş olabilir, yorum satırına al)
        try:
            line_count = count_lines(fpath_str)
            print(f"  Satır : {line_count:,}")
        except Exception as e:
            print(f"  Satır : sayılamadı ({e})")

        # Örnek yükle
        is_review = any(k in fname.lower() for k in ("review", "rating", "user"))
        sample_n = REVIEW_SAMPLE if is_review else META_SAMPLE
        rows = read_jsonl_sample(fpath_str, sample_n)
        print(f"  Örnek : {len(rows):,} satır yüklendi (analiz için)")

        if not rows:
            print("  [UYARI] Hiç satır okunamadı.")
            print()
            continue

        # Sütunlar
        all_keys = set()
        for r in rows:
            all_keys.update(r.keys())
        print(f"\n  SÜTUNLAR ({len(all_keys)} adet):")
        print_separator()

        for key in sorted(all_keys):
            info = analyze_field(rows, key)
            null_str = f"null:{info['null_pct']}%" if info["null_count"] else "non-null"
            type_str = str(info["types"])
            len_str = ""
            if "text_len_avg" in info:
                len_str = f"  avg_len:{info['text_len_avg']}  max:{info['text_len_max']}"
            print(f"  {key:<22}  {null_str:<12}  {type_str:<30}{len_str}")

        # Örnek satırlar
        print(f"\n  İLK {SAMPLE_ROWS} SATIR ÖRNEĞİ:")
        print_separator()
        for i, row in enumerate(rows[:SAMPLE_ROWS]):
            print(f"\n  --- Satır {i+1} ---")
            for k, v in row.items():
                val_str = str(v)
                if len(val_str) > 200:
                    val_str = val_str[:200] + "..."
                print(f"    {k:<20}: {val_str}")

        # Kategori dağılımı (varsa)
        for cat_field in ("main_category", "category", "categories"):
            if cat_field in all_keys:
                cats = [r.get(cat_field) for r in rows if r.get(cat_field)]
                flat_cats = []
                for c in cats:
                    if isinstance(c, list):
                        flat_cats.extend([str(x) for x in c[:1]])  # sadece ilk seviye
                    else:
                        flat_cats.append(str(c))
                top_cats = Counter(flat_cats).most_common(10)
                print(f"\n  KATEGORİ DAĞILIMI ({cat_field}) — ilk 10:")
                print_separator()
                for cat, cnt in top_cats:
                    pct = cnt / len(flat_cats) * 100
                    print(f"    {cat:<50}  {cnt:>6,} ({pct:.1f}%)")
                break

        # Rating dağılımı (varsa)
        for rating_field in ("rating", "average_rating"):
            if rating_field in all_keys:
                ratings = [r.get(rating_field) for r in rows if isinstance(r.get(rating_field), (int, float))]
                if ratings:
                    avg = sum(ratings) / len(ratings)
                    dist = Counter(int(r) for r in ratings)
                    print(f"\n  RATING DAĞILIMI ({rating_field}) — avg:{avg:.2f}")
                    print_separator()
                    for star in sorted(dist.keys(), reverse=True):
                        bar = "█" * (dist[star] * 30 // max(dist.values()))
                        print(f"    {star}★  {bar:<32}  {dist[star]:,}")
                break

        # Metin kalite testi (Hafta 5 chunking için kritik)
        for text_field in ("text", "description", "features"):
            if text_field in all_keys:
                values = [r.get(text_field) for r in rows if r.get(text_field)]
                non_empty = []
                for v in values:
                    if isinstance(v, str) and v.strip():
                        non_empty.append(v)
                    elif isinstance(v, list) and any(str(x).strip() for x in v):
                        non_empty.append(" ".join(str(x) for x in v))

                if non_empty:
                    lengths = [len(v) for v in non_empty]
                    avg_len = sum(lengths) / len(lengths)
                    rich = sum(1 for l in lengths if l > 100)
                    print(f"\n  METİN KALİTESİ ({text_field}):")
                    print_separator()
                    print(f"    Dolu kayıt   : {len(non_empty):,} / {len(values):,}")
                    print(f"    Ort. uzunluk : {avg_len:.0f} karakter")
                    print(f"    >100 karakter: {rich:,} ({rich/len(non_empty)*100:.1f}%) ← chunking için yeterli mi?")
                    print(f"    Örnek metin  : {non_empty[0][:300]!r}")

        print()

    print_separator("═")
    print("  ANALİZ TAMAMLANDI")
    print("  Bu çıktıyı Claude'a yapıştır → şema + seed planı netleştirilecek.")
    print_separator("═")


if __name__ == "__main__":
    main()
