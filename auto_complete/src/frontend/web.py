from __future__ import annotations
import argparse
from flask import Flask, request, jsonify, Response
from backend.engine import Engine
from backend.config import TOP_K

app = Flask(__name__)
_engine: Engine | None = None

# ---------- API ----------
@app.get("/api/complete")
def api_complete():
    q = request.args.get("q", "", type=str)
    k = request.args.get("k", TOP_K, type=int)
    if not q:
        return jsonify([])
    rows = _engine.complete(q, top_k=k)  # type: ignore
    return jsonify(rows)
# ---------- UI ----------
@app.get("/")
def home():
    # A tiny SPA: CSS variables + minimal JS, no external deps.
    html = r"""
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>Autocomplete • Flask UI</title>
<style>
:root{
  --bg:#0b0f14;
  --panel:#0f141b;
  --ink:#cfd8e3;
  --muted:#8a94a6;
  --accent:#6ee7ff;
  --accent-2:#22d3ee;
  --border:#1c2530;
  --danger:#ff5d5d;
  --ok:#45d483;
  --mark-bg:rgba(110,231,255,.2);
}
*{box-sizing:border-box}
html,body{height:100%}
body{
  margin:0; background:var(--bg); color:var(--ink);
  font:16px/1.45 system-ui,-apple-system,Segoe UI,Roboto,Ubuntu,"Helvetica Neue",Arial;
}
.container{
  max-width:980px; margin:24px auto; padding:0 16px;
}
.card{
  background:var(--panel); border:1px solid var(--border);
  border-radius:16px; padding:18px; box-shadow:0 10px 30px rgba(0,0,0,.25);
}
h1{
  font-size:20px; margin:0 0 8px 0; letter-spacing:.3px;
}
.controls{
  display:flex; gap:12px; align-items:center; margin:12px 0 4px 0; flex-wrap:wrap;
}
.input{
  position:relative; flex:1; min-width:240px;
}
.input input{
  width:100%; padding:12px 14px; border-radius:12px; border:1px solid var(--border);
  background:#0b1117; color:var(--ink); outline:none; font-size:16px;
}
.input input:focus{ border-color:var(--accent) }
.badge{
  display:inline-flex; align-items:center; gap:8px;
  padding:10px 12px; border:1px solid var(--border); border-radius:12px;
  background:#0b1117; color:var(--muted);
}
.badge input{
  width:64px; background:transparent; border:none; color:var(--ink); font-size:15px;
  outline:none; text-align:center;
}
.btn{
  padding:10px 14px; border-radius:10px; border:1px solid var(--border);
  background:#0b1117; color:var(--ink); cursor:pointer;
}
.btn:hover{ border-color:var(--accent-2) }
.meta{
  display:flex; justify-content:space-between; align-items:center; color:var(--muted);
  font-size:13px; margin-top:6px;
}
.err{
  display:none; margin-top:12px; padding:10px 12px; border-radius:10px;
  background:rgba(255,93,93,.12); border:1px solid rgba(255,93,93,.35); color:#ffb0b0;
}
.results{
  margin-top:16px; overflow:clip; border-radius:12px; border:1px solid var(--border);
}
.row{
  display:grid; grid-template-columns:3rem 6rem 7rem 1fr; gap:10px; align-items:start;
  padding:12px 14px; border-top:1px solid var(--border);
}
.row:first-child{ border-top:none }
.row:hover{ background:#0d131a }
.head{ background:#0d131a; font-weight:600; color:var(--muted) }
.small{ color:var(--muted); font-variant-numeric:tabular-nums }
.mark{ background:var(--mark-bg); border-bottom:1px solid var(--accent-2) }
.mono{ font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace }
.spinner{
  display:none; width:22px; height:22px; border:3px solid #0b1117; border-top:3px solid var(--accent);
  border-radius:50%; animation:spin 1s linear infinite;
}
@keyframes spin{ to { transform: rotate(360deg) } }
.empty{
  padding:24px; text-align:center; color:var(--muted);
}
a { color: var(--accent); text-decoration: none }
a:hover { text-decoration: underline }
footer{
  margin:26px 0 6px 0; color:var(--muted); font-size:12px; text-align:center;
}
kbd{ background:#111825; border:1px solid var(--border); padding:1px 6px; border-radius:6px; color:var(--ink) }
</style>
</head>
<body>
  <div class="container">
    <div class="card">
      <h1>Autocomplete</h1>
      <div class="controls">
        <div class="input">
          <input id="q" type="text" placeholder="Type to search…" autocomplete="off" autofocus />
        </div>
        <div class="badge">Top-K <input id="k" type="number" min="1" max="50" value="10" class="mono" /></div>
        <button id="clear" class="btn">Clear</button>
        <div id="spin" class="spinner" aria-label="Loading"></div>
      </div>
      <div class="meta">
        <div id="stats">Ready.</div>
        <div>Tip: Press <kbd>Esc</kbd> to clear.</div>
      </div>
      <div id="err" class="err"></div>
      <div class="results">
        <div class="row head">
          <div>#</div><div>Score</div><div>Offset</div><div>Sentence</div>
        </div>
        <div id="out" class="empty">Start typing to see results.</div>
      </div>
    </div>
    <footer>
      Built with Flask • Client-side highlighting • No external JS/CSS deps
    </footer>
  </div>

<script>
const $ = (sel) => document.querySelector(sel);
const q = $("#q"), out = $("#out"), err = $("#err"), stats = $("#stats"), spin = $("#spin"), k = $("#k"), clearBtn = $("#clear");

let t; // debounce timer
function escapeRegExp(s){return s.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')}
function highlight(text, query){
  if(!query) return text;
  try{
    const re = new RegExp(escapeRegExp(query), "ig");
    return text.replace(re, (m)=>`<span class="mark">${m}</span>`);
  }catch(e){ return text; }
}
function fmtOffset(off){ return Array.isArray(off) && off.length===2 ? `(${off[0]},${off[1]})` : "—"; }

async function search(){
  const query = q.value.trimStart(); // keep trailing spaces if the engine cares
  const topk = Math.max(1, Math.min(50, parseInt(k.value || "10", 10)));
  if(query.length === 0){
    out.className = "empty";
    out.innerHTML = "Start typing to see results.";
    stats.textContent = "Ready.";
    err.style.display = "none";
    return;
  }
  spin.style.display = "inline-block";
  err.style.display = "none";
  const t0 = performance.now();
  try{
    const resp = await fetch(`/api/complete?q=${encodeURIComponent(query)}&k=${topk}`);
    if(!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();
    const dt = Math.max(1, Math.round(performance.now() - t0));
    stats.textContent = `Results: ${data.length} • ~${dt} ms`;
    if(!Array.isArray(data) || data.length === 0){
      out.className = "empty";
      out.innerHTML = "No matches.";
      return;
    }
    out.className = "";
    out.innerHTML = data.map((r,i)=>{
      const sent = r.completed_sentence ?? r.original ?? "";
      const display = highlight(sent, query);
      const src = r.source_text ? ` title="${String(r.source_text).replaceAll('"','&quot;')}"` : "";
      return `
        <div class="row">
          <div class="small">${i+1}</div>
          <div class="small mono">${r.score ?? ""}</div>
          <div class="small mono">${fmtOffset(r.offset)}</div>
          <div${src}>${display}</div>
        </div>`;
    }).join("");
  }catch(e){
    err.style.display = "block";
    err.textContent = `Error: ${e.message ?? e}`;
    stats.textContent = "Error.";
  }finally{
    spin.style.display = "none";
  }
}

function debouncedSearch(){
  clearTimeout(t);
  t = setTimeout(search, 150);
}

q.addEventListener("input", debouncedSearch);
k.addEventListener("change", debouncedSearch);
clearBtn.addEventListener("click", ()=>{
  q.value = "";
  q.focus();
  out.className = "empty";
  out.innerHTML = "Start typing to see results.";
  stats.textContent = "Ready.";
  err.style.display = "none";
});
window.addEventListener("keydown", (ev)=>{
  if(ev.key === "Escape"){
    clearBtn.click();
  }else if(ev.key === "Enter"){
    search();
  }
});
</script>
</body>
</html>
"""
    return Response(html, mimetype="text/html")

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Run Flask UI on top of Engine")
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--build", action="store_true")
    mode.add_argument("--load", action="store_true")
    ap.add_argument("--roots", nargs="+", default=[])
    ap.add_argument("--cache", default=None)
    ap.add_argument("--db", dest="db", default=None)  # DSN: "sqlite:///path" or "memory://"
    ap.add_argument("--acx", default=None)
    ap.add_argument("--unit", choices=["line","paragraph","window"])
    ap.add_argument("--window-size", type=int)
    ap.add_argument("--window-step", type=int)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args(argv)

    global _engine
    _engine = Engine()
    if args.build:
        if not args.roots:
            ap.error("--build requires --roots")
        _engine.build(
            roots=args.roots, cache=args.cache, db_dsn=args.db,
            unit=args.unit, window_size=args.window_size, window_step=args.window_step,
            verbose=args.verbose,
        )
    else:
        _engine.load(cache=args.cache, db_dsn=args.db, acx=args.acx, verbose=args.verbose)

    try:
        app.run(host=args.host, port=args.port, debug=args.verbose)
    finally:
        _engine.shutdown()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
