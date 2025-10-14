# backend/db.py
import os, re
from contextlib import contextmanager
from pathlib import Path
from .settings import settings

USE_PG = bool(settings.DATABASE_URL)

# --- helper: konversi placeholder :name -> %(name)s (untuk psycopg) ---
# sebelumnya: _named_re = re.compile(r":([a-zA-Z_][a-zA-Z0-9_]*)")
_named_re = re.compile(r"(?<!:):([a-zA-Z_][a-zA-Z0-9_]*)")  # jangan match '::type'

def _convert_named(sql: str) -> str:
    return _named_re.sub(r"%(\1)s", sql)

if USE_PG:
    import psycopg
    from psycopg.rows import dict_row

    class _PgCursor:
        def __init__(self, cur):
            self._cur = cur
        def execute(self, sql, params=None):
            if isinstance(params, dict):
                sql = _convert_named(sql)
            return self._cur.execute(sql, params)
        def executemany(self, sql, seq_of_params):
            # seq_of_params bisa list[dict] atau list[tuple]
            # kalau dict, konversi placeholder
            if seq_of_params and isinstance(seq_of_params[0], dict):
                sql = _convert_named(sql)
            return self._cur.executemany(sql, seq_of_params)
        def fetchone(self): return self._cur.fetchone()
        def fetchall(self): return self._cur.fetchall()
        @property
        def rowcount(self): return self._cur.rowcount

    class _PgConn:
        def __init__(self, conn): self._conn = conn
        def cursor(self): return _PgCursor(self._conn.cursor())
        def commit(self): self._conn.commit()
        def close(self): self._conn.close()
        # sqlite kompat: executescript
        def executescript(self, script_text: str):
            # pecah di ';' yang simple; abaikan baris kosong/komentar
            stmts = []
            buff = []
            for line in script_text.splitlines():
                l = line.strip()
                if not l or l.startswith("--"):
                    continue
                buff.append(line)
                if l.endswith(";"):
                    stmts.append("\n".join(buff))
                    buff = []
            if buff:
                stmts.append("\n".join(buff))
            with self._conn.cursor() as c:
                for s in stmts:
                    c.execute(s)

    @contextmanager
    def get_conn(_db_path=None):
        conn = psycopg.connect(settings.DATABASE_URL, row_factory=dict_row, autocommit=False)
        try:
            yield _PgConn(conn)
            conn.commit()
        finally:
            conn.close()

else:
    import sqlite3
    DB_PATH = Path(__file__).with_name("data.sqlite")

    @contextmanager
    def get_conn(db_path=None):
        path = Path(db_path) if db_path else DB_PATH
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.commit()
            conn.close()
