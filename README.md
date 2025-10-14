# 🌌 MagangPulse — Dark Mirror UI for MagangHub

> 🚀 *Explore internship data like never before — fast, dark, and data-driven.*

MagangPulse is an **unofficial mirror dashboard** that visualizes public internship listings from **[MagangHub Kemenaker](https://maganghub.kemnaker.go.id/)** using a sleek **dark / light UI**, a **FastAPI** backend, and a **Playwright + BeautifulSoup** scraper.
See **acceptance rate (AR)**, **demand ratio (DR)**, **program study chips**, and **company snapshots** at a glance.


## 🖼️ Website Look-Like
<table>
  <tr>
    <td width="50%" valign="top">
      <a href="https://github.com/Rendika7/magangpulse-app-monitoring-maganghub-kemnaker/blob/main/gambar_website/Gambaran%20Website%201.png?raw=true">
        <img src="https://github.com/Rendika7/magangpulse-app-monitoring-maganghub-kemnaker/blob/main/gambar_website/Gambaran%20Website%201.png?raw=true" alt="MagangPulse — Dashboard Overview" width="100%" />
      </a>
    </td>
    <td width="50%" valign="top">
      <a href="https://github.com/Rendika7/magangpulse-app-monitoring-maganghub-kemnaker/blob/main/gambar_website/Gambaran%20Website%202.png?raw=true">
        <img src="https://github.com/Rendika7/magangpulse-app-monitoring-maganghub-kemnaker/blob/main/gambar_website/Gambaran%20Website%202.png?raw=true" alt="MagangPulse — Compare View (AR/DR)" width="100%" />
      </a>
    </td>
  </tr>
</table>

<p align="center">
  <sub>Kiri: Dashboard Overview • Kanan: Compare View (Acceptance Rate & Demand Ratio)</sub>
</p>


## ✨ Features

* **Full Playwright pagination** — collects multi-page results reliably.
* **Detail enrichment** — scrapes **Program Studi** chips into `sektor` and **Deskripsi** into `deskripsi_short`.
* **/api/options** endpoint — fast distinct lists for **lokasi**, **sektor/prodi**, **perusahaan**.
* **Home stats + timeline** — stores site metrics and “Jadwal Pelaksanaan Program” in DB.
* **SQLite or PostgreSQL (Neon)** — auto-selects Postgres if `DATABASE_URL` is present.
* **Compare Jobs** — pick 2–3 jobs and compare AR/DR, kuota, lokasi, and deskripsi side-by-side.
* **Dark ↔ Light theme toggle** — polished UI with gradients and subtle motion.
* **Export XLSX** — one-click export of filtered results.
* **Computed metrics** — AR = `kuota/pelamar`, DR = `pelamar/kuota`.

---

## 🏗️ Tech Stack

| Layer        | Tech                                 | Purpose                                          |
| ------------ | ------------------------------------ | ------------------------------------------------ |
| **Frontend** | HTML, TailwindCSS, Vanilla JS        | UI, filters, compare, export, theme              |
| **Backend**  | FastAPI                              | REST API for jobs, companies, options, stats     |
| **DB**       | SQLite (default) / PostgreSQL (Neon) | Storage for listings, companies, stats, timeline |
| **Scraper**  | Playwright + BeautifulSoup4          | Pagination & detail enrichment                   |
| **Python**   | 3.10+                                | End-to-end runtime                               |

---

## 📁 Project Structure

```
MagangPulse Website/
│
├── backend/
│   ├── app.py                      # FastAPI routes/endpoints
│   ├── db.py                       # SQLite/Postgres connection wrapper
│   ├── models.py                   # CRUD/queries (lowongan, perusahaan, stats, timeline, options)
│   ├── settings.py                 # .env loader + config
│   ├── schema.sql                  # SQLite schema
│   ├── schema_postgres.sql         # Postgres/Neon schema
│   │
│   ├── scraper/
│   │   ├── fetch.py                # Playwright/requests fetchers + pagination
│   │   ├── parse.py                # Parsers (home, listing, timeline, prodi + deskripsi)
│   │   └── run_full_scrape.py      # Full scrape pipeline + enrichment + DB upserts
│   │
│   └── data.sqlite                 # Generated SQLite DB (if used)
│
├── frontend/
│   ├── index.html                  # Main UI
│   ├── compare.html                # Compare Jobs UI
│   ├── app.js                      # Filters, pagination, API calls, export, theme
│   ├── compare.js                  # Compare page logic
│   └── styles.css                  # Custom styles
│
├── .env                            # Runtime configuration
├── requirements.txt                # Python dependencies
└── README.md
```

---

## ⚙️ Setup

### 1) Clone

```bash
git clone https://github.com/yourusername/magangpulse.git
cd "MagangPulse Website"
```

### 2) Python env

```bash
# Conda (recommended)
conda create -n scrapper-env python=3.10 -y
conda activate scrapper-env
# or: python -m venv .venv && source .venv/bin/activate
```

### 3) Install deps

```bash
pip install -r requirements.txt
playwright install chromium
```

> Linux may require extra system libs for Chromium.

### 4) Configure `.env`

```ini
# Target source
BASE_URL=https://maganghub.kemnaker.go.id/lowongan

# Local SQLite (fallback if DATABASE_URL is empty)
DB_PATH=backend/data.sqlite

# Optional: Neon Postgres
DATABASE_URL="postgresql://<user>:<pass>@<host>/<db>?sslmode=require&channel_binding=require"

# Scraper
MAX_PAGES=999999
THROTTLE_SECONDS=1.0
USER_AGENT="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
REQUEST_TIMEOUT=30
USE_PLAYWRIGHT=1

# Detail enrichment
DETAIL_ENRICH=1
DETAIL_MAX=999999
DETAIL_WORKERS=6
USE_PLAYWRIGHT_DETAIL=1
```

> If `DATABASE_URL` exists, the app uses **Postgres** (`schema_postgres.sql`); otherwise it uses **SQLite** (`schema.sql`).

---

## 🔄 Run

### A) Scrape & Enrich

```bash
python -m backend.scraper.run_full_scrape
```

* Initializes schema (SQLite or Postgres)
* Playwright pagination → parse → enrich (Program Studi + Deskripsi)
* Upserts lowongan & perusahaan aggregates
* Updates home stats and timeline

### B) Start API

```bash
uvicorn backend.app:app --reload --port 8000
```

* Swagger: `http://127.0.0.1:8000/docs`
* Snapshot: `http://127.0.0.1:8000/api/home`

### C) Launch Frontend

```bash
cd frontend
python -m http.server 5500
```

Open `http://127.0.0.1:5500`.

---

## 🔌 API Overview

* **GET `/api/home`** → site stats + program timeline
* **GET `/api/options`** → `{ lokasi:[], sektor:[], perusahaan:[] }`
* **GET `/api/lowongan`** → server-side pagination & filters

  * `page`, `page_size`, `sort` (recent | ar_desc | ar_asc | pelamar_desc | pelamar_asc | kuota_desc | kuota_asc)
  * `query`
  * multi: `perusahaan`, `lokasi`, `sektor` (repeat key)
  * range: `min_ar`, `max_ar`, `min_pelamar`, `max_pelamar`, `min_kuota`, `max_kuota`
* **GET `/api/perusahaan`** → aggregated per-company stats (+ sorting)
* **GET `/api/_debug/db`** → shows DB engine in use (credentials masked)

---

## 🖥️ UI Highlights

* Custom **multi-select** filters (lokasi, sektor/prodi, perusahaan)
* **Compare Jobs** (2–3 picks) including **deskripsi**
* **Export XLSX** via SheetJS
* Responsive 3-column layout, subtle animations, theme toggle

---

## 🧪 Troubleshooting

* **Only 1 page scraped** while `USE_PLAYWRIGHT=1`: ensure your logs show Playwright pagination and **no** “Static mode” warning.
* **Chromium launch errors**: run `playwright install chromium`; install required system libs (Linux).
* **Postgres issues**: verify `DATABASE_URL` and SSL; app auto-switches when present.
* **Few Program Studi/Deskripsi**: raise `DETAIL_MAX` and keep reasonable `DETAIL_WORKERS`.

---

## 🧠 Metrics

* **Acceptance Rate (AR)** = `kuota / pelamar`
* **Demand Ratio (DR)** = `pelamar / kuota`
  Company aggregates use averages/sums of listing metrics.

---

## 🤝 Ethics & Disclaimer

* Unofficial mirror of **public** MagangHub pages.
* Be respectful: throttle requests and use a friendly `USER_AGENT`.
* Use responsibly; don’t overload upstream services.

---

## 🧑‍💻 Author

**Rendika Nurhartanto Suharto** — *AI Engineer • Data Scientist • Tech Creator*
📍 Fresh Graduate from Telkom University Surabaya
[LinkedIn](https://www.linkedin.com/in/rendikanurhartanto-s) • [GitHub](https://github.com/Rendika7)

> *“One dataset, infinite insights — coded with purpose.”*

---

## ⚖️ License

**MIT License © 2025 Rendika Nurhartanto Suharto**
Feel free to fork, remix, and deploy — credit the source ✨