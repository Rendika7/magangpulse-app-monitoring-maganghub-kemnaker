from typing import List, Optional, Tuple, Sequence
from .db import get_conn
from .settings import settings

def upsert_lowongan(rows: List[dict]):
    if not rows:
        return 0
    with get_conn(settings.DB_PATH) as conn:
        cur = conn.cursor()
        q = """
        INSERT INTO lowongan(
            external_id, source_url, judul, perusahaan, lokasi, sektor,
            tanggal_posting, pelamar, kuota, acceptance_rate, demand_ratio,
            velocity_pelamar_per_day, status, deskripsi_short, fetched_at, content_hash
        ) VALUES (:external_id, :source_url, :judul, :perusahaan, :lokasi, :sektor,
                  :tanggal_posting, :pelamar, :kuota, :acceptance_rate, :demand_ratio,
                  :velocity_pelamar_per_day, :status, :deskripsi_short, :fetched_at, :content_hash)
        ON CONFLICT(source_url) DO UPDATE SET
            judul=excluded.judul,
            perusahaan=excluded.perusahaan,
            lokasi=excluded.lokasi,
            sektor=excluded.sektor,
            tanggal_posting=excluded.tanggal_posting,
            pelamar=excluded.pelamar,
            kuota=excluded.kuota,
            acceptance_rate=excluded.acceptance_rate,
            demand_ratio=excluded.demand_ratio,
            velocity_pelamar_per_day=excluded.velocity_pelamar_per_day,
            status=excluded.status,
            deskripsi_short=excluded.deskripsi_short,
            fetched_at=excluded.fetched_at,
            content_hash=excluded.content_hash;
        """
        cur.executemany(q, rows)
        return cur.rowcount

def recompute_perusahaan():
    with get_conn(settings.DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM perusahaan;")
        q = """
        INSERT INTO perusahaan(nama, lokasi, sektor, n_lowongan_aktif, kuota_total, pelamar_total,
                               ar_rata2, dr_rata2, source_url, fetched_at)
        SELECT perusahaan as nama,
               NULL as lokasi,
               NULL as sektor,
               SUM(CASE WHEN status='open' THEN 1 ELSE 0 END) as n_lowongan_aktif,
               SUM(COALESCE(kuota,0)) as kuota_total,
               SUM(COALESCE(pelamar,0)) as pelamar_total,
               AVG(acceptance_rate) as ar_rata2,
               AVG(demand_ratio) as dr_rata2,
               MIN(source_url) as source_url,
               MAX(fetched_at) as fetched_at
        FROM lowongan
        GROUP BY perusahaan;
        """
        cur.execute(q)
        return cur.rowcount

# NEW: site stats & timeline
def upsert_site_stats(
    jumlah_perusahaan=None,
    jumlah_lamaran=None,
    total_lowongan=None,
    fetched_at=None
):
    use_pg = bool(settings.DATABASE_URL)

    with get_conn(settings.DB_PATH) as conn:
        cur = conn.cursor()

        # ensure row id=1 exists (PG vs SQLite syntax)
        if use_pg:
            cur.execute("INSERT INTO site_stats(id) VALUES(1) ON CONFLICT (id) DO NOTHING")
        else:
            cur.execute("INSERT OR IGNORE INTO site_stats(id) VALUES(1)")

        # update using named params (works for both sqlite & our psycopg wrapper)
        cur.execute(
            """
            UPDATE site_stats SET
              jumlah_perusahaan = COALESCE(:jumlah_perusahaan, jumlah_perusahaan),
              jumlah_lamaran    = COALESCE(:jumlah_lamaran,    jumlah_lamaran),
              total_lowongan    = COALESCE(:total_lowongan,    total_lowongan),
              fetched_at        = COALESCE(:fetched_at,        fetched_at)
            WHERE id = 1
            """,
            {
                "jumlah_perusahaan": jumlah_perusahaan,
                "jumlah_lamaran": jumlah_lamaran,
                "total_lowongan": total_lowongan,
                "fetched_at": fetched_at,
            },
        )
        return cur.rowcount

def replace_timeline(items: List[dict]):
    with get_conn(settings.DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM program_timeline;")
        cur.executemany(
            """
            INSERT INTO program_timeline(batch, title, start_date, end_date, status, order_index)
            VALUES(:batch, :title, :start_date, :end_date, :status, :order_index)
            """,
            items,
        )
        return cur.rowcount

def list_home():
    with get_conn(settings.DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM site_stats WHERE id=1")
        stats = dict(cur.fetchone() or {})
        cur.execute("SELECT * FROM program_timeline ORDER BY order_index ASC, id ASC")
        timeline = [dict(r) for r in cur.fetchall()]
        return stats, timeline

def _read_count_row(row):
    """Row bisa tuple/sqlite Row/dict_row → kembalikan integer count."""
    if row is None:
        return 0
    # tuple/list
    if isinstance(row, (tuple, list)):
        return int(row[0])
    # mapping (sqlite Row mapping / psycopg dict_row)
    if hasattr(row, "get"):
        # pakai alias 'cnt' kalau ada; kalau tidak ambil nilai pertama
        return int(row.get("cnt")) if row.get("cnt") is not None else int(next(iter(row.values())))
    # fallback sangat jarang
    return int(list(row)[0])

def list_lowongan(
    page: int = 1,
    page_size: int = 20,
    query: Optional[str] = None,
    perusahaan: Optional[Sequence[str]] = None,
    lokasi: Optional[Sequence[str]] = None,
    sektor: Optional[Sequence[str]] = None,
    min_ar: Optional[float] = None,
    max_ar: Optional[float] = None,
    min_pelamar: Optional[int] = None,
    max_pelamar: Optional[int] = None,
    min_kuota: Optional[int] = None,
    max_kuota: Optional[int] = None,
    sort: str = "recent"
):
    where = ["1=1"]
    params = {}
    if query:
        where.append("(LOWER(judul) LIKE :q OR LOWER(perusahaan) LIKE :q)")
        params["q"] = f"%{query.lower()}%"

    def add_in(field: str, values: Optional[Sequence[str]], key_prefix: str):
        if values:
            vals = [v for v in values if (v is not None and str(v).strip() != "")]
            if vals:
                placeholders = []
                for i, v in enumerate(vals):
                    k = f"{key_prefix}{i}"
                    placeholders.append(f":{k}")
                    params[k] = v
                where.append(f"{field} IN ({', '.join(placeholders)})")

    add_in("perusahaan", perusahaan, "perusahaan_")
    add_in("lokasi", lokasi, "lokasi_")

    if sektor:
        like_parts = []
        for i, v in enumerate([s for s in sektor if s and str(s).strip() != ""]):
            k = f"sektor_like_{i}"
            like_parts.append(f"LOWER(sektor) LIKE :{k}")
            params[k] = f"%{str(v).lower()}%"
        if like_parts:
            where.append("(" + " OR ".join(like_parts) + ")")

    if min_ar is not None:
        where.append("acceptance_rate >= :min_ar"); params["min_ar"] = min_ar
    if max_ar is not None:
        where.append("acceptance_rate <= :max_ar"); params["max_ar"] = max_ar
    if min_pelamar is not None:
        where.append("pelamar >= :min_pelamar"); params["min_pelamar"] = min_pelamar
    if max_pelamar is not None:
        where.append("pelamar <= :max_pelamar"); params["max_pelamar"] = max_pelamar
    if min_kuota is not None:
        where.append("kuota >= :min_kuota"); params["min_kuota"] = min_kuota
    if max_kuota is not None:
        where.append("kuota <= :max_kuota"); params["max_kuota"] = max_kuota

    USE_PG = bool(settings.DATABASE_URL)
    sort_recent = "fetched_at DESC" if USE_PG else "datetime(fetched_at) DESC"
    sort_map = {
        "recent": sort_recent,
        "ar_desc": "acceptance_rate DESC",
        "ar_asc": "acceptance_rate ASC",
        "pelamar_desc": "pelamar DESC",
        "pelamar_asc": "pelamar ASC",
        "kuota_desc": "kuota DESC",
        "kuota_asc": "kuota ASC",
    }
    order = sort_map.get(sort, sort_map["recent"])
    offset = (page - 1) * page_size

    with get_conn(settings.DB_PATH) as conn:
        cur = conn.cursor()
        # ⚠️ pakai alias agar key di dict_row konsisten
        total_q = f"SELECT COUNT(*) AS cnt FROM lowongan WHERE {' AND '.join(where)}"
        cur.execute(total_q, params)
        total = _read_count_row(cur.fetchone())

        q = f"SELECT * FROM lowongan WHERE {' AND '.join(where)} ORDER BY {order} LIMIT :limit OFFSET :offset"
        cur.execute(q, {**params, "limit": page_size, "offset": offset})
        rows = [dict(r) for r in cur.fetchall()]
        return rows, total


def list_perusahaan(sort: str = "ar_desc", page: int = 1, page_size: int = 50):
    sort_map = {
        "ar_desc": "ar_rata2 DESC",
        "ar_asc": "ar_rata2 ASC",
        "pelamar_desc": "pelamar_total DESC",
        "pelamar_asc": "pelamar_total ASC",
        "kuota_desc": "kuota_total DESC",
        "kuota_asc": "kuota_total ASC",
        "aktif_desc": "n_lowongan_aktif DESC",
        "aktif_asc": "n_lowongan_aktif ASC",
    }
    order = sort_map.get(sort, sort_map["ar_desc"])
    offset = (page - 1) * page_size

    with get_conn(settings.DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) AS cnt FROM perusahaan")
        total = _read_count_row(cur.fetchone())

        q = f"SELECT * FROM perusahaan ORDER BY {order} LIMIT :limit OFFSET :offset"
        cur.execute(q, {"limit": page_size, "offset": offset})
        rows = [dict(r) for r in cur.fetchall()]
        return rows, total
    
    
# === Distinct options for dropdowns (lokasi, sektor, perusahaan) ===
def _read_scalar(row, key_or_idx=0):
    """
    Ambil nilai kolom tunggal dari row (kompatibel sqlite Row / tuple / psycopg dict_row).
    """
    # psycopg dict_row / dict-like
    if hasattr(row, "get"):
        if isinstance(key_or_idx, str) and row.get(key_or_idx) is not None:
            return row.get(key_or_idx)
        # fallback: ambil nilai pertama
        try:
            return next(iter(row.values()))
        except Exception:
            pass
    # sqlite Row / tuple / list
    try:
        return row[key_or_idx]
    except Exception:
        try:
            return list(row)[0]
        except Exception:
            return None


def list_distinct_options():
    """
    Kembalikan daftar unik untuk dropdown:
    - perusahaan: DISTINCT perusahaan
    - lokasi    : DISTINCT lokasi
    - sektor    : split ';' dari semua baris yang punya sektor
    """
    with get_conn(settings.DB_PATH) as conn:
        cur = conn.cursor()

        # Perusahaan
        cur.execute("SELECT DISTINCT perusahaan FROM lowongan WHERE perusahaan IS NOT NULL AND perusahaan <> ''")
        perusahaan = sorted({str(_read_scalar(r, "perusahaan") or _read_scalar(r, 0)).strip()
                             for r in cur.fetchall() if _read_scalar(r, "perusahaan") or _read_scalar(r, 0)})

        # Lokasi
        cur.execute("SELECT DISTINCT lokasi FROM lowongan WHERE lokasi IS NOT NULL AND lokasi <> ''")
        lokasi = sorted({str(_read_scalar(r, "lokasi") or _read_scalar(r, 0)).strip()
                         for r in cur.fetchall() if _read_scalar(r, "lokasi") or _read_scalar(r, 0)})

        # Sektor / Program Studi (split ';')
        cur.execute("SELECT sektor FROM lowongan WHERE sektor IS NOT NULL AND sektor <> ''")
        sektor_tokens = set()
        for r in cur.fetchall():
            val = _read_scalar(r, "sektor") or _read_scalar(r, 0)
            if not val:
                continue
            for tok in str(val).split(";"):
                t = tok.strip()
                if t:
                    sektor_tokens.add(t)
        sektor = sorted(sektor_tokens)

    return {
        "perusahaan": perusahaan,
        "lokasi": lokasi,
        "sektor": sektor,
    }

# === OPTIONS untuk dropdown (lokasi, sektor/prodi, perusahaan) ===
def list_options():
    lokasi_set = set()
    sektor_set = set()
    perusahaan_set = set()

    with get_conn(settings.DB_PATH) as conn:
        cur = conn.cursor()

        # Lokasi (distinct)
        cur.execute("SELECT DISTINCT lokasi FROM lowongan WHERE lokasi IS NOT NULL AND TRIM(lokasi) <> ''")
        for r in cur.fetchall():
            v = (r["lokasi"] if isinstance(r, dict) else r[0]) or ""
            v = str(v).strip()
            if v:
                lokasi_set.add(v.upper())

        # Perusahaan (distinct)
        cur.execute("SELECT DISTINCT perusahaan FROM lowongan WHERE perusahaan IS NOT NULL AND TRIM(perusahaan) <> ''")
        for r in cur.fetchall():
            v = (r["perusahaan"] if isinstance(r, dict) else r[0]) or ""
            v = str(v).strip()
            if v:
                perusahaan_set.add(v)

        # Sektor / Program Studi: simpan “A; B; C” → pecah jadi item
        cur.execute("SELECT sektor FROM lowongan WHERE sektor IS NOT NULL AND TRIM(sektor) <> ''")
        for r in cur.fetchall():
            s = (r["sektor"] if isinstance(r, dict) else r[0]) or ""
            for part in str(s).split(";"):
                p = part.strip()
                if p:
                    sektor_set.add(p)

    # urutkan biar rapi/terprediksi
    lokasi = sorted(lokasi_set)
    sektor = sorted(sektor_set)
    perusahaan = sorted(perusahaan_set)
    return {"lokasi": lokasi, "sektor": sektor, "perusahaan": perusahaan}