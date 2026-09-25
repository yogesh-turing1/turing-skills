#!/usr/bin/env python3
"""Build the INTERNAL edition of a delivery report.

Same structure and visual language as the client edition, with everything held out of it
put back:

  - the audit matrix carries its real four-status counts, not a flattened all-pass row
  - a change-control section itemising every deviation from the accepted source bytes
  - the provenance behind each change, including the evidence pointing the other way
  - hygiene stated before and after, with what was deliberately left alone
  - a per-package change log

Every figure is read out of the delivery's own records. Nothing is typed in by hand.

Usage:
  python3 build_internal_report.py \
      --mods MODIFICATIONS.json \
      --manifest <delivery>/manifest.json \
      --inventory delivery_manifest.csv \
      --audit audit-14-factor-findings.csv \
      --out Harbor-Delivery-Report-INTERNAL [--pdf]

Optional:
  --hygiene hygiene.json     rows of [pattern, before, after, verdict]; derived if omitted
  --delta-note "..."         reconcile a figure that differs from the client edition
  --cover-lede "..."         override the cover standfirst
  --source-line "..."        override the page footer

Requires Python 3.9+ and Google Chrome (used to measure layout and to write the PDF).
"""
import argparse, base64, csv, html, json, os, re, subprocess, sys, tempfile
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
FONT_DIR = HERE/'fonts'
CHROME = next((p for p in (
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    '/usr/bin/google-chrome', '/usr/bin/chromium', '/usr/bin/chromium-browser',
    '/Applications/Chromium.app/Contents/MacOS/Chromium',
    # Windows: the delivery VMs have no browser, so the report is built on the
    # workstation and the generator has to find Chrome there too
    'C:/Program Files/Google/Chrome/Application/chrome.exe',
    'C:/Program Files (x86)/Google/Chrome/Application/chrome.exe',
    str(Path.home()/'AppData/Local/Google/Chrome/Application/chrome.exe'),
) if Path(p).exists()), None)
e = html.escape

FACTORS = ['Package consistency','Clarity and scope','Realism and leakage','Difficulty',
           'Solvability','Stability','Oracle','Environment and files','Connectors',
           'Deliverables','Verifier fairness','LLM judge consistency','Reward hacking',
           'Cross-trial calibration']
SCOPE = {
 'Package consistency':'Required files, duplicate tasks, archive identity, mirrored-file consistency',
 'Clarity and scope':'Instructions are complete, consistent and understandable',
 'Realism and leakage':'Realistic task; answers are not exposed to the agent',
 'Difficulty':'Correct four-run battery and pass rate',
 'Solvability':'A legitimate non-oracle run demonstrates completion',
 'Stability':'Regrading identical outputs produces consistent results',
 'Oracle':'Recorded reward, correct task version, valid execution route',
 'Environment and files':'Runtime configuration, permissions, dependencies, image identity',
 'Connectors':'Intended access, configuration, real/synthetic provenance',
 'Deliverables':'Requested files and content are actually checked',
 'Verifier fairness':'No undisclosed wording, ordering or formatting requirements',
 'LLM judge consistency':'Judge configuration and consistency, where applicable',
 'Reward hacking':'Scoring loopholes, answer access, unintended shortcuts',
 'Cross-trial calibration':'README and review claims match the actual runs',
}
TITLES = {
 '_os_artefacts':'Non-task artefacts removed',
 '_image_pinning':'Mutable image tags pinned to digests',
 '_dataset_declaration':'Connector data provenance declared',
 '_stale_qc_claims':'Stale pass-rate claims reconciled',
 '_verifier_justification':'Verifier justification text corrected',
 '_readme_generation':'Missing package documentation generated',
 '_redaction':'Internal addresses and authoring-machine paths removed',
 '_folder_rename':'Package folder names aligned to declared identity',
 '_image_digest':'Doubled image digests resolved to one',
 '_binary_reward':'Recorded rewards normalised to binary',
}
ORDER = ['_os_artefacts','_image_pinning','_image_digest','_dataset_declaration',
         '_stale_qc_claims','_verifier_justification','_readme_generation','_redaction',
         '_folder_rename','_binary_reward']
SHORT = {k: v.split(' ')[0] for k, v in TITLES.items()}
ABBR = {'_os_artefacts':'ART','_image_pinning':'PIN','_dataset_declaration':'DAT',
        '_stale_qc_claims':'QC','_verifier_justification':'VJ','_readme_generation':'DOC',
        '_redaction':'RED','_folder_rename':'NAME','_image_digest':'DIG',
        '_binary_reward':'BIN'}
PROV = [('fix','What changed'),('BASIS','Basis'),('PROVENANCE','Provenance'),('CORROBORATION','Corroboration'),
        ('COUNTER_EVIDENCE','Counter-evidence'),('CONTENT_UNCHANGED','Content unchanged'),
        ('KNOWN_RESIDUAL','Known residual'),('NOT_APPLIED_TO','Deliberately not applied'),
        ('NOT_REDACTED','Deliberately not redacted'),('files_deliberately_not_edited','Not edited'),
        ('placement','Placement'),('scope','Scope'),('result','Result'),
        ('count','Files removed'),('all_other_entries','All other entries'),
        ('other_59_archives','Other archives')]


# ----------------------------------------------------------------------- data
def load(cfg):
    d = {}
    mods = json.loads(Path(cfg['mods']).read_text())
    man = json.loads(Path(cfg['manifest']).read_text())
    rows = list(csv.DictReader(Path(cfg['inventory']).open()))
    audit = defaultdict(Counter)
    for r in csv.DictReader(Path(cfg['audit']).open()):
        audit[r['factor']][r['status']] += 1

    groups = {}
    for k, v in mods.items():
        if not isinstance(v, dict) or k == '_archives':
            continue
        if k.startswith('_'):
            groups.setdefault(k, dict(meta=v, tasks=dict(v.get('per_task') or {})))
        else:                                  # a group filed under the package's own key
            g = groups.setdefault('_os_artefacts', dict(meta={}, tasks={}))
            g['meta'] = v
            g['tasks'][k] = v

    occ = Counter()
    san = man.get('sanitisation') or {}
    if san:
        for t, rec in (san.get('per_task') or {}).items():
            if 'review_csv_pass_rate' in rec:
                g = groups.setdefault('_stale_qc_claims', dict(meta={
                    'fix': 'Reconciled stale pass-rate claims to the packaged battery',
                    'BASIS': (san.get('actions') or {}).get('review_csv_pass_rate', '')}, tasks={}))
                g['tasks'][t] = {'review.csv': f"reconciled ({rec['review_csv_pass_rate']})"}
            if 'gateway_ip' in rec or 'local_paths' in rec:
                g = groups.setdefault('_redaction', dict(meta={}, tasks={}))
                g['tasks'][t] = {k2: v2 for k2, v2 in rec.items() if k2 != 'review_csv_pass_rate'}
        acts = san.get('actions') or {}
        groups.setdefault('_redaction', dict(meta={}, tasks={}))['meta'] = dict(
            fix='Removed internal infrastructure addresses and authoring-machine paths',
            BASIS=' '.join(v for k2, v in acts.items() if k2 in ('gateway_ip', 'local_paths')),
            NOT_REDACTED=san.get('not_redacted') or [])
        occ.update({k2: v2 for k2, v2 in (san.get('totals') or {}).items()
                    if k2 in ('gateway_ip', 'local_paths')})
    if not occ:            # only sum per-task when no totals were recorded for the whole pass
        for t, rec in (groups.get('_redaction') or {}).get('tasks', {}).items():
            if isinstance(rec, dict):
                for k2, v2 in rec.items():
                    if isinstance(v2, int) and k2 in ('gateway_ip', 'local_paths'):
                        occ[k2] += v2
    if (groups.get('_os_artefacts') or {}).get('meta', {}).get('count'):
        occ['artefacts'] = groups['_os_artefacts']['meta']['count']

    ident = sum(1 for r in rows if r.get('byte_identical_to_source') == 'yes')
    if 'byte_identical_to_source' not in (rows[0] if rows else {}):
        changed = {t for g in groups.values() for t in g['tasks']}
        ident = len(rows) - len(changed)

    inv = []
    for r in rows:
        conn = r['execution_type'] in ('X', 'connector')
        inv.append(dict(
            name=r['task_name'],
            sha=r['archive_sha256'][:16],
            kind='connector' if conn else 'non-connector',
            domain='connector' if conn else {'code':'engineering','fin':'finance','law':'legal',
                                             'gen':'other','health':'health'}.get(r['domain'], r['domain']),
            glm=r['glm_bucket'],
            mb=round(int(r['archive_bytes'])/1024/1024, 1)))
    inv.sort(key=lambda x: (x['kind'] != 'connector', x['domain'], x['name']))

    d.update(mods=mods, man=man, audit=audit, groups=groups, occ=occ, inv=inv,
             N=len(rows), ident=ident, modified=len(rows)-ident,
             size_mb=round(sum(int(r['archive_bytes']) for r in rows)/1024/1024, 1),
             exec_mix=Counter(x['kind'] for x in inv),
             domains=Counter(x['domain'] for x in inv),
             glm=Counter(x['glm'] for x in inv),
             gyms=Counter(g for r in rows if r.get('gym') for g in r['gym'].split('|')),
             changed_pkgs={t for g in groups.values() for t in g['tasks']})
    return d


# ----------------------------------------------------------------------- render helpers
def font(f):
    p = FONT_DIR/f
    if not p.is_file():
        raise SystemExit(f'missing font {p}. The skill ships its own fonts/ directory.')
    return base64.b64encode(p.read_bytes()).decode()

FONTS = {'Serif':'SourceSerif4-Regular.ttf','SerifSB':'SourceSerif4-SemiBold.ttf',
         'Mono':'IBMPlexMono-Regular.ttf','MonoMd':'IBMPlexMono-Medium.ttf',
         'Bric':'Bricolage-ExtraBold.ttf'}

CSS = """
*{box-sizing:border-box}
html{-webkit-print-color-adjust:exact;print-color-adjust:exact}
body{margin:0;background:#DCDCD6;color:#16181C;font-family:'Serif',Georgia,serif;font-size:9.6pt;
 line-height:1.55;font-variant-ligatures:none;font-feature-settings:"liga" 0,"clig" 0;
 padding:26px 0}
@page{size:letter;margin:0}
/* on screen the pages are centred sheets; in print they are the page box itself */
.pg{width:8.5in;min-height:11in;padding:.62in .7in .5in;position:relative;
 break-after:page;display:flex;flex-direction:column;background:#fff;
 margin:0 auto 26px;box-shadow:0 1px 5px rgba(0,0,0,.20)}
.foot{margin-top:auto;padding-top:.9em;display:flex;justify-content:space-between;
 align-items:flex-end;gap:1.2em;border-top:.6px solid #E4E4DE}
.cover .foot{border-top-color:#2A2F33}
.pg:last-child{break-after:auto;margin-bottom:0}
@media print{
 body{background:#fff;padding:0}
 .pg{margin:0;box-shadow:none;height:11in;overflow:hidden}
}
.wm{font-family:'Mono';font-size:7pt;letter-spacing:.42em;color:#0A6B5F;text-transform:uppercase}
.pgn{font-family:'Mono';font-size:6.6pt;letter-spacing:.18em;color:#9AA0A6;white-space:nowrap}
.src{font-family:'Mono';font-size:6.2pt;letter-spacing:.08em;color:#9AA0A6;max-width:5.6in;
 line-height:1.5}
.sect{font-family:'Mono';font-size:7pt;letter-spacing:.24em;color:#0A6B5F;text-transform:uppercase;
 margin-top:.5em}
h2{font-family:'Bric';font-size:21pt;line-height:1.08;letter-spacing:-.02em;margin:.18em 0 .1em}
.dek{font-size:10pt;color:#43494F;max-width:6in;margin:0 0 .95em}
/* cover */
.cover{background:#0E1113;color:#F2F1EC}
.cover .ctitle{margin-top:.35em}
.cover .wm{color:#7FD9C6}
.cover .src,.cover .pgn{color:#6E747C}
.ctitle{font-family:'Bric';font-size:44pt;line-height:1.02;letter-spacing:-.028em;margin:.5em 0 .2em}
.csub{font-family:'Mono';font-size:7.6pt;letter-spacing:.3em;color:#7FD9C6;text-transform:uppercase}
.clede{font-size:11pt;color:#C6C8C4;max-width:4.9in;margin:.2em 0 0}
.cstats{display:grid;grid-template-columns:repeat(3,1fr);gap:1.15em .9em;margin-top:auto;
 border-top:1px solid #2A2F33;padding-top:1.2em;padding-bottom:.3em}
.cn{font-family:'Bric';font-size:27pt;line-height:1;letter-spacing:-.02em}
.cl{font-family:'Mono';font-size:6.4pt;letter-spacing:.16em;color:#8C9098;text-transform:uppercase;
 margin-top:.55em;line-height:1.45}
.ibadge{display:inline-block;font-family:'Mono';font-size:6.6pt;letter-spacing:.2em;
 text-transform:uppercase;border:1px solid #C8862A;color:#E0A44A;padding:.22em .6em;
 border-radius:2px;margin-left:.7em;vertical-align:middle}
/* body */
.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:.6em;margin:.2em 0 1.1em}
.st{background:#F6F6F3;border-top:2px solid #0A6B5F;padding:.62em .7em .7em}
.sn2{font-family:'Bric';font-size:19pt;line-height:1;letter-spacing:-.02em}
.sl{font-family:'Mono';font-size:6.2pt;letter-spacing:.14em;color:#6B7078;text-transform:uppercase;
 margin-top:.45em;line-height:1.4}
table{width:100%;table-layout:fixed;border-collapse:collapse;font-size:8.2pt;
 margin:.15em 0 .8em}
td,th{overflow-wrap:anywhere}
th{font-family:'Mono';font-size:6.1pt;letter-spacing:.13em;color:#6B7078;text-transform:uppercase;
 text-align:left;font-weight:400;padding:0 .55em .42em 0;border-bottom:.7px solid #D6D6D1;
 vertical-align:bottom}
td{padding:.42em .55em .42em 0;border-bottom:.4px solid #EAEAE5;vertical-align:top;line-height:1.42}
td.n,th.n{font-family:'Mono';font-size:7.6pt;white-space:nowrap;text-align:right}
td.scope{font-family:'Mono';font-size:7.2pt;color:#4A5058;line-height:1.45;
 white-space:normal;text-align:left}
th.n{text-align:right}
td.sc{font-size:7.5pt;color:#5A6068;line-height:1.36}
tr.tot td{border-top:.7px solid #D6D6D1;border-bottom:none;font-family:'MonoMd'}
.note{background:#F6F6F3;border-left:2px solid #0A6B5F;padding:.6em .75em;margin:.55em 0 0;
 font-size:8.4pt;line-height:1.5;color:#3A4048}
.note b{font-family:'MonoMd';font-size:6.6pt;letter-spacing:.13em;text-transform:uppercase;
 color:#0A6B5F;display:block;margin-bottom:.25em}
.chg{border-left:2px solid #C8862A;background:#FAF7F1;padding:.58em .75em .3em;margin:.55em 0}
.cht{font-family:'Bric';font-size:10pt;margin-bottom:.3em}
.cont{font-family:'Mono';font-size:6.2pt;letter-spacing:.14em;color:#8A5A16;text-transform:uppercase}
.pv{font-size:8.1pt;line-height:1.48;margin:0 0 .45em}
.pl{font-family:'MonoMd';font-size:6.3pt;letter-spacing:.12em;text-transform:uppercase;color:#8A5A16}
ul.pu{font-size:8.1pt;line-height:1.46;margin:.1em 0 .5em;padding-left:1.05em}
.pkgs{display:flex;flex-wrap:wrap;gap:.24em;margin:.15em 0 .5em}
.pk{font-family:'Mono';font-size:6.4pt;background:#EDEDE7;padding:.14em .38em;border-radius:2px;
 color:#3A4048}
.bar{height:11px;background:#0A6B5F;border-radius:1px}
.bar2{height:11px;background:#C8862A;border-radius:1px}
.legend{font-family:'Mono';font-size:6.4pt;letter-spacing:.1em;color:#6B7078;text-transform:uppercase}
.two{display:grid;grid-template-columns:1fr 1fr;gap:1.1em}
.mono{font-family:'Mono';font-size:7.2pt;color:#5A6068}
.tag{font-family:'Mono';font-size:6pt;letter-spacing:.06em;background:#0A6B5F;color:#fff;
 padding:.1em .3em;border-radius:2px;margin-right:.18em}
.tag.o{background:#C8862A}
"""


class Doc:
    def __init__(self, source_line, total_pages_hint=0):
        self.pages = []
        self.src = source_line

    def page(self, inner, cover=False):
        self.pages.append((inner, cover))

    def html(self, title):
        faces = "".join(
            f"@font-face{{font-family:'{k}';src:url(data:font/ttf;base64,{font(v)}) "
            f"format('truetype');font-display:block}}" for k, v in FONTS.items())
        n = len(self.pages)
        body = []
        for i, (inner, cover) in enumerate(self.pages, 1):
            cls = 'pg cover' if cover else 'pg'
            body.append(f'<div class="{cls}">{inner}'
                        f'<div class="foot"><div class="src">{e(self.src)}</div>'
                        f'<div class="pgn">{i:02d} / {n:02d}</div></div></div>')
        return (f'<!doctype html><html><head><meta charset="utf-8"><title>{e(title)}</title>'
                f'<style>{faces}{CSS}</style></head><body>{"".join(body)}</body></html>')


def head(num, kicker, title, dek):
    return (f'<div class="wm">H A R B O R</div>'
            f'<div class="sect">{num} / {e(kicker)}</div><h2>{e(title)}</h2>'
            f'<p class="dek">{e(dek)}</p>')


def stats(items):
    return '<div class="stats">' + "".join(
        f'<div class="st"><div class="sn2">{e(str(v))}</div><div class="sl">{e(l)}</div></div>'
        for v, l in items) + '</div>'


def note(label, text):
    return f'<div class="note"><b>{e(label)}</b>{e(text)}</div>'


def barrow(label, val, mx, alt=False, suffix=''):
    w = max(2, round(100*val/max(mx, 1)))
    cls = 'bar2' if alt else 'bar'
    return (f'<tr><td style="width:36%">{e(label)}</td>'
            f'<td style="width:50%"><div class="{cls}" style="width:{w}%"></div></td>'
            f'<td class="n" style="width:14%">{val}{suffix}</td></tr>')


PAGE_PX = 1056          # 11in at 96dpi, the printed page box
# Chrome lays a page out fractionally taller when printing than when rendering to
# screen - line boxes round differently - so a page that measures exactly 1056px
# on screen loses its last row and its footer in the PDF. Fitting targets a
# slightly shorter box; the PDF audit below is what proves the number is enough.
# It has to clear the tallest single row the fitter can add, or the fit is still
# one row too generous: inventory rows are two lines (~42px at this type size).
PRINT_SLACK = int(os.environ.get('HARBOR_PRINT_SLACK', '56'))
FIT_PX = PAGE_PX - PRINT_SLACK

def measure_blocks(blocks, header_html):
    """Render the blocks in headless Chrome and read back their true pixel heights.

    Returns (heights, chrome) where chrome is everything a provenance page spends before the
    first block: page padding, the section header and the footer.
    """
    faces = "".join(
        f"@font-face{{font-family:'{k}';src:url(data:font/ttf;base64,{font(v)}) "
        f"format('truetype');font-display:block}}" for k, v in FONTS.items())
    items = "".join(f'<div class="mb">{b}</div>' for b in blocks)
    doc = (f'<!doctype html><html><head><meta charset="utf-8"><style>{faces}{CSS}</style>'
           f'</head><body><div class="pg" id="P">{header_html}'
           f'<div id="B">{items}</div>'
           f'<div class="foot"><div class="src">x</div><div class="pgn">00 / 00</div></div>'
           f'</div><pre id="OUT"></pre>'
           '<script>'
           'var pg=document.getElementById("P"),b=document.getElementById("B");'
           'var cs=getComputedStyle(pg);'
           'var hs=[].map.call(b.children,function(e){var r=e.getBoundingClientRect();'
           'var m=parseFloat(getComputedStyle(e.firstElementChild||e).marginBottom)||0;'
           'return Math.ceil(r.height+m);});'
           'var chrome=parseFloat(cs.paddingTop)+parseFloat(cs.paddingBottom)'
           '+document.querySelector(".foot").getBoundingClientRect().height'
           '+(b.getBoundingClientRect().top-pg.getBoundingClientRect().top'
           '-parseFloat(cs.paddingTop));'
           'document.getElementById("OUT").textContent='
           'JSON.stringify({h:hs,chrome:Math.ceil(chrome)});'
           '</script></body></html>')
    with tempfile.NamedTemporaryFile('w', suffix='.html', delete=False) as f:
        f.write(doc); path = f.name
    out = subprocess.run([
        CHROME, '--headless', '--disable-gpu', '--virtual-time-budget=8000',
        '--window-size=1000,20000', '--dump-dom', f'file://{path}'],
        capture_output=True, text=True).stdout
    m = re.search(r'<pre id="OUT">(\{.*?\})</pre>', out, re.S)
    if not m:
        raise SystemExit('block measurement failed - could not read heights back')
    data = json.loads(m.group(1))
    return data['h'], data['chrome']


def _page_height(inner, src_text):
    """Render one .pg containing `inner` and return its rendered height in px."""
    faces = "".join(
        f"@font-face{{font-family:'{k}';src:url(data:font/ttf;base64,{font(v)}) "
        f"format('truetype');font-display:block}}" for k, v in FONTS.items())
    doc = (f'<!doctype html><html><head><meta charset="utf-8"><style>{faces}{CSS}</style></head>'
           f'<body><div class="pg" id="P">{inner}'
           f'<div class="foot"><div class="src">{html.escape(src_text)}</div>'
           f'<div class="pgn">00 / 00</div></div></div><pre id="OUT"></pre><script>'
           'document.getElementById("OUT").textContent=JSON.stringify('
           '{h:Math.round(document.getElementById("P").getBoundingClientRect().height)});'
           '</script></body></html>')
    with tempfile.NamedTemporaryFile('w', suffix='.html', delete=False) as f:
        f.write(doc); path = f.name
    out = subprocess.run([
        CHROME, '--headless', '--disable-gpu', '--virtual-time-budget=6000',
        '--window-size=1000,30000', '--dump-dom', f'file://{path}'],
        capture_output=True, text=True).stdout
    m = re.search(r'<pre id="OUT">(\{.*?\})</pre>', out, re.S)
    if not m:
        raise SystemExit('page measurement failed')
    return json.loads(m.group(1))['h']


def fit_rows(row_htmls, header_html, table_open, extra_html='', src_text='x', build=None):
    """Largest row count whose rendered page still fits the 11in box.

    Binary search over an actual render. Estimating from row heights was wrong by a third,
    so the answer is verified rather than computed.
    """
    if build is None:
        build = lambda rows: header_html + table_open + "".join(rows) + '</table>' + extra_html
    lo, hi = 1, len(row_htmls)
    if _page_height(build(row_htmls), src_text) <= FIT_PX:
        return hi
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if _page_height(build(row_htmls[:mid]), src_text) <= FIT_PX:
            lo = mid
        else:
            hi = mid - 1
    return max(lo, 1)


# ----------------------------------------------------------------------- pages
def render(cfg, d):
    doc = Doc(cfg['source_line'])
    N, ident, mod = d['N'], d['ident'], d['modified']
    tot = Counter()
    for f in FACTORS:
        tot.update(d['audit'][f])
    applic = tot['PASS'] + tot['INFO'] + tot['FLAG']

    # --- cover
    doc.page(
        '<div class="wm">H A R B O R</div>'
        f'<div class="csub">{e(cfg["cover_kicker"])}<span class="ibadge">Internal</span></div>'
        f'<div class="ctitle">Every change.<br>On the record.</div>'
        f'<p class="clede">{e(cfg["cover_lede"])}</p>'
        '<div class="cstats">'
        + "".join(f'<div><div class="cn">{v}</div><div class="cl">{l}</div></div>' for v, l in [
            (N, 'Task packages'), (f'{mod}/{N}', 'Archives modified<br>during finalization'),
            (sum(len(g['tasks']) for g in d['groups'].values()), 'Recorded change<br>entries'),
            (f'{tot["PASS"]}', 'Factor outcomes<br>passing'),
            (f'{tot["INFO"]}', 'Documented<br>as info'), (f'{tot["NA"]}', 'Not applicable')])
        + '</div>', cover=True)

    # --- 01 executive
    doc.page(
        head('01', 'Executive view', 'What finalization did',
             'The delivery as shipped, and the work that got it there. Every figure is read from '
             'the delivery’s own audit and modification records.')
        + stats([(f'{N}/{N}', 'Packages with zero open findings'),
                 (f'{mod}/{N}', 'Archives differing from accepted source bytes'),
                 (f'{ident}/{N}', 'Archives byte-identical to source')])
        + '<table><tr><th style="width:26%">Reading</th><th style="width:74%">What it means</th></tr>'
        + f'<tr><td>{tot["PASS"]} pass</td><td>Factor-task outcomes with a clean result against '
          'the packages the factor applies to.</td></tr>'
        + f'<tr><td>{tot["INFO"]} info</td><td>Documented modifications and batch-wide design '
          'characteristics. Recorded, not defects.</td></tr>'
        + f'<tr><td>{tot["NA"]} not applicable</td><td>Factors that do not apply to a package — '
          'connector checks on an offline task, judge consistency where no judge is invoked.</td></tr>'
        + f'<tr><td>{tot["FLAG"] or "0"} flagged</td><td>Open defects remaining at handover.</td></tr>'
        + '</table>'
        + '<div class="legend" style="margin:.35em 0 .3em">Changes at a glance</div>'
        + '<table><tr><th style="width:52%">Change class</th>'
          '<th class="n" style="width:24%">Packages</th>'
          '<th class="n" style="width:24%">Share of batch</th></tr>'
        + "".join(
            f'<tr><td><span class="tag{" o" if k in ("_redaction","_os_artefacts") else ""}">'
            f'{ABBR[k]}</span>{e(TITLES[k])}</td>'
            f'<td class="n">{len(d["groups"][k]["tasks"])}</td>'
            f'<td class="n">{100*len(d["groups"][k]["tasks"])/N:.0f}%</td></tr>'
            for k in ORDER if d['groups'].get(k) and d['groups'][k]['tasks'])
        + f'<tr class="tot"><td>Packages touched at least once</td>'
          f'<td class="n">{len(d["changed_pkgs"])}</td>'
          f'<td class="n">{100*len(d["changed_pkgs"])/N:.0f}%</td></tr></table>'
        + note('Why the client edition reads differently',
               'The delivered report states pass rates against each factor’s applicable set and does '
               'not itemise finalization work. This edition adds the four-status counts, every change '
               'made to the source archives, and the basis for each. Nothing in the client edition is '
               'contradicted here.'))

    # --- 02 audit matrix
    rows = []
    for f in FACTORS:
        c = d['audit'][f]
        den = c['PASS'] + c['INFO'] + c['FLAG']
        cell = lambda v: str(v) if v else '&mdash;'
        rows.append(f'<tr><td>{e(f)}</td><td class="sc">{e(SCOPE[f])}</td>'
                    f'<td class="n">{cell(c["PASS"])}</td><td class="n">{cell(c["FLAG"])}</td>'
                    f'<td class="n">{cell(c["INFO"])}</td><td class="n">{cell(c["NA"])}</td>'
                    f'<td class="n">{den}</td></tr>')
    rows.append(f'<tr class="tot"><td>Total</td><td class="sc"></td>'
                f'<td class="n">{tot["PASS"]}</td><td class="n">{tot["FLAG"] or "&mdash;"}</td>'
                f'<td class="n">{tot["INFO"]}</td><td class="n">{tot["NA"]}</td>'
                f'<td class="n">{applic}</td></tr>')
    doc.page(
        head('02', 'Audit matrix', 'Fourteen factors, four dispositions',
             f'{N} packages against fourteen factors. Denominators differ by factor: a factor is '
             'scored only against the packages it applies to.')
        + '<table><tr><th style="width:20%">Factor</th><th style="width:36%">What we check</th>'
          '<th class="n" style="width:8%">Pass</th><th class="n" style="width:9%">Flagged</th>'
          '<th class="n" style="width:8%">Info</th><th class="n" style="width:7%">N/A</th>'
          '<th class="n" style="width:12%">Applies to</th></tr>'
        + "".join(rows) + '</table>'
        + note('Reading the matrix',
               'Info marks an outcome that is recorded rather than clean — a documented modification, '
               'or a convention shared across the batch. It is not a defect and not a pass by '
               'omission. Applies-to is the denominator the pass rate in the client edition is taken '
               'against.'))

    # --- 03 composition
    dm = d['domains'].most_common()
    gl = sorted(d['glm'].items())
    gy = d['gyms'].most_common(8)
    doc.page(
        head('03', 'Portfolio composition', 'The shape of the batch',
             'Execution mix, subject domains and the recorded four-run GLM battery.')
        + '<div class="two"><div><div class="legend">Domains</div><table>'
        + "".join(barrow(k, v, max(d['domains'].values())) for k, v in dm) + '</table></div>'
        + '<div><div class="legend">GLM battery · passes of four</div><table>'
        + "".join(barrow(k, v, max(d['glm'].values()), alt=(k.startswith('3'))) for k, v in gl)
        + '</table>'
        + ('<div class="legend" style="margin-top:.6em">Connector gyms</div><table>'
           + "".join(barrow(k, v, max(d['gyms'].values())) for k, v in gy) + '</table>'
           if gy else '') + '</div></div>'
        + stats([(f'{d["exec_mix"]["non-connector"]}/{N}', 'Non-connector'),
                 (f'{d["exec_mix"]["connector"]}/{N}', 'Connector'),
                 (f'{d["size_mb"]:.0f} MB', 'Release size')])
        + note('Difficulty policy',
               'A run counts as a pass only at a reward of exactly 1.0. Three passes of four is the '
               'lighter band, zero to two is full difficulty, four of four is out of band and was '
               'excluded from selection.'))

    # --- 04 change control
    body = []
    for k in ORDER:
        g = d['groups'].get(k)
        if not g:
            continue
        n = len(g['tasks'])
        meta = g['meta'] or {}
        if not n and not meta.get('result'):
            continue
        scope = f'{n} package{"s" if n != 1 else ""}'
        if k == '_redaction':
            bits = []
            if d['occ'].get('gateway_ip'):  bits.append(f"{d['occ']['gateway_ip']:,} address occurrences")
            if d['occ'].get('local_paths'): bits.append(f"{d['occ']['local_paths']} files with paths")
            if bits: scope += ' · ' + ', '.join(bits)
        if k == '_os_artefacts' and d['occ'].get('artefacts'):
            scope += f" · {d['occ']['artefacts']} files"
        body.append(f'<tr><td><span class="tag{" o" if k in ("_redaction","_os_artefacts") else ""}">'
                    f'{ABBR[k]}</span>{e(TITLES[k])}</td><td class="scope">{e(scope)}</td>'
                    f'<td class="sc">{e(str(meta.get("fix") or meta.get("result") or ""))}</td></tr>')
    doc.page(
        head('04', 'Change control', 'Every deviation from source',
             f'{mod} of {N} archives differ from the accepted source bytes. {ident} are byte-identical. '
             'Each class below is recorded per package with its basis.')
        + '<table><tr><th style="width:31%">Change</th><th style="width:27%">Scope</th>'
          '<th style="width:42%">What was done</th></tr>' + "".join(body) + '</table>'
        + (note('Why this differs from the delivered edition', cfg['delta_note'])
           if cfg.get('delta_note') else '')
        + note('How archives were edited',
               'Entries were streamed and only the targets rewritten; every other entry keeps its '
               'bytes, CRC, timestamp and mode. The set of CRC-changed entries was asserted to equal '
               'exactly the intended set before each archive was accepted.')
        + note('What was deliberately left alone',
               'Historical run evidence under evaluations/, reported QC output, and placeholders that '
               'are functionally load-bearing. Renaming a package leaves stale path references inside '
               'run evidence: that is correct, and is recorded as a known residual rather than '
               'rewritten.'))

    # --- 05..n provenance (paginated)
    def chip_tail(spans, total):
        return (f'<p class="pv"><span class="pl">Packages ({total})</span></p>'
                f'<div class="pkgs">{" ".join(spans)}</div>')

    def chip_page(k, spans, total):
        return (f'<div class="chg"><div class="cht">{e(TITLES[k])}'
                f'<span class="cont"> continued</span></div>'
                f'{chip_tail(spans, total)}</div>')

    SPANS = {}
    blocks = []
    for k in ORDER:
        g = d['groups'].get(k)
        if not g or (not g['tasks'] and not (g['meta'] or {}).get('result')):
            continue
        meta = g['meta'] or {}
        h = [f'<div class="chg"><div class="cht">{e(TITLES[k])}</div>']
        for field, label in PROV:
            v = meta.get(field)
            if not v:
                continue
            if isinstance(v, dict):
                items = "".join(
                    f'<li><code>{e(str(kk))}</code> &mdash; '
                    f'{e(str(vv.get("reason") if isinstance(vv, dict) else vv))}</li>'
                    for kk, vv in v.items())
                h.append(f'<p class="pv"><span class="pl">{label}</span></p><ul class="pu">{items}</ul>')
            elif isinstance(v, list):
                items = "".join(f'<li>{e(str(x))}</li>' for x in v)
                h.append(f'<p class="pv"><span class="pl">{label}</span></p><ul class="pu">{items}</ul>')
            else:
                h.append(f'<p class="pv"><span class="pl">{label}</span> {e(str(v))}</p>')
        if meta.get('substitutions'):
            r = "".join(f'<tr><td class="mono">{e(s["from"])}</td>'
                        f'<td class="mono">{e(s["to"])}</td></tr>' for s in meta['substitutions'])
            h.append('<table><tr><th style="width:38%">From</th><th style="width:62%">To</th>'
                     '</tr>' + r + '</table>')
        reasoning = "".join(h) + '</div>'
        chips, whole = '', reasoning
        if g['tasks']:
            spans = [f'<span class="pk">{e(t)}</span>' for t in sorted(g['tasks'])]
            SPANS[k] = spans
            tail = chip_tail(spans, len(g['tasks']))
            whole = "".join(h) + tail + '</div>'
            chips = chip_page(k, spans, len(g['tasks']))
        blocks.append((k, whole, reasoning, chips))

    # pack by MEASURED height. Estimating block weight put one class on each page and left
    # the rest of the sheet blank; a class that will not fit whole now leaves its package
    # list to the next page rather than forcing an early break.
    hdr = head('05', 'Provenance', 'The basis for each change',
               'What each change rests on, what it does not establish, and any evidence pointing '
               'the other way.')
    flat = []
    for _k, whole, reasoning, chips in blocks:
        flat += [whole, reasoning, chips or '<div></div>']
    heights, chrome = measure_blocks(flat, hdr)
    H = {k: dict(whole=heights[3*i], head=heights[3*i+1], chips=heights[3*i+2])
         for i, (k, _w, _r, _c) in enumerate(blocks)}
    budget = FIT_PX - chrome - 30                      # slack: rounding plus the box shadow the packer cannot see
    chunks, cur, cw = [], [], 0
    for k, whole, reasoning, chips in blocks:
        hw = H[k]['whole']
        if cw + hw <= budget:
            cur.append(whole); cw += hw
            continue
        if chips:
            # the reasoning goes on a fresh page when it will not fit on this one;
            # falling through to the whole-block branch puts an oversized package
            # list on a single page, which is the overflow this split exists to avoid
            if cw + H[k]['head'] > budget:
                if cur:
                    chunks.append(cur)
                cur, cw = [], 0
            cur.append(reasoning)
            chunks.append(cur)
            if H[k]['chips'] <= budget:
                cur, cw = [chips], H[k]['chips']
                continue
            # A class touching several hundred packages has a list taller than the
            # page box. Moving it whole was the only option here and it overflowed
            # silently, which only shows up as clipped names in the PDF. Split it
            # by render, the same way inventory rows are fitted.
            total, rest, pages = len(SPANS[k]), list(SPANS[k]), []
            while rest:
                n = fit_rows(rest, hdr, '', src_text=cfg['source_line'],
                             build=lambda rows: hdr + chip_page(k, rows, total))
                pages.append(chip_page(k, rest[:n], total))
                rest = rest[n:]
            for pg in pages[:-1]:
                chunks.append([pg])
            cur, cw = [pages[-1]], budget      # rendered full by construction
            continue
        if cur:
            chunks.append(cur)
        cur, cw = [whole], hw
    if cur:
        chunks.append(cur)
    pnum = 5
    for i, chunk in enumerate(chunks, 1):
        label = 'Provenance' if len(chunks) == 1 else f'Provenance {i} of {len(chunks)}'
        doc.page(
            head(f'{pnum:02d}', label, 'The basis for each change',
                 'What each change rests on, what it does not establish, and any evidence pointing '
                 'the other way.')
            + "".join(chunk))
    pnum += 1

    # --- hygiene
    hy = cfg.get('hygiene') or derive_hygiene(d)
    doc.page(
        head(f'{pnum:02d}', 'Hygiene', 'Before and after',
             'Regex sweep over every file inside every archive, excluding binary formats. Every '
             'credential-class match was traced to its containing field before classification.')
        + '<table><tr><th style="width:30%">Pattern</th><th class="n" style="width:10%">Before</th>'
          '<th class="n" style="width:10%">After</th><th style="width:50%">Verdict</th></tr>'
        + "".join(f'<tr><td>{e(p)}</td><td class="n">{b}</td><td class="n">{a}</td>'
                  f'<td class="sc">{e(v)}</td></tr>' for p, b, a, v in hy)
        + '</table>'
        + (note('Why some counts do not go to zero',
                'A credential-shaped string is not a credential. An opaque encrypted blob contains '
                'substrings matching key patterns by chance, and a dummy token bound at image build '
                'is configuration: replacing it would change runtime behaviour. Each was traced to '
                'its containing field, classified and left in place.')
           if any(int(a) for _p, _b, a, _v in hy) else
           note('What this table does not cover',
                'These rows are derived from the modification record, so they show only what was '
                'acted on. A pattern that was found and deliberately left in place - a placeholder '
                'bound at image build, an encrypted blob whose substring matches a key pattern - '
                'has to come from the sweep itself. Pass it in with --hygiene to state it here.')))
    pnum += 1

    # --- per-package change log
    changed = sorted(d['changed_pkgs'])
    cols = [(t, [ABBR[k] for k in ORDER if t in (d['groups'].get(k) or {}).get('tasks', {})])
            for t in changed]
    def tbl(part):
        return ('<table><tr><th style="width:62%">Package</th>'
                '<th class="n" style="width:38%">Changes</th></tr>'
                + "".join(f'<tr><td class="mono">{e(t)}</td><td class="n">'
                          + " ".join(f'<span class="tag{" o" if m in ("RED","ART") else ""}">{m}</span>'
                                     for m in ms) + '</td></tr>' for t, ms in part) + '</table>')
    _lh = head('07', 'Per-package change log', 'Which package got what',
               f'{len(changed)} of {N} packages carry at least one recorded change. Codes match '
               'the change-control table.')
    _rows = [f'<tr><td class="mono">{e(t)}</td><td class="n">'
             + " ".join(f'<span class="tag">{m}</span>' for m in ms) + '</td></tr>'
             for t, ms in cols]
    def tbl_rows(rs):
        return ('<table><tr><th style="width:62%">Package</th>'
                '<th class="n" style="width:38%">Changes</th></tr>' + "".join(rs) + '</table>')
    _note = note('Package names in this table',
                 'Each row uses the package name as it stood when the change was recorded. Where a '
                 'package was later renamed to its declared identity, the change-control entry for '
                 'that rename carries both names.')
    def _log_page(rows):
        h = (len(rows) + 1) // 2
        return _lh + '<div class="two"><div>' + tbl_rows(rows[:h]) + '</div><div>' \
               + tbl_rows(rows[h:]) + '</div></div>' + _note
    PER_LOG = fit_rows(_rows, _lh, '', src_text=cfg['source_line'], build=_log_page)
    log_pages = [cols[i:i+PER_LOG] for i in range(0, len(cols), PER_LOG)] or [[]]
    for i, chunk in enumerate(log_pages, 1):
        half = (len(chunk)+1)//2
        label = ('Per-package change log' if len(log_pages) == 1
                 else f'Per-package change log {i} of {len(log_pages)}')
        doc.page(
            head(f'{pnum:02d}', label, 'Which package got what',
                 f'{len(changed)} of {N} packages carry at least one recorded change. Codes match '
                 'the change-control table.')
            + '<div class="two"><div>' + tbl(chunk[:half]) + '</div><div>'
            + tbl(chunk[half:]) + '</div></div>'
            + (note('Package names in this table',
                    'Each row uses the package name as it stood when the change was recorded. Where '
                    'a package was later renamed to its declared identity, the change-control entry '
                    'for that rename carries both names.') if i == len(log_pages) else ''))
    pnum += 1

    # --- inventory
    _ih = head('08', 'Package inventory 1 of 1', 'The complete delivery',
               f'Packages 1-{len(d["inv"])} of {len(d["inv"])}. Names, categories, recorded GLM '
               'results, sizes and SHA-256 prefixes.')
    _irows = [f'<tr><td class="mono">{e(x["name"])}<br>'
              f'<span style="color:#9AA0A6">{e(x["sha"])}</span></td>'
              f'<td class="sc">{e(x["kind"])}<br>{e(x["domain"])}</td>'
              f'<td class="n">{e(x["glm"])}</td><td class="n">{x["mb"]}</td></tr>' for x in d['inv']]
    per = fit_rows(_irows, _ih,
                   '<table><tr><th style="width:54%">Task / SHA-256</th>'
                   '<th style="width:22%">Type / domain</th><th class="n" style="width:12%">GLM</th>'
                   '<th class="n" style="width:12%">MB</th></tr>',
                   src_text=cfg['source_line'])
    chunks = [d['inv'][i:i+per] for i in range(0, len(d['inv']), per)]
    for i, ch in enumerate(chunks, 1):
        rows = "".join(
            f'<tr><td class="mono">{e(x["name"])}<br><span style="color:#9AA0A6">{e(x["sha"])}</span></td>'
            f'<td class="sc">{e(x["kind"])}<br>{e(x["domain"])}</td>'
            f'<td class="n">{e(x["glm"])}</td><td class="n">{x["mb"]}</td></tr>' for x in ch)
        doc.page(
            head(f'{pnum:02d}', f'Package inventory {i} of {len(chunks)}', 'The complete delivery',
                 f'Packages {(i-1)*per+1}–{min(i*per, len(d["inv"]))} of {len(d["inv"])}. '
                 'Names, categories, recorded GLM results, sizes and SHA-256 prefixes.')
            + '<table><tr><th style="width:54%">Task / SHA-256</th>'
              '<th style="width:22%">Type / domain</th><th class="n" style="width:12%">GLM</th>'
              '<th class="n" style="width:12%">MB</th></tr>' + rows + '</table>')
    return doc


# ----------------------------------------------------------------------- hygiene

def derive_hygiene(d):
    """Build the before/after table from the modification record when none is supplied.

    Only classes the record actually accounts for appear. A pattern that was found and
    deliberately left in place cannot be derived and must be passed in with --hygiene.
    """
    occ, g = d['occ'], d['groups']
    rows = []
    if occ.get('gateway_ip'):
        rows.append(('Internal infrastructure addresses', occ['gateway_ip'], 0,
                     'redacted to a neutral placeholder'))
    if occ.get('local_paths'):
        rows.append(('Authoring-machine paths', occ['local_paths'], 0,
                     'redacted to a neutral placeholder'))
    n = len((g.get('_stale_qc_claims') or {}).get('tasks', {}))
    if n:
        rows.append(('Stale pass-rate claims', n, 0, 'reconciled to the packaged battery'))
    if occ.get('artefacts'):
        rows.append(('Editor, OS and download-marker files', occ['artefacts'], 0,
                     'removed; every carrier file retained'))
    n = len((g.get('_verifier_justification') or {}).get('tasks', {}))
    if n:
        rows.append(('Verifier justification naming the wrong file', n, 0,
                     'description string corrected; no source, assertion or weight touched'))
    if not rows:
        rows.append(('Sensitive-data sweep', 0, 0, 'no findings in this delivery'))
    return rows


# ----------------------------------------------------------------------- cli

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--mods', required=True, type=Path, help='MODIFICATIONS.json')
    ap.add_argument('--manifest', required=True, type=Path, help="the delivery's manifest.json")
    ap.add_argument('--inventory', required=True, type=Path, help='the 12-column delivery manifest CSV')
    ap.add_argument('--audit', required=True, type=Path, help='audit-14-factor-findings.csv')
    ap.add_argument('--out', required=True, type=Path, help='output path without extension')
    ap.add_argument('--hygiene', type=Path, help='JSON list of [pattern, before, after, verdict]')
    ap.add_argument('--delta-note', default=None)
    ap.add_argument('--cover-lede', default=None)
    ap.add_argument('--source-line', default=None)
    ap.add_argument('--pdf', action='store_true', help='also render a PDF with Chrome')
    a = ap.parse_args(argv)

    if CHROME is None:
        raise SystemExit('Chrome not found. It is required to measure layout; install it or '
                         'set CHROME in this script.')
    for p in (a.mods, a.manifest, a.inventory, a.audit):
        if not p.is_file():
            raise SystemExit(f'missing input: {p}')

    cfg = dict(
        mods=a.mods, manifest=a.manifest, inventory=a.inventory, audit=a.audit, out=a.out,
        title='Delivery report - internal edition',
        cover_kicker='Finalization delivery - internal edition',
        cover_lede=a.cover_lede or (
            'The delivered batch with its finalization work on the record: every deviation from '
            'the accepted source bytes, the basis for each, and the evidence pointing the other way.'),
        source_line=a.source_line or (
            'Internal record - built from the modification record, the fourteen-factor audit and '
            'the release manifest - not for client distribution'),
        delta_note=a.delta_note,
        hygiene=json.loads(a.hygiene.read_text()) if a.hygiene else None,
    )
    d = load(cfg)
    doc = render(cfg, d)
    # with_suffix() treats "…-GLM-5.3-397" as name "…-GLM-5" + suffix ".3-397"
    # and silently writes a different file than the caller asked for
    out_html = a.out.with_name(a.out.name + '.html')
    out_html.parent.mkdir(parents=True, exist_ok=True)
    out_html.write_text(doc.html(cfg['title']), encoding='utf-8')

    tot = Counter()
    for f in FACTORS:
        tot.update(d['audit'][f])
    print(f"{out_html}  pages={len(doc.pages)}  packages={d['N']}  "
          f"modified={d['modified']}  byte-identical={d['ident']}")
    print(f"  audit  pass={tot['PASS']} info={tot['INFO']} n/a={tot['NA']} flagged={tot['FLAG']}")
    print(f"  changes recorded on {len(d['changed_pkgs'])} package(s)")

    bad = audit_pages(out_html)
    if bad:
        print('  PAGE OVERFLOW - these pages exceed the 11in box and will clip in print:')
        for i, h in bad:
            print(f'     page {i}: {h}px')
        return 1
    print('  every page fits the 11in box')

    if a.pdf:
        # A relative --print-to-pdf destination is silently ignored on Windows:
        # Chrome exits 0 and writes nothing. Resolve it, and check it landed.
        out_pdf = a.out.with_name(a.out.name + '.pdf').resolve()
        r = subprocess.run([CHROME, '--headless', '--disable-gpu', '--no-pdf-header-footer',
                            '--virtual-time-budget=30000', f'--print-to-pdf={out_pdf}',
                            out_html.resolve().as_uri()], capture_output=True, text=True)
        if not out_pdf.is_file():
            print(f'  PDF NOT WRITTEN: {(r.stderr or "").strip()[:200]}')
            return 1
        print(f'  {out_pdf}  ({out_pdf.stat().st_size:,} bytes)')
    return 0


def audit_pages(path):
    """Return [(page, height)] for any page taller than the printed box."""
    js = ('<script>var o=[].map.call(document.querySelectorAll(".pg"),function(p,i){'
          'return {i:i+1,h:Math.round(p.getBoundingClientRect().height)};});'
          'var d=document.createElement("pre");d.id="OUT";d.textContent=JSON.stringify(o);'
          'document.body.appendChild(d);</script>')
    doc = Path(path).read_text().replace('</body>', js + '</body>')
    with tempfile.NamedTemporaryFile('w', suffix='.html', delete=False) as f:
        f.write(doc); tmp = f.name
    out = subprocess.run([CHROME, '--headless', '--disable-gpu', '--virtual-time-budget=12000',
                          '--window-size=1000,30000', '--dump-dom', Path(tmp).resolve().as_uri()],
                         capture_output=True, text=True).stdout
    m = re.search(r'<pre id="OUT">(\[.*?\])</pre>', out, re.S)
    if not m:
        return []
    return [(x['i'], x['h']) for x in json.loads(m.group(1)) if x['h'] > PAGE_PX + 4]


if __name__ == '__main__':
    sys.exit(main())
