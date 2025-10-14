# prototype_playwright_check.py
"""
Prototype sanity-check untuk scraping MagangHub:
- Render listing dengan Playwright (multi-halaman)
- Ambil perusahaan, judul, lokasi, tanggal, pelamar/kuota, URL detail
- (Opsional) masuk ke halaman detail untuk ambil 'Program Studi'
- Simpan debug HTML, preview 5 baris pertama, dan ringkasan unik

Cara pakai (contoh):
  python prototype_playwright_check.py
  python prototype_playwright_check.py --pages 3 --details 20 --delay 0.8
  python prototype_playwright_check.py --json out.json --csv out.csv

Catatan:
- Script ini hanya untuk testing cepat. Untuk produksi pakai modul backend/scraper yang sudah kamu tulis.
"""

import re
import time
import json
import csv
import argparse
from collections import Counter
from urllib.parse import urljoin
from pathlib import Path
from typing import List, Dict, Optional

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

BASE_ROOT = "https://maganghub.kemnaker.go.id"
LIST_URL = f"{BASE_ROOT}/lowongan"

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/140.0.0.0 Safari/537.36"
)

NUM_ID_RX   = re.compile(r"(\d{1,3}(?:\.\d{3})+|\d+)")
P_RX        = re.compile(r"(\d[\d\.]*)\s*pelamar", re.I)
K_RX        = re.compile(r"(\d[\d\.]*)\s*(kebutuhan|kuota)", re.I)
LOC_HINT_RX = re.compile(r"\b(KOTA|KAB\.?|KABUPATEN|PROV\.?|PROVINSI)\b", re.I)

MONTH_MAP = {
    "Januari":"01","Februari":"02","Maret":"03","April":"04","Mei":"05","Juni":"06",
    "Juli":"07","Agustus":"08","September":"09","Oktober":"10","November":"11","Desember":"12",
    "Jan":"01","Feb":"02","Mar":"03","Apr":"04","Mei":"05","Jun":"06","Jul":"07","Agu":"08",
    "Sep":"09","Okt":"10","Nov":"11","Des":"12"
}

def to_int_id(num_text: Optional[str]) -> Optional[int]:
    if not num_text: return None
    m = NUM_ID_RX.search(num_text)
    if not m: return None
    return int(m.group(1).replace(".", ""))

def id_date_to_iso(text: Optional[str]) -> Optional[str]:
    # "3 Oktober 2025" -> "2025-10-03"
    if not text: return None
    parts = text.strip().split()
    if len(parts) == 3 and parts[1] in MONTH_MAP:
        d, m, y = parts
        try:
            return f"{y}-{MONTH_MAP[m]}-{int(d):02d}"
        except Exception:
            return None
    return None

def get_rendered_html(page, url: str, wait_selectors: List[str], delay_after_scroll: float = 0.6) -> str:
    page.goto(url, timeout=90_000, wait_until="networkidle")
    # Tunggu salah satu selector muncul
    for sel in wait_selectors:
        try:
            page.wait_for_selector(sel, timeout=15_000)
            break
        except PWTimeout:
            continue
    # Nudge lazy-load
    for _ in range(3):
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(delay_after_scroll)
    return page.content()

def parse_listing_page(html: str) -> List[Dict]:
    soup = BeautifulSoup(html, "lxml")
    items: List[Dict] = []

    for a in soup.select("a.v-card.v-card--flat.v-card--link[href*='/lowongan/view/']"):
        href = a.get("href", "")
        source_url = urljoin(BASE_ROOT, href) if href else None

        company_el = a.select_one("h6.text-h6") or a.select_one("h6")
        title_el   = a.select_one("h5.text-h5") or a.select_one("h5")

        # Lokasi (div kecil berisi KAB/KOTA, PROVINSI)
        lokasi = None
        for div in a.find_all("div"):
            txt = (div.get_text(strip=True) or "")
            if not txt: 
                continue
            style = (div.get("style") or "").lower()
            if ("font-size" in style and ("," in txt or LOC_HINT_RX.search(txt))):
                lokasi = txt; break
        if not lokasi and company_el:
            sib = company_el.find_next("div")
            if sib:
                txt = sib.get_text(strip=True) or ""
                if ("," in txt or LOC_HINT_RX.search(txt)):
                    lokasi = txt
        if lokasi:
            lokasi = re.sub(r"\s*,\s*", " , ", lokasi).strip()

        # Tanggal
        tanggal_iso = None
        cal_icon = a.select_one(".tabler-calendar")
        if cal_icon:
            span = cal_icon.find_next("span")
            if span:
                tanggal_iso = id_date_to_iso(span.get_text(strip=True))

        # Pelamar / Kebutuhan
        pelamar = kuota = None
        users_icon = a.select_one(".tabler-users")
        if users_icon:
            span = users_icon.find_next("span")
            if span:
                info = span.get_text(" ", strip=True)
                mp = P_RX.search(info); mk = K_RX.search(info)
                if mp: pelamar = to_int_id(mp.group(1))
                if mk: kuota   = to_int_id(mk.group(1))

        items.append({
            "source_url": source_url,
            "perusahaan": company_el.get_text(strip=True) if company_el else None,
            "judul":      title_el.get_text(strip=True)   if title_el   else None,
            "lokasi":     lokasi,
            "tanggal":    tanggal_iso,
            "pelamar":    pelamar,
            "kuota":      kuota,
            "sektor":     None,  # akan di-enrich dari detail
        })
    return items

def parse_detail_program_studi(html: str) -> List[str]:
    soup = BeautifulSoup(html, "lxml")
    # Cari label "Program Studi"
    label = None
    for lab in soup.find_all(["label", "div", "span"], string=re.compile(r"^\s*Program Studi\s*$", re.I)):
        label = lab; break
    if not label: 
        return []
    # Cari container chip di sekitar label (common Vuetify layout)
    container = None
    for anc in [label.parent, getattr(label, "find_parent", lambda *_:None)("div")]:
        if not anc: 
            continue
        cand = anc.find(class_=re.compile(r"flex-wrap|gap-2", re.I))
        if cand:
            container = cand; break
    if not container:
        container = soup.find(class_=re.compile(r"flex-wrap|gap-2", re.I))
    if not container:
        return []

    prodi = []
    for chip in container.find_all(class_=re.compile(r"v-chip__content")):
        t = chip.get_text(strip=True)
        if t and t not in prodi:
            prodi.append(t)
    return prodi

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", type=int, default=2, help="Maks halaman listing yang di-scan (default: 2)")
    ap.add_argument("--details", type=int, default=20, help="Maks detail pages yang di-enrich (default: 20)")
    ap.add_argument("--delay", type=float, default=0.6, help="Delay scroll / antar navigasi (default: 0.6s)")
    ap.add_argument("--json",  type=str, default="", help="Path simpan JSON hasil (optional)")
    ap.add_argument("--csv",   type=str, default="", help="Path simpan CSV hasil (optional)")
    args = ap.parse_args()

    all_rows: List[Dict] = []
    debug_dir = Path("debug_proto"); debug_dir.mkdir(exist_ok=True)

    with sync_playwright() as p:
        # gunakan firefox kalau chromium kadang ke-block
        try:
            browser = p.firefox.launch(headless=True)
        except Exception:
            browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(user_agent=UA, viewport={"width":1366,"height":900})
        page = ctx.new_page()

        # ====== 1) Crawl listing multi-halaman
        print(f"[INFO] Open listing: {LIST_URL}")
        page.goto(LIST_URL, timeout=90_000, wait_until="networkidle")
        time.sleep(args.delay)

        for i in range(args.pages):
            print(f"[INFO] Capture listing page {i+1}")
            html = get_rendered_html(
                page,
                LIST_URL,
                wait_selectors=[
                    "a.v-card.v-card--flat.v-card--link[href*='/lowongan/view/']",
                    "text=Daftar Lowongan Magang",
                ],
                delay_after_scroll=args.delay
            )
            (debug_dir / f"listing_page_{i+1}.html").write_text(html, encoding="utf-8")
            rows = parse_listing_page(html)
            all_rows.extend(rows)

            # klik pagination next
            next_btn = page.locator("li.v-pagination__next button[aria-label='Next page']:not([disabled])")
            # fallback: numeric page
            if next_btn.count() > 0:
                next_btn.first.click()
                try:
                    page.wait_for_selector("a.v-card.v-card--flat.v-card--link[href*='/lowongan/view/']", timeout=20_000)
                except PWTimeout:
                    pass
                time.sleep(args.delay)
            else:
                # coba klik angka halaman berikutnya
                next_page_num = str(i + 2)
                btn = page.locator(f"li.v-pagination__item button:has-text('{next_page_num}')")
                if btn.count() > 0:
                    btn.first.click()
                    try:
                        page.wait_for_selector("a.v-card.v-card--flat.v-card--link[href*='/lowongan/view/']", timeout=20_000)
                    except PWTimeout:
                        pass
                    time.sleep(args.delay)
                else:
                    print("[INFO] No more pages; stop.")
                    break

        # ====== 2) Enrich Program Studi dari detail (maks N)
        print(f"[INFO] Enrich detail Program Studi (maks {args.details})…")
        count_detail = 0
        for r in all_rows:
            if count_detail >= args.details:
                break
            if not r.get("source_url"):
                continue
            try:
                page.goto(r["source_url"], timeout=90_000, wait_until="networkidle")
                time.sleep(args.delay)
                html = page.content()
                if count_detail < 3:  # simpan beberapa sampel detail
                    (debug_dir / f"detail_sample_{count_detail+1}.html").write_text(html, encoding="utf-8")
                prodi_list = parse_detail_program_studi(html) or []
                if prodi_list:
                    r["sektor"] = "; ".join(prodi_list)
            except Exception as e:
                # keep going
                pass
            count_detail += 1

        browser.close()

    # ====== 3) Ringkasan & preview
    print(f"\n[SUM] Total rows listing: {len(all_rows)}")
    print("[PREVIEW] 5 teratas:")
    for row in all_rows[:5]:
        print({
            "judul": row.get("judul"),
            "perusahaan": row.get("perusahaan"),
            "lokasi": row.get("lokasi"),
            "tanggal": row.get("tanggal"),
            "pelamar": row.get("pelamar"),
            "kuota": row.get("kuota"),
            "sektor": row.get("sektor"),
            "url": row.get("source_url"),
        })

    # hitung uniqueness sederhana
    perusahaan = [r.get("perusahaan") for r in all_rows if r.get("perusahaan")]
    lokasi     = [r.get("lokasi")     for r in all_rows if r.get("lokasi")]
    prodi_flat = []
    for r in all_rows:
        if r.get("sektor"):
            prodi_flat += [s.strip() for s in str(r["sektor"]).split(";") if s.strip()]

    print(f"\n[UNIQUE] Perusahaan: {len(set(perusahaan))} • Lokasi: {len(set(lokasi))} • Prodi (distinct): {len(set(prodi_flat))}")
    if prodi_flat:
        top_prodi = Counter(prodi_flat).most_common(10)
        print("[TOP Prodi] 10 terbanyak:", top_prodi)

    # ====== 4) Simpan JSON/CSV kalau diminta
    if args.json:
        Path(args.json).write_text(json.dumps(all_rows, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[SAVE] JSON -> {args.json}")
    if args.csv:
        cols = ["judul","perusahaan","lokasi","tanggal","pelamar","kuota","sektor","source_url"]
        with open(args.csv, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            for r in all_rows:
                w.writerow({k: r.get(k) for k in cols})
        print(f"[SAVE] CSV  -> {args.csv}")

    print(f"[DEBUG] HTML disimpan di folder: {debug_dir.resolve()}")
    print("[DONE] Prototype selesai.")

if __name__ == "__main__":
    main()
