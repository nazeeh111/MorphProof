"""A local, dependency-free evidence browser. Reports never execute embedded code."""
from __future__ import annotations

import hashlib
import json
import math
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


def _safe(value: Any) -> Any:
    if isinstance(value, float) and not math.isfinite(value):
        return "NaN" if math.isnan(value) else ("+Infinity" if value > 0 else "-Infinity")
    if isinstance(value, dict):
        return {str(k): _safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(v) for v in value]
    return value


def render_studio(run_dir: Path) -> Path:
    """Render report.json and optional run.json to a portable studio.html file."""
    run_dir = Path(run_dir).resolve()
    report = json.loads((run_dir / "report.json").read_text(encoding="utf-8"))
    metadata_path = run_dir / "run.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.exists() else {}
    if not isinstance(report, dict) or not isinstance(metadata, dict):
        raise ValueError("Studio report.json and run.json must contain JSON objects")
    if not isinstance(metadata.get("attempts", []), list):
        raise ValueError("Studio run.json attempts must be a JSON array")
    for record in [metadata, *metadata.get("attempts", [])]:
        if isinstance(record, dict):
            record["_source_hashes"] = {
                key: hashlib.sha256(record[key].encode("utf-8")).hexdigest()
                for key in ("reference_source", "rust_source") if isinstance(record.get(key), str)
            }
    bundle = _safe({"report": report, "run": metadata})
    # Preserve Python's float representation (including signed zero) on download.
    bundle["report_export"] = json.dumps(bundle["report"], ensure_ascii=True, indent=2)
    for attempt in bundle["run"].get("attempts", []):
        if isinstance(attempt, dict) and isinstance(attempt.get("report"), dict):
            attempt["_report_export"] = json.dumps(attempt["report"], ensure_ascii=True, indent=2)
    payload = json.dumps(bundle, ensure_ascii=True)
    payload = payload.replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")
    destination = run_dir / "studio.html"
    destination.write_text(_PAGE.replace("__MORPHPROOF_DATA__", payload), encoding="utf-8")
    return destination


def serve(run_dir: Path, host: str = "127.0.0.1", port: int = 8765) -> None:
    """Serve only the rendered UI and its report; no file browsing or mutations."""
    run_dir = Path(run_dir).resolve()
    render_studio(run_dir)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            route = self.path.split("?", 1)[0]
            paths = {"/": ("studio.html", "text/html; charset=utf-8"),
                     "/studio.html": ("studio.html", "text/html; charset=utf-8"),
                     "/report.json": ("report.json", "application/json; charset=utf-8")}
            target = paths.get(route)
            if not target:
                self.send_error(404)
                return
            try:
                content = (run_dir / target[0]).read_bytes()
            except OSError:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", target[1])
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.end_headers()
            self.wfile.write(content)

        def log_message(self, format: str, *args: Any) -> None:
            pass

    server = ThreadingHTTPServer((host, port), Handler)
    print(f"MORPHPROOF Studio: http://{host}:{server.server_address[1]}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


_PAGE = r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>MORPHPROOF Studio · Behavioral evidence</title>
<style>
:root{--paper:#f5f3ec;--card:#fffefa;--ink:#242923;--muted:#687068;--line:#d9ddd2;--orange:#d84f24;--teal:#236f61;--soft:#e8eee5;--mono:ui-monospace,SFMono-Regular,Consolas,monospace;--sans:Inter,ui-sans-serif,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
*{box-sizing:border-box}html{scroll-behavior:smooth;scroll-padding-top:28px}body{margin:0;font:14px/1.55 var(--sans);background:var(--paper);color:var(--ink)}button,select{font:inherit;color:inherit}button,select,a{touch-action:manipulation}button,select{min-height:40px}button{cursor:pointer}button:focus-visible,select:focus-visible,a:focus-visible,summary:focus-visible{outline:3px solid var(--orange);outline-offset:4px}a{color:inherit}button{background:var(--card);border:1px solid var(--line);padding:8px 13px;border-radius:5px}button:hover{border-color:var(--ink)}.app{max-width:1680px;margin:auto;display:grid;grid-template-columns:216px minmax(0,1fr);min-height:100vh}.rail{position:sticky;top:0;height:100vh;background:#222922;color:#f5f3ec;padding:30px 22px;display:flex;flex-direction:column;border-right:1px solid #394237}.brand{display:flex;align-items:center;gap:10px;font-size:15px;letter-spacing:.045em;font-weight:800}.mark{width:30px;height:30px;flex:none}.studio-label{font:10px var(--mono);color:#aab9a5;letter-spacing:.18em;padding:9px 0 0 41px}.rail-note{font:11px/1.8 var(--mono);color:#9eac9a;margin:52px 0 15px}.rail nav{display:grid;gap:6px}.rail nav a{font-size:12px;text-decoration:none;color:#d1dacd;padding:11px 10px;border-radius:4px;display:flex;gap:12px}.rail nav a:hover{background:#364033;color:#fff}.rail nav a[aria-current=location]{background:#364033;color:#fff}.nav-num{font:10px var(--mono);color:#aab9a5;padding-top:3px}.rail-foot{margin-top:auto;padding-top:80px;font:11px/1.8 var(--mono);color:#9eac9a}.rail-foot b{display:block;color:#e0e7da;font-weight:400}.workspace{padding:0 42px 45px;min-width:0}.topbar{height:79px;display:flex;align-items:center;justify-content:space-between;gap:20px;border-bottom:1px solid var(--line)}.crumb{font:11px var(--mono);color:var(--muted)}.crumb span{color:var(--ink)}.top-actions{display:flex;align-items:center;gap:14px}.local{font:10px var(--mono);color:var(--teal);white-space:nowrap}.local:before{content:"";display:inline-block;width:6px;height:6px;margin-right:7px;border-radius:50%;background:var(--teal)}.export{font-size:11px;min-height:33px;padding:6px 10px}.hero{padding:35px 0 27px;display:flex;align-items:flex-start;justify-content:space-between;gap:25px}.eyebrow{font:10px/1.5 var(--mono);letter-spacing:.14em;text-transform:uppercase;color:var(--muted);margin-bottom:9px}h1{font-size:35px;line-height:1.15;letter-spacing:-1.6px;margin:0 0 13px;font-weight:650}h1 em{font-style:normal;color:var(--orange)}.intro{font-size:13px;color:var(--muted);max-width:570px;margin:0}.status{display:inline-flex;align-items:center;gap:7px;border:1px solid #b9cec1;background:#edf3eb;color:var(--teal);padding:8px 11px;font:11px var(--mono);white-space:nowrap}.status:before{content:"";width:6px;height:6px;border-radius:50%;background:currentColor}.status.fail{background:#fbede6;color:#a33f20;border-color:#e7baa4}.status.error{background:#f2eada;color:#835b20;border-color:#d9c6a3}.hero-right{padding-top:4px;text-align:right}.run-id{font:10px var(--mono);color:var(--muted);margin-top:9px}.notice{border-left:3px solid var(--orange);padding:11px 14px;background:#eeeade;font-size:12px;color:#5c6256;margin-bottom:23px}.metric-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));border:1px solid var(--line);background:var(--card);margin-bottom:25px}.metric{padding:17px 19px 14px;border-right:1px solid var(--line)}.metric:last-child{border-right:0}.metric-label{font:10px var(--mono);color:var(--muted)}.metric-number{font-size:31px;line-height:1.35;letter-spacing:-1px;display:block;margin-top:6px}.metric-number .unit{font:12px var(--mono);letter-spacing:0;margin-left:5px;color:var(--muted)}.metric-detail{font:10px/1.6 var(--mono);color:var(--muted)}.metric-number.alert{color:var(--orange)}.section-title{display:flex;align-items:center;justify-content:space-between;gap:20px;margin:0 0 13px}.section-title h2{margin:0;font-size:16px;letter-spacing:-.3px;font-weight:650}.section-title h2 .section-no{font:10px var(--mono);color:var(--muted);margin-right:10px}.section-caption{font:10px var(--mono);color:var(--muted)}.panel{min-width:0;border:1px solid var(--line);background:var(--card)}.flow{display:flex;margin-bottom:29px;overflow-x:auto}.flow-step{min-width:145px;flex:1;padding:15px 17px;border-right:1px solid var(--line);position:relative}.flow-step:last-child{border-right:0}.flow-step .step-label{font:10px var(--mono);color:var(--muted);display:block;margin-bottom:5px}.flow-step strong{font-size:12px;font-weight:550;display:block}.flow-step .step-meta{font:10px var(--mono);color:var(--muted);display:block;margin-top:5px}.flow-step.active{box-shadow:inset 0 3px var(--teal)}.flow-step.failed{box-shadow:inset 0 3px var(--orange)}.workbench-head{display:flex;align-items:center;justify-content:space-between;gap:20px;margin-bottom:13px}.controls{display:flex;gap:9px;align-items:center;flex-wrap:wrap}.control{display:flex;align-items:center;gap:7px;font:10px var(--mono);color:var(--muted)}select{background:var(--card);border:1px solid var(--line);padding:7px 29px 7px 10px;border-radius:4px;max-width:220px;font:11px var(--mono)}.comparison{display:grid;grid-template-columns:minmax(0,1.25fr) minmax(270px,.85fr);gap:20px;margin-bottom:28px}.panel-top{flex-wrap:wrap;padding:13px 16px;border-bottom:1px solid var(--line);display:flex;justify-content:space-between;gap:12px;align-items:center}.panel-title{font:11px var(--mono);font-weight:600}.tabs{display:flex;gap:3px}.tab{border:0;background:none;font:10px var(--mono);min-height:30px;padding:5px 9px}.tab[aria-selected=true]{background:var(--soft);color:var(--teal)}.code-wrap{background:#252c28;color:#e5ecdf;padding:18px 0;overflow:auto;min-height:273px;max-height:395px}.code-lines{margin:0;counter-reset:line;font:11px/1.85 var(--mono);tab-size:4;white-space:pre;min-width:max-content}.code-line{display:block;counter-increment:line;padding:0 19px 0 0}.code-line:before{content:counter(line);display:inline-block;text-align:right;color:#7f9181;width:44px;padding-right:16px;user-select:none}.code-empty{white-space:pre-wrap;padding:0 20px;color:#aab9a8;font:12px/1.7 var(--mono)}.code-foot{flex-wrap:wrap;overflow-wrap:anywhere;font:10px var(--mono);color:var(--muted);padding:10px 16px;display:flex;justify-content:space-between}.claims{padding:4px 16px}.claim{padding:13px 0;border-bottom:1px solid var(--line)}.claim:last-child{border-bottom:0}.claim-top{display:flex;justify-content:space-between;gap:12px;font:11px var(--mono)}.claim-bottom{font-size:11px;color:var(--muted);margin-top:6px;overflow-wrap:anywhere}.pill{font:9px var(--mono);text-transform:uppercase;color:var(--teal);letter-spacing:.04em}.pill.fail{color:#aa4527}.pill.unknown{color:#777661}.empty{padding:25px 18px;color:var(--muted);font:12px/1.7 var(--mono)}.case-list{display:grid;gap:10px;margin-bottom:27px}.case{border:1px solid var(--line);background:var(--card)}.case summary{cursor:pointer;padding:14px 17px;display:flex;gap:12px;align-items:center;list-style:none}.case summary::-webkit-details-marker{display:none}.case summary:before{content:"+";font:17px var(--mono);color:var(--orange);width:14px}.case[open] summary:before{content:"−"}.case-number{font:10px var(--mono);color:var(--muted)}.case-name{font:11px var(--mono);font-weight:600}.case-tag{margin-left:auto;font:9px var(--mono);color:#a33f20;background:#f6e6dc;padding:4px 7px}.case-body{padding:0 18px 18px;border-top:1px solid var(--line)}.input-grid{display:grid;grid-template-columns:1fr 1fr;gap:20px;padding:15px 0}.field-label{font:9px var(--mono);letter-spacing:.08em;color:var(--muted);text-transform:uppercase;margin-bottom:6px}.sample{font:11px/1.7 var(--mono);overflow:auto;max-height:140px;white-space:pre-wrap;word-break:break-word;margin:0}.observations{display:grid;grid-template-columns:1fr 1fr;gap:1px;background:var(--line);border:1px solid var(--line)}.observation{background:#f1f4ec;padding:13px}.observation:last-child{background:#faf0e8}.case-note{font:10px var(--mono);color:var(--muted);margin-top:12px}.bottom-grid{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:20px;margin-bottom:26px}.table{width:100%;border-collapse:collapse;font:10px/1.7 var(--mono);table-layout:fixed}.table td{padding:10px 16px;border-bottom:1px solid var(--line);vertical-align:top;overflow-wrap:anywhere}.table tr:last-child td{border-bottom:0}.bench-table{table-layout:auto}.bench-table td:first-child{width:auto}.bench-table th{font-weight:400;color:var(--muted);padding:9px 12px;border-bottom:1px solid var(--line);text-align:left;font-size:9px}.bench-table td{padding:9px 12px;font-size:9px}.bench-wrap{overflow-x:auto}.table td:first-child{color:var(--muted);width:36%;word-break:normal}.limitations{padding:14px 18px 14px 32px;margin:0;font-size:11px;color:var(--muted)}.limitations li{padding:4px 0}.footer{border-top:1px solid var(--line);padding-top:18px;display:flex;justify-content:space-between;gap:15px;font:10px/1.6 var(--mono);color:var(--muted)}.footer strong{color:var(--ink);font-weight:400}#toast{position:fixed;bottom:22px;right:22px;background:var(--ink);color:var(--paper);padding:12px 17px;border-radius:4px;font:11px var(--mono);z-index:10}#toast:empty{display:none}.sr-only{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}
@media(min-width:1450px){.workspace{padding-left:56px;padding-right:56px}h1{font-size:42px}.hero{padding-top:43px;padding-bottom:32px}.code-wrap{min-height:310px}.metric{padding-top:21px;padding-bottom:19px}}
@media(max-width:1150px){.app{grid-template-columns:172px minmax(0,1fr)}.rail{padding:28px 15px}.brand{font-size:12px;gap:7px}.mark{width:25px;height:25px}.studio-label{padding-left:32px;font-size:9px}.workspace{padding-left:25px;padding-right:25px}.comparison{grid-template-columns:minmax(0,1.1fr) minmax(230px,.9fr);gap:14px}.metric{padding:14px}.metric-label{font-size:9px}h1{font-size:31px}.workbench-head{align-items:flex-start;flex-direction:column;gap:9px}.controls{width:100%;justify-content:flex-end}}
@media(max-width:850px){.app{grid-template-columns:1fr}.rail{position:static;height:auto;padding:17px 22px;display:flex;flex-direction:row;justify-content:space-between;align-items:center;gap:15px}.rail nav,.rail-note,.rail-foot,.studio-label{display:none}.workspace{padding:0 22px 30px}.topbar{height:64px}.hero{padding-top:25px;gap:15px}.hero-right{max-width:180px}.status{font-size:9px}.metric-grid{grid-template-columns:repeat(2,1fr)}.metric:nth-child(2){border-right:0}.metric:nth-child(-n+2){border-bottom:1px solid var(--line)}.comparison{grid-template-columns:minmax(0,1fr)}.bottom-grid{grid-template-columns:1fr}.claims{display:grid;grid-template-columns:1fr 1fr;gap:0 20px}.code-wrap{min-height:220px}.flow-step{min-width:150px}.section-caption{font-size:9px}.code-lines{font-size:11px}}
@media(max-width:520px){.workspace{padding:0 15px 25px}.local{display:none}.topbar{height:58px}.hero{display:block}.hero-right{text-align:left;max-width:none;padding-top:17px;display:flex;align-items:center;gap:15px}.run-id{margin:0}h1{font-size:31px}.intro{font-size:12px}.metric-number{font-size:28px}.metric-detail{font-size:9px}.section-title{gap:10px}.section-title h2{font-size:14px}.section-caption{display:none}.claims{display:block}.controls{justify-content:flex-start}.control{display:grid;gap:4px}select{max-width:160px}.input-grid,.observations{grid-template-columns:1fr}.case-tag{font-size:8px}.case summary{gap:8px;padding:12px}.case-body{padding:0 12px 12px}.footer{display:block}.footer span:last-child{display:block;margin-top:6px}}
@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}}@media print{.rail,.top-actions,.controls,.tabs{display:none}.app{display:block}.workspace{padding:0}.code-wrap{max-height:none}.case-body{display:block}.comparison{grid-template-columns:minmax(0,1fr)}.hero{padding-top:20px}.footer{break-inside:avoid}body{background:#fff}}

[hidden]{display:none!important}
.hero{padding-bottom:18px}
.witness{margin:0 0 21px;border-block:1px solid var(--line);padding:12px 0;display:flex;align-items:center;justify-content:space-between;gap:14px}
.witness-values{min-width:0;display:grid;grid-template-columns:.9fr 1fr 1fr;flex:1;margin:0;gap:12px}
.witness-values dt{font-size:12px;color:var(--muted)}
.witness-values dd{margin:2px 0 0;font:700 clamp(18px,2.5vw,34px)/1.15 var(--mono);overflow-wrap:anywhere}
.witness-values div:last-child dd{color:#a33f20}
#inspect-witness{min-height:44px}
.flow{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(175px,100%),1fr));gap:1px;background:var(--line);overflow:visible;margin-bottom:22px}
.flow-step{width:100%;border:0;border-radius:0;text-align:left;background:var(--card);min-width:0;min-height:55px}
.flow-step[aria-pressed=true]{background:var(--soft);box-shadow:inset 0 -3px var(--teal)}
.flow-step.failed[aria-pressed=true]{background:#fbede6;box-shadow:inset 0 -3px var(--orange)}
.flow-step strong{font-size:14px;overflow-wrap:anywhere}
.flow-step .step-meta{font-size:11px}
.case summary:focus-visible{outline-offset:-3px}
@media(max-width:610px){.witness{display:block}.witness-values{gap:8px}#inspect-witness{margin-top:10px}.flow{grid-template-columns:1fr}}
</style></head><body>
<div class="app"><aside class="rail"><div><div class="brand"><svg class="mark" viewBox="0 0 32 32" aria-hidden="true"><path d="M1 1h12v12H1zM19 19h12v12H19z" fill="#e56438"/><path d="M19 1h12L13 31H1z" fill="#edf0e4"/></svg>MORPHPROOF</div><div class="studio-label">STUDIO / 01</div></div><div class="rail-note">WORKSPACE</div><nav aria-label="Report sections"><a href="#overview"><span class="nav-num">01</span>Overview</a><a href="#workbench"><span class="nav-num">02</span>Contract inspector</a><a href="#counterexamples"><span class="nav-num">03</span>Counterexamples</a><a href="#reproduce"><span class="nav-num">04</span>Provenance</a></nav><div class="rail-foot"><b>Change the implementation.</b>Preserve the contract.<br>Prove what was tested.<br><br>LOCAL EVIDENCE BROWSER<br>NO CLOUD REQUIRED</div></aside>
<main class="workspace" id="overview"><header class="topbar"><div class="crumb">MORPHPROOF <span>/ Behavioral evidence</span></div><div class="top-actions"><span class="local">Local report</span><button class="export" id="export">↓ Export JSON</button></div></header>
<section class="hero" aria-labelledby="report-title"><div><h1 id="report-title">Recorded transformation evidence</h1><p class="intro" id="intro">Inspect the outcomes and tested inputs for this attempt.</p></div><div class="hero-right"><div class="status" id="status" role="status">Loading evidence</div><div class="run-id" id="run-id"></div></div></section>
<section id="witness" class="witness" aria-label="Recorded positional counterexample" hidden>
  <dl class="witness-values"><div><dt>Recorded input</dt><dd id="witness-input"></dd></div><div><dt>Python reference</dt><dd id="witness-reference"></dd></div><div><dt>Candidate</dt><dd id="witness-candidate"></dd></div></dl>
  <button id="inspect-witness" type="button">Inspect this counterexample</button>
</section>
<div class="section-title"><h2>Transformation record</h2></div><section class="panel flow" id="flow" aria-label="Select a recorded transformation attempt"></section>
<div class="notice">A finite test suite provides evidence of compatibility. It does not prove universal equivalence.</div>
<section class="metric-grid" aria-label="Recorded results"><div class="metric"><div class="metric-label">DIFFERENTIAL TESTS</div><strong class="metric-number" id="tested">—</strong><div class="metric-detail">Candidate executions recorded</div></div><div class="metric"><div class="metric-label">INCOMPATIBILITIES</div><strong class="metric-number" id="failures">—</strong><div class="metric-detail" id="failure-detail">Observed behavior differences</div></div><div class="metric"><div class="metric-label">COUNTEREXAMPLE SEARCH</div><strong class="metric-number" id="shrinks">—</strong><div class="metric-detail">Additional minimization executions</div></div><div class="metric"><div class="metric-label" id="metric4-label">DECLARED FUNCTIONS</div><strong class="metric-number" id="metric4">—</strong><div class="metric-detail" id="metric4-detail">Within the selected contract</div></div></section>

<section id="workbench"><div class="workbench-head"><div class="section-title" style="margin:0"><h2><span class="section-no">02</span>Contract inspector</h2></div><div class="controls"><label class="control">ATTEMPT <select id="attempt" aria-label="Select transformation attempt"></select></label><label class="control">FUNCTION <select id="function" aria-label="Filter function"></select></label></div></div><div class="comparison"><section class="panel"><div class="panel-top"><span class="panel-title">Implementation</span><div class="tabs" role="tablist" aria-label="Source language"><button class="tab" id="python-tab" role="tab" aria-controls="code" aria-selected="true" tabindex="0" data-code="reference_source">Python reference</button><button class="tab" id="rust-tab" role="tab" aria-controls="code" aria-selected="false" tabindex="-1" data-code="rust_source">Rust candidate</button></div></div><div class="code-wrap" id="code" role="tabpanel" aria-labelledby="python-tab" tabindex="0"></div><div class="code-foot"><span id="code-label">Frozen reference</span><span id="code-hash"></span></div></section><section class="panel"><div class="panel-top"><span class="panel-title">Behavioral claims</span><span class="section-caption">EVIDENCE LEDGER</span></div><div class="claims" id="claims"></div></section></div></section>
<section id="counterexamples"><div class="section-title"><h2><span class="section-no">03</span>Counterexamples</h2><span class="section-caption" id="case-caption">Minimal inputs, observable differences</span></div><div class="case-list" id="cases"></div></section>
<section id="reproduce"><div class="section-title"><h2><span class="section-no">04</span>Reproduce & inspect</h2><span class="section-caption">Source identity and limits</span></div><div class="bottom-grid"><section class="panel"><div class="panel-top"><span class="panel-title">Run provenance</span><span class="section-caption">SHA-256</span></div><table class="table" aria-label="Run provenance"><tbody id="provenance"></tbody></table></section><section class="panel"><div class="panel-top"><span class="panel-title" id="other-title">Scope & limitations</span></div><ul class="limitations" id="limitations"></ul><div class="bench-wrap"><table class="table bench-table" id="benchmark-rows" aria-label="Per-function benchmark results"><thead><tr><th>FUNCTION</th><th>INPUTS</th><th>PYTHON μs</th><th>RUST μs</th><th>SPEEDUP</th></tr></thead><tbody id="benchmark-data"></tbody></table></div><table class="table" id="benchmark-table" aria-label="Benchmark conditions"><tbody id="benchmark"></tbody></table></section></div></section>
<footer class="footer"><span><strong>MORPHPROOF</strong> · Change the implementation. Preserve the contract.</span><span>VERIFIED ≠ UNIVERSALLY PROVEN</span></footer></main></div><div id="toast" role="status" aria-live="polite"></div>
<script id="evidence-data" type="application/json">__MORPHPROOF_DATA__</script>
<script>
'use strict';
const data=JSON.parse(document.getElementById('evidence-data').textContent),meta=data.run||{},root=data.report||{};
const $=id=>document.getElementById(id), node=(tag,cls,txt)=>{const e=document.createElement(tag);if(cls)e.className=cls;if(txt!==undefined)e.textContent=txt;return e;};
const pretty=v=>JSON.stringify(v,(_k,x)=>Object.is(x,-0)?'-0.0':x&&typeof x==='object'&&Object.keys(x).length===1&&'$float'in x?({nan:'NaN','+inf':'+Infinity','-inf':'-Infinity'}[x.$float]||x):x,2),num=v=>Number.isFinite(Number(v))?Number(v).toLocaleString():'—';
const asArray=value=>Array.isArray(value)?value:[];
const isRecord=value=>value!==null&&typeof value==='object'&&!Array.isArray(value);
const functionRecords=r=>asArray(r.functions).filter(isRecord);
let report=root,activeCode='reference_source',witnessTarget=null;
const attempts=asArray(meta.attempts).filter(a=>isRecord(a?.report));
if(!attempts.length)attempts.push({label:'Current candidate',report:root,_report_export:data.report_export});
const testedCount=r=>(Number(r.totals?.tested)||0)+(Number(r.totals?.api_tested)||0);
const statusText=r=>r.status==='incompatible'?'Compatibility failure found':
  r.status==='compatible'&&testedCount(r)>0?'Compatible on tested inputs':'Verification incomplete';
const statusClass=r=>r.status==='incompatible'?'fail':
  r.status==='compatible'&&testedCount(r)>0?'':'error';
function floatText(value){
  if(typeof value==='number'){
    if(Object.is(value,-0))return '-0.0';
    return Number.isInteger(value)?value.toFixed(1):String(value);
  }
  return isRecord(value)?({nan:'NaN','+inf':'+Infinity','-inf':'-Infinity'})[value.$float]:undefined;
}
function displayOutcome(outcome){
  if(outcome?.kind==='return'&&typeof outcome.type==='string'&&Object.hasOwn(outcome,'value')){
    const value=outcome.type==='float'?floatText(outcome.value):pretty(outcome.value);
    if(value!==undefined)return {text:value,identity:[outcome.kind,outcome.type,value]};
  }
  if(outcome?.kind==='exception'&&typeof outcome.type==='string'&&typeof outcome.message==='string'){
    return {text:outcome.type,identity:[outcome.kind,outcome.type,outcome.message]};
  }
}
function positionalWitness(candidate,functions=functionRecords(candidate)){
  if(candidate.status!=='incompatible'||!(Number(candidate.totals?.failures)>0))return null;
  for(const f of functions){
    if(f.status!=='incompatible'||!(Number(f.failures)>0)||typeof f.name!=='string'||!f.name)continue;
    for(const test of asArray(f.counterexamples)){
      if(!isRecord(test)||Object.hasOwn(test,'keyword')||test.family==='keyword-api')continue;
      const observations=[
        [test.minimized_input,test.minimized_reference,test.minimized_candidate],
        [test.input,test.reference,test.candidate],
      ];
      for(const [index,[input,reference,replacement]] of observations.entries()){
        if(!Array.isArray(input)||!input.every(value=>floatText(value)!==undefined))continue;
        const a=displayOutcome(reference),b=displayOutcome(replacement);
        if(a&&b&&JSON.stringify(a.identity)!==JSON.stringify(b.identity)){
          return {test,input,minimized:index===0,reference:a.text,candidate:b.text,functionName:f.name,
            sameDisplay:a.text===b.text};
        }
      }
    }
  }
  return null;
}
const latestWitness=attempts.reduce((last,attempt,i)=>positionalWitness(attempt.report)?i:last,-1);
attempts.forEach((a,i)=>{
  const option=node('option','',a.label||'Attempt '+(i+1));
  option.value=i;
  $('attempt').append(option);
});
$('attempt').value=latestWitness<0?attempts.length-1:latestWitness;
const attemptButtons=attempts.map((a,i)=>{
  const style=a.report.status==='incompatible'?' failed':'';
  const button=node('button','flow-step'+style);
  button.type='button';
  button.append(node('strong','',a.label||'Attempt '+(i+1)),node('span','step-meta',statusText(a.report)));
  button.addEventListener('click',()=>{
    $('attempt').value=i;
    render();
  });
  $('flow').append(button);
  return button;
});
function renderWitness(witness){
  $('witness').hidden=!witness;
  $('report-title').textContent=witness?'A recorded input changes the result':statusText(report);
  if(!witness){
    $('intro').textContent=report.status==='compatible'&&testedCount(report)>0
      ? 'The selected attempt agrees on the recorded comparisons. Inspect the test counts and remaining limits below.'
      : report.status==='incompatible'
        ? 'Review the reported differences and errors below. No complete positional witness is available for this selection.'
        : 'Review the recorded test counts and errors below.';
    return;
  }
  $('intro').textContent='Compare the saved Python and candidate outcomes for '+witness.functionName+'.';
  $('witness-input').textContent=witness.input.length<=5?'['+witness.input.map(floatText).join(', ')+']':witness.input.length+' values';
  $('witness-reference').textContent=witness.reference;
  $('witness-candidate').textContent=witness.candidate+(witness.sameDisplay?' · differs in details':'');
}
$('inspect-witness').addEventListener('click',()=>{
  if(!witnessTarget)return;
  witnessTarget.open=true;
  witnessTarget.querySelector('summary').focus({preventScroll:true});
  witnessTarget.scrollIntoView({block:'start'});
});
function fillFunctions(){const selected=$('function').value;$('function').replaceChildren();const all=node('option','','All functions');all.value='';$('function').append(all);for(const f of functionRecords(report)){const o=node('option','',f.name);o.value=f.name;$('function').append(o);}if([...$('function').options].some(o=>o.value===selected))$('function').value=selected;}
function chosen(){return functionRecords(report).filter(f=>!$('function').value||f.name===$('function').value);}
function source(){
  const index=Number($('attempt').value),attempt=attempts[index];
  const referenceHash=report.provenance?.reference_sha256;
  const sharedReference=activeCode==='reference_source'&&referenceHash&&
    meta._source_hashes?.reference_source===referenceHash;
  const fallback=index===attempts.length-1||sharedReference?meta:{};
  const s=attempt[activeCode]??fallback[activeCode];$('code').replaceChildren();if(typeof s==='string'&&s.length){const pre=node('pre','code-lines');for(const line of s.split('\n'))pre.append(node('span','code-line',line||' '));$('code').append(pre);}else $('code').append(node('div','code-empty',activeCode==='reference_source'?'Reference source was not attached to this run. Inspect its SHA-256 below.':'Rust source was not attached to this run. Inspect the generated project separately.'));$('code-label').textContent=activeCode==='reference_source'?'Frozen Python reference':'Generated Rust source';const hash=(attempt._source_hashes||{})[activeCode]||(fallback._source_hashes||{})[activeCode]||'';$('code-hash').textContent=hash?hash.slice(0,12):'';}
function claim(title,state,description){const c=node('div','claim'),top=node('div','claim-top');top.append(node('span','',title),node('span','pill '+(state==='failed'?'fail':state==='untested'?'unknown':''),state));c.append(top,node('div','claim-bottom',description));return c;}
function renderClaims(){const functions=chosen(),tested=functions.reduce((n,f)=>n+(Number(f.tested)||0)+(Number(f.api_tested)||0),0),failures=functions.reduce((n,f)=>n+(Number(f.failures)||0)+(Number(f.api_failures)||0),0),c=$('claims');c.replaceChildren();for(const f of functions)c.append(claim(f.name,f.status==='compatible'?'tested':f.status==='incompatible'?'failed':'untested',num(f.tested)+' positional + '+num(f.api_tested||0)+' keyword checks · '+num((Number(f.failures)||0)+(Number(f.api_failures)||0))+' differences'));if(!functions.length)c.append(node('div','empty','No declared function results were recorded.'));for(const f of functions)for(const e of asArray(f.errors))c.append(claim(f.name+' execution','untested',pretty(e)));c.append(claim('Declared input domain',failures?'failed':tested?'tested':'untested',failures?'At least one behavior differs on tested inputs.':'Compatibility applies only to the sampled inputs.'));c.append(claim('Universal equivalence','untested','No formal proof is attached to this report.'));c.append(claim('Outside the contract','untested','Other types, APIs and side effects are not covered.'));}
function field(label,value){const e=node('div');e.append(node('div','field-label',label),node('pre','sample',pretty(value)??'Not recorded'));return e;}
function renderCases(){
  const cases=$('cases');
  cases.replaceChildren();
  witnessTarget=null;
  const functions=chosen(),witness=positionalWitness(report,functions);
  renderWitness(witness);
  let count=0;
  for(const f of functions)for(const test of asArray(f.counterexamples)){
    if(!isRecord(test))continue;
    count++;
    const details=node('details','case');
    if(test===witness?.test){
      witnessTarget=details;
      details.open=true;
    }else if(!witness&&count===1)details.open=true;
    const summary=node('summary');
    summary.append(node('span','case-number',String(count).padStart(2,'0')),node('span','case-name',f.name),
      node('span','case-tag',test.keyword?'KEYWORD API DIFFERS':'BEHAVIOR DIFFERS'));
    const body=node('div','case-body'),inputs=node('div','input-grid'),observations=node('div','observations');
    const useRecorded=test===witness?.test&&!witness.minimized;
    inputs.append(field(test.keyword?'Discovered input · keyword '+test.keyword:'Discovered input',test.input));
    if(!useRecorded)inputs.append(field('Minimized input',test.minimized_input??test.input));
    const reference=field('Python reference',useRecorded?test.reference:test.minimized_reference??test.reference);
    const candidate=field('Candidate',useRecorded?test.candidate:test.minimized_candidate??test.candidate);
    reference.className=candidate.className='observation';
    observations.append(reference,candidate);
    body.append(inputs,observations,node('div','case-note',test.keyword
      ? 'Keyword API probe. This API counterexample was not minimized.'
      : 'Minimization is bounded. The smallest discovered input is not a proof of a globally minimal counterexample.'));
    details.append(summary,body);
    cases.append(details);
  }
  if(!count)cases.append(node('div','panel empty',report.status==='compatible'&&testedCount(report)>0
    ? 'No counterexample was observed within this test budget. Untested behavior remains unknown.'
    : 'No counterexample detail was recorded for the selected function. Check errors and the raw report.'));
  $('case-caption').textContent=count+' recorded counterexample'+(count===1?'':'s');
}
function tableRows(target,entries){target.replaceChildren();for(const [key,value]of entries){const tr=node('tr');tr.append(node('td','',key.replaceAll('_',' ')),node('td','',typeof value==='object'?pretty(value):String(value)));target.append(tr);}}
function renderBenchmark(bench){$('benchmark-table').hidden=!bench;$('benchmark-rows').hidden=!bench||!Array.isArray(bench.rows)||!bench.rows.length;$('benchmark-data').replaceChildren();if(!bench)return;tableRows($('benchmark'),Object.entries(bench).filter(([key])=>key!=='rows'));for(const row of Array.isArray(bench.rows)?bench.rows:[]){const tr=node('tr');for(const value of [row.function??'—',num(row.length),Number.isFinite(row.python_median_ns)?(row.python_median_ns/1000).toFixed(2):'—',Number.isFinite(row.rust_median_ns)?(row.rust_median_ns/1000).toFixed(2):'—',Number.isFinite(row.speedup)?row.speedup.toFixed(2)+'×':'—'])tr.append(node('td','',value));$('benchmark-data').append(tr);}}
function render(){const idx=Number($('attempt').value);report=attempts[idx].report;fillFunctions();const t=report.totals||{},funcs=functionRecords(report);$('status').className='status '+statusClass(report);$('status').textContent=statusText(report);$('run-id').textContent='RUN / '+String(report.provenance?.reference_sha256||'UNRECORDED').slice(0,10).toUpperCase();$('tested').textContent=num((Number(t.tested)||0)+(Number(t.api_tested)||0));$('tested').nextElementSibling.textContent=num(t.tested||0)+' positional + '+num(t.api_tested||0)+' keyword checks';$('failures').textContent=num((Number(t.failures)||0)+(Number(t.api_failures)||0));$('failures').className='metric-number '+((Number(t.failures)||0)+(Number(t.api_failures)||0)>0?'alert':'');$('shrinks').textContent=num(t.shrink_executions??0);$('metric4').textContent=num(funcs.length);const bench=attempts[idx].benchmark??(idx===attempts.length-1?meta.benchmark:null);const speed=bench?.speedup;if(typeof speed==='number'&&Number.isFinite(speed)&&speed>0){$('metric4-label').textContent='MEASURED SPEEDUP';$('metric4').replaceChildren(document.createTextNode(speed.toFixed(2)),node('span','unit','×'));$('metric4-detail').textContent='Selected benchmark; see input sizes below';}else{$('metric4-label').textContent='DECLARED FUNCTIONS';$('metric4-detail').textContent='Within the selected contract';}attemptButtons.forEach((button,i)=>button.setAttribute('aria-pressed',String(i===idx)));source();renderClaims();renderCases();tableRows($('provenance'),Object.entries(report.provenance||{}).flatMap(([key,value])=>key==='artifact_sha256'&&value&&typeof value==='object'?Object.entries(value).map(([path,hash])=>['Artifact: '+path,hash]):[[key,value]]));$('limitations').replaceChildren();const limits=Array.isArray(report.limitations)?report.limitations:[];for(const l of [...limits,'Only trusted repositories should be executed. Worker isolation is not a security sandbox.'])$('limitations').append(node('li','',typeof l==='string'?l:pretty(l)));renderBenchmark(bench);$('other-title').textContent=bench?'Limits & measured performance':'Scope & limitations';}
// Anchor navigation follows the selected section, including browser history.
function markCurrentSection(){const hash=location.hash||'#overview';for(const link of document.querySelectorAll('.rail nav a')){if(link.getAttribute('href')===hash)link.setAttribute('aria-current','location');else link.removeAttribute('aria-current');}}
window.addEventListener('hashchange',markCurrentSection);markCurrentSection();
$('attempt').addEventListener('change',render);$('function').addEventListener('change',()=>{renderClaims();renderCases();});
for(const tab of document.querySelectorAll('.tab')){tab.addEventListener('click',()=>{activeCode=tab.dataset.code;for(const t of document.querySelectorAll('.tab')){const on=t===tab;t.setAttribute('aria-selected',String(on));t.tabIndex=on?0:-1;}$('code').setAttribute('aria-labelledby',tab.id);source();});tab.addEventListener('keydown',e=>{if(e.key==='ArrowRight'||e.key==='ArrowLeft'){e.preventDefault();const other=tab.id==='python-tab'?$('rust-tab'):$('python-tab');other.click();other.focus();}});}
$('export').addEventListener('click',()=>{const url=URL.createObjectURL(new Blob([attempts[Number($('attempt').value)]._report_export],{type:'application/json'})),a=node('a');a.href=url;a.download='morphproof-report.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);$('toast').textContent='Selected report exported.';setTimeout(()=>{$('toast').textContent='';},3500);});
render();
</script></body></html>'''
