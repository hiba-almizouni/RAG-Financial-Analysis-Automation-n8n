"""
bridge_api.py — Pont entre ton projet RAG existant et n8n
==========================================================
Ce script démarre un serveur HTTP local (Flask) que n8n appelle
via des nœuds "HTTP Request".

COMMENT LANCER :
  cd ton_projet_rag/          ← racine de ton projet RAG existant
  python bridge/bridge_api.py

Le serveur écoute sur : http://localhost:5678

ENDPOINTS exposés à n8n :
  GET  /health              → vérifie que le serveur tourne
  GET  /status              → état de ChromaDB (nb chunks indexés)
  POST /query               → RAG : question → réponse + sources + score
  POST /scoring             → scoring T3 complet (4 critères pondérés)
  POST /ingest              → re-indexation du dossier data/ (optionnel)
"""

import sys
import os
import json
import re
from pathlib import Path
from datetime import datetime

# ── Ajouter le dossier src/ du projet RAG au path ─────────────────
# Ce fichier doit être dans : ton_projet_rag/bridge/bridge_api.py
# Donc le dossier src/ est à ../src/ depuis ici
RAG_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR  = RAG_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

from flask import Flask, request, jsonify
import chromadb
from chromadb.utils import embedding_functions

# Importer depuis ton projet RAG existant
from config import (
    CHROMA_DIR, COLLECTION_NAME, EMBEDDING_MODEL,
    TOP_K_RETRIEVAL, OUTPUT_DIR, SCORING_CRITERIA,
    get_recommendation, validate_config, HF_TOKEN
)

app = Flask(__name__)

# ── Singleton : pipeline RAG chargé une seule fois ────────────────
_rag_pipeline = None

def get_rag():
    """Charge le pipeline RAG une seule fois (lazy loading)."""
    global _rag_pipeline
    if _rag_pipeline is None:
        from rag_pipeline import RAGPipeline
        _rag_pipeline = RAGPipeline()
        _rag_pipeline.load_retriever()
        _rag_pipeline.load_llm()
    return _rag_pipeline


# ══════════════════════════════════════════════════════════════════
# ENDPOINT 1 — Health check
# ══════════════════════════════════════════════════════════════════

@app.route("/health", methods=["GET"])
def health():
    """
    n8n l'appelle pour vérifier que le serveur est actif.
    Utilisé dans le nœud de démarrage du workflow.
    """
    return jsonify({
        "status":    "ok",
        "timestamp": datetime.now().isoformat(),
        "rag_root":  str(RAG_ROOT),
        "chroma_dir": str(CHROMA_DIR),
    })


# ══════════════════════════════════════════════════════════════════
# ENDPOINT 2 — Statut ChromaDB
# ══════════════════════════════════════════════════════════════════

@app.route("/status", methods=["GET"])
def status():
    """
    Vérifie que ChromaDB est bien indexé.
    n8n l'utilise avant de lancer le scoring pour s'assurer
    que les données sont disponibles.
    """
    try:
        emb_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=EMBEDDING_MODEL
        )
        client = chromadb.PersistentClient(path=str(CHROMA_DIR))
        col    = client.get_collection(COLLECTION_NAME, embedding_function=emb_fn)
        count  = col.count()
        return jsonify({
            "status":          "ready",
            "collection":      COLLECTION_NAME,
            "chunks_indexed":  count,
            "chroma_dir":      str(CHROMA_DIR),
            "embedding_model": EMBEDDING_MODEL,
        })
    except Exception as e:
        return jsonify({
            "status":  "not_ready",
            "error":   str(e),
            "hint":    "Lance d'abord : python src/ingest.py",
        }), 503


# ══════════════════════════════════════════════════════════════════
# ENDPOINT 3 — Requête RAG simple
# ══════════════════════════════════════════════════════════════════

@app.route("/query", methods=["POST"])
def query():
    """
    Répond à une question via le pipeline RAG existant.

    Body JSON attendu depuis n8n :
    {
      "question": "Quelle est la rentabilité de FallahTech ?"
    }

    Retourne :
    {
      "question":   "...",
      "response":   "Score: 6/10\nJustification: ...",
      "sources":    ["fichier1.pdf", "fichier2.xlsx"],
      "score":      6.0,
      "no_context": false
    }
    """
    body = request.get_json(silent=True) or {}
    question = body.get("question", "").strip()

    if not question:
        return jsonify({"error": "Champ 'question' manquant dans le body"}), 400

    try:
        rag    = get_rag()
        result = rag.ask(question, verbose=False)
        return jsonify({
            "question":   result["question"],
            "response":   result["response"],
            "sources":    result["sources"],
            "score":      result["score"],
            "no_context": result["no_context"],
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ══════════════════════════════════════════════════════════════════
# ENDPOINT 4 — Scoring T3 complet
# ══════════════════════════════════════════════════════════════════

@app.route("/scoring", methods=["POST"])
def scoring():
    """
    Lance le scoring T3 complet (4 critères pondérés).
    n8n appelle cet endpoint UNE SEULE FOIS et récupère
    le rapport complet avec score pondéré + recommandation.

    Body JSON (optionnel) :
    {
      "criteria_ids": ["financier", "commercial"]   ← sous-ensemble optionnel
    }

    Retourne :
    {
      "score_total":    6.35,
      "recommandation": "INVESTIR SOUS CONDITIONS",
      "criteres": [ { "id", "label", "score", "poids", "reponse", "sources" }, ... ],
      "timestamp": "..."
    }
    """
    body         = request.get_json(silent=True) or {}
    filter_ids   = body.get("criteria_ids", None)  # None = tous les critères

    criteria = SCORING_CRITERIA
    if filter_ids:
        criteria = [c for c in criteria if c["id"] in filter_ids]

    try:
        rag         = get_rag()
        results     = []
        score_total = 0.0

        for crit in criteria:
            result = rag.ask(crit["question"], verbose=False)
            score  = result["score"] or 0.0
            results.append({
                "id":             crit["id"],
                "label":          crit["label"],
                "poids":          crit["weight"],
                "poids_pct":      f"{int(crit['weight'] * 100)}%",
                "score":          score,
                "score_pondere":  round(score * crit["weight"], 3),
                "reponse":        result["response"],
                "sources":        result["sources"],
                "no_context":     result["no_context"],
            })
            score_total += score * crit["weight"]

        score_total   = round(score_total, 2)
        recommandation = get_recommendation(score_total)

        # Sauvegarder aussi en local (même que scoring.py)
        ts          = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = OUTPUT_DIR / f"rapport_n8n_{ts}.json"
        report_data = {
            "source":         "n8n",
            "score_total":    score_total,
            "recommandation": recommandation,
            "criteres":       results,
            "timestamp":      datetime.now().isoformat(),
        }
        report_path.write_text(
            json.dumps(report_data, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

        return jsonify(report_data)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ══════════════════════════════════════════════════════════════════
# ENDPOINT 5 — Re-indexation (optionnel)
# ══════════════════════════════════════════════════════════════════

@app.route("/ingest", methods=["POST"])
def ingest():
    """
    Re-lance l'ingestion des documents (ingest.py).
    Utile si tu as ajouté de nouveaux documents dans data/.
    n8n peut l'appeler en début de workflow pour garder l'index à jour.
    """
    try:
        import subprocess
        ingest_script = SRC_DIR / "ingest.py"
        result = subprocess.run(
            [sys.executable, str(ingest_script)],
            capture_output=True, text=True, timeout=600
        )
        return jsonify({
            "status":      "done" if result.returncode == 0 else "error",
            "returncode":  result.returncode,
            "stdout":      result.stdout[-2000:],   # derniers 2000 chars
            "stderr":      result.stderr[-500:],
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ══════════════════════════════════════════════════════════════════
# LANCEMENT
# ══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("\n" + "═" * 54)
    print("  FALLAHTECH — BRIDGE API (RAG ↔ n8n)")
    print("═" * 54)
    print(f"  RAG root  : {RAG_ROOT}")
    print(f"  ChromaDB  : {CHROMA_DIR}")
    print(f"  Port      : 5678")
    print()
    print("  Endpoints disponibles :")
    print("    GET  http://localhost:5678/health")
    print("    GET  http://localhost:5678/status")
    print("    POST http://localhost:5678/query")
    print("    POST http://localhost:5678/scoring")
    print("    POST http://localhost:5678/ingest")
    print("═" * 54 + "\n")

    validate_config()

    # Précharger le pipeline au démarrage (évite la latence au 1er appel n8n)
    print("Préchargement du pipeline RAG...", flush=True)
    get_rag()
    print("✓ Prêt ! n8n peut maintenant appeler les endpoints.\n")

    app.run(host="0.0.0.0", port=5678, debug=False)
