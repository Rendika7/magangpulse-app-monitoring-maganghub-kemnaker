// frontend/compare.js

// API base (sama seperti app.js)
const isLocal =
  typeof location !== "undefined" &&
  /^(localhost|127\.0\.0\.1)$/.test(location.hostname);
const API_BASE = (window.API_BASE && typeof window.API_BASE === "string")
  ? window.API_BASE.replace(/\/+$/, "")
  : (isLocal ? "http://127.0.0.1:8000" : location.origin);

const $  = (s) => document.querySelector(s);
const $$ = (s) => Array.from(document.querySelectorAll(s));
const debounce = (fn, ms=250)=>{ let t; return (...a)=>{ clearTimeout(t); t=setTimeout(()=>fn(...a), ms); }; };
const pct = (x)=> (x==null? "—" : (x*100).toFixed(1)+"%");
const num = (x)=> (x==null || isNaN(Number(x)) ? "—" : Number(x).toLocaleString("id-ID"));

const MIN_CHARS = 3; // ← batas minimal ketik untuk mulai mencari

const picked = [null, null, null]; // objek job (r from API)

function updateButtons(){
  const n = picked.filter(Boolean).length;
  $("#btn-compare").disabled = n < 2;
}
function clearAll(){
  picked.fill(null);
  $$(".cmp-picked").forEach(el=>el.textContent="");
  $$(".cmp-input").forEach(inp=>{ inp.value=""; });
  $("#cmp-result").classList.add("hidden");
  updateButtons();
}

// hanya kirim request kalau q >= 3
async function searchJobs(q){
  q = (q || "").trim();
  if (q.length < MIN_CHARS) return [];
  const p = new URLSearchParams();
  p.set("page", "1");
  p.set("page_size", "10");
  p.set("sort", "recent");
  p.set("query", q);
  const res = await fetch(`${API_BASE}/api/lowongan?`+p.toString(), {cache:"no-store"});
  if(!res.ok) return [];
  const j = await res.json();
  return j.data || [];
}

function renderDropdown(dd, rows, slotIdx){
  if(!rows.length){
    dd.innerHTML = `<div class="p-2 text-xs text-zinc-500">Tidak ada hasil.</div>`;
    return;
  }
  dd.innerHTML = rows.map(r => `
    <button type="button" class="w-full text-left p-2 hover:bg-zinc-800/70">
      <div class="font-medium">${r.judul || "—"}</div>
      <div class="text-xs text-zinc-400">${r.perusahaan || "—"} • ${(r.lokasi||"—").toUpperCase()}</div>
    </button>
  `).join("");
  Array.from(dd.children).forEach((btn, i)=>{
    btn.addEventListener("click", ()=>{
      picked[slotIdx] = rows[i];
      const box = dd.closest(".cmp-slot").querySelector(".cmp-picked");
      box.innerHTML = `
        <div class="rounded-xl border border-zinc-800 bg-zinc-900 p-2">
          <div class="font-medium">${rows[i].judul || "—"}</div>
          <div class="text-xs text-zinc-500">${rows[i].perusahaan || "—"}</div>
          <div class="text-xs text-zinc-500">${(rows[i].lokasi||"—").toUpperCase()}</div>
        </div>`;
      dd.classList.add("hidden");
      updateButtons();
    });
  });
}

function setupSlot(slot){
  const idx = Number(slot.dataset.slot);
  const inp = slot.querySelector(".cmp-input");
  const dd  = slot.querySelector(".cmp-dd");

  inp.addEventListener("input", debounce(async ()=>{
    const q = (inp.value||"").trim();

    // tampilkan hint ketika < MIN_CHARS
    if(q.length < MIN_CHARS){
      dd.classList.remove("hidden");
      dd.innerHTML = `<div class="p-2 text-xs text-zinc-500">Ketik minimal ${MIN_CHARS} karakter…</div>`;
      return;
    }

    const rows = await searchJobs(q);
    dd.classList.remove("hidden");
    renderDropdown(dd, rows, idx);
  }, 250));

  document.addEventListener("click", (e)=>{
    if(!slot.contains(e.target)) dd.classList.add("hidden");
  });
}

function fieldRow(label, values){
  const th = `<th class="text-left align-top px-3 py-2 text-xs text-zinc-400 w-48">${label}</th>`;
  // whitespace-pre-line agar deskripsi (newline) rapi
  const tds = values.map(v => `<td class="align-top px-3 py-2 rounded-xl border border-zinc-800 bg-zinc-900 whitespace-pre-line">${v}</td>`).join("");
  return `<tr>${th}${tds}</tr>`;
}

function renderCompare(){
  const cols = picked.filter(Boolean);
  if(cols.length < 2) return;

  $("#cmp-count").textContent = `${cols.length} job dibandingkan`;
  const vals = (fn)=> cols.map(fn);

  const body = [
    // Judul + perusahaan
    fieldRow("Judul", vals(r=>`<div class="font-semibold">${r.judul||"—"}</div><div class="text-xs text-zinc-500">${r.perusahaan||"—"}</div>`)),
    fieldRow("Lokasi", vals(r=>(r.lokasi||"—").toUpperCase())),
    fieldRow("Program Studi", vals(r => r.sektor || "—")),    
    fieldRow("Tanggal Posting", vals(r=> r.tanggal_posting || "—")),
    fieldRow("Pelamar", vals(r=> num(r.pelamar))),
    fieldRow("Kuota",   vals(r=> num(r.kuota))),
    fieldRow("Acceptance Rate", vals(r=> pct(r.acceptance_rate))),
    fieldRow("Demand Ratio",    vals(r=> (r.demand_ratio==null? "—" : Number(r.demand_ratio).toFixed(2)))),
    // === BARU: Deskripsi ===
    fieldRow("Deskripsi",    vals(r => (r.deskripsi_short && r.deskripsi_short.trim()) ? r.deskripsi_short : "—")),
    fieldRow("Tautan Sumber", vals(r=> r.source_url ? `<a class="underline text-sky-400" href="${r.source_url}" target="_blank" rel="noopener">Lihat detail →</a>` : "—")),
  ].join("");

  $("#cmp-tbody").innerHTML = body;
  $("#cmp-result").classList.remove("hidden");
}

window.addEventListener("DOMContentLoaded", ()=>{
  $$(".cmp-slot").forEach(setupSlot);
  $("#btn-compare").addEventListener("click", renderCompare);
  $("#btn-clear").addEventListener("click", clearAll);
  updateButtons();
});