# backend/scraper/parse.py
import re
from bs4 import BeautifulSoup
from datetime import datetime
from typing import List, Dict, Tuple, Optional

# --- Regex & helpers umum ---
NUM_ID_RX = re.compile(r"(\d{1,3}(?:\.\d{3})+|\d+)")
P_RX = re.compile(r"(\d[\d\.]*)\s*pelamar", re.I)
K_RX = re.compile(r"(\d[\d\.]*)\s*(kebutuhan|kuota)", re.I)
FOUND_RX = re.compile(r"Ditemukan\s+(\d[\d\.]*)\s+lowongan", re.I)
LOC_HINT_RX = re.compile(r"\b(KOTA|KAB\.?|KABUPATEN|PROV\.?|PROVINSI)\b", re.I)

MONTH_MAP = {
  "Januari":"01","Februari":"02","Maret":"03","April":"04","Mei":"05","Juni":"06",
  "Juli":"07","Agustus":"08","September":"09","Oktober":"10","November":"11","Desember":"12",
  # short
  "Jan":"01","Feb":"02","Mar":"03","Apr":"04","Mei":"05","Jun":"06","Jul":"07","Agu":"08",
  "Sep":"09","Okt":"10","Nov":"11","Des":"12"
}

def to_int_id(num_text: Optional[str]) -> Optional[int]:
    if not num_text:
        return None
    m = NUM_ID_RX.search(num_text)
    if not m:
        return None
    return int(m.group(1).replace('.', ''))

def id_date_to_iso(text: Optional[str]) -> Optional[str]:
    # contoh: "3 Oktober 2025"
    if not text:
        return None
    parts = text.strip().split()
    if len(parts) == 3 and parts[1] in MONTH_MAP:
        d, m, y = parts
        try:
            return f"{y}-{MONTH_MAP[m]}-{int(d):02d}"
        except:
            return None
    return None

# -------- HOME --------
def parse_home_stats(html: str) -> Tuple[Optional[int], Optional[int]]:
    soup = BeautifulSoup(html, 'lxml')
    jumlah_perusahaan = None
    jumlah_lamaran = None

    # Cari label "Jumlah Perusahaan"
    for label in soup.find_all(string=re.compile(r"Jumlah Perusahaan", re.I)):
        h4 = None
        for anc in getattr(label, "parents", []):
            h4 = getattr(anc, "find", lambda *_:None)('h4')
            if h4:
                jumlah_perusahaan = to_int_id(h4.get_text(strip=True))
                break
        if jumlah_perusahaan:
            break

    # Cari label "Jumlah Lamaran"
    for label in soup.find_all(string=re.compile(r"Jumlah Lamaran", re.I)):
        h4 = None
        for anc in getattr(label, "parents", []):
            h4 = getattr(anc, "find", lambda *_:None)('h4')
            if h4:
                jumlah_lamaran = to_int_id(h4.get_text(strip=True))
                break
        if jumlah_lamaran:
            break

    return jumlah_perusahaan, jumlah_lamaran

def parse_timeline(html: str) -> List[Dict]:
    soup = BeautifulSoup(html, 'lxml')
    items: List[Dict] = []
    container = soup.select_one('.timeline-section') or soup

    batch_chip = container.find(string=re.compile(r"Batch", re.I)) if container else None
    batch = None
    if batch_chip:
        m = re.search(r"Batch\s*(\d+)", batch_chip)
        batch = f"Batch {m.group(1)}" if m else (batch_chip.strip() if isinstance(batch_chip, str) else None)

    order = 0
    for it in container.select('.timeline .timeline-item'):
        title_el = it.find(['h5','h6'])
        date_el = it.find(class_=re.compile(r"text-muted|small|text-body", re.I))
        title = title_el.get_text(strip=True) if title_el else None

        date_text = date_el.get_text(strip=True) if date_el else ''
        parts = [s.strip() for s in date_text.split('-')]
        start_date = id_date_to_iso(parts[0]) if parts else None
        end_date = id_date_to_iso(parts[1]) if len(parts) > 1 else None

        classes = it.get('class') or []
        status = 'active' if 'active' in classes else ('upcoming' if 'upcoming' in classes else None)

        items.append({
            'batch': batch,
            'title': title,
            'start_date': start_date,
            'end_date': end_date,
            'status': status,
            'order_index': order
        })
        order += 1
    return items

# -------- LISTING --------
def parse_total_lowongan(html: str) -> Optional[int]:
    txt = BeautifulSoup(html, 'lxml').get_text(' ', strip=True)
    m = FOUND_RX.search(txt)
    return to_int_id(m.group(1)) if m else None

def compute_metrics(pelamar: Optional[int], kuota: Optional[int]):
    pelamar = pelamar or 0
    kuota = kuota or 0
    ar = None
    dr = None
    if pelamar > 0:
        ar = (kuota / pelamar)
    if kuota > 0:
        dr = (pelamar / kuota)
    return ar, dr

def parse_listing_page(html: str) -> List[Dict]:
    soup = BeautifulSoup(html, "lxml")
    items: List[Dict] = []

    # (opsional) total lowongan — kalau mau dipakai di tempat lain
    _ = parse_total_lowongan(html)

    # Kartu: <a class="v-card v-card--flat v-card--link" href="/lowongan/view/...">
    for a in soup.select("a.v-card.v-card--flat.v-card--link[href*='/lowongan/view/']"):
        href = a.get("href", "")
        source_url = ("https://maganghub.kemnaker.go.id" + href) if href.startswith("/") else (href or None)

        # Perusahaan & Judul (pakai fallback kecil)
        company_el = a.select_one("h6.text-h6") or a.select_one("h6")
        title_el = a.select_one("h5.text-h5") or a.select_one("h5")

        # Lokasi: contoh "KAB. TANGERANG , BANTEN" (sering ada pada <div style="font-size: 11px;"> ... </div>)
        lokasi = None
        # 1) Heuristik: cari div kecil yang berisi pola lokasi (ada koma atau LOC_HINT_RX)
        for div in a.find_all("div"):
            txt = (div.get_text(strip=True) or "")
            if not txt:
                continue
            style = (div.get("style") or "").lower()
            if ("font-size" in style and ("," in txt or LOC_HINT_RX.search(txt))):
                lokasi = txt
                break
        # 2) Fallback: div setelah nama perusahaan
        if not lokasi and company_el:
            sib = company_el.find_next("div")
            if sib:
                txt = sib.get_text(strip=True) or ""
                if ("," in txt or LOC_HINT_RX.search(txt)):
                    lokasi = txt
        # 3) Normalisasi ringan (hapus spasi ganda di sekitar koma)
        if lokasi:
            lokasi = re.sub(r"\s*,\s*", " , ", lokasi).strip()



        # Tanggal: <i class="tabler-calendar"> ... <span>3 Oktober 2025</span>
        cal_icon = a.select_one(".tabler-calendar")
        tanggal = None
        if cal_icon:
            span = cal_icon.find_next("span")
            if span:
                tanggal = span.get_text(strip=True)
        tanggal_iso = id_date_to_iso(tanggal) if tanggal else None

        # Pelamar | Kebutuhan: <i class="tabler-users"> ... <span>905 pelamar | 1 kebutuhan</span>
        users_icon = a.select_one(".tabler-users")
        pelamar = kuota = None
        if users_icon:
            span = users_icon.find_next("span")
            if span:
                info = span.get_text(" ", strip=True)
                mp = P_RX.search(info); mk = K_RX.search(info)
                if mp: pelamar = to_int_id(mp.group(1))
                if mk: kuota   = to_int_id(mk.group(1))

        ar, dr = compute_metrics(pelamar, kuota)

        items.append({
            "external_id": source_url,
            "source_url": source_url,
            "judul": title_el.get_text(strip=True) if title_el else None,
            "perusahaan": company_el.get_text(strip=True) if company_el else None,
            "lokasi": lokasi,
            "sektor": None,
            "tanggal_posting": tanggal_iso,
            "pelamar": pelamar,
            "kuota": kuota,
            "acceptance_rate": ar,
            "demand_ratio": dr,
            "velocity_pelamar_per_day": None,
            "status": "open",
            "deskripsi_short": None,
            "fetched_at": datetime.utcnow().isoformat(),
            "content_hash": None
        })

    return items

# -------- DETAIL: DESKRIPSI (robust, berbasis label) --------
def parse_detail_deskripsi(html: str) -> Optional[str]:
    """
    Ambil blok 'Deskripsi' dari halaman detail lowongan.

    Strategi (sesuai prompt):
    - Cari label 'Deskripsi' (normalize-space).
    - Ambil ancestor barisnya (v-row / row container).
    - Dari baris itu, ambil kolom kanan yang mengandung .text-body-1 lalu <p>.
    - Normalisasi whitespace dan bullet.

    Fallback:
    - Jika struktur tidak persis sama, cari div.text-body-1 terdekat setelah label.
    """
    soup = BeautifulSoup(html, "lxml")

    # 1) Temukan elemen label "Deskripsi" (tahan variasi tag & spasi)
    def _is_deskripsi_label(el) -> bool:
        if not el or not hasattr(el, "get_text"):
            return False
        txt = el.get_text(" ", strip=True)
        return bool(re.match(r"^Deskripsi$", txt, flags=re.I))

    label = None
    for el in soup.find_all(["label", "div", "span"]):
        if _is_deskripsi_label(el):
            label = el
            break
    if not label:
        # fallback: cari string "Deskripsi" lalu ambil parent sebagai 'label'
        cand = soup.find(string=re.compile(r"^\s*Deskripsi\s*$", re.I))
        if cand and getattr(cand, "parent", None):
            label = cand.parent

    if not label:
        return None

    # 2) Ambil "baris" terdekat (v-row / row container)
    row = None
    # cari parent yang class-nya mengandung v-row
    row = label.find_parent(class_=re.compile(r"\bv-row\b", re.I))
    # kalau nggak ketemu, ambil parent div terdekat sebagai fallback
    if not row:
        row = label.find_parent("div")

    # 3) Dari baris itu, ambil kolom kanan yang mengandung .text-body-1
    target = None
    if row:
        target = row.find(class_=re.compile(r"\btext-body-1\b", re.I))
        # beberapa halaman pakai v-col-md-8 sebagai kolom kanan
        if not target:
            right = row.find(class_=re.compile(r"\bv-col-md-8\b|\bv-col-12\b", re.I))
            if right:
                target = right.find(class_=re.compile(r"\btext-body-1\b", re.I)) or right

    # 4) Fallback terakhir: cari .text-body-1 tepat setelah label
    if not target:
        # cari sibling/next block yang mengandung text-body-1
        sib = label.find_next(class_=re.compile(r"\btext-body-1\b", re.I))
        if sib:
            target = sib

    if not target:
        return None

    # 5) Ambil semua <p> (atau teks mentah kalau <p> tidak ada)
    parts: List[str] = []
    for p in target.find_all("p"):
        t = p.get_text(" ", strip=True)
        if t:
            parts.append(t)
    if not parts:
        # misal kontennya langsung text node tanpa <p>
        raw = target.get_text("\n", strip=True)
        if raw:
            parts = [raw]

    if not parts:
        return None

    # 6) Normalisasi bullet & whitespace
    text = "\n".join(parts)
    # ubah "- foo" atau "• foo" jadi bullet konsisten
    text = re.sub(r"^\s*[-•]\s*", "• ", text, flags=re.M)
    # rapikan spasi gandaa
    text = re.sub(r"[ \t]+\n", "\n", text)
    return text.strip() or None

# -------- DETAIL PAGE --------
def parse_detail_program_studi(html: str) -> List[str]:
    """
    Ambil daftar Program Studi dari halaman detail lowongan.
    Struktur yang dicari (kurang lebih):
      <label>Program Studi</label>
      <div class="d-flex flex-wrap gap-2">
         <span class="v-chip ..."><div class="v-chip__content">Teknik Sipil</div></span> ...
      </div>
    Return: list of strings (tanpa duplikat, urutan sesuai kemunculan).
    """
    soup = BeautifulSoup(html, "lxml")

    # 1) Cari label "Program Studi" (beberapa halaman pakai <label>, kadang <div>)
    label = None
    for lab in soup.find_all(["label", "div", "span"], string=re.compile(r"^\s*Program Studi\s*$", re.I)):
        label = lab; break
    # 2) Jika label tidak ketemu, fallback: langsung sweep semua chip dan lihat konteks terdekat
    containers = []
    if label:
        # Struktur Vuetify: label -> (kolom kanan) -> wrapper chip 'flex-wrap gap-2'
        # coba parent langsung
        for anc in [label.parent, getattr(label, "find_parent", lambda *_:None)("div")]:
            if not anc: continue
            cand = anc.find(class_=re.compile(r"(flex-wrap|gap-2)", re.I))
            if cand: containers.append(cand); break
        # fallback: cari sibling kolom kanan terdekat
        if not containers:
            sib = label.find_next(class_=re.compile(r"(flex-wrap|gap-2)", re.I))
            if sib: containers.append(sib)
    if not containers:
        # fallback global terakhir: semua wrapper chip di halaman
        containers = soup.find_all(class_=re.compile(r"(flex-wrap|gap-2)", re.I))

    prodi: List[str] = []
    for cont in containers:
        for chip in cont.find_all(class_=re.compile(r"v-chip__content")):
            t = chip.get_text(strip=True)
            if t and t not in prodi:
                prodi.append(t)
    return prodi
