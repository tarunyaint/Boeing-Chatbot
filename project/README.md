# ✈  Boeing 737-800 AMM Chatbot

AI chatbot for the Boeing 737-800 Aircraft Maintenance Manual.
**Stack:** HTML/CSS/JS · Python Flask · PostgreSQL or MongoDB · Free AI API

---

## ⚡ Quick Start (5 steps)

### Step 1 — Open in VS Code
Open the `boeing737_amm_chatbot/` folder in VS Code.

### Step 2 — Create virtual environment
Open the VS Code terminal (`Ctrl + `` ` ``) and run:

```bash
cd backend
python -m venv venv
```

**Activate it:**
- Mac / Linux: `source venv/bin/activate`
- Windows:     `venv\Scripts\activate`

You should see `(venv)` in your terminal prompt.

### Step 3 — Install packages
```bash
pip install -r requirements.txt
```

### Step 4 — Add your free API key
Open `backend/.env` and replace `YOUR_GEMINI_KEY_HERE` with your real key.

**Get a free Gemini key (takes 30 seconds):**
→ https://aistudio.google.com/apikey
→ Click "Create API Key" → Copy it → Paste into .env

```
AI_PROVIDER=gemini
GEMINI_API_KEY=AIza...your-key-here...
```

**Set your PostgreSQL password** (whatever you set when you installed Postgres):
```
POSTGRES_PASSWORD=yourpassword
```

### Step 5 — Set up database and run

**Create the database** (only once):
```bash
psql -U postgres -c "CREATE DATABASE amm_chatbot;"
```

**Index the manual** (only once):
```bash
python ingest.py
```
Wait for: `Done — X chunks indexed in PostgresDB`

**Start the server:**
```bash
python app.py
```

You'll see:
```
==================================================
  ✈   Boeing 737-800 AMM Chatbot
==================================================
  AI Provider : GEMINI
  Database    : PostgresDB
  URL         : http://localhost:5000
  API Health  : http://localhost:5000/api/health
==================================================
```

**Open the chatbot:**
Open `frontend/index.html` in your browser
OR install the **Live Server** VS Code extension and click "Go Live".

---

## 🗂 Project Structure

```
boeing737_amm_chatbot/
├── .vscode/
│   ├── launch.json        ← Press F5 to run Flask
│   └── settings.json      ← Python path config
├── backend/
│   ├── app.py             ← Flask app (all API routes)
│   ├── db.py              ← Database layer (Postgres + MongoDB)
│   ├── ingest.py          ← Manual chunking script (run once)
│   ├── retrieval.py       ← Keyword search logic
│   ├── requirements.txt   ← Python packages
│   └── .env               ← YOUR config (API key + DB settings)
├── frontend/
│   ├── index.html         ← Chat UI
│   ├── css/style.css      ← Styling
│   └── js/app.js          ← All browser logic
└── data/
    └── manual.txt         ← Boeing 737-800 AMM text
```

---

## 🔑 Free AI Providers

| Provider | Free Limit | Get Key |
|---|---|---|
| **Google Gemini** ⭐ (default) | 1,500 req/day | https://aistudio.google.com/apikey |
| Groq (LLaMA 3.1) | Generous daily | https://console.groq.com |
| OpenRouter | Free model tier | https://openrouter.ai |

To switch provider, edit `backend/.env`:
```
AI_PROVIDER=groq
GROQ_API_KEY=your-key-here
```

---

## 🌐 API Endpoints

| Method | URL | Description |
|---|---|---|
| GET | /api/health | Check server is running |
| GET | /api/chapters | List indexed chapters |
| POST | /api/chat | Send message, get answer |
| GET | /api/sessions | List all chat sessions |
| POST | /api/sessions | Create new session |
| GET | /api/sessions/<id> | Get session + history |
| DELETE | /api/sessions/<id> | Delete session |

---

## 🐘 Using MongoDB instead of PostgreSQL

Edit `backend/.env`:
```
DB_TYPE=mongo
MONGO_URI=mongodb://localhost:27017/
MONGO_DB=amm_chatbot
```
Make sure MongoDB is running (`mongod`), then run `python ingest.py` again.

---

## ⚠ Disclaimer
This chatbot uses a **synthetic training document** only.
Not derived from official OEM documentation.
**Do not use for actual aircraft maintenance.**
