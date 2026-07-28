"""
Test Scripti: /description/batch endpoint'ini uçtan uca test eder.

Çalıştırmak için:
    python scripts/test_batch_e2e.py

Beklenen Akış:
    1. Webhook dinleyici (mock server) port 9999'da başlatılır.
    2. 3 ürün /description/batch'e POST edilir.
    3. API 202 Accepted döner.
    4. queue_poller arka planda Ollama'yı çağırır.
    5. Her iş bitince mock webhook server'a POST gelir.
    6. Script sonuçları terminale basar ve çıkar.
"""
import asyncio
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread

import httpx

API_URL = "http://localhost:8000/description/batch"
MOCK_WEBHOOK_PORT = 9999
MOCK_WEBHOOK_URL = f"http://host.docker.internal:{MOCK_WEBHOOK_PORT}/webhook"

# Lokal test: Docker yoksa localhost kullan
import socket
try:
    socket.getaddrinfo("host.docker.internal", 80)
except socket.gaierror:
    MOCK_WEBHOOK_URL = f"http://localhost:{MOCK_WEBHOOK_PORT}/webhook"

results: list[dict] = []
expected_count = 3


class MockWebhookHandler(BaseHTTPRequestHandler):
    """Gelen webhook POST'larını yakalar ve results listesine ekler."""
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        data = json.loads(body.decode())
        results.append(data)
        self.send_response(200)
        self.end_headers()
        print(f"\n[WEBHOOK] Alindi #{len(results)}/{expected_count}")
        print(f"   ID: {data.get('external_reference_id')}")
        print(f"   Status: {data.get('status')}")
        if data.get("generated_text"):
            preview = data["generated_text"][:150].replace("\n", " ")
            print(f"   HTML Preview: {preview}...")

    def log_message(self, format, *args):  # noqa: A002
        pass  # Gereksiz HTTP logları sustur


def run_mock_server():
    server = HTTPServer(("0.0.0.0", MOCK_WEBHOOK_PORT), MockWebhookHandler)
    server.serve_forever()


async def main():
    # 1. Mock webhook server'ı arka planda başlat
    t = Thread(target=run_mock_server, daemon=True)
    t.start()
    print(f"[OK] Mock webhook server port {MOCK_WEBHOOK_PORT}'da dinleniyor...")
    await asyncio.sleep(0.5)

    # 2. Test urunleri
    payload = {
        "webhook_url": MOCK_WEBHOOK_URL,
        "products": [
            {
                "external_reference_id": "row_1",
                "product_title": "Erkek Siyah Kosu Ayakkabisi",
                "product_features": "Taban: EVA kopuk, Ust Malzeme: Orgu file, Renk: Siyah/Beyaz, Agirlik: 285g",
            },
            {
                "external_reference_id": "row_2",
                "product_title": "Kadin Oversize Triko Kazak",
                "product_features": "Materyal: %80 Akril %20 Yun, Kesim: Oversize, Yaka: Balikciyaka, Renk: Deve Tuyu",
            },
            {
                "external_reference_id": "row_3",
                "product_title": "Paslanmaz Celik Termos 500ml",
                "product_features": "Kapasite: 500ml, Malzeme: 316 Paslanmaz Celik, Sicaklik koruma: 12 saat sicak 24 saat soguk",
            },
        ],
    }

    # 3. API'ye istek at
    print(f"\n[SEND] {API_URL} adresine {len(payload['products'])} urun gonderiliyor...")
    async with httpx.AsyncClient() as client:
        resp = await client.post(API_URL, json=payload, timeout=10.0)

    print(f"[API] HTTP {resp.status_code}")
    data = resp.json()
    print(f"   batch_id: {data.get('batch_id')}")
    print(f"   message: {data.get('message')}")

    if resp.status_code != 202:
        print("[FAIL] Hata: 202 Accepted beklendi!")
        return

    # 4. Webhook'larin gelmesini bekle (max 5 dakika)
    print(f"\n[WAIT] {expected_count} webhook bekleniyor (max 5 dk)...")
    for _ in range(300):
        if len(results) >= expected_count:
            break
        await asyncio.sleep(1)

    # 5. Sonuclari ozetle
    print(f"\n{'='*50}")
    print(f"[RESULT] {len(results)}/{expected_count} webhook alindi.")
    completed = sum(1 for r in results if r.get("status") == "COMPLETED")
    failed = sum(1 for r in results if r.get("status") == "FAILED")
    print(f"   Tamamlanan: {completed}")
    print(f"   Basarisiz:  {failed}")

    if completed == expected_count:
        print("\n[SUCCESS] Uctan uca batch sistemi calisiyor!")
    else:
        print("\n[WARN] Bazi isler tamamlanamadi. Docker loglarini kontrol edin.")


if __name__ == "__main__":
    asyncio.run(main())
