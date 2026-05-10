import sqlite3
import uuid
from pathlib import Path

_DB_PATH = Path(__file__).parent.parent.parent / "data" / "aiops.db"
_DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                id          TEXT PRIMARY KEY,
                title       TEXT,
                created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS messages (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id  TEXT NOT NULL,
                role        TEXT NOT NULL,
                type        TEXT NOT NULL,
                content     TEXT NOT NULL,
                image_data  TEXT,
                created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            );
        """)
        # Migrate existing DB: add image_data if missing
        try:
            conn.execute("ALTER TABLE messages ADD COLUMN image_data TEXT")
        except Exception:
            pass  # column already exists


def create_session(title: str = "新对话") -> str:
    sid = str(uuid.uuid4())
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO sessions (id, title) VALUES (?, ?)", (sid, title)
        )
    return sid


def save_message(session_id: str, role: str, msg_type: str, content: str, image_data: str | None = None):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO messages (session_id, role, type, content, image_data) VALUES (?, ?, ?, ?, ?)",
            (session_id, role, msg_type, content, image_data),
        )
        conn.execute(
            "UPDATE sessions SET updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (session_id,),
        )


def get_sessions() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM sessions ORDER BY updated_at DESC LIMIT 50"
        ).fetchall()
    return [dict(r) for r in rows]


def get_session_messages(session_id: str) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, session_id, role, type, content, created_at FROM messages WHERE session_id=? ORDER BY id",
            (session_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_message_image(msg_id: int) -> str | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT image_data FROM messages WHERE id=?", (msg_id,)
        ).fetchone()
    if row is None:
        return None
    return row["image_data"]


def delete_session(session_id: str):
    with get_conn() as conn:
        conn.execute("DELETE FROM messages WHERE session_id=?", (session_id,))
        conn.execute("DELETE FROM sessions WHERE id=?", (session_id,))


def rename_session(session_id: str, title: str):
    with get_conn() as conn:
        conn.execute(
            "UPDATE sessions SET title=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (title, session_id),
        )
