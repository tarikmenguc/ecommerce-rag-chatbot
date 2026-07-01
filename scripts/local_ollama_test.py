import ollama
import time
import sys

sys.stdout.reconfigure(encoding='utf-8')

def test_local_model():
    print("🚀 Ollama ile Llama 3.1'e (Lokal) bağlanılıyor...")
    
    # E-ticaret ürün açıklaması promptu
    prompt = """You are an expert e-commerce copywriter. 
Write a short, catchy 2-sentence product description for a 'Stainless Steel Water Bottle'.
"""
    
    start_time = time.time()
    
    try:
        # Ollama SDK ile modele istek atıyoruz
        response = ollama.chat(model='llama3.1', messages=[
            {
                'role': 'user',
                'content': prompt,
            },
        ])
        
        end_time = time.time()
        latency = end_time - start_time
        
        print("\n" + "="*50)
        print("Cevap (Llama 3.1 - Lokal):")
        print("="*50)
        print(response['message']['content'])
        print("\n" + "="*50)
        print(f"⏱️ Süre (Latency): {latency:.2f} saniye")
        print("💰 Maliyet (Cost): $0.00 (Tamamen Ücretsiz!)")
        print("="*50)
        
    except Exception as e:
        print(f"Hata oluştu: {e}")
        print("Lütfen terminalde Ollama'nın açık olduğundan emin olun.")

if __name__ == "__main__":
    test_local_model()
