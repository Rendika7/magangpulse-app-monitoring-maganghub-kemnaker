# backend/scraper/run_full_scrape.py
import os
from urllib.parse import urljoin
from datetime import datetime
from time import perf_counter  # + timing high-res

from backend.settings import settings
from backend.db import get_conn
from backend.models import (
    upsert_lowongan, recompute_perusahaan,
    upsert_site_stats, replace_timeline
)
from backend.scraper.fetch import fetch_html, fetch_listing_pages_playwright, fetch_detail_html
from backend.scraper.parse import (
    parse_listing_page, parse_total_lowongan,
    parse_home_stats, parse_timeline, parse_detail_program_studi, parse_detail_deskripsi
)

from dotenv import load_dotenv
load_dotenv()  # baca .env di root project

# =============== Timing utils ===============
def fmt_dur(sec: float) -> str:
    """Format durasi: 1h 23m 45.6s / 12m 03.2s / 4.2s"""
    sec = float(sec)
    if sec >= 3600:
        h = int(sec // 3600); m = int((sec % 3600) // 60); s = sec % 60
        return f"{h}h {m}m {s:0.1f}s"
    if sec >= 60:
        m = int(sec // 60); s = sec % 60
        return f"{m}m {s:05.2f}s"
    return f"{sec:0.2f}s"

class StepTimer:
    """Context manager untuk print durasi step dengan prefix [time]."""
    def __init__(self, label: str):
        self.label = label
        self.t0 = None
    def __enter__(self):
        self.t0 = perf_counter()
        print(f"[time] ▶ {self.label} …", flush=True)
        return self
    def __exit__(self, exc_type, exc, tb):
        dt = perf_counter() - self.t0
        status = "OK" if exc is None else "ERR"
        print(f"[time] ⏱ {self.label} [{status}] {fmt_dur(dt)}", flush=True)


def _schema_path():
    here = os.path.dirname(__file__)
    # pakai schema PG kalau DATABASE_URL ada
    if getattr(settings, "DATABASE_URL", None):
        return os.path.abspath(os.path.join(here, "..", "schema_postgres.sql"))
    return os.path.abspath(os.path.join(here, "..", "schema.sql"))

def init_db():
    schema = _schema_path()
    with open(schema, "r", encoding="utf-8") as f, get_conn(settings.DB_PATH) as conn:
        conn.executescript(f.read())


def _base_root():
    base = settings.BASE_URL.strip().rstrip("/")
    return base.split("/lowongan")[0] if "/lowongan" in base else base

def crawl_listing():
    base_root = _base_root()

    # total dari halaman 1 (untuk estimasi)
    first = fetch_html(f"{base_root}/lowongan")
    total_lowongan = parse_total_lowongan(first.html)

    all_rows, pages_html = [], []

    if settings.USE_PLAYWRIGHT:
        print("[STEP] 1/4 Pagination with Playwright…", flush=True)
        t_pag = perf_counter()
        pages_html = fetch_listing_pages_playwright(base_root, settings.MAX_PAGES)
        print(f"[time] Pagination collected {len(pages_html)} pages in {fmt_dur(perf_counter()-t_pag)}", flush=True)
    else:
        print("[WARN] Static mode: hanya ambil halaman 1.", flush=True)
        pages_html = [fetch_html(f"{base_root}/lowongan").html]

    # -------- Parse listing pages --------
    from hashlib import sha256
    print(f"[STEP] 2/4 Parsing {len(pages_html)} pages into cards…", flush=True)
    t_parse = perf_counter()                                      
    for pi, html in enumerate(pages_html, 1):        
        rows = parse_listing_page(html)
        for r in rows:
            if r.get("source_url", "").startswith("/"):
                r["source_url"] = urljoin(base_root, r["source_url"])
            key = f"{r.get('judul')}|{r.get('perusahaan')}|{r.get('pelamar')}|{r.get('kuota')}|{r.get('tanggal_posting')}"
            r["content_hash"] = sha256(key.encode("utf-8")).hexdigest()
        all_rows.extend(rows)
        if pi % 10 == 0 or pi == len(pages_html):
            print(f"[INFO]  … parsed pages {pi}/{len(pages_html)} (cards so far: {len(all_rows)})", flush=True)

    print(f"[time] Parsed listing cards total: {len(all_rows)} in {fmt_dur(perf_counter()-t_parse)}", flush=True)  # +

    # -------- ENRICH (Program Studi) --------
    if getattr(settings, "DETAIL_ENRICH", True) and all_rows:
        from concurrent.futures import ThreadPoolExecutor, as_completed
        limit   = min(getattr(settings, "DETAIL_MAX", 400), len(all_rows))
        workers = max(1, getattr(settings, "DETAIL_WORKERS", 6))
        print(f"[STEP] 3/4 Enrich detail pages: limit={limit}, workers={workers}, playwright_detail={getattr(settings,'USE_PLAYWRIGHT_DETAIL', False)}", flush=True)

        def enrich_one(r):
            url = r.get("source_url")
            if not url:
                return r
            try:
                det = fetch_detail_html(url)
                # Program Studi
                prodi_list = parse_detail_program_studi(det.html) or []
                if prodi_list:
                    r["sektor"] = "; ".join(prodi_list)

                # Deskripsi (baru!)
                desc = parse_detail_deskripsi(det.html)
                if desc:
                    # batasi agar tidak terlalu panjang (opsional)
                    r["deskripsi_short"] = desc[:1200]
            except Exception:
                pass
            return r
        
        # === ENRICH: Program Studi (sektor) dari halaman detail ===
        # Aman: batasi jumlah parallelism implicit (disini sequential; bisa diparalelkan jika perlu)
        # Ikuti throttle global via settings.THROTTLE_SECONDS (sudah diterapkan di fetch requests).
            
        t_enrich = perf_counter()
        enriched = []
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futures = [ex.submit(enrich_one, all_rows[i]) for i in range(limit)]
            done = 0
            for fut in as_completed(futures):
                enriched.append(fut.result())
                done += 1
                if done % 50 == 0 or done == limit:               
                    elapsed = perf_counter() - t_enrich           
                    rate = done / elapsed if elapsed > 0 else 0.0
                    print(f"[INFO]  … detail done {done}/{limit} • {rate:0.2f} jobs/s • elapsed {fmt_dur(elapsed)}", flush=True)

        dt_enrich = perf_counter() - t_enrich
        all_rows = enriched + all_rows[limit:]        
        n_with = sum(1 for r in all_rows[:limit] if (r.get("sektor") or "").strip())
        print(f"[time] Enrichment complete: with_prodi={n_with}/{limit} in {fmt_dur(dt_enrich)}", flush=True)
    else:
        print("[INFO] Detail enrichment disabled or no rows.", flush=True)

    return all_rows, total_lowongan

def crawl_home():
    base_root = _base_root()
    res = fetch_html(f"{base_root}/")
    perusahaan, lamaran = parse_home_stats(res.html)
    timeline = parse_timeline(res.html)
    return perusahaan, lamaran, timeline

def main():
    t_all = perf_counter()  # + total wall-time
    from backend.settings import settings
    print(f"[cfg] MAX_PAGES={settings.MAX_PAGES} | DETAIL_MAX={getattr(settings,'DETAIL_MAX',None)} | "
        f"DETAIL_ENRICH={getattr(settings,'DETAIL_ENRICH',None)} | WORKERS={getattr(settings,'DETAIL_WORKERS',None)}",
        flush=True)
    print("[STEP] 0/4 Init DB schema…", flush=True)
    
    
    with StepTimer("Init DB schema"):                      
        init_db()

    print("[STEP] 1/4 Crawl listing (pagination + parsing)…", flush=True)
    with StepTimer("Crawl listing (pagination + parsing + enrich)"):  
        rows, total_low = crawl_listing()
        print(f"[INFO] Crawl complete. Rows parsed: {len(rows)} • Est. total_lowongan: {total_low}", flush=True)

    print("[STEP] 2/4 Upsert listing → DB…", flush=True)
    with StepTimer("Upsert listing & recompute perusahaan"):           
        upsert_lowongan(rows)
        recompute_perusahaan()
        print("[INFO] Upsert & recompute_perusahaan selesai.", flush=True)

    print("[STEP] 3/4 Fetch home stats & timeline…", flush=True)
    with StepTimer("Fetch home stats & timeline + upsert"):            
        perusahaan, lamaran, tl = crawl_home()
        upsert_site_stats(
            jumlah_perusahaan=perusahaan,
            jumlah_lamaran=lamaran,
            total_lowongan=total_low,
            fetched_at=datetime.utcnow().isoformat()
        )
        if tl:
            replace_timeline(tl)
        print("[INFO] Home stats & timeline disimpan.", flush=True)

    # ---- LOG VERIFIKASI ENRICHMENT (tetap seperti punyamu) ----
    n_with_prodi = sum(1 for r in rows if (r.get("sektor") or "").strip() != "")
    print(
        f"[SUMMARY] Lowongan upserted: {len(rows)} | total_lowongan={total_low} | "
        f"perusahaan={perusahaan} | lamaran={lamaran} | timeline_items={len(tl or [])} | "
        f"dengan_ProgramStudi={n_with_prodi}",
        flush=True
    )

    try:
        import pandas as pd
        df = pd.DataFrame(rows, columns=[
            "judul","perusahaan","lokasi","sektor","tanggal_posting","pelamar","kuota","source_url"
        ])
        print("\n=== SAMPLE HASIL SCRAPE (head) ===", flush=True)
        print(df.head(12).to_string(index=False), flush=True)
        # ringkasan unik prodi (10 contoh)
        semua_prodi = []
        for s in df["sektor"].dropna():
            for p in str(s).split(";"):
                p = p.strip()
                if p: semua_prodi.append(p)
        top = pd.Series(semua_prodi).value_counts().head(10) if semua_prodi else None
        if top is not None:
            print("\nTop Program Studi (contoh):", flush=True)
            print(top.to_string(), flush=True)
    except Exception as e:
        # fallback simple print jika pandas tidak ada
        print("\n(pandas tidak tersedia / gagal cetak head, fallback list 5 baris)", flush=True)
        for i, r in enumerate(rows[:3], 1):
            print(f"[{i}] {r.get('judul')} | {r.get('perusahaan')} | {r.get('lokasi')} | sektor={r.get('sektor')}", flush=True)

    print(f"[DONE] 4/4 All tasks finished ✅ • total wall time {fmt_dur(perf_counter()-t_all)}", flush=True)

if __name__ == "__main__":
    main()