PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS lowongan (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  external_id TEXT UNIQUE,
  source_url TEXT UNIQUE,
  judul TEXT,
  perusahaan TEXT,
  lokasi TEXT,
  sektor TEXT,
  tanggal_posting TEXT,
  pelamar INTEGER,
  kuota INTEGER,
  acceptance_rate REAL,
  demand_ratio REAL,
  velocity_pelamar_per_day REAL,
  status TEXT,
  deskripsi_short TEXT,
  fetched_at TEXT,
  content_hash TEXT
);

CREATE TABLE IF NOT EXISTS perusahaan (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  nama TEXT UNIQUE,
  lokasi TEXT,
  sektor TEXT,
  n_lowongan_aktif INTEGER,
  kuota_total INTEGER,
  pelamar_total INTEGER,
  ar_rata2 REAL,
  dr_rata2 REAL,
  source_url TEXT,
  fetched_at TEXT
);

-- NEW: stats beranda + total lowongan
CREATE TABLE IF NOT EXISTS site_stats (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  jumlah_perusahaan INTEGER,
  jumlah_lamaran INTEGER,
  total_lowongan INTEGER,
  fetched_at TEXT
);
INSERT OR IGNORE INTO site_stats(id) VALUES(1);

-- NEW: timeline program
CREATE TABLE IF NOT EXISTS program_timeline (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  batch TEXT,
  title TEXT,
  start_date TEXT,
  end_date TEXT,
  status TEXT,
  order_index INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_lowongan_company ON lowongan(perusahaan);
CREATE INDEX IF NOT EXISTS idx_lowongan_ar ON lowongan(acceptance_rate);
CREATE INDEX IF NOT EXISTS idx_lowongan_loc ON lowongan(lokasi);