# 🌾 RAG-Financial-Analysis-Automation-n8n

> **Automated Investment Scoring of FallahTech SARL** using Retrieval-Augmented Generation (RAG) and n8n workflow automation — ENISo · Technologie de Pointe

---

## 📌 Project Overview

This project automates the financial due diligence process for **FallahTech SARL**, a Tunisian AgriTech startup applying for a Series A investment round.

It combines two complementary approaches :

| Part | Technology | Role |
|------|-----------|------|
| **Part A — RAG** | Python · LangChain · ChromaDB · Qwen2.5 | Manual pipeline : ingest documents → retrieve → analyze |
| **Part B — n8n** | n8n · Flask · HuggingFace API | Automated pipeline : trigger → score → HTML report → browser |

The system automatically scores FallahTech across 4 weighted criteria and produces a final investment recommendation :  
✅ **INVEST** · ⚠️ **INVEST WITH CONDITIONS** · ❌ **DO NOT INVEST**

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────┐
│                    n8n Workflow                      │
│  Trigger → Health Check → ChromaDB Check →          │
│  Scoring (4 criteria) → HTML Report → Browser       │
└──────────────────────┬──────────────────────────────┘
                       │ HTTP (localhost:5679)
┌──────────────────────▼──────────────────────────────┐
│              bridge_api.py (Flask)                   │
│  /health  /status  /query  /scoring                 │
└──────────────────────┬──────────────────────────────┘
                       │ Python import
┌──────────────────────▼──────────────────────────────┐
│              RAG Pipeline (Python)                   │
│  query_data.py · ChromaDB · HuggingFace API         │
│  Embeddings: all-mpnet-base-v2                      │
│  LLM: Qwen/Qwen2.5-7B-Instruct                     │
└─────────────────────────────────────────────────────┘
```

---

## 📊 Scoring Grid (Task T3)

| Criterion | Weight | What is evaluated |
|-----------|--------|-------------------|
| 💰 Financial | 40% | Profitability, solvency, liquidity (2023–2025) |
| 📈 Commercial | 30% | Revenue growth, retention rate, subscribers |
| 👥 Team | 15% | Founders, employees, expertise |
| 🌍 Market | 15% | AgriTech market potential, Series A valuation |

---

## 📁 Project Structure

```
RAG-Financial-Analysis-Automation-n8n/
│
├── 📂 data/                          ← Financial documents (PDF + Excel)
│   └── .gitkeep
│
├── 📂 chroma/                        ← ChromaDB vector database (auto-generated)
│   └── .gitkeep
│
├── 📂 outputs/                       ← Generated reports (JSON + HTML)
│   └── .gitkeep
│
├── 📂 bridge/
│   └── bridge_api.py                 ← Flask server (RAG ↔ n8n bridge)
│
├── 📂 workflow/
│   └── fallahtech_scoring_workflow.json  ← n8n workflow (ready to import)
│
├── create_database.py                ← Step 1 : index documents into ChromaDB
├── query_data.py                     ← Step 2 : RAG pipeline (ask questions)
├── requirements.txt                  ← Python dependencies
├── .env.example                      ← Environment variables template
├── .gitignore
└── README.md
```

---

## ⚙️ Tech Stack

**RAG Pipeline**
- 🐍 Python 3.10+
- 🦜 LangChain + LangChain-Community
- 🗄️ ChromaDB (local vector store)
- 🤗 HuggingFace — `Qwen/Qwen2.5-7B-Instruct` (LLM)
- 🔢 `sentence-transformers/all-mpnet-base-v2` (embeddings)
- 📄 PyMuPDF (PDF parsing) · pandas + openpyxl (Excel)

**Automation**
- ⚡ n8n (workflow automation)
- 🌐 Flask (HTTP bridge)
- 🔁 HuggingFace Inference API

---

## 🚀 Quick Start

### 1. Clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/RAG-Financial-Analysis-Automation-n8n.git
cd RAG-Financial-Analysis-Automation-n8n
```

### 2. Create virtual environment

```bash
python -m venv rag_env

# Windows
rag_env\Scripts\activate

# Linux / macOS
source rag_env/bin/activate
```

### 3. Install dependencies

```bash
pip install flask huggingface-hub langchain langchain-community langchain-chroma langchain-huggingface langchain-core langchain-text-splitters chromadb sentence-transformers python-dotenv pymupdf pandas openpyxl transformers torch
```

### 4. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and add your HuggingFace token :
```
HF_TOKEN=hf_your_token_here
```

> Get your token at : https://huggingface.co/settings/tokens  
> Required permissions : **Read** + **Make calls to Inference Providers**

### 5. Add your documents

Place your PDF and Excel files in the `data/` folder.

### 6. Index documents

```bash
python create_database.py
```

### 7. Test RAG manually

```bash
python query_data.py
```

### 8. Start the bridge server

```bash
python bridge/bridge_api.py
```

The server starts on **http://localhost:5679**

### 9. Start n8n (in a separate terminal, venv OFF)

```bash
n8n start
```

Open **http://localhost:5678** → Import `workflow/fallahtech_scoring_workflow.json` → Click **Execute Workflow**

---

## 🌐 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Server health check |
| GET | `/status` | ChromaDB index status |
| POST | `/query` | Single RAG question |
| POST | `/scoring` | Full T3 scoring (4 criteria) |

**Example query :**
```bash
curl -X POST http://localhost:5679/query \
  -H "Content-Type: application/json" \
  -d "{\"question\": \"What is FallahTech's profitability?\"}"
```

**Example response :**
```json
{
  "question": "What is FallahTech's profitability?",
  "response": "Score: 6/10\nJustification: ...",
  "sources": ["Etats_Financiers_NCT.pdf"],
  "score": 6.0,
  "no_context": false
}
```

---

## 📋 n8n Workflow Nodes

```
1. Manual Trigger
2. Health Check          → GET /health
3. ChromaDB Status       → GET /status
4. Ready? (IF node)      → routes to scoring or error
5. Run T3 Scoring        → POST /scoring  (4 criteria × LLM)
6. Build HTML Report     → JavaScript code node
7. Prepare Binary        → encode HTML for file save
8. Send Email (Gmail)    → optional
9. Save HTML locally     → outputs/ folder
10. Final Summary        → logs result
```

---

## 📤 Output Example

After running the workflow, a report opens automatically in your browser :

```
📊 Rapport de Scoring — FallahTech SARL
Généré le 08/04/2026 à 14:41

Score final pondéré :  6.35 / 10
Recommandation       :  ⚠️ INVESTIR SOUS CONDITIONS

Critère      Poids   Score   Pondéré
Financier    40%     6/10    2.40
Commercial   30%     8/10    2.40
Équipe       15%     6/10    0.90
Marché       15%     7/10    1.05
```

---

## 🎓 Academic Context

- **School** : École Nationale d'Ingénieurs de Sousse (ENISo)


---

## ⚠️ Notes

- FallahTech SARL is a **fictional company** created for this academic project. All financial data is invented.
- The `data/` folder is excluded from git (`.gitignore`) — add your own documents locally.
- The `.env` file is excluded from git — never commit your HuggingFace token.

---

## 📄 License

MIT License — free to use for educational purposes.
