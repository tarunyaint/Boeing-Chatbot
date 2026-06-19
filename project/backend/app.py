"""
app.py
Flask backend for the Boeing 737-800 AMM Chatbot.

Supported free AI providers (set AI_PROVIDER in .env):
  gemini      — Google Gemini 1.5 Flash  (free, 1500 req/day)
                Get key: https://aistudio.google.com/apikey
  groq        — Groq LLaMA 3.1           (free, fast)
                Get key: https://console.groq.com
  openrouter  — OpenRouter free models   (free tier)
                Get key: https://openrouter.ai

API Routes:
  GET    /api/health
  GET    /api/chapters
  POST   /api/chat
  POST   /api/sessions
  GET    /api/sessions
  GET    /api/sessions/<id>
  DELETE /api/sessions/<id>
"""

import os
import requests
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv

from db import get_db
from retrieval import retrieve, build_context

load_dotenv()

# ── App setup ─────────────────────────────────────────────────
app = Flask(__name__, static_folder="../frontend", static_url_path="")
CORS(app)

db          = get_db()
AI_PROVIDER = os.getenv("AI_PROVIDER", "gemini").lower()
MAX_HISTORY = 10   # conversation pairs kept in context

# ── System prompt ─────────────────────────────────────────────
SYSTEM_PROMPT = """You are a technical assistant for the Boeing 737-800 Aircraft Maintenance Manual (AMM), document SYN-AMM-737-800-001 Revision 12.

You are given CONTEXT excerpts retrieved from the manual plus conversation history. Use them to answer accurately.

Rules:
- Answer using ONLY the provided CONTEXT. Always cite the chapter or section.
- If the context doesn't contain the answer, say so clearly and suggest which chapter to check.
- Format procedures as numbered steps.
- Highlight WARNINGs and CAUTIONs when present in context.
- Be concise and technically precise.
- For safety-critical answers always add: "⚠️ SYNTHETIC TRAINING DOCUMENT — not for use on actual aircraft."

Use plain text with light Markdown (bold, numbered lists, bullets). No headers."""


# ══════════════════════════════════════════════════════════════
#  AI Provider Functions
# ══════════════════════════════════════════════════════════════

def call_gemini(messages, system):
    """Google Gemini 1.5 Flash — free 1,500 req/day."""
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key or api_key == "YOUR_GEMINI_KEY_HERE":
        raise ValueError("GEMINI_API_KEY not set in backend/.env")

    url = (
        "https://generativelanguage.googleapis.com/v1beta"
        f"/models/gemini-1.5-flash:generateContent?key={api_key}"
    )

    # Convert to Gemini format (roles: user / model)
    contents = []
    for m in messages:
        role = "model" if m["role"] == "assistant" else "user"
        contents.append({"role": role, "parts": [{"text": m["content"]}]})

    payload = {
        "system_instruction": {"parts": [{"text": system}]},
        "contents": contents,
        "generationConfig": {"maxOutputTokens": 1024, "temperature": 0.3},
    }
    resp = requests.post(url, json=payload, timeout=30)
    resp.raise_for_status()
    return resp.json()["candidates"][0]["content"]["parts"][0]["text"]


def call_groq(messages, system):
    """Groq — free LLaMA 3.1 inference."""
    api_key = os.getenv("GROQ_API_KEY", "")
    if not api_key or api_key == "YOUR_GROQ_KEY_HERE":
        raise ValueError("GROQ_API_KEY not set in backend/.env")

    model = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
    payload = {
        "model": model,
        "messages": [{"role": "system", "content": system}] + messages,
        "max_tokens": 1024,
        "temperature": 0.3,
    }
    resp = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        json=payload,
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def call_openrouter(messages, system):
    """OpenRouter — aggregator with free model tiers."""
    api_key = os.getenv("OPENROUTER_API_KEY", "")
    if not api_key or api_key == "YOUR_OPENROUTER_KEY_HERE":
        raise ValueError("OPENROUTER_API_KEY not set in backend/.env")

    model = os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.1-8b-instruct:free")
    payload = {
        "model": model,
        "messages": [{"role": "system", "content": system}] + messages,
        "max_tokens": 1024,
        "temperature": 0.3,
    }
    resp = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        json=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "HTTP-Referer": "http://localhost:5000",
            "X-Title": "Boeing 737-800 AMM Chatbot",
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def call_ai(messages, system):
    providers = {
        "gemini":     call_gemini,
        "groq":       call_groq,
        "openrouter": call_openrouter,
    }
    fn = providers.get(AI_PROVIDER)
    if not fn:
        raise ValueError(
            f"Unknown AI_PROVIDER '{AI_PROVIDER}'. "
            "Choose: gemini, groq, openrouter"
        )
    return fn(messages, system)


# ══════════════════════════════════════════════════════════════
#  Routes
# ══════════════════════════════════════════════════════════════

# Serve frontend
@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


# ── Health check ───────────────────────────────────────────────
@app.route("/api/health")
def health():
    return jsonify({
        "status":    "ok",
        "db":        db.__class__.__name__,
        "ai":        AI_PROVIDER,
        "timestamp": datetime.utcnow().isoformat(),
    })


# ── Chapters ───────────────────────────────────────────────────
@app.route("/api/chapters")
def chapters():
    return jsonify(db.get_chapters())


# ── Sessions ───────────────────────────────────────────────────
@app.route("/api/sessions", methods=["POST"])
def create_session():
    title = "New Chat"
    if request.is_json and request.json:
        title = request.json.get("title", "New Chat")
    sid = db.create_session(title)
    return jsonify({"id": sid, "title": title}), 201


@app.route("/api/sessions", methods=["GET"])
def list_sessions():
    return jsonify(db.get_sessions())


@app.route("/api/sessions/<session_id>", methods=["GET"])
def get_session(session_id):
    session = db.get_session(session_id)
    if not session:
        return jsonify({"error": "Session not found"}), 404
    return jsonify({
        "session":  session,
        "messages": db.get_messages(session_id),
    })


@app.route("/api/sessions/<session_id>", methods=["DELETE"])
def delete_session(session_id):
    db.delete_session(session_id)
    return jsonify({"deleted": session_id})


# ── Chat ───────────────────────────────────────────────────────
@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    user_msg   = (data.get("message") or "").strip()
    session_id = data.get("session_id")

    if not user_msg:
        return jsonify({"error": "message field is required"}), 400

    # Create or auto-title session
    if not session_id:
        title      = user_msg[:50] + ("…" if len(user_msg) > 50 else "")
        session_id = db.create_session(title)
    else:
        session = db.get_session(session_id)
        if session and session.get("title") == "New Chat":
            db.update_session_title(
                session_id,
                user_msg[:50] + ("…" if len(user_msg) > 50 else "")
            )

    # Save user message
    db.add_message(session_id, "user", user_msg)

    # Retrieve relevant manual chunks
    chunks  = retrieve(db, user_msg, limit=6)
    context = build_context(chunks)

    # Build conversation history (trim to MAX_HISTORY pairs)
    history = db.get_messages(session_id)[:-1]   # exclude the message just added
    if len(history) > MAX_HISTORY * 2:
        history = history[-(MAX_HISTORY * 2):]

    ai_messages = [{"role": m["role"], "content": m["content"]} for m in history]

    # Inject context into current user turn
    ai_messages.append({
        "role":    "user",
        "content": f"CONTEXT FROM MANUAL:\n{context}\n\nUSER QUESTION:\n{user_msg}",
    })

    # Call AI provider
    try:
        reply = call_ai(ai_messages, SYSTEM_PROMPT)
    except requests.HTTPError as e:
        body = e.response.text[:300] if e.response else "no response"
        return jsonify({"error": f"AI API error {e.response.status_code}: {body}"}), 502
    except Exception as e:
        return jsonify({"error": str(e)}), 502

    # Save reply
    db.add_message(session_id, "assistant", reply)

    # Source chapters for the frontend to display
    source_chapters = list({c.get("chapter") for c in chunks if c.get("chapter")})

    return jsonify({
        "session_id":      session_id,
        "reply":           reply,
        "source_chapters": source_chapters,
        "provider":        AI_PROVIDER,
    })


# ══════════════════════════════════════════════════════════════
#  Entry point
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    port  = int(os.getenv("FLASK_PORT", 5000))
    debug = os.getenv("FLASK_ENV", "development") == "development"

    print("\n" + "="*50)
    print("  ✈   Boeing 737-800 AMM Chatbot")
    print("="*50)
    print(f"  AI Provider : {AI_PROVIDER.upper()}")
    print(f"  Database    : {db.__class__.__name__}")
    print(f"  URL         : http://localhost:{port}")
    print(f"  API Health  : http://localhost:{port}/api/health")
    print("="*50 + "\n")

    app.run(host="0.0.0.0", port=port, debug=debug)
