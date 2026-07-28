---
license: apache-2.0
base_model: unsloth/llama-3-8b-Instruct-bnb-4bit
tags:
- unsloth
- llama-3
- e-commerce
- copywriting
- lora
- peft
language:
- tr
- en
---

# Llama-3 8B E-Commerce Copywriter (LoRA Adapter)

This is a fine-tuned LoRA adapter for the `llama-3-8b-Instruct` model, specifically trained to generate highly engaging, SEO-friendly, and marketing-optimized product descriptions for e-commerce platforms.

## Model Details
- **Base Model**: `unsloth/llama-3-8b-Instruct-bnb-4bit`
- **Training Data**: 2,207 synthetic e-commerce product entries (Titles and Features) generated and curated for high-quality marketing copy.
- **Language**: Turkish (Primary), English
- **Task**: Text Generation / Copywriting
- **Format**: Safetensors / GGUF (Available for Ollama)

## Intended Use
This model is designed to assist e-commerce sellers, marketers, and developers in automating the creation of product descriptions. It takes a short product title and a list of features as input, and outputs a structured, persuasive product description.

## Prompt Format
The model uses the standard Llama-3 Chat template.

## Training Configuration
- **Method**: QLoRA (via Unsloth)
- **Rank (r)**: 16
- **Alpha**: 32
- **Target Modules**: `q_proj`, `k_proj`, `v_proj`, `o_proj`, `gate_proj`, `up_proj`, `down_proj`
- **Batch Size**: 8
- **Learning Rate**: 2e-4
- **Optimizer**: `adamw_8bit`
- **Epochs**: 1

## Example Output
**Input:**
```text
Title: Neutrogena Hydro Boost Water Gel, 1.7 oz
Features:
- Oil-free face moisturizer with hyaluronic acid
- Instantly quenches dry skin
- Non-comedogenic, dye-free
- For extra-dry skin
```

**Output:**
```text
**Replenish Your Skin's Thirst in an Instant**

Say goodbye to parched skin with Neutrogena Hydro Boost Water Gel. This lightweight, oil-free moisturizer is infused with powerful hyaluronic acid that instantly quenches dryness, leaving your complexion feeling refreshed and revitalized...
```