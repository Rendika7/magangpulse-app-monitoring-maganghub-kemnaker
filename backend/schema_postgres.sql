-- backend/schema_postgres.sql

-- Struktur untuk Postgres (Neon)
CREATE TABLE IF NOT EXISTS lowongan (
  id SERIAL PRIMARY KEY,
  external_id TEXT UNIQUE,
  source_url TEXT UNIQUE,
  judul TEXT,
  perusahaan TEXT,
  lokasi TEXT,
  sektor TEXT,
  tanggal_posting DATE,
  pelamar INTEGER,
  kuota INTEGER,
  acceptance_rate DOUBLE PRECISION,
  demand_ratio DOUBLE PRECISION,
  velocity_pelamar_per_day DOUBLE PRECISION,
  status TEXT,
  deskripsi_short TEXT,
  fetched_at TIMESTAMPTZ,
  content_hash TEXT
);

CREATE TABLE IF NOT EXISTS perusahaan (
  id SERIAL PRIMARY KEY,
  nama TEXT UNIQUE,
  lokasi TEXT,
  sektor TEXT,
  n_lowongan_aktif INTEGER,
  kuota_total INTEGER,
  pelamar_total INTEGER,
  ar_rata2 DOUBLE PRECISION,
  dr_rata2 DOUBLE PRECISION,
  source_url TEXT,
  fetched_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS site_stats (
  id INTEGER PRIMARY KEY,
  jumlah_perusahaan INTEGER,
  jumlah_lamaran INTEGER,
  total_lowongan INTEGER,
  fetched_at TIMESTAMPTZ
);
INSERT INTO site_stats(id) VALUES(1)
ON CONFLICT (id) DO NOTHING;

CREATE TABLE IF NOT EXISTS program_timeline (
  id SERIAL PRIMARY KEY,
  batch TEXT,
  title TEXT,
  start_date DATE,
  end_date DATE,
  status TEXT,
  order_index INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_lowongan_company ON lowongan(perusahaan);
CREATE INDEX IF NOT EXISTS idx_lowongan_ar ON lowongan(acceptance_rate);
CREATE INDEX IF NOT EXISTS idx_lowongan_loc ON lowongan(lokasi);