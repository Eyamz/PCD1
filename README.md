# 🇹🇳 Tunisian Proverbs - AI-Powered Web Application

A complete web application combining proverb discovery with AI-powered semantic analysis and image generation. Built with FastAPI, Phi-2 LLM, and Stable Diffusion XL, optimized for RTX 2050 (4GB VRAM).

## ✨ Features

- **Browse 999 Proverbs** - Explore authentic Tunisian proverbs with cultural context
- **Search & Filter** - Find proverbs by keywords and themes
- **AI Interpretation** - Phi-2 LLM generates semantic meaning and cultural insights
- **Image Generation** - SDXL creates visual representations of proverb scenes
- **Persistent Storage** - SQLite + ChromaDB for metadata and semantic embeddings
- **Fast & Responsive** - FastAPI backend with async generation, instant search

## 🚀 Quick Start

### 1. Install & Activate Python Environment

```powershell
cd "C:\Users\eyamz\OneDrive - ensi-uma.tn\Desktop\pcd"
.\.venv\Scripts\Activate.ps1
```

### 2. Start the Server

```bash
python run.py
```

### 3. Open Browser

Visit **http://localhost:8000**

## 📱 How to Use

- **Explore:** Browse 999 proverbs by theme or search keyword
- **Generate:** Click to generate AI interpretation + SDXL image
- **Custom:** Enter your own proverb for private analysis

*First generation takes 30-60 seconds (models download ~7GB). Subsequent generations are ~10-15 seconds.*

## 🛠️ Tech Stack

| Component | Tech |
|-----------|------|
| Backend | FastAPI |
| LLM | Phi-2 (2.7B) |
| Images | SDXL 1.0 |
| Database | SQLite + ChromaDB |
| Frontend | HTML/CSS/JS |

## 📁 Key Files

- `app.py` - REST API server
- `proverb_pipeline_lite.py` - AI pipeline
- `database.py` - Data layer
- `website/` - Frontend
- `config.json` - Settings
- `ARCHITECTURE.md` - Design notes

## ⚙️ Configuration

Edit `config.json`:
```json
{
  "system": {"device": "cuda", "enable_image_generation": true},
  "generation": {"image_steps": 25, "use_fp16": true}
}
```

## 🖥️ Requirements

- GPU: NVIDIA RTX 2050+ (4GB VRAM minimum)
- RAM: 16GB+
- Storage: 30GB free
- Python: 3.10+

## 📚 Learn More

See `ARCHITECTURE.md` for design evolution and key decisions.

---

**Built with ❤️ for Tunisian cultural heritage**
