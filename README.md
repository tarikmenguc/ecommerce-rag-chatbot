<div align="center">
  
# 🤖 Shopify AI Optimizer

**The $0/month Local AI Engine that writes your e-commerce product descriptions on autopilot.**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=flat&logo=fastapi)](https://fastapi.tiangolo.com)
[![Shopify](https://img.shields.io/badge/Shopify-95BF47?style=flat&logo=shopify&logoColor=white)](https://shopify.com)

[Live Demo](http://localhost:8000) &middot; [API Documentation](http://localhost:8000/docs) &middot; [Report Bug](#)

<br/>

![Hero](docs/assets/screenshot1.png)

</div>

---

## 🎯 What is Shopify AI Optimizer?

Writing compelling product descriptions and managing massive catalogs is a time-consuming bottleneck for e-commerce businesses. 

**Shopify AI Optimizer** is a production-ready, local AI pipeline that connects directly to your Shopify Store, "looks" at your product photos, and generates high-converting, SEO-friendly HTML copy automatically. 

**And the best part? It runs 100% locally. Your data stays with you, and there are absolutely no monthly AI subscription fees.**

<div align="center">
  <img src="docs/assets/screenshot3.png" alt="Dashboard View" width="100%">
</div>

---

## ✨ Features that save you hundreds of hours

<div align="center">
  <img src="docs/assets/screenshot2.png" alt="Features Grid" width="100%">
</div>

- 📸 **Visual Analysis Engine:** Uses Vision LLMs (Llama 3.2 Vision) to look at product images and understand their color, material, style, and target audience automatically.
- 💬 **Live AI Assistant:** Features a built-in context-aware chat assistant that acts as your personal marketing consultant for each specific product.
- 🚀 **Asynchronous & Resilient:** Relies on robust Python background workers that handle heavy AI tasks and Shopify API rate limits invisibly, keeping your UI lightning fast.
- 📊 **Bulk Excel/CSV Import:** Drag-and-drop spreadsheets to create hundreds of new products. The system validates them, enriches them with AI, and pushes them live.
- 🔒 **Absolute Privacy:** Your business data never leaves your server. Competitors cannot scrape your prompts, and you stay fully GDPR compliant.

---

## ⚙️ How it Works in 5 Steps

<div align="center">
  <img src="docs/assets/screenshot4.png" alt="How it works pipeline" width="100%">
</div>

1. **Connect:** Enter your Shopify API token to sync your catalog instantly.
2. **Scan:** The system downloads and analyzes your product images using Multimodal Vision AI.
3. **Generate:** A unique, SEO-optimized, and compelling description is crafted.
4. **Approve:** Review the generated copy from the beautiful glassmorphism dashboard.
5. **Publish:** Push the approved updates back to your live Shopify store with a single click.

---

## 🛠️ Technical Stack & Architecture

This project was built without relying on heavy frameworks like LangChain. It uses direct SDK integration for maximum performance, control, and transparency.

- **Backend / API:** Python, `FastAPI`, `Uvicorn`, `SQLAlchemy` (Async)
- **Database / Vector Store:** `PostgreSQL` (with `pgvector` extension)
- **AI Models & Inference:** Local inference via `Ollama` (Llama 3.2 Vision) and Gemini API integration
- **Frontend UI:** HTML5, Vanilla CSS (Glassmorphism), JavaScript
- **Background Jobs:** Async `asyncio` task queues and `httpx`
- **Infrastructure:** Docker & Docker Compose

---

## 🚀 Getting Started

### 1. Prerequisites
- Docker & Docker Compose
- A Shopify Store (Custom App Access Token)
- [Ollama](https://ollama.com/) installed locally (if utilizing local models)

### 2. Environment Setup
Clone the repository and prepare your environment variables:
```bash
git clone https://github.com/yourusername/shopify-ai-optimizer.git
cd shopify-ai-optimizer
cp .env.example .env
```
*(Make sure to edit `.env` and add your `SHOPIFY_STORE_DOMAIN` and `SHOPIFY_ACCESS_TOKEN`)*

### 3. Launch the Stack
Start the Database, Backend API, and Background Workers automatically:
```bash
docker compose up --build -d
```

### 4. Experience the Magic
Navigate to `http://localhost:8000` in your browser. Watch the system ingest your products, analyze the visuals, and write beautiful marketing copy in real time.

<br/>

<div align="center">
  <i>Designed & Developed for Modern E-Commerce</i>
</div>
