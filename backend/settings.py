# backend/settings.py
from dotenv import load_dotenv
# Baca .env dari CWD (root project) lebih dulu
load_dotenv()

from pydantic import BaseModel
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
# (opsional) jika ada backend/.env juga ikut dibaca tanpa menimpa yg sudah ada
load_dotenv(BASE_DIR / ".env")

def _as_bool(v: str, default=False) -> bool:
    if v is None:
        return default
    return str(v).strip().lower() in {"1", "true", "yes", "y", "on"}

def _sanitize_ua(ua: str) -> str:
    if not ua:
        return ua
    ua = ua.strip()
    if (ua.startswith('"') and ua.endswith('"')) or (ua.startswith("'") and ua.endswith("'")):
        ua = ua[1:-1]
    return ua

class Settings(BaseModel):
    BASE_URL: str = os.getenv("BASE_URL", "https://maganghub.kemnaker.go.id/lowongan")

    # sqlite fallback path (diabaikan bila DATABASE_URL ada)
    DB_PATH: str = os.getenv(
        "DB_PATH",
        os.path.abspath(os.path.join(os.path.dirname(__file__), "data.sqlite"))
    )

    # Postgres (Neon) URL
    DATABASE_URL: str | None = os.getenv("DATABASE_URL")

    USER_AGENT: str = _sanitize_ua(os.getenv("USER_AGENT", "MagangPulse/1.0 (+https://example.local)"))
    REQUEST_TIMEOUT: int = int(os.getenv("REQUEST_TIMEOUT", "20"))
    THROTTLE_SECONDS: float = float(os.getenv("THROTTLE_SECONDS", "1.0"))
    MAX_PAGES: int = int(os.getenv("MAX_PAGES", "20"))
    USE_PLAYWRIGHT: bool = _as_bool(os.getenv("USE_PLAYWRIGHT"), default=False)

    # ==== ⬇️ Tambahan yang dipakai di enrichment/listing detail ====
    DETAIL_ENRICH: bool = _as_bool(os.getenv("DETAIL_ENRICH"), default=True)
    DETAIL_MAX: int = int(os.getenv("DETAIL_MAX", "400"))
    DETAIL_WORKERS: int = int(os.getenv("DETAIL_WORKERS", "6"))
    # opsional: kalau mau pakai browser khusus untuk halaman detail
    USE_PLAYWRIGHT_DETAIL: bool = _as_bool(
        os.getenv("USE_PLAYWRIGHT_DETAIL"),
        # fallback ke USE_PLAYWRIGHT bila tidak diset
        default=_as_bool(os.getenv("USE_PLAYWRIGHT"), False))

settings = Settings()