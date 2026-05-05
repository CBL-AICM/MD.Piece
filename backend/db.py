"""
Database layer — Supabase-compatible SQLite fallback.

When Supabase credentials are available, use the real client.
Otherwise, provide a SQLite-backed query builder that implements
the same .table().select().eq().insert().delete().execute() API
so all router code works without modification.
"""

import json
import logging
import os
import sqlite3
import uuid
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    from supabase import create_client, Client
    _supabase_available = True
except BaseException:
    _supabase_available = False
    Client = None

# Production fallback：本專案的 Supabase publishable (anon) key 與 URL。
# anon key 設計上就是公開的（前端 client-side 也會看到），commit 進 repo 沒
# 安全風險；若有設環境變數則優先採用（典型情境是改用 service_role 以 bypass RLS）。
# 對應的 Supabase migration: md_piece_full_schema_and_anon_access (RLS 已 disable)。
_DEFAULT_SUPABASE_URL = "https://tbqvpqvvvgfgaezxbhkz.supabase.co"
_DEFAULT_SUPABASE_KEY = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRicXZwcXZ2dmdmZ2FlenhiaGt6Iiwicm9sZSI6ImFub24i"
    "LCJpYXQiOjE3NzM2NTA3OTYsImV4cCI6MjA4OTIyNjc5Nn0."
    "gMiXYsqw6V4GlvGLZx8ZHXZMudnx5no_cD9E5aQ3kVs"
)
SUPABASE_URL = os.getenv("SUPABASE_URL") or _DEFAULT_SUPABASE_URL
SUPABASE_KEY = os.getenv("SUPABASE_KEY") or _DEFAULT_SUPABASE_KEY

_client = None

# ─── SQLite DB path ──────────────────────────────────────────
# Vercel's /var/task is read-only; only /tmp is writable. Detect serverless
# and put the DB there so the SQLite fallback at least boots (data is
# ephemeral per cold start).
def _default_db_path():
    if os.getenv("VERCEL") or os.getenv("AWS_LAMBDA_FUNCTION_NAME"):
        return "/tmp/md_piece.db"
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "md_piece.db")

DB_PATH = _default_db_path()

# ─── Table schemas (auto-create) ─────────────────────────────
_SCHEMAS = {
    "patients": """
        CREATE TABLE IF NOT EXISTS patients (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            age INTEGER,
            gender TEXT,
            phone TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )""",
    "doctors": """
        CREATE TABLE IF NOT EXISTS doctors (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            specialty TEXT,
            phone TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )""",
    "medical_records": """
        CREATE TABLE IF NOT EXISTS medical_records (
            id TEXT PRIMARY KEY,
            patient_id TEXT,
            doctor_id TEXT,
            visit_date TEXT,
            symptoms TEXT,
            diagnosis TEXT,
            prescription TEXT,
            notes TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (patient_id) REFERENCES patients(id),
            FOREIGN KEY (doctor_id) REFERENCES doctors(id)
        )""",
    "symptoms_log": """
        CREATE TABLE IF NOT EXISTS symptoms_log (
            id TEXT PRIMARY KEY,
            patient_id TEXT,
            symptoms TEXT,
            ai_response TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )""",
    "emotions": """
        CREATE TABLE IF NOT EXISTS emotions (
            id TEXT PRIMARY KEY,
            patient_id TEXT,
            score INTEGER,
            note TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )""",
    "medications": """
        CREATE TABLE IF NOT EXISTS medications (
            id TEXT PRIMARY KEY,
            patient_id TEXT,
            name TEXT NOT NULL,
            dosage TEXT,
            frequency TEXT,
            category TEXT,
            purpose TEXT,
            instructions TEXT,
            photo_data TEXT,
            recognized_from_photo INTEGER DEFAULT 0,
            active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (patient_id) REFERENCES patients(id)
        )""",
    "medication_logs": """
        CREATE TABLE IF NOT EXISTS medication_logs (
            id TEXT PRIMARY KEY,
            patient_id TEXT,
            medication_id TEXT,
            taken INTEGER DEFAULT 1,
            taken_at TEXT DEFAULT (datetime('now')),
            skip_reason TEXT,
            notes TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (patient_id) REFERENCES patients(id),
            FOREIGN KEY (medication_id) REFERENCES medications(id)
        )""",
    "medication_effects": """
        CREATE TABLE IF NOT EXISTS medication_effects (
            id TEXT PRIMARY KEY,
            patient_id TEXT,
            medication_id TEXT,
            effectiveness INTEGER DEFAULT 3,
            side_effects TEXT,
            symptom_changes TEXT,
            notes TEXT,
            recorded_at TEXT DEFAULT (datetime('now')),
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (patient_id) REFERENCES patients(id),
            FOREIGN KEY (medication_id) REFERENCES medications(id)
        )""",
    "xiaohe_conversations": """
        CREATE TABLE IF NOT EXISTS xiaohe_conversations (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            user_message TEXT,
            reply TEXT,
            mode TEXT DEFAULT 'patient',
            version TEXT DEFAULT 'normal',
            created_at TEXT DEFAULT (datetime('now'))
        )""",
    "experiments": """
        CREATE TABLE IF NOT EXISTS experiments (
            id TEXT PRIMARY KEY,
            name TEXT,
            val_bpb REAL,
            train_loss REAL,
            steps INTEGER,
            duration_minutes REAL,
            notes TEXT,
            colab_url TEXT,
            kept INTEGER DEFAULT 0,
            submitted_at TEXT DEFAULT (datetime('now'))
        )""",
    "users": """
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            username TEXT UNIQUE,
            password_hash TEXT,
            nickname TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('doctor', 'patient')),
            avatar_color TEXT DEFAULT '#5B9FE8',
            avatar_url TEXT,
            id_number TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )""",
    "doctor_notes": """
        CREATE TABLE IF NOT EXISTS doctor_notes (
            id TEXT PRIMARY KEY,
            patient_id TEXT NOT NULL,
            doctor_id TEXT,
            record_id TEXT,
            content TEXT NOT NULL,
            next_focus TEXT,
            tags TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (patient_id) REFERENCES patients(id),
            FOREIGN KEY (doctor_id) REFERENCES doctors(id),
            FOREIGN KEY (record_id) REFERENCES medical_records(id)
        )""",
    "medication_changes": """
        CREATE TABLE IF NOT EXISTS medication_changes (
            id TEXT PRIMARY KEY,
            patient_id TEXT NOT NULL,
            medication_id TEXT NOT NULL,
            doctor_id TEXT,
            change_type TEXT NOT NULL CHECK(change_type IN
                ('start', 'stop', 'dose_up', 'dose_down', 'switch', 'frequency', 'other')),
            previous_dosage TEXT,
            new_dosage TEXT,
            previous_frequency TEXT,
            new_frequency TEXT,
            reason TEXT,
            effective_date TEXT DEFAULT (datetime('now')),
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (patient_id) REFERENCES patients(id),
            FOREIGN KEY (medication_id) REFERENCES medications(id),
            FOREIGN KEY (doctor_id) REFERENCES doctors(id)
        )""",
    "alerts": """
        CREATE TABLE IF NOT EXISTS alerts (
            id TEXT PRIMARY KEY,
            patient_id TEXT NOT NULL,
            alert_type TEXT NOT NULL CHECK(alert_type IN
                ('er_visit', 'missed_medication', 'self_discontinued',
                 'infection', 'low_mood', 'psych_crisis', 'other')),
            severity TEXT NOT NULL DEFAULT 'medium' CHECK(severity IN ('low', 'medium', 'high', 'critical')),
            title TEXT NOT NULL,
            detail TEXT,
            metadata TEXT,
            source TEXT,
            acknowledged INTEGER DEFAULT 0,
            acknowledged_by TEXT,
            acknowledged_at TEXT,
            resolved INTEGER DEFAULT 0,
            resolved_at TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (patient_id) REFERENCES patients(id)
        )""",

    "diet_records": """
        CREATE TABLE IF NOT EXISTS diet_records (
            id TEXT PRIMARY KEY,
            patient_id TEXT NOT NULL,
            meal_type TEXT NOT NULL CHECK(meal_type IN ('breakfast', 'lunch', 'dinner', 'snack')),
            foods TEXT NOT NULL,
            note TEXT DEFAULT '',
            eaten_at TEXT NOT NULL DEFAULT (datetime('now')),
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )""",
}


_db_initialized = False

def _get_conn():
    global _db_initialized
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    if not _db_initialized:
        for sql in _SCHEMAS.values():
            conn.execute(sql)
        _migrate_users_table(conn)
        conn.commit()
        _db_initialized = True
    return conn


def _migrate_users_table(conn):
    """Add auth-related columns to existing users tables."""
    cols = {row[1] for row in conn.execute("PRAGMA table_info(users)")}
    additions = [
        ("username", "TEXT"),
        ("password_hash", "TEXT"),
        ("avatar_url", "TEXT"),
        ("id_number", "TEXT"),
    ]
    for name, decl in additions:
        if name not in cols:
            try:
                conn.execute(f"ALTER TABLE users ADD COLUMN {name} {decl}")
            except sqlite3.OperationalError:
                pass
    try:
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username ON users(username) WHERE username IS NOT NULL")
    except sqlite3.OperationalError:
        pass


def _init_db():
    conn = _get_conn()
    for sql in _SCHEMAS.values():
        conn.execute(sql)
    conn.commit()
    conn.close()
    logger.info(f"SQLite database initialized at {DB_PATH}")


# ─── Supabase-compatible query builder backed by SQLite ───────

import re as _re

_IDENT_RE = _re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _safe_ident(name):
    """Validate an SQL identifier (table or column name) against a strict
    allowlist before interpolation. Raises ValueError on rejection so we
    fail closed rather than risk an injected fragment reaching the DB."""
    if not isinstance(name, str) or not _IDENT_RE.match(name):
        raise ValueError(f"unsafe SQL identifier: {name!r}")
    return name


class _SqliteResult:
    def __init__(self, data):
        self.data = data


class _SqliteQuery:
    """Mimics the Supabase query builder API with SQLite."""

    def __init__(self, table_name):
        self._table = table_name
        self._op = "select"
        self._select_cols = "*"
        self._conditions = []
        self._params = []
        self._order_col = None
        self._order_desc = False
        self._limit_n = None
        self._insert_data = None
        self._update_data = None

    # ─── Operation setters ──────────────
    def select(self, cols="*", **kwargs):
        self._op = "select"
        self._select_cols = cols
        return self

    def insert(self, data, **kwargs):
        self._op = "insert"
        if isinstance(data, str):
            data = json.loads(data)
        self._insert_data = data
        return self

    def update(self, data, **kwargs):
        self._op = "update"
        if isinstance(data, str):
            data = json.loads(data)
        self._update_data = data
        return self

    def delete(self, **kwargs):
        self._op = "delete"
        return self

    # ─── Condition builders ─────────────
    def eq(self, col, val):
        self._conditions.append(f'"{_safe_ident(col)}" = ?')
        self._params.append(val)
        return self

    def neq(self, col, val):
        self._conditions.append(f'"{_safe_ident(col)}" != ?')
        self._params.append(val)
        return self

    def gte(self, col, val):
        self._conditions.append(f'"{_safe_ident(col)}" >= ?')
        self._params.append(val)
        return self

    def gt(self, col, val):
        self._conditions.append(f'"{_safe_ident(col)}" > ?')
        self._params.append(val)
        return self

    def lte(self, col, val):
        self._conditions.append(f'"{_safe_ident(col)}" <= ?')
        self._params.append(val)
        return self

    def lt(self, col, val):
        self._conditions.append(f'"{_safe_ident(col)}" < ?')
        self._params.append(val)
        return self

    def ilike(self, col, val):
        self._conditions.append(f'"{_safe_ident(col)}" LIKE ? COLLATE NOCASE')
        self._params.append(val)
        return self

    def order(self, col, desc=False, **kwargs):
        self._order_col = _safe_ident(col)
        self._order_desc = desc
        return self

    def limit(self, n):
        self._limit_n = n
        return self

    # ─── Execute ────────────────────────
    @staticmethod
    def _serialize_value(v):
        """Serialize lists/dicts to JSON strings for SQLite storage."""
        if isinstance(v, (list, dict)):
            return json.dumps(v, ensure_ascii=False)
        return v

    @staticmethod
    def _deserialize_row(row_dict):
        """Try to parse JSON strings back into lists/dicts."""
        for k, v in row_dict.items():
            if isinstance(v, str) and v and v[0] in ('[', '{'):
                try:
                    row_dict[k] = json.loads(v)
                except (json.JSONDecodeError, ValueError):
                    pass
        return row_dict

    def execute(self):
        conn = _get_conn()
        try:
            if self._op == "select":
                return self._exec_select(conn)
            elif self._op == "insert":
                return self._exec_insert(conn)
            elif self._op == "update":
                return self._exec_update(conn)
            elif self._op == "delete":
                return self._exec_delete(conn)
        finally:
            conn.close()

    def _where_clause(self):
        if not self._conditions:
            return "", []
        return " WHERE " + " AND ".join(self._conditions), list(self._params)

    def _exec_select(self, conn):
        where, params = self._where_clause()
        table = _safe_ident(self._table)
        sql = f'SELECT * FROM "{table}"{where}'
        if self._order_col:
            direction = "DESC" if self._order_desc else "ASC"
            sql += f' ORDER BY "{_safe_ident(self._order_col)}" {direction}'
        if self._limit_n:
            sql += f" LIMIT {int(self._limit_n)}"

        rows = conn.execute(sql, params).fetchall()
        data = [self._deserialize_row(dict(r)) for r in rows]

        # Handle Supabase-style join syntax: "*, patients(name)"
        if self._select_cols and self._select_cols != "*":
            data = self._resolve_joins(conn, data, self._select_cols)

        return _SqliteResult(data)

    def _resolve_joins(self, conn, data, cols_expr):
        """Parse Supabase-style join: '*, patients(name, age)' → add nested dict."""
        import re
        joins = re.findall(r'(\w+)\(([^)]+)\)', cols_expr)
        if not joins:
            return data

        for row in data:
            for ref_table, ref_cols in joins:
                safe_ref = _safe_ident(ref_table)
                fk_col = f"{safe_ref[:-1]}_id" if safe_ref.endswith("s") else f"{safe_ref}_id"
                fk_val = row.get(fk_col)
                if fk_val:
                    ref_row = conn.execute(
                        f'SELECT * FROM "{safe_ref}" WHERE id = ?', (fk_val,)
                    ).fetchone()
                    if ref_row:
                        ref_dict = dict(ref_row)
                        wanted = [c.strip() for c in ref_cols.split(",")]
                        row[ref_table] = {k: ref_dict.get(k) for k in wanted}
                    else:
                        row[ref_table] = None
                else:
                    row[ref_table] = None
        return data

    def _exec_insert(self, conn):
        data = self._insert_data
        if not data:
            return _SqliteResult([])

        if "id" not in data or not data["id"]:
            data["id"] = str(uuid.uuid4())
        if "created_at" not in data:
            data["created_at"] = datetime.now(timezone.utc).isoformat()

        # Serialize complex types
        serialized = {k: self._serialize_value(v) for k, v in data.items()}
        table = _safe_ident(self._table)
        col_idents = [_safe_ident(k) for k in serialized.keys()]
        cols = ', '.join(f'"{k}"' for k in col_idents)
        placeholders = ', '.join('?' for _ in serialized)
        sql = f'INSERT INTO "{table}" ({cols}) VALUES ({placeholders})'
        conn.execute(sql, list(serialized.values()))
        conn.commit()
        return _SqliteResult([data])

    def _exec_update(self, conn):
        data = self._update_data
        if not data:
            return _SqliteResult([])

        serialized = {k: self._serialize_value(v) for k, v in data.items()}
        table = _safe_ident(self._table)
        col_idents = [_safe_ident(k) for k in serialized.keys()]
        set_clause = ', '.join(f'"{k}" = ?' for k in col_idents)
        set_params = list(serialized.values())
        where, where_params = self._where_clause()
        sql = f'UPDATE "{table}" SET {set_clause}{where}'
        conn.execute(sql, set_params + where_params)
        conn.commit()

        select_sql = f'SELECT * FROM "{table}"{where}'
        rows = conn.execute(select_sql, where_params).fetchall()
        return _SqliteResult([self._deserialize_row(dict(r)) for r in rows])

    def _exec_delete(self, conn):
        table = _safe_ident(self._table)
        where, params = self._where_clause()
        select_sql = f'SELECT * FROM "{table}"{where}'
        rows = conn.execute(select_sql, params).fetchall()
        data = [self._deserialize_row(dict(r)) for r in rows]

        sql = f'DELETE FROM "{table}"{where}'
        conn.execute(sql, params)
        conn.commit()
        return _SqliteResult(data)


class _SqliteSupabase:
    """Drop-in replacement for Supabase client using SQLite."""
    def table(self, name):
        return _SqliteQuery(name)


# ─── PostgREST shim over httpx (used on Vercel where the
#     `supabase` package was removed for bundle size) ─────────

try:
    import httpx
    _httpx_available = True
except ImportError:
    httpx = None
    _httpx_available = False


class _HttpxResult:
    def __init__(self, data):
        self.data = data


class _HttpxQuery:
    """Minimal PostgREST client mimicking the Supabase query-builder API."""

    def __init__(self, base_url, headers, table_name):
        self._base = base_url
        self._headers = headers
        self._table = _safe_ident(table_name)
        self._op = "select"
        self._select_cols = "*"
        self._filters = []     # list of (col, "eq.val") tuples
        self._order = None     # (col, desc)
        self._limit = None
        self._payload = None

    # operation setters
    def select(self, cols="*", **_):
        self._op = "select"; self._select_cols = cols; return self
    def insert(self, data, **_):
        self._op = "insert"; self._payload = data; return self
    def update(self, data, **_):
        self._op = "update"; self._payload = data; return self
    def delete(self, **_):
        self._op = "delete"; return self

    # conditions — encode for PostgREST query string
    def _add(self, col, op, val):
        self._filters.append((_safe_ident(col), f"{op}.{val}"))
        return self
    def eq(self, col, val):     return self._add(col, "eq", val)
    def neq(self, col, val):    return self._add(col, "neq", val)
    def gte(self, col, val):    return self._add(col, "gte", val)
    def gt(self, col, val):     return self._add(col, "gt", val)
    def lte(self, col, val):    return self._add(col, "lte", val)
    def lt(self, col, val):     return self._add(col, "lt", val)
    def ilike(self, col, val):  return self._add(col, "ilike", val)

    def order(self, col, desc=False, **_):
        self._order = (_safe_ident(col), bool(desc))
        return self
    def limit(self, n):
        self._limit = int(n); return self

    def _build_qs(self, extra=None):
        params = []
        for col, val in self._filters:
            params.append((col, val))
        if self._order:
            col, desc = self._order
            params.append(("order", f"{col}.{'desc' if desc else 'asc'}"))
        if self._limit is not None:
            params.append(("limit", str(self._limit)))
        if extra:
            params.extend(extra)
        return params

    def execute(self):
        url = f"{self._base}/rest/v1/{self._table}"
        if self._op == "select":
            params = self._build_qs([("select", self._select_cols)])
            r = httpx.get(url, headers=self._headers, params=params, timeout=10.0)
            r.raise_for_status()
            return _HttpxResult(r.json())

        if self._op == "insert":
            headers = {**self._headers, "Prefer": "return=representation"}
            body = self._payload if isinstance(self._payload, list) else [self._payload]
            r = httpx.post(url, headers=headers, json=body, timeout=10.0)
            if r.status_code >= 400:
                logger.error("Supabase insert failed: %s — %s", r.status_code, r.text)
                r.raise_for_status()
            return _HttpxResult(r.json())

        if self._op == "update":
            headers = {**self._headers, "Prefer": "return=representation"}
            params = self._build_qs()
            r = httpx.patch(url, headers=headers, params=params, json=self._payload, timeout=10.0)
            if r.status_code >= 400:
                logger.error("Supabase update failed: %s — %s", r.status_code, r.text)
                r.raise_for_status()
            return _HttpxResult(r.json())

        if self._op == "delete":
            headers = {**self._headers, "Prefer": "return=representation"}
            params = self._build_qs()
            r = httpx.delete(url, headers=headers, params=params, timeout=10.0)
            if r.status_code >= 400:
                logger.error("Supabase delete failed: %s — %s", r.status_code, r.text)
                r.raise_for_status()
            return _HttpxResult(r.json())


class _HttpxSupabase:
    def __init__(self, url, key):
        self._url = url.rstrip("/")
        self._headers = {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }

    def table(self, name):
        return _HttpxQuery(self._url, self._headers, name)


# ─── Public API ───────────────────────────────────────────────

def get_supabase():
    """取得資料庫 client。有 Supabase 憑證用 Supabase，否則用 SQLite。

    在 serverless 環境（Vercel / Lambda）下，/tmp/ 是 ephemeral 的，
    每個 function instance 各自獨立、cold start 後消失。若沒有 Supabase
    憑證就 fallback 到 SQLite，會導致「註冊後資料隨機消失」的 bug
    （instance A 寫入的帳號，instance B 看不到）。為避免這種「靜默」
    資料遺失，serverless 模式下強制要求 Supabase 憑證。
    """
    global _client
    if _client is None:
        is_serverless = bool(os.getenv("VERCEL") or os.getenv("AWS_LAMBDA_FUNCTION_NAME"))
        if SUPABASE_URL and SUPABASE_KEY:
            if _supabase_available:
                _client = create_client(SUPABASE_URL, SUPABASE_KEY)
                logger.info("Connected to Supabase via supabase-py")
            elif _httpx_available:
                _client = _HttpxSupabase(SUPABASE_URL, SUPABASE_KEY)
                logger.info("Connected to Supabase via httpx PostgREST shim")
            else:
                if is_serverless:
                    raise RuntimeError(
                        "Serverless 環境偵測到 Supabase 憑證，但 supabase-py 與 httpx "
                        "皆無法載入；無法使用 SQLite fallback（資料會在 cold start 後遺失）。"
                    )
                _init_db()
                _client = _SqliteSupabase()
                logger.warning("Supabase creds present but no client lib — falling back to SQLite")
        else:
            if is_serverless:
                raise RuntimeError(
                    "Serverless 環境（Vercel / Lambda）必須設定 SUPABASE_URL 與 SUPABASE_KEY。"
                    "在 /tmp/ 上的 SQLite 是 ephemeral，會造成註冊後帳號隨機消失。"
                    "請到 Vercel Dashboard → Project → Settings → Environment Variables 設定憑證。"
                )
            _init_db()
            _client = _SqliteSupabase()
            logger.info("Using SQLite database (local)")
    return _client
