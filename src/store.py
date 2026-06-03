"""会话持久化层（SQLite，零外部依赖）。

设计目标：GitHub 拉下来即可运行——数据库文件在首次使用时自动创建，
无需任何外部服务或迁移步骤。保存会话、消息、累积线索与每轮追踪信息，
使「最近会话 / 历史会话 / 线索 / 追踪」在进程重启后依然可用。
"""
from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _make_title(message: str, max_len: int = 22) -> str:
    one = " ".join((message or "").split())
    if not one:
        return "新会话"
    return one if len(one) <= max_len else one[: max_len - 1] + "…"


_LEAD_KEYS = ["product", "quantity", "country", "email", "material", "drawing_available"]


def _lead_completeness(lead: dict) -> int:
    return sum(1 for k in _LEAD_KEYS if lead.get(k) not in (None, ""))


class SessionStore:
    def __init__(self, db_path: str):
        self.path = Path(db_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        with self._lock:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    id              TEXT PRIMARY KEY,
                    title           TEXT,
                    created_at      TEXT,
                    updated_at      TEXT,
                    visitor_country TEXT,
                    visitor_email   TEXT,
                    lead_fields     TEXT
                );
                CREATE TABLE IF NOT EXISTS messages (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id  TEXT,
                    role        TEXT,
                    content     TEXT,
                    meta        TEXT,
                    ts          TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_msg_session ON messages(session_id);
                """
            )
            self._conn.commit()

    # --------------------------- 会话 --------------------------- #
    def ensure_session(self, session_id: str, visitor: dict, first_message: str) -> None:
        with self._lock:
            row = self._conn.execute(
                "SELECT id FROM sessions WHERE id=?", (session_id,)
            ).fetchone()
            now = _now()
            if row is None:
                self._conn.execute(
                    "INSERT INTO sessions(id,title,created_at,updated_at,"
                    "visitor_country,visitor_email,lead_fields) VALUES(?,?,?,?,?,?,?)",
                    (session_id, _make_title(first_message), now, now,
                     (visitor or {}).get("country") or "",
                     (visitor or {}).get("email") or "", json.dumps({})),
                )
            else:
                # 更新访客信息（若本轮带了新值）
                v = visitor or {}
                if v.get("country") or v.get("email"):
                    self._conn.execute(
                        "UPDATE sessions SET visitor_country=COALESCE(NULLIF(?,''),visitor_country),"
                        "visitor_email=COALESCE(NULLIF(?,''),visitor_email) WHERE id=?",
                        (v.get("country") or "", v.get("email") or "", session_id),
                    )
            self._conn.commit()

    def get_history(self, session_id: str) -> list[dict]:
        """供 LLM 上下文使用的历史（仅 visitor/agent 文本）。"""
        with self._lock:
            rows = self._conn.execute(
                "SELECT role,content FROM messages WHERE session_id=? AND role IN "
                "('visitor','agent') ORDER BY id", (session_id,)
            ).fetchall()
        return [{"role": "assistant" if r["role"] == "agent" else "visitor",
                 "content": r["content"]} for r in rows]

    def get_lead(self, session_id: str) -> dict:
        with self._lock:
            row = self._conn.execute(
                "SELECT lead_fields FROM sessions WHERE id=?", (session_id,)
            ).fetchone()
        return json.loads(row["lead_fields"]) if row and row["lead_fields"] else {}

    def append_message(self, session_id: str, role: str, content: str,
                       meta: dict | None = None) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO messages(session_id,role,content,meta,ts) VALUES(?,?,?,?,?)",
                (session_id, role, content,
                 json.dumps(meta or {}, ensure_ascii=False), _now()),
            )
            self._conn.execute("UPDATE sessions SET updated_at=? WHERE id=?",
                               (_now(), session_id))
            self._conn.commit()

    def update_lead(self, session_id: str, lead_fields: dict) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE sessions SET lead_fields=?, updated_at=? WHERE id=?",
                (json.dumps(lead_fields, ensure_ascii=False), _now(), session_id),
            )
            self._conn.commit()

    def list_sessions(self, limit: int = 50) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT s.*, "
                "(SELECT content FROM messages m WHERE m.session_id=s.id AND m.role='visitor' "
                " ORDER BY m.id LIMIT 1) AS first_msg, "
                "(SELECT COUNT(*) FROM messages m WHERE m.session_id=s.id) AS msg_count "
                "FROM sessions s ORDER BY s.updated_at DESC LIMIT ?", (limit,)
            ).fetchall()
        out = []
        for r in rows:
            lead = json.loads(r["lead_fields"]) if r["lead_fields"] else {}
            out.append({
                "id": r["id"],
                "title": r["title"] or _make_title(r["first_msg"] or ""),
                "preview": _make_title(r["first_msg"] or "", 28),
                "created_at": r["created_at"],
                "updated_at": r["updated_at"],
                "country": r["visitor_country"] or None,
                "message_count": r["msg_count"],
                "lead_completeness": _lead_completeness(lead),
            })
        return out

    def get_session(self, session_id: str) -> dict | None:
        with self._lock:
            s = self._conn.execute(
                "SELECT * FROM sessions WHERE id=?", (session_id,)
            ).fetchone()
            if s is None:
                return None
            msgs = self._conn.execute(
                "SELECT role,content,meta,ts FROM messages WHERE session_id=? ORDER BY id",
                (session_id,)
            ).fetchall()
        return {
            "id": s["id"],
            "title": s["title"],
            "created_at": s["created_at"],
            "updated_at": s["updated_at"],
            "visitor": {"country": s["visitor_country"] or None,
                        "email": s["visitor_email"] or None},
            "lead_fields": json.loads(s["lead_fields"]) if s["lead_fields"] else {},
            "messages": [
                {"role": m["role"], "content": m["content"],
                 "meta": json.loads(m["meta"]) if m["meta"] else {}, "ts": m["ts"]}
                for m in msgs
            ],
        }

    def delete_session(self, session_id: str) -> bool:
        with self._lock:
            cur = self._conn.execute("DELETE FROM sessions WHERE id=?", (session_id,))
            self._conn.execute("DELETE FROM messages WHERE session_id=?", (session_id,))
            self._conn.commit()
            return cur.rowcount > 0
