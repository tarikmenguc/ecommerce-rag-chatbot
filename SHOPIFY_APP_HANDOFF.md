# Shopify App Migration Handoff Document

## 1. Projenin Amacı ve Hedefi
Bu doküman, tek oyunculu (single-tenant) ve özel bir iç araç olarak geliştirilen "Shopify AI Optimizer" projesinin, **herkese açık, ticari bir Shopify App Store Eklentisine (SaaS)** dönüştürülmesi için yeni yapay zeka oturumuna rehberlik etmesi amacıyla hazırlanmıştır. 

**Yeni Projenin Hedefi:** 
Satıcıların Shopify App Store'dan indirebileceği, aylık abonelikle çalışacak, yapay zeka destekli bir "Katalog Optimize Edici ve Excel İçe Aktarıcı" eklentisi geliştirmek. 

## 2. Eski Projeden (Buradan) Kopyalanacak ve Uyarlanacak Çekirdek Özellikler
Eski projenin "Beyni" çok iyi çalışmaktadır. Yeni projede sıfırdan yazılmayıp, eski projeden alınıp yeni mimariye entegre edilecek dosyalar ve mantıklar şunlardır:

1.  **AI Promtları ve Metin Yazarlığı (LLM):** `app/llm.py` içindeki tüm prompt yapıları, SEO odaklı metin üretme fonksiyonları.
2.  **Vision AI Entegrasyonu:** `app/vision.py` içindeki ürün fotoğraflarını okuyup anlama yeteneği.
3.  **Excel/CSV İçe Aktarma Mantığı:** `app/routers/excel_import.py` içindeki dosya ayrıştırma (pandas), sütun doğrulama (price, title vs.) ve hataları ayıklama algoritması.
4.  **Arka Plan İşçisi (Worker):** `app/shopify_worker.py` içindeki işleyiş. Ancak bu işçi artık sadece 1 mağaza için değil, veritabanındaki `store_id` (Mağaza ID) değerine göre tüm mağazaların sıraya giren işlerini eritecek şekilde (Multi-tenant) güncellenmelidir.
5.  **AI Chat Asistanı:** Frontend'deki `[CONTEXT: ...]` gömme mantığı ve `app/agent.py` içindeki bağlama duyarlı sohbet asistanı altyapısı.

## 3. Yeni Projede Sıfırdan Kurulması Gerekenler (Shopify Eklenti Mimarisi)
Yeni projeye başlarken doğrudan eski kodu kopyalamak YERİNE, resmi bir **Shopify App Template** (Node.js/React veya Python/FastAPI tabanlı) ile başlanmalıdır. Bu şablon üzerine aşağıdaki yapılar inşa edilmelidir:

1.  **OAuth 2.0 ve Kimlik Doğrulama:** 
    *   Satıcılar uygulamayı yüklediğinde Shopify'ın vereceği `access_token`'ları her mağaza için ayrı ayrı veritabanına kaydetmek.
    *   Uygulamanın Shopify Admin paneline gömülü (Embedded App - Polaris UI) veya Standalone olarak güvenle açılmasını sağlamak (Session Token verification).
2.  **Multi-Tenant Veritabanı Mimarisi:**
    *   Tüm veritabanı tablolarına (örneğin `shopify_job`) mutlaka `shop_domain` veya `shop_id` sütunu eklenmelidir. Hiçbir mağaza diğerinin verisini görmemelidir.
3.  **Billing API (Abonelik/Ödeme):**
    *   Satıcılardan aylık ücret veya "kredi" bazlı ücret alabilmek için Shopify Billing API entegrasyonu.
4.  **Webhooks:**
    *   Örneğin `app/uninstalled` webhook'u dinlenerek, eklentiyi silen mağazanın veritabanımızdaki access_token'ı ve kişisel verileri temizlenmelidir.

## 4. Kesinlikle Çöpe Atılacak / Taşınmayacak Kısımlar
Aşağıdaki yapılar eski projede yerel kullanım için yapılmış olup yeni Shopify App mimarisinde yeri yoktur:
*   `n8n` otomasyon aracı ve ona ait tüm docker/ayar dosyaları.
*   `app/routers/mock_shopify.py` (Sahte Shopify sunucusu mantığı).
*   Tek kullanıcılı `.env` (SHOPIFY_ACCESS_TOKEN gibi değerler artık `.env`'de değil, her mağaza için veritabanında dinamik olarak tutulacaktır).

## 5. Yeni Oturumdaki Yapay Zekaya (Sana) İlk Görev
Lütfen bu dokümanı anladığını onayla ve bana **"Shopify App Store için Python tabanlı (FastAPI + React) resmi uygulama şablonunu nasıl kuracağımı"** adım adım göstererek projenin temel iskeletini oluşturmaya başlayalım.
