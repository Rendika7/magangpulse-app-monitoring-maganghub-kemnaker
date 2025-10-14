// frontend/app.js

// --- API base robust (mendukung file:// dan port random DevServer) ---
const isLocal =
  typeof location !== "undefined" &&
  /^(localhost|127\.0\.0\.1)$/.test(location.hostname);
const API_BASE = (window.API_BASE && typeof window.API_BASE === "string")
  ? window.API_BASE.replace(/\/+$/, "")
  : (isLocal ? "http://127.0.0.1:8000" : location.origin);

// ========= Utilities =========
const $  = (sel) => document.querySelector(sel);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));
const pct = (x) => (x == null ? "—" : (x * 100).toFixed(1) + "%");
const num = (x) => (x == null || isNaN(Number(x)) ? "—" : Number(x).toLocaleString("id-ID"));
function debounce(fn, ms=250){ let t; return (...a)=>{ clearTimeout(t); t=setTimeout(()=>fn(...a), ms); }; }



// ========= Mini component: MultiSelect (dropdown + checkbox) =========
function createMultiSelect(rootId, { placeholder="Pilih", onChange } = {}){
  const root = document.getElementById(rootId);
  if (!root) return null;
  root.classList.add("ms");
  const tpl = `
    <button type="button" class="ms-btn">
      <span class="ms-label text-sm text-zinc-400">${placeholder}</span>
      <svg width="18" height="18" viewBox="0 0 24 24" class="opacity-80"><path fill="currentColor" d="M7 10l5 5 5-5z"/></svg>
    </button>
    <div class="ms-panel">
      <input type="text" class="ms-search inp" placeholder="Cari...">
      <div class="ms-list"></div>
    </div>`;
  root.innerHTML = tpl;
  const btn   = root.querySelector(".ms-btn");
  const panel = root.querySelector(".ms-panel");
  const list  = root.querySelector(".ms-list");
  const search= root.querySelector(".ms-search");
  let options = [];   // [{value,label}]
  let picked  = new Set();

  function renderList(){
    const q = (search.value||"").toLowerCase();
    const items = options.filter(o => o.label.toLowerCase().includes(q));
    list.innerHTML = items.map(o=>`
      <label class="ms-item">
        <input type="checkbox" value="${o.value}" ${picked.has(o.value)?"checked":""}>
        <span class="text-sm">${o.label}</span>
      </label>`).join("") || `<div class="text-xs text-zinc-500 p-2">Tidak ada opsi.</div>`;
    list.querySelectorAll("input[type=checkbox]").forEach(cb=>{
      cb.addEventListener("change", ()=>{
        if (cb.checked) picked.add(cb.value); else picked.delete(cb.value);
        updateLabel(); if (onChange) onChange(getSelected());
      });
    });
  }
  function updateLabel(){
    const lab = root.querySelector(".ms-label");
    if (picked.size===0){ lab.textContent = placeholder; lab.classList.add("text-zinc-400"); return; }
    const sample = options.filter(o=>picked.has(o.value)).slice(0,2).map(o=>o.label);
    lab.classList.remove("text-zinc-400");
    lab.innerHTML = `<div class="ms-tags">
      ${sample.map(s=>`<span class="ms-tag">${s}</span>`).join("")}
      ${picked.size>2 ? `<span class="ms-tag">+${picked.size-2}</span>` : ""}
    </div>`;
  }
  function setOptions(arr){
    // arr: array of strings (unique)
    options = (arr||[]).map(v=>({ value:String(v), label:String(v) }));
    options.sort((a,b)=>a.label.localeCompare(b.label));
    renderList(); updateLabel();
  }
  function getSelected(){ return Array.from(picked.values()); }
  function clear(){ picked.clear(); search.value=""; renderList(); updateLabel(); }

  // events
  btn.addEventListener("click", (e)=>{ e.stopPropagation(); root.classList.toggle("open"); search.focus(); });
  document.addEventListener("click", (e)=>{
    if (!root.contains(e.target)) root.classList.remove("open");
  });
  search.addEventListener("input", debounce(renderList, 120));

  return { setOptions, getSelected, clear };
}







// ========= Countdown (deadline: 15 Oct 2025 23:59 WIB) =========
function startCountdown() {
  const deadline = new Date("2025-10-15T23:59:00+07:00").getTime();
  const el = $("#countdown");
  if (!el) return;
  const tick = () => {
    const now = Date.now(); let dist = Math.max(0, deadline - now);
    const d = Math.floor(dist / 86400000);
    const h = Math.floor((dist / 3600000) % 24);
    const m = Math.floor((dist / 60000) % 60);
    const s = Math.floor((dist / 1000) % 60);
    el.textContent = `${d} hari, ${h} jam, ${m} menit, ${s} detik`;
  };
  tick(); setInterval(tick, 1000);
}

// ========= Global State (untuk pagination & filter) =========
let STATE = {
  page: 1,
  page_size: 20,
  total: 0,
  sort: "recent",
  q: "",
  lokasi: [],       // multi-select
  sektor: [],       // multi-select
  perusahaan: [],   // multi-select
  min_ar: null,
  max_ar: null,
};

// refs komponen multi-select
let msLokasi, msSektor, msPerusahaan;

// ========= Home (stat + timeline) =========
async function loadHome() {
  const url = `${API_BASE}/api/home`;
  let res;
  try{
    res = await fetch(url, { cache: "no-store" });
  }catch(e){
    console.error("Home fetch error:", e);
    renderTimeline([]);
    return;
  }
  if (!res.ok) {
    console.error("Home fetch failed:", res.status, res.statusText, url);
    renderTimeline([]);
    return;
  }
  const { stats, timeline } = await res.json();

  if (stats) {
    $("#stat-perusahaan") && ($("#stat-perusahaan").textContent = num(stats.jumlah_perusahaan));
    $("#stat-lamaran") && ($("#stat-lamaran").textContent    = num(stats.jumlah_lamaran));
    $("#stat-lowongan") && ($("#stat-lowongan").textContent   = num(stats.total_lowongan));
    const ts = stats.fetched_at ? new Date(stats.fetched_at).toLocaleString("id-ID") : "";
    $("#home-snapshot") && ($("#home-snapshot").textContent = ts);
    const par = document.querySelector("section.p-5 p.text-xs");
    if (par){
      par.innerHTML = `Data diperoleh langsung dari scraping website MagangHub dan disajikan ulang sebagai API oleh <span class="font-medium text-zinc-300">MagangPulse</span> (<span class="font-medium">MagangPulse API v1.1.0</span>). Snapshot terakhir: <span class="font-medium">${ts || "—"}</span>.`;
    }
  }
  renderTimeline(timeline || []);
}

function renderTimeline(items) {
  const host = $("#timeline");
  if(!host) return;
  host.innerHTML = "";
  items.forEach((it) => {
    const div = document.createElement("div");
    div.className = `p-4 rounded-2xl bg-zinc-900/60 card timeline-card ${it.status==='active' ? 'active' : ''}`;
    const badge = it.batch ? `<span class="text-xs text-violet-400">${it.batch}</span>` : "";
    const date  = (it.start_date || "") + (it.end_date ? ` → ${it.end_date}` : "");
    div.innerHTML = `
      <div class="flex items-start justify-between">
        <div class="text-sm text-zinc-400">${badge}</div>
        <div class="text-xs text-zinc-500">${it.status || ""}</div>
      </div>
      <div class="mt-1 font-semibold">${it.title || "—"}</div>
      <div class="text-sm text-zinc-400 mt-1">${date}</div>`;
    host.appendChild(div);
  });
}

// ========= Jobs (server-side pagination) =========
function paramsFromState(){
  const p = new URLSearchParams();
  p.set("page", String(STATE.page));
  p.set("page_size", String(STATE.page_size));
  p.set("sort", STATE.sort || "recent");
  if (STATE.q) p.set("query", STATE.q);
  // multi: kirim berulang key=val
  (STATE.lokasi||[]).forEach(v => p.append("lokasi", v));
  (STATE.sektor||[]).forEach(v => p.append("sektor", v));
  (STATE.perusahaan||[]).forEach(v => p.append("perusahaan", v));
  if (STATE.min_ar != null && STATE.min_ar !== "") p.set("min_ar", STATE.min_ar);
  if (STATE.max_ar != null && STATE.max_ar !== "") p.set("max_ar", STATE.max_ar);
  return p;
}

async function fetchJobsPage(){
  const host = $("#jobs");
  if (!host) return;
  host.innerHTML = `<div class="text-sm text-zinc-400">Memuat…</div>`;

  const url = `${API_BASE}/api/lowongan?` + paramsFromState().toString();

  // robust fetch + retry
  let tries = 0, res, json, lastErr;
  while (tries < 3){
    tries++;
    try{
      res = await fetch(url, { cache: "no-store" });
      if(!res.ok) throw new Error(`HTTP ${res.status}`);
      json = await res.json(); break;
    }catch(e){
      lastErr = e; await new Promise(r=>setTimeout(r, 250*tries));
    }
  }
  if(!json){
    console.error("Fetch gagal:", lastErr);
    host.innerHTML = `<div class="text-sm text-red-400">Gagal memuat data.</div>`;
    return;
  }

  const rows = json.data || [];
  STATE.total = json.total ?? 0;
  renderJobs(rows);
  renderPager();
}

function renderJobs(rows){
  const host = $("#jobs");
  if (!host) return;
  host.innerHTML = "";
  if (!rows.length){
    host.innerHTML = '<div class="text-sm text-zinc-400">Tidak ada data yang cocok.</div>';
    return;
  }
  rows.forEach(r=>{
    const card = document.createElement("div");
    card.className = "job-card rounded-2xl border border-zinc-800 bg-zinc-900/60 p-4";
    card.innerHTML = `
      <div>
        <div class="text-lg font-semibold title mb-1">${r.judul || "—"}</div>
        <div class="text-sm text-zinc-400 company mb-2">${r.perusahaan || "—"}</div>
        <div class="text-xs text-zinc-500 meta mb-3">
          <span class="text-zinc-400">Penempatan Kerja:</span> ${(r.lokasi||"—").toUpperCase()}
        </div>
        <div class="grid grid-cols-2 gap-2">
          <div class="rounded-xl bg-zinc-900 border border-zinc-800 p-3">
            <div class="text-xs text-zinc-400">Peluang</div>
            <div class="text-base font-semibold">${pct(r.acceptance_rate)}</div>
          </div>
          <div class="rounded-xl bg-zinc-900 border border-zinc-800 p-3">
            <div class="text-xs text-zinc-400">Pelamar/Kuota</div>
            <div class="text-base font-semibold">${num(r.pelamar)}/${num(r.kuota)}</div>
          </div>
        </div>
      </div>
      ${r.tanggal_posting ? `<div class="mt-3 text-[11px] text-zinc-500">Posting: ${r.tanggal_posting}</div>` : ""}
      <div class="job-footer mt-3">
        <a href="${r.source_url || "#"}" target="_blank" rel="noopener"
          class="inline-flex w-full items-center justify-center rounded-xl px-4 py-2 text-sm font-medium
                  text-white bg-gradient-to-r from-violet-600 to-blue-600 hover:from-violet-500 hover:to-blue-500">
          Lihat detail lowongan →
        </a>
      </div>`;
    host.appendChild(card);
  });
}

function renderPager(){
  const pager = $("#pager");
  if (!pager) return;
  pager.innerHTML = "";
  const totalPages = Math.max(1, Math.ceil(STATE.total / STATE.page_size));
  const cp = STATE.page;

  // wrapper
  const bar = document.createElement("div");
  bar.className = "flex flex-wrap md:flex-nowrap justify-center items-center gap-4 p-4 font-sans text-zinc-200";

  const group = document.createElement("div");
  group.className = "flex flex-wrap justify-center items-center gap-2";

  const makeBtn = (label, page, disabled=false, active=false) => {
    const b = document.createElement("button");
    b.textContent = label;
    b.className =
      "px-3 py-2 rounded-xl border border-zinc-800 text-sm transition " +
      (active ? "bg-blue-900 text-white" : "hover:bg-zinc-800");
    if (disabled) {
      b.className += " opacity-50 cursor-not-allowed";
    } else {
      b.addEventListener("click", ()=>{
        if (page===STATE.page) return;
        STATE.page = page; fetchJobsPage();
      });
    }
    return b;
  };

  // Sebelumnya
  group.appendChild(makeBtn("Sebelumnya", Math.max(1, cp-1), cp<=1, false));

  // halaman 1..5 … last
  const tp = totalPages;
  const firstPages = [1,2,3,4,5].filter(p => p<=tp);
  const lastPage = tp;

  let lastAdded = 0;
  const addPage = (p)=>{
    if (p<1 || p>tp) return;
    if (lastAdded && p-lastAdded>1) {
      const ell = document.createElement("span");
      ell.textContent = "…";
      ell.className = "px-2 text-zinc-400";
      group.appendChild(ell);
    }
    group.appendChild(makeBtn(String(p), p, false, p===cp));
    lastAdded = p;
  };

  firstPages.forEach(addPage);
  if (tp > 5) addPage(tp);

  // Berikutnya
  group.appendChild(makeBtn("Berikutnya", Math.min(tp, cp+1), cp>=tp, false));

  // meta "Halaman X dari Y"
  const meta = document.createElement("div");
  meta.className = "text-xs text-zinc-400";
  meta.textContent = `Halaman ${cp} dari ${tp}`;

  bar.appendChild(group);
  bar.appendChild(meta);

  // separator line di atas pagination
  const wrap = document.createElement("div");
  wrap.className = "mt-4 pt-4 border-t border-zinc-800/80"; // garis tipis elegan
  wrap.appendChild(bar);
  pager.appendChild(wrap);}

// ========= (Opsional) kumpulkan opsi dropdown dari sampel halaman =========
// Catatan: hanya buat bantu isi <select> provinsi/sektor/perusahaan, bukan untuk render utama
async function fetchSomeJobsForOptions(maxPages=3, pageSize=100){
  const uniq = new Set();
  const rows = [];
  let page = 1, total = Infinity;
  while (page <= maxPages && (page-1)*pageSize < total){
    const p = new URLSearchParams();
    p.set("page", String(page));
    p.set("page_size", String(pageSize));
    p.set("sort", "recent");
    const res = await fetch(`${API_BASE}/api/lowongan?`+p.toString(), { cache:"no-store" });
    if(!res.ok) break;
    const j = await res.json();
    total = j.total ?? 0;
    (j.data||[]).forEach(r=>{
      const key = (r.perusahaan||"")+"|"+(r.lokasi||"")+"|"+(r.sektor||"");
      if (!uniq.has(key)){ uniq.add(key); rows.push(r); }
    });
    if (!(j.data||[]).length) break;
    page++;
  }
  return rows;
}

function fillDropdownsFromRows(rows){
  const provinces = new Set(), sectors = new Set(), companies = new Set();
  rows.forEach(r=>{
    if (r.lokasi) provinces.add(String(r.lokasi||"").toUpperCase());
    if (r.sektor){
      // r.sektor bisa "Teknik Sipil; Teknik Industri; Akuntansi"
      String(r.sektor).split(";").map(s=>s.trim()).filter(Boolean).forEach(s=>sectors.add(s));
    }    if (r.perusahaan) companies.add(String(r.perusahaan||""));
  });
  msLokasi?.setOptions([...provinces]);
  msSektor?.setOptions([...sectors]);
  msPerusahaan?.setOptions([...companies]);
}

// ========= Companies (ringkas) =========
async function loadCompanies(){
  const mapSort = (k, ord) => {
    if (k==="aktif") return ord==="asc" ? "aktif_asc" : "aktif_desc";
    if (k==="kuota") return ord==="asc" ? "kuota_asc" : "kuota_desc";
    // default AR
    return ord==="asc" ? "ar_asc" : "ar_desc";
  };
  const k = $("#co-sort")?.value || "ar";
  const ord = $("#co-order")?.value || "desc";
  const sort = mapSort(k, ord);
  try{
    const res = await fetch(`${API_BASE}/api/perusahaan?sort=${encodeURIComponent(sort)}&page=1&page_size=15`, { cache:"no-store" });
    const json = await res.json();
    const host = $("#companies");
    if (!host) return;
    host.innerHTML = "";
    (json.data || []).forEach(it=>{
      const div = document.createElement("div");
      div.className = "rounded-xl bg-zinc-900/60 border border-zinc-800 p-3";
      div.innerHTML = `
        <div class="text-sm font-medium">${it.nama || "—"}</div>
        <div class="text-xs text-zinc-500 mt-1">
          AR rata-rata: <span class="font-semibold">${pct(it.ar_rata2)}</span>
          • Aktif: ${num(it.n_lowongan_aktif)}
          • Kuota: ${num(it.kuota_total)}
        </div>`;
      host.appendChild(div);
    });
  } catch(e){
    console.error(e);
  }
}

// ========= Export XLSX (ambil semua halaman bertahap) =========
async function exportXLSX(){
  const all = [];
  // ambil snapshot filter saat ini
  const snap = { ...STATE };
  let page = 1, total = Infinity;

  while ((page-1)*100 < total){
    const p = new URLSearchParams();
    p.set("page", String(page)); p.set("page_size", "100");
    p.set("sort", snap.sort || "recent");
    if (snap.q) p.set("query", snap.q);
    if (snap.lokasi) p.set("lokasi", snap.lokasi);
    if (snap.sektor) p.set("sektor", snap.sektor);
    if (snap.perusahaan) p.set("perusahaan", snap.perusahaan);
    if (snap.min_ar != null && snap.min_ar!=="") p.set("min_ar", snap.min_ar);
    if (snap.max_ar != null && snap.max_ar!=="") p.set("max_ar", snap.max_ar);

    const res = await fetch(`${API_BASE}/api/lowongan?`+p.toString(), { cache:"no-store" });
    const j = await res.json();
    total = j.total ?? 0;
    (j.data||[]).forEach(r=>all.push(r));
    if (!(j.data||[]).length) break;
    page++;
  }

  const rows = all.map(r=>({
    Judul: r.judul,
    Perusahaan: r.perusahaan,
    Lokasi: r.lokasi,
    "Program Studi": r.sektor,          // kini terisi hasil enrichment
    "Tanggal Posting": r.tanggal_posting,
    Pelamar: r.pelamar,
    Kuota: r.kuota,
    "Acceptance Rate": r.acceptance_rate,
    "Demand Ratio": r.demand_ratio,
    URL: r.source_url
  }));
  const ws = XLSX.utils.json_to_sheet(rows);
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, "Lowongan");
  XLSX.writeFile(wb, "magangpulse_lowongan.xlsx");
}

// ========= Init =========
window.addEventListener("DOMContentLoaded", async () => {
  startCountdown();
  loadHome();
  loadCompanies();

  // init komponen multi-select
  msLokasi = createMultiSelect("ms-lokasi",  { placeholder: $("#ms-lokasi")?.dataset?.placeholder || "Provinsi (Semua)"});
  msSektor = createMultiSelect("ms-sektor",  { placeholder: $("#ms-sektor")?.dataset?.placeholder || "Program Studi (Semua)"});
  msPerusahaan = createMultiSelect("ms-perusahaan", { placeholder: $("#ms-perusahaan")?.dataset?.placeholder || "Perusahaan (Semua)"});



  // handler filter internal perusahaan
  $("#co-sort")?.addEventListener("change", loadCompanies);
  $("#co-order")?.addEventListener("change", loadCompanies);

  // set awal page size dari UI (default 20)
  const psEl = $("#page_size");
  STATE.page_size = parseInt(psEl?.value || "20", 10);
  STATE.page = 1;

  // Initial fetch page 1 (langsung tampil data)
  await fetchJobsPage();

  // Isi dropdown (opsional) dari sampel beberapa halaman agar ada pilihan
  await loadOptions();

  // Tombol Terapkan
  $("#btnApply")?.addEventListener("click", ()=>{
    STATE.page = 1;
    STATE.sort = $("#sort")?.value || "recent";
    // ambil values dari komponen custom
    STATE.lokasi = msLokasi?.getSelected() || [];
    STATE.sektor = msSektor?.getSelected() || [];
    STATE.perusahaan = msPerusahaan?.getSelected() || [];
    STATE.min_ar = $("#min_ar")?.value;
    STATE.max_ar = $("#max_ar")?.value;
    fetchJobsPage();
  });

  // Tombol Reset
  $("#btnReset")?.addEventListener("click", ()=>{
    ["q","min_ar","max_ar"].forEach(id=>{ const el=$("#"+id); if(el) el.value=""; });
    // kosongkan komponen custom
    msLokasi?.clear(); msSektor?.clear(); msPerusahaan?.clear();
    $("#sort") && ($("#sort").value = "recent");
    $("#page_size") && ($("#page_size").value = "20");
    STATE = { page:1, page_size:25, total:0, sort:"recent", q:"", lokasi:[], sektor:[], perusahaan:[], min_ar:null, max_ar:null };
    fetchJobsPage();
  });

  // Streaming search (≥3 huruf → langsung query). Kosong → tampil semua.
  $("#q")?.addEventListener("input", debounce(()=>{
    const v = ($("#q").value || "").trim();
    STATE.q = v.length >= 3 ? v : "";
    STATE.page = 1;
    fetchJobsPage();
  }, 220));

  // Sort berubah
  $("#sort")?.addEventListener("change", ()=>{
    STATE.sort = $("#sort").value || "recent";
    STATE.page = 1; fetchJobsPage();
  });

  // Page size berubah
  $("#page_size")?.addEventListener("change", ()=>{
    STATE.page_size = parseInt($("#page_size").value, 10) || 25;
    STATE.page = 1; fetchJobsPage();
  });

  // Export
  $("#btn-export")?.addEventListener("click", exportXLSX);
});




// ========= Theme (dark/light) =========
(function initTheme(){
  const metaTheme = document.querySelector('meta[name="theme-color"]');

  function setTheme(mode){
    const isDark = mode === "dark";
    document.documentElement.classList.toggle("dark", isDark);
    document.documentElement.classList.toggle("light", !isDark);
    localStorage.setItem("theme", isDark ? "dark" : "light");
    if (metaTheme) metaTheme.setAttribute("content", isDark ? "#0a0a0a" : "#f8fafc");
    // toggle icons
    const sun = document.getElementById("icon-sun");
    const moon = document.getElementById("icon-moon");
    if (sun && moon){ sun.classList.toggle("hidden", isDark); moon.classList.toggle("hidden", !isDark); }
  }

  // initial: saved -> system -> dark default
  const saved = localStorage.getItem("theme");
  const prefersDark = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
  setTheme(saved || (prefersDark ? "dark" : "light"));

  // handle button
  window.addEventListener("DOMContentLoaded", () => {
    const btn = document.getElementById("theme-toggle");
    if (btn){
      btn.addEventListener("click", () => {
        const nowDark = document.documentElement.classList.contains("dark");
        setTheme(nowDark ? "light" : "dark");
      });
    }
  });
})();


// ========= Options endpoint (lebih akurat & cepat) =========
async function loadOptions() {
  try {
    const res = await fetch(`${API_BASE}/api/options`, { cache: "no-store" });
    if (!res.ok) throw new Error("HTTP " + res.status);
    const j = await res.json();
    msLokasi?.setOptions(j.lokasi || []);
    msSektor?.setOptions(j.sektor || []);       // <-- Program Studi muncul dari sini
    msPerusahaan?.setOptions(j.perusahaan || []);
  } catch (e) {
    console.warn("Gagal /api/options, fallback ke sampling:", e);
    try {
      const sample = await fetchSomeJobsForOptions(3, 100);
      fillDropdownsFromRows(sample); // fallback lama
    } catch (err) {
      console.warn("Fallback sampling juga gagal:", err);
    }
  }
}