"""Playground web app — try your own data + prompt against the HTA logic.

Pure standard library (`http.server`): no install, no build step.

    PYTHONPATH=src python playground/app.py        # then open http://localhost:8000

Paste a CSV, type a question, and name the outcome column (plus an optional group or
predictor column). The app profiles the variables, runs the real BET dependence
engine over every numeric pair, and recommends a statistical test using the §6.2
decision tree. Use the sample links to load the shipped demo datasets.

What it does NOT do: call any LLM, or run the full Step-6 executor for group
comparisons (those are *recommended*, not executed — that module isn't built yet).
"""

from __future__ import annotations

import csv
import html
import io
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
sys.path.insert(0, str(ROOT / "src"))   # make `hta` importable
sys.path.insert(0, str(ROOT))           # make `playground` importable when run as a script

from playground import pipeline as P  # noqa: E402, N812

SAMPLES: dict[str, dict[str, str]] = {
    "stars": {
        "file": str(DATA / "bright_stars.csv"),
        "outcome": "sin_latitude", "predictor": "longitude_deg", "group": "",
        "prompt": "Are bright stars uniformly scattered (latitude independent of longitude)?",
    },
    "gene": {
        "file": str(DATA / "gene_pair_subtype.csv"),
        "outcome": "NAV3", "predictor": "DZIP1", "group": "subtype",
        "prompt": "Is NAV3 associated with DZIP1, and does NAV3 differ by subtype?",
    },
    "overdose": {
        "file": str(DATA / "overdose_ed_visits.csv"),
        "outcome": "nonfatal_overdose_ed_rate_per_100k",
        "predictor": "clinic_density_per_100k", "group": "",
        "prompt": "Is clinic density associated with the nonfatal overdose ED visit rate?",
    },
}

STYLE = """
:root { color-scheme: light dark; }
* { box-sizing: border-box; }
body { font: 15px/1.5 system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
       max-width: 920px; margin: 0 auto; padding: 1.5rem; }
h1 { font-size: 1.5rem; margin-bottom: .2rem; }
.sub { color: #666; margin-top: 0; }
textarea, input { width: 100%; font-family: ui-monospace, monospace; padding: .5rem;
       border: 1px solid #bbb; border-radius: 6px; background: Field; color: FieldText; }
textarea { height: 170px; white-space: pre; }
label { display: block; font-weight: 600; margin: .8rem 0 .25rem; }
.row { display: flex; gap: .8rem; flex-wrap: wrap; }
.row > div { flex: 1; min-width: 180px; }
button { margin-top: 1rem; padding: .6rem 1.4rem; font-size: 1rem; border: 0;
       border-radius: 6px; background: #2563eb; color: #fff; cursor: pointer; }
table { border-collapse: collapse; width: 100%; margin: .6rem 0; font-size: 14px; }
th, td { border: 1px solid #ccc; padding: .3rem .5rem; text-align: left; }
th { background: rgba(127,127,127,.12); }
.card { border: 1px solid #ccc; border-radius: 8px; padding: 1rem 1.2rem; margin: 1rem 0; }
.test { font-size: 1.25rem; font-weight: 700; color: #2563eb; }
.tag { display: inline-block; padding: .05rem .45rem; border-radius: 4px; font-size: 12px;
       background: rgba(127,127,127,.18); }
.warn { color: #b45309; }
.grid { border-collapse: collapse; margin: .4rem 0; }
.grid td { width: 22px; height: 22px; padding: 0; border: 1px solid #bbb; }
.on { background: #6366f1; }
.muted { color: #777; font-size: 13px; }
a { color: #2563eb; }
code { background: rgba(127,127,127,.15); padding: 0 .25rem; border-radius: 3px; }
"""


def page(body: str) -> bytes:
    return (f"<!doctype html><html><head><meta charset='utf-8'>"
            f"<meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<title>HTA Playground</title><style>{STYLE}</style></head>"
            f"<body>{body}</body></html>").encode("utf-8")


def esc(s: object) -> str:
    return html.escape(str(s))


def form(csv_text: str = "", prompt: str = "", outcome: str = "", group: str = "",
         predictor: str = "", note: str = "") -> str:
    samples = " · ".join(
        f"<a href='/?sample={k}'>{k}</a>" for k in SAMPLES
    )
    note_html = f"<p class='warn'>{esc(note)}</p>" if note else ""
    return f"""
    <h1>HTA Playground</h1>
    <p class='sub'>Try your own data and prompt against the Hypothesis Testing Agent's
    profiler, BET dependence engine, and test selector.</p>
    {note_html}
    <p class='muted'>Load a sample: {samples}</p>
    <form method='post' action='/analyze'>
      <label>Data (CSV, with a header row)</label>
      <textarea name='csv' placeholder='paste CSV here...'>{esc(csv_text)}</textarea>
      <label>Your question / hypothesis</label>
      <input name='prompt' value='{esc(prompt)}'
             placeholder='e.g. Is blood pressure different between the two arms?'>
      <div class='row'>
        <div><label>Outcome column</label>
          <input name='outcome' value='{esc(outcome)}'></div>
        <div><label>Group column <span class='muted'>(comparison; optional)</span></label>
          <input name='group' value='{esc(group)}'></div>
        <div><label>Predictor column <span class='muted'>(association; optional)</span></label>
          <input name='predictor' value='{esc(predictor)}'></div>
      </div>
      <button type='submit'>Analyse</button>
    </form>
    <p class='muted'>Pure-stdlib demo. No LLM calls; group comparisons are
    <em>recommended</em>, not executed (the Step-6 executor isn't built yet).</p>
    """


def region_grid(cells: list[tuple[int, int]], g: int) -> str:
    if not cells or not g:
        return ""
    on = set(cells)
    rows = ""
    for r in range(g - 1, -1, -1):
        tds = "".join(f"<td class='{'on' if (r, c) in on else ''}'></td>" for c in range(g))
        rows += f"<tr>{tds}</tr>"
    return ("<p class='muted'>Dependence region (where points concentrate; "
            "U → right, V → up):</p>"
            f"<table class='grid'>{rows}</table>")


def _num(v: float | None) -> str:
    return f"{v:.3g}" if v is not None else "—"


def profile_table(cols: dict[str, P.Column]) -> str:
    head = ("<tr><th>column</th><th>type</th><th>n</th><th>missing</th>"
            "<th>mean</th><th>sd</th><th>skew</th><th>normality</th><th>notes</th></tr>")
    body = ""
    for c in cols.values():
        body += (f"<tr><td><code>{esc(c.name)}</code></td><td>{c.var_type}</td>"
                 f"<td>{c.n}</td><td>{c.n_missing}</td>"
                 f"<td>{_num(c.mean)}</td><td>{_num(c.sd)}</td><td>{_num(c.skew)}</td>"
                 f"<td>{c.nonnormality or '—'}</td><td>{esc('; '.join(c.notes))}</td></tr>")
    return f"<table>{head}{body}</table>"


def screen_table(cols: dict[str, P.Column], raw: dict[str, list[str]]) -> str:
    from hta.bet_screen import pairwise_screen
    numeric = {n: c.numeric for n, c in cols.items()
               if c.var_type in ("CONTINUOUS", "ORDINAL", "COUNT") and len(c.numeric) >= 8}
    # align numeric columns on complete rows
    names = list(numeric)
    if len(names) < 2:
        return "<p class='muted'>Need ≥ 2 numeric columns for the pairwise screen.</p>"
    nrow = len(raw[names[0]])
    aligned: dict[str, list[float]] = {n: [] for n in names}
    for i in range(nrow):
        vals = {n: P._to_float(raw[n][i]) for n in names}
        if all(v is not None for v in vals.values()):
            for n in names:
                aligned[n].append(vals[n])  # type: ignore[arg-type]
    res = pairwise_screen(aligned, max_pairs=60, seed=0)
    head = ("<tr><th>pair</th><th>form</th><th>dir</th><th>BET z</th>"
            "<th>p (adj)</th><th>Pearson</th><th>nonlinear-only</th></tr>")
    body = ""
    for f in res.findings:
        flag = "<span class='tag'>yes</span>" if f.nonlinear_only else ""
        sig = "" if f.significant else " class='muted'"
        body += (f"<tr{sig}><td>{esc(f.x)}×{esc(f.y)}</td><td>{f.form}</td>"
                 f"<td>{f.direction}</td><td>{f.bet_z:.2f}</td><td>{f.p_value:.3g}</td>"
                 f"<td>{f.pearson_r:+.2f}</td><td>{flag}</td></tr>")
    extra = ""
    if res.notes:
        extra = "<p class='muted'>" + " ".join(esc(n) for n in res.notes) + "</p>"
    return f"<table>{head}{body}</table>{extra}"


def results(csv_text: str, prompt: str, outcome: str, group: str, predictor: str) -> str:
    try:
        rows = list(csv.reader(io.StringIO(csv_text)))
    except csv.Error as e:
        return form(csv_text, prompt, outcome, group, predictor, note=f"CSV parse error: {e}")
    rows = [r for r in rows if any(cell.strip() for cell in r)]
    if len(rows) < 2:
        return form(csv_text, prompt, outcome, group, predictor,
                    note="Need a header row plus at least one data row.")
    header = [h.strip() for h in rows[0]]
    data = rows[1:]
    raw = {h: [(r[i] if i < len(r) else "") for r in data] for i, h in enumerate(header)}
    cols = {h: P.profile_column(h, raw[h]) for h in header}

    if outcome not in cols:
        return form(csv_text, prompt, outcome, group, predictor,
                    note=f"Outcome column '{outcome}' not found. Columns: {', '.join(header)}")

    group_col = group if group in cols else None
    predictor_col = predictor if predictor in cols else None
    sel = P.select(cols, outcome, group_col, predictor_col, prompt, raw)

    computed = ""
    if sel.computed:
        computed = "<ul>" + "".join(
            f"<li><b>{esc(k)}:</b> {esc(v)}</li>" for k, v in sel.computed.items()) + "</ul>"
    caveats = ""
    if sel.caveats:
        caveats = ("<p><b>Caveats</b></p><ul>"
                   + "".join(f"<li class='warn'>{esc(c)}</li>" for c in sel.caveats) + "</ul>")

    return f"""
    <p><a href='/'>← back</a></p>
    <h1>Analysis</h1>
    <p class='sub'>Prompt: <em>{esc(prompt) or '(none)'}</em></p>

    <div class='card'>
      <p class='muted'>Recommended analysis for outcome <code>{esc(outcome)}</code>
      {("· group <code>" + esc(group_col) + "</code>") if group_col else ""}
      {("· predictor <code>" + esc(predictor_col) + "</code>") if predictor_col else ""}</p>
      <p class='test'>{esc(sel.test)}</p>
      <p>{esc(sel.rationale)}</p>
      {computed}
      {region_grid(sel.region, sel.grid_size)}
      {caveats}
    </div>

    <h2>Data profile</h2>
    {profile_table(cols)}

    <h2>BET dependence screen (all numeric pairs)</h2>
    <p class='muted'>The real engine: copula-transform → depth-2 Max BET → form + region.
    A <span class='tag'>yes</span> means the pair is dependent but Pearson/Spearman miss it.</p>
    {screen_table(cols, raw)}

    <p class='muted'><a href='/'>Analyse another dataset →</a></p>
    """


class Handler(BaseHTTPRequestHandler):
    def _send(self, body: bytes, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        q = parse_qs(urlparse(self.path).query)
        sample = (q.get("sample") or [""])[0]
        if sample in SAMPLES:
            s = SAMPLES[sample]
            text = Path(s["file"]).read_text(encoding="utf-8") if Path(s["file"]).exists() else ""
            self._send(page(form(text, s["prompt"], s["outcome"], s["group"], s["predictor"])))
        elif urlparse(self.path).path in ("/", "/index.html"):
            self._send(page(form()))
        else:
            self._send(page("<p>Not found. <a href='/'>Home</a></p>"), 404)

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", 0))
        fields = parse_qs(self.rfile.read(length).decode("utf-8"), keep_blank_values=True)

        def g(k: str) -> str:
            return (fields.get(k) or [""])[0].strip()

        self._send(page(results(g("csv"), g("prompt"), g("outcome"), g("group"), g("predictor"))))

    def log_message(self, *args: object) -> None:  # quiet console
        pass


def main(port: int = 8000) -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")   # type: ignore[union-attr]  # cp1252 consoles
    except (AttributeError, ValueError):
        pass
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"HTA Playground -> http://localhost:{port}  (Ctrl-C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nbye")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 8000)
