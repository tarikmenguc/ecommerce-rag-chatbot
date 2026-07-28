# 🚀 E-Commerce AI Copywriter (End-to-End LLM Fine-Tuning & Deployment)

Welcome to the **E-Commerce AI Copywriter** project! This repository showcases a complete, end-to-end AI engineering pipeline—from generating a synthetic dataset and fine-tuning an open-source LLM, to serving it via a FastAPI backend with a premium Glassmorphism UI.

## 🎯 What is this project?
Writing compelling, SEO-friendly, and highly converting product descriptions is a time-consuming and expensive process for e-commerce businesses. While APIs like GPT-4 or Gemini can do this, they incur recurring costs and rate limits at scale. 

**This project solves that problem by:**
1. Fine-tuning a local, open-source model (**Llama-3 8B**) to become an expert e-commerce copywriter.
2. Generating high-quality descriptions from just a short product title and a few bullet-point features.
3. Operating at **$0 recurring cost** with absolute data privacy.

## ✨ Key Features & Architecture
- **Synthetic Data Generation:** Used Google Gemini to generate a dataset of 2,207 high-quality e-commerce examples (Titles, Features, and target Descriptions).
- **QLoRA Fine-Tuning:** Fine-tuned `llama-3-8b-Instruct` using the `Unsloth` library to massively reduce VRAM usage (fits on a free Kaggle/Colab T4 GPU).
- **FastAPI Backend:** A lightweight, async REST API to serve the model to front-end applications.
- **Ollama Integration:** The fine-tuned weights are converted to GGUF and served locally via Ollama for seamless inference.
- **Premium UI:** A vanilla HTML/CSS/JS frontend featuring a modern dark/light-gray theme, glassmorphism effects, and skeleton loaders to provide a premium user experience.
- **A/B Testing Framework:** Includes automated scripts to test the fine-tuned local model against commercial APIs (Gemini 3.5 Flash) to measure Latency, Cost, and Quality.

## 📈 Why Local Fine-Tuning? (The ROI)
In our A/B test on 100 products:
- **Commercial API (Gemini):** Fast (~8.8s) but subject to strict rate limits (15 RPM on free tier) and recurring API costs for massive catalogs.
- **Our Fine-Tuned Llama-3:** Completely **Free**, no rate limits, and zero data-privacy concerns. The text output is perfectly structured for Amazon/Shopify with engaging hooks and bullet points.

## 🛠️ Tech Stack
- **AI & Training:** Hugging Face `transformers`, `peft`, `unsloth`, `trl`, `ollama`
- **Backend:** Python, `FastAPI`, `Uvicorn`, `Pydantic`
- **Frontend:** HTML5, Vanilla CSS (Glassmorphism design), JavaScript
- **Deployment:** Docker (for API & Database), Hugging Face Hub

## 🚀 How to Run Locally

### 1. Prerequisites
- Python 3.10+
- [Ollama](https://ollama.com/) installed locally.

### 2. Setup the Model
You can pull the fine-tuned model directly from Hugging Face or build it in Ollama:
```bash
# Pull the base model
ollama run llama3

# Or if you have the Modelfile from this repo
ollama create e-commerce -f Modelfile
```

### 3. Start the API
```bash
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 4. Open the UI
Simply open `http://localhost:8000` in your browser. Enter a product title, list its features, and watch the AI write a high-converting description in seconds!

## 🔮 Future Roadmap (Phase 2)
- **Batch Processing:** Ability to upload an Excel/CSV file of 1,000+ products and generate descriptions in bulk.
- **n8n / Make.com Integrations:** Automated workflows that pull new products from Trendyol/Shopify, write the descriptions via our API, and push them back to the marketplace automatically.
