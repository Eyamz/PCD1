# 🇹🇳 TuniSaid — Tunisian Proverb Storyteller

> Discover the wisdom and stories behind Tunisian proverbs powered by AI

**TuniSaid** is a full-stack web application that transforms Tunisian proverbs into beautiful, multi-lingual stories and illustrations. Select a proverb, generate AI-crafted narratives in English, French, or Arabic, listen to native-language audio narration, and explore AI-generated visual scenes.

---

## ✨ Features

- **🔍 Browse 999+ Proverbs** - Explore authentic Tunisian sayings with cultural context
- **🎯 Smart Search & Filter** - Find proverbs by keywords and themes
- **🤖 AI Story Generation** - Groq Llama 3.3 70B generates deep cultural insights
- **🧠 Vocabulary-Enriched RAG** - Arabic vocabulary reference integrated into AI context for accurate interpretations
- **🎨 Visual Illustrations** - Hugging Face Inference API creates stunning images (with 3-token rotation for reliability)
- **🌍 Multi-Language Support** - English, French, and Arabic explanations
- **🎙️ Audio Narration** - gTTS for Arabic, ElevenLabs for English/French
- **⚡ Fast & Responsive** - FastAPI with async processing, real-time generation
- **💾 Persistent Storage** - SQLite database + FAISS vector embeddings for RAG

---

## 🛠️ Tech Stack

### Backend
- **Framework**: FastAPI (Python async web framework)
- **LLM**: Groq API + Llama 3.3 70B (free tier, no rate limits)
- **RAG**: FAISS for semantic search + Arabic vocabulary reference CSV for context enrichment
- **Image Generation**: Hugging Face Inference API (Stable Diffusion XL) with 3-token rotation for rate limit management
- **Audio**: gTTS (Google TTS for Arabic), ElevenLabs (English/French)
- **Database**: SQLite + FAISS embeddings

### Frontend
- **HTML5** - Semantic markup
- **CSS3** - Modern responsive design with flexbox
- **Vanilla JavaScript** - No frameworks, lightweight & fast
- **API Communication** - Fetch API with async/await

### Infrastructure
- **Server**: Uvicorn (ASGI server)
- **Environment**: Python 3.10+, Virtual environment
- **API Keys**: Groq, Hugging Face, ElevenLabs (configured via `.env`)

---

## 📋 Prerequisites

- **Python 3.10+** installed
- **Virtual environment** (included in repo as `.venv/`)
- **API Keys** (optional but recommended):
  - `GROQ_API_KEY` - For AI explanations (get free key at [console.groq.com](https://console.groq.com))
  - `HF_API_TOKEN` - For image generation (get free token at [huggingface.co](https://huggingface.co))
  - `ELEVENLABS_API_KEY` - For English/French audio (optional, gTTS works for Arabic)
- **5GB disk space** - For FAISS embeddings and ChromaDB

---

## 🚀 Installation & Setup

### Step 1: Clone the Repository

```bash
cd "path/to/your/projects"
git clone <repository-url>
cd pcd
```

### Step 2: Activate Python Virtual Environment

**Windows (PowerShell):**
```powershell
.\.venv\Scripts\Activate.ps1
```

**Windows (Command Prompt):**
```cmd
.venv\Scripts\activate.bat
```

**macOS/Linux:**
```bash
source .venv/bin/activate
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 4: Configure Environment Variables

Create a `.env` file in the project root:

```env
# Groq API (free, get key at console.groq.com)
# This is REQUIRED for proverb interpretation
GROQ_API_KEY=gsk_your_key_here

# Hugging Face - Token Rotation for Image Generation
# Use ANY ONE of these tokens (app rotates through them to manage rate limits)
# If all tokens hit rate limits, wait 1 hour for reset
HF_API_TOKEN=hf_your_token_here

# ElevenLabs (optional, for English/French audio)
ELEVENLABS_API_KEY=sk_your_key_here

# Application settings
DEBUG=false
LOG_LEVEL=INFO
```

> **Note**: 
> - `GROQ_API_KEY` is **required** for AI interpretation
> - `HF_API_TOKEN` is optional; without it, image generation will be skipped
> - If you provide multiple HF tokens to the app, they'll rotate automatically to avoid rate limits

### Step 5: Start the Server

```bash
python run.py
```

Or manually with uvicorn:
```bash
uvicorn app:app --host 0.0.0.0 --port 8888 --reload
```

### Step 6: Open in Browser

Visit: **http://localhost:8888**

---

## 📱 How to Use

### Explore Mode
1. Click **"Explore a Proverb"**
2. Browse the list or search by keyword (e.g., "القلب", "dara", "heart")
3. Click a proverb to see preview
4. Click **"Generate Story"**

### Custom Mode
1. Click **"Enter a Proverb"**
2. Write any Tunisian proverb (Arabic, Darja, or French)
3. Click **"Generate Story"**
4. Wait for AI generation (10-30 seconds)

### View Results
- **Language Tabs**: Switch between English, French, العربية
- **Generate Image**: Create a visual scene for the proverb
- **Generate Narration**: Listen to native-language audio
- **Change Language**: Switch UI language, audio narration follows

---

## 📁 Folder & File Structure

```
pcd/
├── app.py                          # FastAPI backend (routes, API endpoints)
├── database.py                     # SQLite database management
├── proverb_pipeline_lite.py       # Image generation pipeline
├── rag_groq_pipeline.py           # RAG system (Groq + FAISS + Chroma)
├── run.py                         # Server startup script
├── requirements.txt               # Python dependencies
├── config.json                    # App configuration (models, paths)
├── .env                           # Environment variables (API keys)
│
├── website/                       # Frontend files
│   ├── index.html                # Main web page
│   ├── style.css                 # Styling (flexbox layout, responsive)
│   ├── script.js                 # JavaScript (UI logic, API calls)
│   ├── favicon.ico               # Browser tab icon
│   ├── proverbs.json             # 999 Tunisian proverbs dataset
│   └── generated/                # Generated images & audio files
│       ├── image_*.png           # AI-generated proverb illustrations
│       └── narration_*.mp3       # Audio narrations
│
├── data/                         # Data & embeddings
│   ├── proverbs.db              # SQLite database (metadata, themes)
│   ├── arabic_vocabulary_reference.csv  # Arabic vocabulary for RAG context
│   ├── chromadb/                # Chroma vector store (embeddings)
│   └── faiss_vectorstore_proverbs/
│       └── index.faiss          # FAISS semantic search index
│
├── logs/                        # Application logs
├── ARCHITECTURE.md              # System design documentation
├── GROQ_INTEGRATION_SUMMARY.md # Groq API integration notes
└── README.md                    # This file
```

### Key Directories Explained

| Directory | Purpose |
|-----------|---------|
| `website/` | Frontend HTML/CSS/JS + generated assets |
| `website/generated/` | AI-generated images and audio files (created on-demand) |
| `data/` | SQLite DB, FAISS embeddings, ChromaDB vectors, vocabulary CSV |
| `logs/` | Application runtime logs for debugging |

---

## 🔧 Project Architecture

### Backend Flow
```
User Request (Proverb)
    ↓
FastAPI Route Handler
    ↓
Groq RAG Pipeline
    ├─ Search FAISS for similar proverbs (top-4)
    ├─ Load Arabic vocabulary reference from CSV
    ├─ Extract relevant vocabulary terms from proverb
    ├─ Build enriched RAG prompt with context
    └─ Call Groq Llama 3.3 70B API
       └─ Generate English/French/Arabic explanations
    ↓
Image Generation (Optional)
    ├─ Rotate through HF API tokens (3-token pool)
    ├─ Extract visual prompt from Groq response
    ├─ Call Hugging Face Inference API (SDXL)
    └─ Save generated PNG to website/generated/
    ↓
Audio Narration (Optional)
    ├─ Arabic → gTTS (Free Google TTS)
    ├─ English/French → ElevenLabs API
    └─ Save MP3 to website/generated/
    ↓
JSON Response → Frontend
```

### Frontend Flow
```
User Interacts with UI
    ↓
JavaScript Detects Language Selection
    ↓
Fetch API → /api/explain (POST)
    ↓
Display Story + Image + Audio Player
    ↓
On Language Change:
    ├─ Show relevant translation
    ├─ Reset audio player
    └─ Ready for new narration
```

### RAG System (Retrieval-Augmented Generation)

The app uses a sophisticated RAG pipeline to ground AI interpretations in cultural knowledge:

1. **Semantic Retrieval (FAISS)**
   - User input proverb is embedded using `sentence-transformers/all-MiniLM-L6-v2`
   - Top-4 similar proverbs are retrieved from FAISS index
   - Provides cultural context and related themes

2. **Vocabulary Enrichment (CSV)**
   - Arabic vocabulary reference (`arabic_vocabulary_reference.csv`) is loaded on startup
   - Words in the input proverb are automatically matched to vocabulary entries
   - Adds Tunisian dialect variants, English translations, and category info to RAG context

3. **Prompt Building**
   - Retrieved proverbs + vocabulary context + cultural themes assembled into enriched prompt
   - Prompt sent to Groq Llama 3.3 70B with full cultural knowledge

4. **Image Generation with Token Rotation**
   - 3 Hugging Face API tokens rotate to avoid rate limits
   - Each image request uses a different token (round-robin)
   - Handles 30+ images before hitting rate limits (1 image per token = 3x capacity)

---

## 🔑 API Endpoints

| Endpoint | Method | Purpose | Response |
|----------|--------|---------|----------|
| `/` | GET | Serve frontend (index.html) | HTML page |
| `/api/health` | GET | Check server status | `{"status": "healthy"}` |
| `/api/proverbs` | GET | Get all proverbs with filters | List of proverbs |
| `/api/explain` | POST | Generate AI explanation | Story + image prompt in 3 languages |
| `/api/generate-image` | POST | Create visual scene | Image file path + URL |
| `/api/narrate` | POST | Generate audio narration | MP3 file path + audio URL |
| `/generated/*` | GET | Serve generated assets | Images & audio files |

---

## 🌍 Environment Variables

```env
# REQUIRED - Groq API (free tier, no rate limits)
GROQ_API_KEY=gsk_your_groq_key_here

# RECOMMENDED - Hugging Face (for image generation)
# Token rotation: App rotates through multiple tokens to manage rate limits
HF_API_TOKEN=hf_your_huggingface_token_here

# OPTIONAL - ElevenLabs (Arabic uses free gTTS by default)
ELEVENLABS_API_KEY=sk_your_elevenlabs_key_here

# APPLICATION CONFIG
DEBUG=false                  # Show detailed error messages
LOG_LEVEL=INFO             # Log level: DEBUG, INFO, WARNING, ERROR
```

**Getting API Keys:**
- **Groq**: Visit [console.groq.com](https://console.groq.com) → Sign up → Copy API key
- **Hugging Face**: Visit [huggingface.co](https://huggingface.co) → Sign up → Settings → Access Tokens
  - **Important**: Accept the Stable Diffusion XL model license to use image generation
  - **Token Rotation**: If you have multiple HF accounts, provide all tokens for better rate limit handling
- **ElevenLabs**: Visit [elevenlabs.io](https://elevenlabs.io) → Sign up → API Keys

---

## ⚡ Performance Notes

- **First Generation**: 10-30 seconds (models load, embeddings search)
- **Subsequent Requests**: 5-15 seconds (RAG context retrieval + Groq API)
- **Image Generation**: 8-20 seconds (Hugging Face inference)
- **Audio Generation**: 2-5 seconds (gTTS/ElevenLabs API)
- **Database Queries**: <100ms (SQLite + FAISS optimized)

---

## 🐛 Troubleshooting

### Server Won't Start
```
Error: Port 8888 already in use
Solution: Kill existing process or use different port:
  uvicorn app:app --port 8889
```

### Image Generation Fails (402 Payment Required)
```
Error: "402 Payment Required" from Hugging Face
Causes:
  1. Token has no access to Stable Diffusion XL model
  2. All tokens have hit rate limits
Solutions:
  1. Accept Stable Diffusion XL license: https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0
  2. Wait ~1 hour for rate limit reset
  3. Provide additional HF tokens for rotation
  4. Generate images without token (skip image generation)
```

### Audio Narration Not Working (Arabic)
```
Problem: gTTS not installed
Solution: pip install gtts
OR: Use ElevenLabs instead (add ELEVENLABS_API_KEY to .env)
```

### Vocabulary Not Being Used in RAG
```
Solution: Restart the server
The vocabulary CSV (arabic_vocabulary_reference.csv) is loaded on startup
```

---

## 📚 Additional Resources

- **ARCHITECTURE.md** - Detailed system design and tech decisions
- **GROQ_INTEGRATION_SUMMARY.md** - How Groq API is integrated
- **config.json** - Full application configuration
- **.env.example** - Template for environment variables (create as .env)

---

## 📝 License

This project is private and for educational/demonstration purposes.

---

## 👤 Author

Created as a comprehensive AI-powered language & culture learning tool.

---

**Last Updated**: April 2026
**Status**: Production Ready ✅

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
