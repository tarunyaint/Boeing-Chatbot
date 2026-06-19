"""
db.py
Database abstraction layer.
Supports PostgreSQL (psycopg2) and MongoDB (pymongo).
Switch by changing DB_TYPE in .env — no other code changes needed.
"""

import os
import uuid
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

DB_TYPE = os.getenv("DB_TYPE", "postgres").lower()


# ══════════════════════════════════════════════════════════════
#  PostgreSQL
# ══════════════════════════════════════════════════════════════

class PostgresDB:
    def __init__(self):
        import psycopg2
        import psycopg2.extras
        self.conn = psycopg2.connect(
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=int(os.getenv("POSTGRES_PORT", 5432)),
            dbname=os.getenv("POSTGRES_DB", "amm_chatbot"),
            user=os.getenv("POSTGRES_USER", "postgres"),
            password=os.getenv("POSTGRES_PASSWORD", "postgres"),
        )
        self.conn.autocommit = True
        self.extras = psycopg2.extras
        self._create_tables()
        print("[DB] Connected to PostgreSQL")

    def _create_tables(self):
        with self.conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id         TEXT PRIMARY KEY,
                    title      TEXT,
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                );
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id         TEXT PRIMARY KEY,
                    session_id TEXT REFERENCES sessions(id) ON DELETE CASCADE,
                    role       TEXT NOT NULL,
                    content    TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT NOW()
                );
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS chunks (
                    id       SERIAL PRIMARY KEY,
                    chapter  TEXT,
                    section  TEXT,
                    content  TEXT NOT NULL,
                    keywords TEXT[]
                );
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_msg_session  ON messages(session_id);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_chunk_kw     ON chunks USING GIN(keywords);")

    # ── Sessions ───────────────────────────────────────────────

    def create_session(self, title="New Chat"):
        sid = str(uuid.uuid4())
        with self.conn.cursor() as cur:
            cur.execute("INSERT INTO sessions (id, title) VALUES (%s, %s)", (sid, title))
        return sid

    def get_sessions(self):
        with self.conn.cursor(cursor_factory=self.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM sessions ORDER BY updated_at DESC")
            return [dict(r) for r in cur.fetchall()]

    def get_session(self, session_id):
        with self.conn.cursor(cursor_factory=self.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM sessions WHERE id = %s", (session_id,))
            row = cur.fetchone()
            return dict(row) if row else None

    def update_session_title(self, session_id, title):
        with self.conn.cursor() as cur:
            cur.execute(
                "UPDATE sessions SET title = %s, updated_at = NOW() WHERE id = %s",
                (title, session_id)
            )

    def touch_session(self, session_id):
        with self.conn.cursor() as cur:
            cur.execute("UPDATE sessions SET updated_at = NOW() WHERE id = %s", (session_id,))

    def delete_session(self, session_id):
        with self.conn.cursor() as cur:
            cur.execute("DELETE FROM sessions WHERE id = %s", (session_id,))

    # ── Messages ───────────────────────────────────────────────

    def add_message(self, session_id, role, content):
        mid = str(uuid.uuid4())
        with self.conn.cursor() as cur:
            cur.execute(
                "INSERT INTO messages (id, session_id, role, content) VALUES (%s, %s, %s, %s)",
                (mid, session_id, role, content)
            )
        self.touch_session(session_id)
        return mid

    def get_messages(self, session_id):
        with self.conn.cursor(cursor_factory=self.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM messages WHERE session_id = %s ORDER BY created_at ASC",
                (session_id,)
            )
            return [dict(r) for r in cur.fetchall()]

    # ── Chunks ─────────────────────────────────────────────────

    def clear_chunks(self):
        with self.conn.cursor() as cur:
            cur.execute("TRUNCATE TABLE chunks RESTART IDENTITY;")

    def insert_chunk(self, chapter, section, content, keywords):
        with self.conn.cursor() as cur:
            cur.execute(
                "INSERT INTO chunks (chapter, section, content, keywords) VALUES (%s, %s, %s, %s)",
                (chapter, section, content, keywords)
            )

    def search_chunks(self, query_keywords, limit=6):
        if not query_keywords:
            return []
        with self.conn.cursor(cursor_factory=self.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT *, (
                    SELECT COUNT(*) FROM unnest(keywords) k
                    WHERE k = ANY(%s::text[])
                ) AS score
                FROM chunks
                WHERE keywords && %s::text[]
                ORDER BY score DESC
                LIMIT %s
            """, (query_keywords, query_keywords, limit))
            return [dict(r) for r in cur.fetchall()]

    def get_chapters(self):
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT DISTINCT chapter FROM chunks WHERE chapter IS NOT NULL ORDER BY chapter"
            )
            return [r[0] for r in cur.fetchall()]


# ══════════════════════════════════════════════════════════════
#  MongoDB
# ══════════════════════════════════════════════════════════════

class MongoDB:
    def __init__(self):
        from pymongo import MongoClient
        uri    = os.getenv("MONGO_URI",  "mongodb://localhost:27017/")
        dbname = os.getenv("MONGO_DB",   "amm_chatbot")
        client = MongoClient(uri)
        db = client[dbname]
        self.sessions = db["sessions"]
        self.messages = db["messages"]
        self.chunks   = db["chunks"]
        self.sessions.create_index("updated_at")
        self.messages.create_index("session_id")
        self.chunks.create_index("keywords")
        print("[DB] Connected to MongoDB")

    def _clean(self, doc):
        if doc is None:
            return None
        doc = dict(doc)
        doc.pop("_id", None)
        for k, v in doc.items():
            if isinstance(v, datetime):
                doc[k] = v.isoformat()
        return doc

    # ── Sessions ───────────────────────────────────────────────

    def create_session(self, title="New Chat"):
        sid = str(uuid.uuid4())
        now = datetime.utcnow()
        self.sessions.insert_one({"id": sid, "title": title,
                                   "created_at": now, "updated_at": now})
        return sid

    def get_sessions(self):
        return [self._clean(d) for d in
                self.sessions.find({}, {"_id": 0}).sort("updated_at", -1)]

    def get_session(self, session_id):
        return self._clean(self.sessions.find_one({"id": session_id}, {"_id": 0}))

    def update_session_title(self, session_id, title):
        self.sessions.update_one(
            {"id": session_id},
            {"$set": {"title": title, "updated_at": datetime.utcnow()}}
        )

    def touch_session(self, session_id):
        self.sessions.update_one(
            {"id": session_id},
            {"$set": {"updated_at": datetime.utcnow()}}
        )

    def delete_session(self, session_id):
        self.sessions.delete_one({"id": session_id})
        self.messages.delete_many({"session_id": session_id})

    # ── Messages ───────────────────────────────────────────────

    def add_message(self, session_id, role, content):
        mid = str(uuid.uuid4())
        self.messages.insert_one({
            "id": mid, "session_id": session_id,
            "role": role, "content": content,
            "created_at": datetime.utcnow()
        })
        self.touch_session(session_id)
        return mid

    def get_messages(self, session_id):
        return [self._clean(d) for d in
                self.messages.find({"session_id": session_id}, {"_id": 0})
                             .sort("created_at", 1)]

    # ── Chunks ─────────────────────────────────────────────────

    def clear_chunks(self):
        self.chunks.delete_many({})

    def insert_chunk(self, chapter, section, content, keywords):
        self.chunks.insert_one({
            "chapter": chapter, "section": section,
            "content": content, "keywords": keywords
        })

    def search_chunks(self, query_keywords, limit=6):
        if not query_keywords:
            return []
        pipeline = [
            {"$match": {"keywords": {"$in": query_keywords}}},
            {"$addFields": {"score": {"$size": {
                "$ifNull": [{"$setIntersection": ["$keywords", query_keywords]}, []]
            }}}},
            {"$sort": {"score": -1}},
            {"$limit": limit},
            {"$project": {"_id": 0}},
        ]
        return [self._clean(d) for d in self.chunks.aggregate(pipeline)]

    def get_chapters(self):
        return sorted(self.chunks.distinct("chapter"))


# ══════════════════════════════════════════════════════════════
#  Factory
# ══════════════════════════════════════════════════════════════

def get_db():
    if DB_TYPE == "mongo":
        return MongoDB()
    return PostgresDB()
