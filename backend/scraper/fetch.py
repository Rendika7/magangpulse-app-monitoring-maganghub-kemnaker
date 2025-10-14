# backend/scraper/fetch.py
import time, math, re
import hashlib, requests
from ..settings import settings
from playwright.sync_api import sync_playwright
from .parse import parse_total_lowongan, parse_listing_page

HEADERS = {"User-Agent": settings.USER_AGENT}

class FetchResult:
    def __init__(self, url: str, html: str):
        self.url = url
        self.html = html
        self.hash = hashlib.sha256(html.encode("utf-8")).hexdigest()

def fetch_html_requests(url: str) -> FetchResult:
    r = requests.get(url, headers=HEADERS, timeout=settings.REQUEST_TIMEOUT)
    r.raise_for_status()
    time.sleep(settings.THROTTLE_SECONDS)
    return FetchResult(url, r.text)

def fetch_html_playwright(url: str) -> FetchResult:
    """
    Render satu halaman dengan Playwright (untuk halaman yang benar-benar punya URL).
    """
    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
    except Exception:
        return fetch_html_requests(url)

    ua = settings.USER_AGENT
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(user_agent=ua,
                                  viewport={"width": 1366, "height": 900})
        page = ctx.new_page()
        page.goto(url, timeout=90_000, wait_until="networkidle")

        # Toleran menunggu listing siap
        for sel in [
            "a.v-card.v-card--flat.v-card--link[href*='/lowongan/view/']",
            "text=Daftar Lowongan Magang",
        ]:
            try:
                page.wait_for_selector(sel, timeout=10_000)
                break
            except PWTimeout:
                pass

        # Nudge lazy-load
        for _ in range(3):
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(0.6)

        html = page.content()
        browser.close()
        return FetchResult(url, html)

def fetch_listing_pages_playwright(base_root: str, max_pages: int):
    pages_html = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_default_timeout(20_000)  # ⬅️ biar gak nunggu lama

        url = f"{base_root}/lowongan"
        print(f"[INFO] Navigating to {url}")
        page.goto(url, timeout=90_000, wait_until="networkidle")
        time.sleep(2)

        # Estimasi jumlah halaman dari teks "Ditemukan XXXX lowongan"
        total_text = page.content()
        total_low = parse_total_lowongan(total_text) or 0
        per_page = 20
        est_pages = math.ceil(total_low / per_page) if total_low else max_pages
        pages_to_grab = min(est_pages, max_pages)
        print(f"[INFO] Estimasi halaman: total_low={total_low}, per_page={per_page}, pages≈{est_pages}, cap={pages_to_grab}")

        def click_next(i):
            next_num = i + 2
            nb = page.get_by_role("button", name=re.compile("Next", re.I))
            if nb.count() > 0:
                aria = (nb.first.get_attribute("aria-disabled") or "").lower().strip()
                disabled = aria == "true" or (nb.first.get_attribute("disabled") is not None)
                if not disabled:
                    nb.first.scroll_into_view_if_needed()
                    nb.first.click()
                    return True
            btn = page.locator("li.v-pagination__item button", has_text=str(next_num))
            if btn.count() > 0:
                btn.first.scroll_into_view_if_needed()
                btn.first.click()
                return True
            btn = page.locator(f"button[aria-label*='Page {next_num}']")
            if btn.count() > 0:
                btn.first.scroll_into_view_if_needed()
                btn.first.click()
                return True
            return False

        for i in range(pages_to_grab):
            print(f"[INFO] Capturing page {i+1}")
            pages_html.append(page.content())

            # kalau ini halaman terakhir yg direncanakan → stop (jangan klik apa pun)
            if i == pages_to_grab - 1:
                break

            # simpan teks item pertama untuk deteksi perubahan
            first_card = page.locator("a.v-card.v-card--flat.v-card--link[href*='/lowongan/view/']").first
            before_txt = (first_card.inner_text() or "") if first_card.count() else ""

            if not click_next(i):
                print("[INFO] Tidak menemukan tombol Next/angka. Selesai.")
                break

            # tunggu konten berubah max 12s, kalau tidak berubah ya berhenti
            try:
                page.wait_for_function(
                    """(prev) => {
                        const el = document.querySelector("a.v-card.v-card--flat.v-card--link[href*='/lowongan/view/']");
                        return el && el.innerText.trim() !== (prev || "").trim();
                    }""",
                    arg=before_txt,
                    timeout=12_000,
                )
            except Exception:
                print("[WARN] Halaman tidak berubah setelah klik. Asumsi sudah akhir. Stop.")
                break

            time.sleep(0.8)
        # ⬇️ tambahkan ini
        print(f"[STEP] Pagination complete. Collected {len(pages_html)} pages. Handing off to parser...", flush=True)
        
        browser.close()
    return pages_html



def fetch_html(url: str) -> FetchResult:
    if settings.USE_PLAYWRIGHT:
        return fetch_html_playwright(url)
    return fetch_html_requests(url)

def fetch_detail_playwright(url: str) -> FetchResult:
    """
    Render halaman DETAIL lowongan dengan wait yang spesifik:
    - label 'Program Studi' / chip '.v-chip__content'
    - plus nudge lazy-load (scroll)
    """
    ua = settings.USER_AGENT
    with sync_playwright() as p:
        # Chromium lebih stabil di situs ini
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(user_agent=ua,
                                    viewport={"width": 1366, "height": 900})
        page = ctx.new_page()
        page.goto(url, timeout=120_000, wait_until="networkidle")
        # tunggu salah satu tanda detail siap
        targets = [
            "text=Detail Lowongan",
            "label:has-text('Program Studi')",
            ".v-chip__content",
            "label:has-text('Deskripsi')"
        ]
        for sel in targets:
            try:
                page.wait_for_selector(sel, timeout=30_000)
                break
            except Exception:
                pass
        # nudge render chip
        for _ in range(4):
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(500)
        html = page.content()
        browser.close()
        return FetchResult(url, html)

def fetch_detail_html(url: str) -> FetchResult:
    """
    Render detail dengan Playwright lebih dahulu (karena chip Program Studi butuh render).
    Jatuh ke requests jika Playwright gagal/unavailable.
    """
    try:
        return fetch_detail_playwright(url)  # prefer Playwright
    except Exception:
        pass
    # fallback: static HTML
    return fetch_html_requests(url)