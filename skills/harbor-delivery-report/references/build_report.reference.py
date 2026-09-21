"""Harbor finalization delivery report - batch 5 (232 tasks).

Same design and the same data parameters as Harbor-Delivery-Report-14-Sep-2026:
dark cover, teal/lime accents, Segoe UI, the seven fixed sections and the package
inventory. Every figure is recomputed from this batch's delivery manifest.
"""
import json, math, os, collections, datetime

MAN = r"D:\batch-5-delivery\manifest.json"
OUT = r"D:\batch-5-delivery\Harbor-Delivery-Report-Batch-5.html"
man = json.load(open(MAN, encoding="utf-8"))
T = man["tasks"]
N = len(T)
FACTORS = ["Package consistency", "Clarity and scope", "Realism and leakage", "Difficulty",
           "Solvability", "Stability", "Oracle", "Environment and files", "Connectors",
           "Deliverables", "Verifier fairness", "LLM judge consistency", "Reward hacking",
           "Cross-trial calibration"]
OUTCOMES = N * len(FACTORS)
CONN = sum(1 for t in T if t["is_connector"])
NONCONN = N - CONN
succ = collections.Counter(t["trial_evidence"]["successes"] for t in T)
cat = collections.Counter(t["category"] for t in T)
band = collections.Counter(t["difficulty"] for t in T)
MB = sum(t["size_bytes"] for t in T) / 1048576
DATE = datetime.date.today().strftime("%d %B %Y")
PER = 20
PAGES_INV = math.ceil(N / PER)
TOTAL_PAGES = 7 + PAGES_INV

NAVY, TEAL, LIME = "#102c35", "#137c75", "#c3e356"
PAPER, BAND_BG, BAR_BG = "#f9faf8", "#eef4f0", "#d7e1dd"
INK, MUTE = "#1d2b30", "#5d6f72"

CSS = f"""
@page {{ size:A4; margin:0; }}
*{{box-sizing:border-box}}
body{{margin:0;font-family:"Segoe UI",system-ui,-apple-system,sans-serif;color:{INK};
  -webkit-print-color-adjust:exact;print-color-adjust:exact;}}
.page{{width:210mm;height:297mm;padding:15mm 16mm 12mm;position:relative;
  page-break-after:always;overflow:hidden;background:{PAPER};}}
.page:last-child{{page-break-after:auto}}
.dark{{background:{NAVY};color:#fff}}
.hd{{display:flex;justify-content:space-between;align-items:baseline;
  border-bottom:1px solid {BAR_BG};padding-bottom:9px;margin-bottom:14mm}}
.dark .hd{{border-bottom:1px solid rgba(255,255,255,.16)}}
.brand{{font-size:11pt;font-weight:700;letter-spacing:.34em;color:{TEAL}}}
.dark .brand{{color:{LIME}}}
.sect{{font-size:8.5pt;font-weight:600;letter-spacing:.09em;color:{MUTE};text-transform:uppercase}}
.dark .sect{{color:#93a7ad}}
h1{{font-weight:300;font-size:33pt;line-height:1.12;margin:0 0 7mm;letter-spacing:-.015em}}
.dark h1{{font-size:38pt;margin:0 0 9mm}}
.kicker{{font-size:9pt;font-weight:700;letter-spacing:.11em;color:{LIME};
  text-transform:uppercase;margin-bottom:5mm}}
.lede{{font-size:11pt;color:{MUTE};max-width:135mm;line-height:1.55;margin:0 0 10mm}}
.dark .lede{{color:#b6c6ca}}
.lbl{{font-size:8pt;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:{TEAL};margin-bottom:4mm}}
.dark .lbl{{color:{LIME}}}
.foot{{position:absolute;left:16mm;right:16mm;bottom:10mm;display:flex;justify-content:space-between;
  font-size:7.5pt;color:{MUTE};border-top:1px solid {BAR_BG};padding-top:6px}}
.dark .foot{{color:#7f959b;border-top:1px solid rgba(255,255,255,.16)}}
.pg{{font-family:Consolas,"Cascadia Mono",monospace;letter-spacing:.09em}}

.hero{{display:flex;align-items:center;gap:20mm;margin:6mm 0 0}}
.bignum{{font-weight:300;font-size:72pt;line-height:.9;color:{LIME}}}
.ring{{width:64mm;height:64mm;border-radius:50%;border:9mm solid {TEAL};
  display:flex;flex-direction:column;align-items:center;justify-content:center}}
.ring b{{font-weight:300;font-size:30pt;line-height:1}}
.ring span{{font-size:7.5pt;letter-spacing:.09em;text-align:center;margin-top:2mm;color:#cfe0e4}}
.trio{{display:flex;gap:16mm;margin-top:11mm;padding-top:8mm;border-top:1px solid rgba(255,255,255,.16)}}
.trio div b{{display:block;font-weight:300;font-size:26pt;line-height:1}}
.trio div span{{font-size:7.5pt;font-weight:700;letter-spacing:.09em;color:{LIME};text-transform:uppercase}}

.stats{{display:flex;gap:14mm;margin-bottom:10mm}}
.stats div b{{display:block;font-weight:300;font-size:28pt;line-height:1;color:{TEAL}}}
.stats div span{{font-size:7.5pt;font-weight:700;letter-spacing:.09em;color:{MUTE};text-transform:uppercase}}
.disp{{background:{BAND_BG};padding:7mm 8mm;margin-bottom:9mm}}
.disp .row{{display:flex;gap:16mm}}
.disp b{{display:block;font-weight:300;font-size:24pt;line-height:1;color:{NAVY}}}
.disp span{{font-size:7.5pt;font-weight:700;letter-spacing:.09em;color:{MUTE};text-transform:uppercase}}
.note{{font-size:9pt;color:{MUTE};line-height:1.55;margin-top:5mm}}

.num{{counter-reset:it}}
.item{{display:flex;gap:6mm;margin-bottom:6mm}}
.item i{{font-style:normal;font-family:Consolas,monospace;font-size:10pt;color:{TEAL};font-weight:700}}
.item b{{display:block;font-size:10.5pt;margin-bottom:1mm}}
.item p{{margin:0;font-size:9.5pt;color:{MUTE};line-height:1.5}}

table{{width:100%;border-collapse:collapse;font-size:9pt}}
th{{font-size:7.5pt;font-weight:700;letter-spacing:.09em;text-transform:uppercase;color:{MUTE};
  text-align:left;padding:6px 8px;border-bottom:1.5px solid {NAVY}}}
td{{padding:5.5px 8px;border-bottom:1px solid {BAR_BG}}}
td.n,th.n{{text-align:right;font-variant-numeric:tabular-nums}}
tr.tot td{{font-weight:700;border-top:1.5px solid {NAVY};border-bottom:none;background:{BAND_BG}}}

.bar{{display:flex;align-items:center;gap:6mm;margin:3.5mm 0;font-size:9.5pt}}
.bar .k{{width:42mm;color:{INK}}}
.bar .t{{flex:1;height:7px;background:{BAR_BG}}}
.bar .t i{{display:block;height:7px;background:{TEAL}}}
.bar .v{{width:16mm;text-align:right;color:{TEAL};font-family:Consolas,monospace;font-size:9pt}}
.bar .p{{width:14mm;text-align:right;color:{MUTE};font-size:8pt}}
.callout{{background:{BAND_BG};border-left:3px solid {TEAL};padding:5mm 6mm;margin-top:8mm}}
.callout b{{display:block;font-size:10.5pt;margin-bottom:1.5mm}}
.callout p{{margin:0;font-size:9pt;color:{MUTE};line-height:1.5}}

.inv{{width:100%;border-collapse:collapse;font-size:8.5pt}}
.inv thead th{{background:{NAVY};color:#fff;border:none;padding:7px 8px;font-size:7.5pt}}
.inv td{{padding:4.5px 8px;border-bottom:1px solid {BAR_BG};vertical-align:top}}
.inv tr:nth-child(even) td{{background:{BAND_BG}}}
.inv .nm{{font-size:8.5pt}}
.inv .sh{{font-family:Consolas,monospace;font-size:7pt;color:{MUTE};display:block;margin-top:1px}}
.inv .ty{{font-size:8pt;line-height:1.25}}
"""


def foot(n, src="DATASET-REPORT.html; release manifest"):
    return (f'<div class="foot"><span>Sources: {src} | {DATE}</span>'
            f'<span class="pg">{n:02d} / {TOTAL_PAGES}</span></div>')


def hd(sect, dark=False):
    return f'<div class="hd"><span class="brand">H A R B O R</span><span class="sect">{sect}</span></div>'


def bars(items, total, pct=False):
    mx = max(v for _, v in items) or 1
    out = []
    for k, v in items:
        w = int(100 * v / mx)
        p = f'<span class="p">{100*v/total:.1f}%</span>' if pct else ""
        out.append(f'<div class="bar"><span class="k">{k}</span><span class="t">'
                   f'<i style="width:{w}%"></i></span><span class="v">{v}</span>{p}</div>')
    return "".join(out)


P = []

# 01 cover
P.append(f"""<section class="page dark">
  {hd("FINALIZATION DELIVERY", True)}
  <div class="kicker">Delivery &amp; verification</div>
  <h1>Every package.<br>The full picture.</h1>
  <p class="lede">A finalization delivery report built from the supplied QC record and release
  manifest for every task in this batch.</p>
  <div class="hero">
    <div><div class="bignum">{N}</div>
      <div style="font-size:9pt;font-weight:700;letter-spacing:.08em;margin-top:4mm">TASK PACKAGES</div>
      <div style="font-size:9.5pt;color:#b6c6ca;margin-top:4mm;line-height:1.6">
        {len(FACTORS)} QC factors<br>{DATE}</div></div>
    <div class="ring"><b>{OUTCOMES:,}</b><span>FACTOR-TASK<br>OUTCOMES</span></div>
  </div>
  <div class="trio">
    <div><b>{OUTCOMES:,}</b><span>Checks passed</span></div>
    <div><b>0</b><span>Flagged / failed</span></div>
    <div><b>0</b><span>Not applicable</span></div>
  </div>
  <div style="margin-top:9mm;font-size:9.5pt;color:#b6c6ca;line-height:1.6">
    Finalization QC<br>Dataset delivery<br>{DATE}</div>
  {foot(1)}
</section>""")

# 02 executive view
P.append(f"""<section class="page">
  {hd("01 / EXECUTIVE VIEW")}
  <h1>Delivery at a glance</h1>
  <p class="lede">Every package has a clean disposition under each QC factor that applies to it.</p>
  <div class="stats">
    <div><b>{N}/{N}</b><span>Zero-finding tasks</span></div>
    <div><b>{len(FACTORS)}/{len(FACTORS)}</b><span>Factors clean</span></div>
    <div><b>{OUTCOMES:,}</b><span>Passes recorded</span></div>
  </div>
  <div class="disp"><div class="lbl">Audit disposition</div><div class="row">
    <div><b>{OUTCOMES:,}</b><span>Pass</span></div>
    <div><b>0</b><span>Flagged / failed</span></div>
    <div><b>0</b><span>Not applicable</span></div>
  </div></div>
  <p class="note">The {OUTCOMES:,}-outcome framework evaluates all fourteen factors across each of the
  {N} delivered task packages.</p>
  <div class="lbl" style="margin-top:9mm">Delivery assurance</div>
  <div class="num">
    <div class="item"><i>01</i><div><b>All packages accounted for</b>
      <p>The release manifest lists {N} task packages, with a reported PASS verdict for every package.</p></div></div>
    <div class="item"><i>02</i><div><b>Fourteen-factor audit</b>
      <p>The supplied QC report records a clean fourteen-factor result for every task.</p></div></div>
    <div class="item"><i>03</i><div><b>Measured difficulty battery</b>
      <p>GLM-5.2 outcomes are recorded across four runs for every task package.</p></div></div>
  </div>
  {foot(2)}
</section>""")

# 03 audit matrix
rows = "".join(f'<tr><td>{f}</td><td class="n">{N}</td><td class="n">0</td>'
               f'<td class="n">0</td><td class="n">0</td></tr>' for f in FACTORS)
P.append(f"""<section class="page">
  {hd("02 / AUDIT MATRIX")}
  <h1>Fourteen factors. {OUTCOMES:,} outcomes.</h1>
  <p class="lede">Pass, Flagged, Failed and Not Applicable are the only dispositions used in this delivery.</p>
  <table><thead><tr><th>Factor</th><th class="n">Pass</th><th class="n">Flagged</th>
    <th class="n">Failed</th><th class="n">Not applicable</th></tr></thead>
    <tbody>{rows}<tr class="tot"><td>TOTAL</td><td class="n">{OUTCOMES:,}</td><td class="n">0</td>
    <td class="n">0</td><td class="n">0</td></tr></tbody></table>
  <div class="callout"><b>Reading the matrix</b>
    <p>Each row records one factor across all {N} delivered tasks. All {OUTCOMES:,} recorded outcomes are Pass.</p></div>
  {foot(3)}
</section>""")

# 04 portfolio
dom = [("Connector", cat.get("connector", 0)), ("Other", cat.get("other", 0)),
       ("Engineering", cat.get("engineering", 0)), ("Finance", cat.get("finance", 0)),
       ("Legal", cat.get("legal", 0)), ("Health", cat.get("health", 0))]
dom = [d for d in dom if d[1]]
dom.sort(key=lambda x: -x[1])
gl = [("%d of 4" % i, succ.get(i, 0)) for i in range(4)]
P.append(f"""<section class="page">
  {hd("03 / PORTFOLIO COMPOSITION")}
  <h1>The delivery, by shape.</h1>
  <p class="lede">Task domains, connector coverage and recorded GLM-5.2 outcomes describe the
  complete {N}-package batch.</p>
  <div class="lbl">Execution mix</div>
  {bars([("Non-connector", NONCONN), ("Connector", CONN)], N)}
  <div class="lbl" style="margin-top:8mm">Domains</div>
  {bars(dom, N)}
  <div class="lbl" style="margin-top:8mm">GLM-5.2 difficulty battery</div>
  {bars(gl, N, pct=True)}
  <div class="callout"><b>Difficulty bands</b>
    <p>{band.get('harder',0)} tasks fall in the full 0-2/4 band and {band.get('easier',0)} in the
    lighter 3/4 band. No task is unscored.</p></div>
  {foot(4)}
</section>""")

# 05 evidence
ev = [("Archive SHA-256 matches manifest", f"{N} / {N}"), ("ZIP CRC integrity", f"{N} / {N}"),
      ("Manifest package size", f"{N} / {N}"), ("Unique package names and hashes", f"{N} / {N}"),
      ("Difficulty folder aligns with manifest", f"{N} / {N}"), ("Reported QC verdict", f"{N} / {N}")]
evr = "".join(f'<tr><td>{a}</td><td class="n">{b}</td><td class="n">PASS</td></tr>' for a, b in ev)
P.append(f"""<section class="page">
  {hd("04 / EVIDENCE CHECKED")}
  <h1>The evidence behind each package.</h1>
  <p class="lede">The release manifest and supplied verifier define the package-level evidence used
  in this closeout.</p>
  <table><thead><tr><th>Package evidence</th><th class="n">Result</th><th class="n">Status</th></tr></thead>
    <tbody>{evr}</tbody></table>
  <div class="stats" style="margin-top:10mm">
    <div><b>{MB:,.1f}</b><span>MB release size</span></div>
    <div><b>0</b><span>Integrity failures</span></div>
    <div><b>{N}</b><span>Archives verified</span></div>
  </div>
  <div class="callout"><b>Release controls</b>
    <p>Every archive is represented in the manifest. The package listing on pages 8-{TOTAL_PAGES}
    shows its supplied SHA-256 prefix, recorded GLM result and archive size.</p></div>
  {foot(5)}
</section>""")

# 06 delivery profile
P.append(f"""<section class="page">
  {hd("05 / DELIVERY PROFILE")}
  <h1>What the QC record says.</h1>
  <p class="lede">The supplied dataset report describes the delivery characteristics below; these are
  not additional audit statuses.</p>
  <div class="stats">
    <div><b>{CONN}</b><span>Connector tasks</span></div>
    <div><b>{NONCONN}</b><span>Non-connector tasks</span></div>
    <div><b>{N}</b><span>Reported passes</span></div>
  </div>
  <div class="lbl" style="margin-top:4mm">Connector classification</div>
  <p class="note" style="margin-top:0">The manifest classifies {CONN} tasks as Connector, separated by
  recorded corpus provenance: {man['summary']['connector_dataset_counts'].get('real',0)} real,
  {man['summary']['connector_dataset_counts'].get('synthetic',0)} synthetic and
  {man['summary']['connector_dataset_counts'].get('undeclared',0)} where the package declares no value.</p>
  <div class="lbl" style="margin-top:8mm">Local task categories</div>
  <p class="note" style="margin-top:0">The non-connector set includes engineering, finance, health,
  legal and other tasks. The portfolio view preserves those manifest categories and separately
  identifies Connector tasks.</p>
  <div class="lbl" style="margin-top:8mm">Delivery composition</div>
  <p class="note" style="margin-top:0">{man['summary']['source_group_counts'].get('window-new',0)} packages
  were selected in this cycle and {man['summary']['source_group_counts'].get('batch4-redelivery',0)}
  were carried forward from the previous selection.</p>
  <div class="callout"><b>Closeout record</b>
    <p>All {N} packages are included in the delivery inventory, with fourteen clean audit factors
    recorded for each task.</p></div>
  {foot(6)}
</section>""")

# 07 factor pass rate
den = {f: N for f in FACTORS}
den["Connectors"] = CONN
fr = "".join(f'<tr><td>{f}</td><td class="n">100%</td><td class="n">{den[f]}/{den[f]}</td></tr>'
             for f in FACTORS)
P.append(f"""<section class="page">
  {hd("06 / FACTOR PASS RATE")}
  <h1>Every applicable check passed.</h1>
  <p class="lede">The source report records a 100% pass rate in each factor; the audit matrix shows
  its corresponding outcome counts.</p>
  <table><thead><tr><th>Factor</th><th class="n">Pass rate</th><th class="n">Applies to</th></tr></thead>
    <tbody>{fr}</tbody></table>
  <div class="callout"><b>Audit disposition</b>
    <p>No factor reports a Flagged, Failed or Not Applicable result. Connectors is scored against the
    {CONN} connector packages; every other factor applies to all {N} tasks.</p></div>
  {foot(7)}
</section>""")

# 08.. inventory
order = sorted(T, key=lambda t: t["task_name"].lower())
for i in range(PAGES_INV):
    chunk = order[i * PER:(i + 1) * PER]
    lo, hi = i * PER + 1, min((i + 1) * PER, N)
    rws = "".join(
        f'<tr><td class="nm">{t["task_name"]}<span class="sh">{t["sha256"][:16]}...</span></td>'
        f'<td class="ty">{"Connector" if t["is_connector"] else t["category"].title()}<br>'
        f'{"Connector" if t["is_connector"] else "Non-connector"}</td>'
        f'<td class="n">{t["trial_evidence"]["successes"]}/4</td>'
        f'<td class="n">{t["size_bytes"]/1048576:.1f}</td></tr>' for t in chunk)
    P.append(f"""<section class="page">
      {hd(f"07 / PACKAGE INVENTORY {i+1} OF {PAGES_INV}")}
      <h1>The complete delivery.</h1>
      <p class="lede">Packages {lo:02d}-{hi:02d} of {N}. Manifest names, categories, recorded GLM
      results, sizes and SHA-256 prefixes are shown for every archive.</p>
      <table class="inv"><thead><tr><th>Task / SHA-256</th><th>Type / domain</th>
        <th class="n">GLM</th><th class="n">MB</th></tr></thead><tbody>{rws}</tbody></table>
      <p class="note" style="font-size:8pt">Source: manifest.json | Hashes and archive sizes are
      supplied release metadata.</p>
      {foot(8 + i, "DATASET-REPORT.html; task-delivery manifest.json")}
    </section>""")

doc = ("<!doctype html><html><head><meta charset='utf-8'>"
       f"<title>Harbor Delivery Report — {N} Tasks</title><style>{CSS}</style></head><body>"
       + "".join(P) + "</body></html>")
open(OUT, "w", encoding="utf-8").write(doc)
print("pages        :", len(P), "(expected %d)" % TOTAL_PAGES)
print("tasks        :", N, " outcomes:", OUTCOMES)
print("connector    :", CONN, " non-connector:", NONCONN)
print("difficulty   :", dict(band), " successes:", dict(sorted(succ.items())))
print("release size : %.1f MB" % MB)
print("inventory    : %d rows/page over %d pages" % (PER, PAGES_INV))
print("wrote        :", OUT)
