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

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

_client = None

# ─── SQLite DB path ──────────────────────────────────────────
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "md_piece.db")

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
        self._conditions.append(f'"{col}" = ?')
        self._params.append(val)
        return self

    def neq(self, col, val):
        self._conditions.append(f'"{col}" != ?')
        self._params.append(val)
        return self

    def gte(self, col, val):
        self._conditions.append(f'"{col}" >= ?')
        self._params.append(val)
        return self

    def lte(self, col, val):
        self._conditions.append(f'"{col}" <= ?')
        self._params.append(val)
        return self

    def ilike(self, col, val):
        self._conditions.append(f'"{col}" LIKE ? COLLATE NOCASE')
        self._params.append(val)
        return self

    def order(self, col, desc=False, **kwargs):
        self._order_col = col
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
        sql = f'SELECT * FROM "{self._table}"{where}'
        if self._order_col:
            direction = "DESC" if self._order_desc else "ASC"
            sql += f' ORDER BY "{self._order_col}" {direction}'
        if self._limit_n:
            sql += f" LIMIT {self._limit_n}"

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
                fk_col = f"{ref_table[:-1]}_id" if ref_table.endswith("s") else f"{ref_table}_id"
                fk_val = row.get(fk_col)
                if fk_val:
                    ref_row = conn.execute(
                        f'SELECT * FROM "{ref_table}" WHERE id = ?', (fk_val,)
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
        cols = ', '.join(f'"{k}"' for k in serialized.keys())
        placeholders = ', '.join('?' for _ in serialized)
        sql = f'INSERT INTO "{self._table}" ({cols}) VALUES ({placeholders})'
        conn.execute(sql, list(serialized.values()))
        conn.commit()
        return _SqliteResult([data])

    def _exec_update(self, conn):
        data = self._update_data
        if not data:
            return _SqliteResult([])

        serialized = {k: self._serialize_value(v) for k, v in data.items()}
        set_clause = ', '.join(f'"{k}" = ?' for k in serialized.keys())
        set_params = list(serialized.values())
        where, where_params = self._where_clause()
        sql = f'UPDATE "{self._table}" SET {set_clause}{where}'
        conn.execute(sql, set_params + where_params)
        conn.commit()

        select_sql = f'SELECT * FROM "{self._table}"{where}'
        rows = conn.execute(select_sql, where_params).fetchall()
        return _SqliteResult([self._deserialize_row(dict(r)) for r in rows])

    def _exec_delete(self, conn):
        where, params = self._where_clause()
        select_sql = f'SELECT * FROM "{self._table}"{where}'
        rows = conn.execute(select_sql, params).fetchall()
        data = [self._deserialize_row(dict(r)) for r in rows]

        sql = f'DELETE FROM "{self._table}"{where}'
        conn.execute(sql, params)
        conn.commit()
        return _SqliteResult(data)


class _SqliteSupabase:
    """Drop-in replacement for Supabase client using SQLite."""
    def table(self, name):
        return _SqliteQuery(name)


# ─── Public API ───────────────────────────────────────────────

def get_supabase():
    """取得資料庫 client。有 Supabase 憑證用 Supabase，否則用 SQLite。"""
    global _client
    if _client is None:
        if _supabase_available and SUPABASE_URL and SUPABASE_KEY:
            _client = create_client(SUPABASE_URL, SUPABASE_KEY)
            logger.info("Connected to Supabase")
        else:
            _init_db()
            _client = _SqliteSupabase()
            logger.info("Using SQLite database (local)")
    return _client
