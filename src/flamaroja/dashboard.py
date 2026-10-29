from __future__ import annotations

import json
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO

_PAGE = """<!doctype html>
<html lang="ca">
<head>
<meta charset="utf-8">
<title>flama-roja-jev</title>
<style>
  :root { --bg:#0d1117; --panel:#161b22; --border:#30363d; --text:#e6edf3; --dim:#8b949e; --win:#7ee787; --accent:#ff7a2f; }
  * { box-sizing: border-box; }
  body { background:var(--bg); color:var(--text); margin:0; padding:20px;
         font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace; font-size:14px; }
  header { display:flex; gap:18px; align-items:baseline; margin-bottom:16px; flex-wrap:wrap; }
  h1 { font-size:18px; margin:0; color:var(--accent); }
  header .stat { color:var(--dim); } header .stat b { color:var(--text); }
  .grid { display:grid; grid-template-columns: 484px 1fr; gap:16px; max-width:1280px; }
  @media (max-width: 1000px) { .grid { grid-template-columns: 1fr; } }
  .card { background:var(--panel); border:1px solid var(--border); border-radius:10px; padding:14px; margin-bottom:14px; }
  .card h2 { font-size:12px; text-transform:uppercase; letter-spacing:.08em; color:var(--dim); margin:0 0 10px; }
  img.game { width:480px; image-rendering:pixelated; border-radius:6px; display:block; background:#000; }
  .q { margin-bottom:12px; }
  .q .head { display:flex; justify-content:space-between; margin-bottom:4px; }
  .q .val { color:var(--win); font-weight:bold; }
  .row { display:flex; align-items:center; gap:8px; margin:3px 0; }
  .row .label { width:130px; color:var(--dim); overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
  .row .bar { flex:1; height:9px; background:#21262d; border-radius:5px; overflow:hidden; }
  .row .bar i { display:block; height:100%; background:#58a6ff; border-radius:5px; }
  .row.winner .bar i { background:var(--win); }
  .row.winner .label { color:var(--text); }
  .row .pct { width:52px; text-align:right; color:var(--dim); }
  .press { display:inline-block; background:var(--accent); color:#000; font-weight:bold;
           padding:3px 10px; border-radius:6px; margin-right:6px; }
  .log { color:var(--dim); line-height:1.5; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
  .log b { color:var(--text); }
  .dialog { font-style:italic; color:#d2a8ff; min-height:18px; }
  .party-row { display:flex; justify-content:space-between; padding:2px 0; }
  .hp-low { color:#f85149; } .hp-ok { color:var(--win); }
</style>
</head>
<body>
<header>
  <h1>flama-roja-jev</h1>
  <span class="stat">backend <b id="backend">-</b></span>
  <span class="stat">model <b id="model">-</b></span>
  <span class="stat">cicle <b id="cycle">0</b></span>
  <span class="stat">frame <b id="frame">0</b></span>
  <span class="stat">latencia <b id="latency">0</b>ms</span>
  <span class="stat">tokens <b id="tokens">-</b></span>
</header>
<div class="grid">
  <div>
    <div class="card"><h2>game boy advance</h2><img class="game" id="stream" src="/stream"></div>
    <div class="card"><h2>estat</h2><div id="state">-</div></div>
    <div class="card"><h2>accio executada</h2><div id="presses">-</div></div>
  </div>
  <div>
    <div class="card"><h2>decisions de jev (paral·leles sobre el mateix estat)</h2><div id="questions">-</div></div>
    <div class="card"><h2>ultims cicles</h2><div class="log" id="log">-</div></div>
  </div>
</div>
<script>
const QUESTIONS = [
  ["screen_mode","choice","pantalla"],
  ["overworld_action","choice","accio overworld"],
  ["dialog_response","choice","resposta dialog"],
  ["battle_plan","choice","pla batalla"],
  ["objective","choice","objectiu"],
  ["party_critical","noul","party critical"],
  ["enemy_threat","score","amenaaca enemic"],
];
function esc(s){const d=document.createElement("div");d.textContent=String(s);return d.innerHTML;}
function bars(q){
  const probs = q.probs || {};
  const entries = Object.entries(probs).sort((a,b)=>b[1]-a[1]);
  if(!entries.length) return `<div class="row"><span class="label">${esc(q.value)}</span></div>`;
  return entries.map(([k,v],i)=>`<div class="row ${i===0?"winner":""}">
    <span class="label">${esc(k)}</span>
    <span class="bar"><i style="width:${Math.max(2,Math.round(v*100))}%"></i></span>
    <span class="pct">${(v*100).toFixed(1)}%</span></div>`).join("");
}
function gauge(q){
  const v = Math.max(0, Math.min(1, Number(q.value)||0));
  const col = v>0.66?"#f85149":v>0.33?"#d29922":"#7ee787";
  return `<div class="row winner"><span class="bar"><i style="width:${(v*100).toFixed(1)}%;background:${col}"></i></span>
          <span class="pct">${v.toFixed(2)}</span></div>`;
}
async function tick(){
  try{
    const s = await (await fetch("/api/state")).json();
    document.getElementById("backend").textContent = s.backend||"-";
    document.getElementById("model").textContent = s.model||"-";
    document.getElementById("cycle").textContent = s.cycle??0;
    document.getElementById("frame").textContent = s.frame??0;
    document.getElementById("latency").textContent = s.latency_ms??0;
    document.getElementById("tokens").textContent = s.usage ? `${s.usage.input}/${s.usage.output}` : "-";
    const st = s.state||{};
    const party = (st.party||[]).map(m=>`<div class="party-row"><span>${esc(m.nickname||m.species)} Lv${m.level}</span>
      <span class="${(m.current_hp||0)<10?"hp-low":"hp-ok"}">HP ${m.current_hp}</span></div>`).join("");
    document.getElementById("state").innerHTML =
      `map <b>${st.map?.bank}/${st.map?.number}</b> pos (${st.map?.camera_x},${st.map?.camera_y})<br>
       jugador <b>${esc(st.player?.name||"-")}</b><br>${party}
       <div class="dialog">${esc(st.dialog?.text||"")}</div>`;
    document.getElementById("presses").innerHTML =
      (s.presses||[]).map(p=>`<span class="press">${esc(p.button)}</span>`).join("") || "<small>espera</small>";
    document.getElementById("questions").innerHTML = (s.decisions||[]).map(([id,type,label,val,probs])=>{
      let body;
      if(type==="noul") body = gauge({value:val});
      else if(type==="score"){ const v=Math.max(0,Math.min(2,Number(val)||0));
        body=`<div class="row winner"><span class="bar"><i style="width:${(v/2*100).toFixed(1)}%;background:#d29922"></i></span><span class="pct">${v.toFixed(2)}/2</span></div>`; }
      else body = bars({value:val,probs:probs});
      return `<div class="q"><div class="head"><span>${esc(label)}</span><span class="val">${esc(val)}</span></div>${body}</div>`;
    }).join("");
    document.getElementById("log").innerHTML = (s.log||[]).map(l=>`<div>${esc(l)}</div>`).join("");
  }catch(e){}
  setTimeout(tick, 300);
}
tick();
</script>
</body></html>
"""


class Dashboard:
    def __init__(self, backend: str, model: str, port: int = 8000) -> None:
        self.backend = backend
        self.model = model
        self.port = port
        self.jpeg = b""
        self.data: dict = {"backend": backend, "model": model, "log": []}
        self._log: deque[str] = deque(maxlen=12)
        self._lock = threading.Lock()
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    def publish_frame(self, image) -> None:
        buf = BytesIO()
        image.convert("RGB").save(buf, "JPEG", quality=70)
        with self._lock:
            self.jpeg = buf.getvalue()

    def publish(
        self,
        cycle: int,
        frame: int,
        latency_ms: int,
        usage: tuple[int, int] | None,
        state: dict,
        decisions: list,
        presses: list,
        line: str,
    ) -> None:
        self._log.appendleft(line)
        with self._lock:
            self.data.update(
                {
                    "cycle": cycle,
                    "frame": frame,
                    "latency_ms": latency_ms,
                    "usage": {"input": usage[0], "output": usage[1]} if usage else None,
                    "state": state,
                    "decisions": decisions,
                    "presses": presses,
                    "log": list(self._log),
                }
            )

    def start(self) -> None:
        dash = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args) -> None:
                pass

            def do_GET(self) -> None:
                if self.path == "/api/state":
                    with dash._lock:
                        body = json.dumps(dash.data).encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                elif self.path == "/stream":
                    self.send_response(200)
                    self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
                    self.end_headers()
                    try:
                        while True:
                            with dash._lock:
                                frame = dash.jpeg
                            if not frame:
                                time.sleep(0.05)
                                continue
                            self.wfile.write(
                                b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: "
                                + str(len(frame)).encode()
                                + b"\r\n\r\n"
                                + frame
                                + b"\r\n"
                            )
                            time.sleep(1 / 30)
                    except (BrokenPipeError, ConnectionResetError):
                        return
                else:
                    body = _PAGE.encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)

        self._server = ThreadingHTTPServer(("127.0.0.1", self.port), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server = None
