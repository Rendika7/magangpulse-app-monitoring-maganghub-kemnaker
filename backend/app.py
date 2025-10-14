from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, List
from .models import list_lowongan, list_perusahaan, list_home, list_distinct_options, list_options

app = FastAPI(title="MagangPulse API", version="1.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/home")
def api_home():
    stats, timeline = list_home()
    return {"stats": stats, "timeline": timeline}

@app.get("/api/options")
def api_options():
    return list_options()

@app.get("/api/lowongan")
def api_lowongan(
    page: int = 1,
    page_size: int = 20,
    query: Optional[str] = None,
    perusahaan: Optional[List[str]] = Query(None),
    lokasi: Optional[List[str]] = Query(None),
    sektor: Optional[List[str]] = Query(None),
    min_ar: Optional[float] = Query(None, ge=0.0, le=1.0),
    max_ar: Optional[float] = Query(None, ge=0.0, le=1.0),
    min_pelamar: Optional[int] = None,
    max_pelamar: Optional[int] = None,
    min_kuota: Optional[int] = None,
    max_kuota: Optional[int] = None,
    sort: str = "recent"
):
    items, total = list_lowongan(page, page_size, query, perusahaan, lokasi, sektor,
                                 min_ar, max_ar, min_pelamar, max_pelamar,
                                 min_kuota, max_kuota, sort)
    return {"data": items, "total": total, "page": page, "page_size": page_size, "snapshot": True}

@app.get("/api/perusahaan")
def api_perusahaan(sort: str = "ar_desc", page: int = 1, page_size: int = 50):
    items, total = list_perusahaan(sort, page, page_size)
    return {"data": items, "total": total, "page": page, "page_size": page_size, "snapshot": True}


# ===== DEBUG: lihat DB yang dipakai API =====
@app.get("/api/_debug/db")
def api_debug_db():
    from .settings import settings
    use_pg = bool(settings.DATABASE_URL)

    # mask password biar aman saat dilihat di browser/log
    db_url = settings.DATABASE_URL
    if db_url:
        try:
            # potong bagian kredensial sebelum '@'
            cred, rest = db_url.split("@", 1)
            proto = cred.split("://", 1)[0]
            db_url = f"{proto}://***:***@{rest}"
        except Exception:
            db_url = "postgresql://***:***@…"

    return {"use_postgres": use_pg, "db_url": db_url}

@app.get("/api/options")
def api_options():
    """
    Daftar unik opsi untuk dropdown (perusahaan, lokasi, sektor/program studi).
    """
    return list_distinct_options()