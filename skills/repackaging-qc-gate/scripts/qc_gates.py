#!/usr/bin/env python3
"""Packaging QC gates for Harbor task deliveries.

Run against a packaged delivery (a directory containing manifest.json) or against any
directory of task archives. Reads ZIP members only: never extracts, never executes anything
bundled, never writes to the archives it inspects.

    python3 qc_gates.py <path>                     # human-readable, exits non-zero on a BLOCK
    python3 qc_gates.py <path> --json report.json  # machine-readable report
    python3 qc_gates.py <path> --csv report.csv    # one row per finding
    python3 qc_gates.py <path> --gate G01 --gate G05
    python3 qc_gates.py <path> --warn-only         # always exit 0

Exit codes: 0 clean or WARN only; 1 at least one BLOCK finding; 2 usage or unreadable input.
"""
from __future__ import annotations

import argparse, csv, hashlib, json, re, sys, zipfile
from collections import Counter, defaultdict
from pathlib import Path, PurePosixPath

try:
    import tomllib
except ImportError:                                     # Python < 3.11
    try:
        import tomli as tomllib
    except ImportError:
        tomllib = None

VERSION = "1.0"

# --------------------------------------------------------------------------- helpers

BINARY = {'.png','.jpg','.jpeg','.gif','.pdf','.zip','.gz','.tar','.db','.sqlite','.xlsx',
          '.docx','.pptx','.woff','.woff2','.ico','.so','.pyc','.jar','.class','.wasm'}
TEXT_MAX = 8_000_000

# A pass is a reward of EXACTLY 1.0. Not 0.9999999999999988, not "exit code 0".
STRICT = re.compile(r'^\s*1(?:\.0+)?\s*$')

# Only a PASS-RATE claim counts. "completed 4/4 executions" and "4/4 runs" are completion
# counts, not pass rates, and must not be rewritten.
PASS_CLAIM = re.compile(
    r'(?:pass\s*rate[^.\n]{0,40}?`?(\d)\s*/\s*4)|(?:`?(\d)\s*/\s*4`?\s*(?:full\s+)?passes)', re.I)

# Container and service accounts look like home directories but are generic infrastructure.
SERVICE_ACCOUNTS = ('rlgymagent', 'harbor', 'runner', 'node', 'user', 'app', 'ubuntu', 'root')
MAC_PATH  = re.compile(rb'/Users/[a-z][a-z0-9._-]{1,40}')
WIN_PATH  = re.compile(rb'C:[\\/]Users[\\/][A-Za-z0-9._-]{1,40}')
HOME_PATH = re.compile(rb'/home/(?!(?:' + '|'.join(SERVICE_ACCOUNTS).encode() + rb')/)'
                       rb'[a-z][a-z0-9._-]{2,40}/')

# A leaked endpoint is an address in a HOST POSITION - after a scheme, an @, or a
# host/url/endpoint key, or carrying a port. A bare dotted quad is not enough: task corpora
# and agent reasoning contain digit-group notation (a card mask described as "4.4.4.4") and
# version-like strings that match a naive IPv4 pattern by chance.
IPV4_HOST = re.compile(
    rb'(?:[a-z][a-z0-9+.-]*://|@|\b(?:host|hostname|server|endpoint|base_?url|baseURL|addr|address|'
    rb'proxy|gateway|target)\b["\']?\s*[:=]\s*["\']?)'
    rb'(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})'
    rb'|(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3}):\d{2,5}\b', re.I)
DOC_NETS = ((192,0,2),(198,51,100),(203,0,113))

OS_ARTEFACT = re.compile(
    r'(:Zone\.Identifier$|(^|/)\.DS_Store$|(^|/)\._[^/]+$|(^|/)__MACOSX(/|$)'
    r'|\.swp$|\.swo$|~$|\.orig$|\.rej$|(^|/)Thumbs\.db$|(^|/)desktop\.ini$)')

# Where an image reference is load-bearing. Historical run evidence and reported QC output
# record what happened at run time and are deliberately out of scope.
IMAGE_SCOPE = ('environment/Dockerfile', 'task.toml', 'environment/_app/task.toml')
IMAGE_IN_DOCKERFILE = re.compile(r'^\s*FROM\s+(\S+)', re.M)
IMAGE_IN_TOML = re.compile(r'^\s*image\s*=\s*["\']([^"\']+)["\']', re.M)
# A bare name with no registry host and no tag resolves to :latest implicitly.
SCRATCH_BASES = {'scratch'}

GYM_DATASET = re.compile(
    r'GYM_DATASET\s*=\s*["\']?\$?\{?GYM_DATASET:-(\w+)\}?|GYM_DATASET\s*=\s*(real|synthetic)\b')

DOC_EXT = r'(?:csv|json|md|txt|pdf|xlsx|docx|pptx|html|yaml|yml)'


def is_routable_ipv4(m) -> bool:
    g = [x for x in m.groups() if x is not None]
    if len(g) != 4:
        return False
    o = [int(x) for x in g]
    if any(x > 255 for x in o):
        return False
    if o[0] in (0, 10, 127) or o[:2] == [169, 254] or (o[0] == 172 and 16 <= o[1] <= 31) \
       or o[:2] == [192, 168] or o[0] >= 224:
        return False
    if tuple(o[:3]) in DOC_NETS:
        return False
    return True


def text_members(z: zipfile.ZipFile):
    """Yield (name, bytes) for members worth scanning as text."""
    for zi in z.infolist():
        if zi.is_dir() or Path(zi.filename).suffix.lower() in BINARY or zi.file_size > TEXT_MAX:
            continue
        try:
            yield zi.filename, z.read(zi.filename)
        except Exception:
            continue


# --------------------------------------------------------------------------- gate defs

GATES = [
    dict(id='G01', name='Mutable image reference',
         severity='BLOCK', scope='package',
         summary='A base or gym image is referenced by a tag rather than an immutable digest.',
         why='A tag can be repointed at a different build. Once it moves, the package no longer '
             'describes an environment anyone can reconstruct, and a regrade silently runs '
             'against different software than the recorded battery did.',
         fix='Resolve the tag to its digest and pin it in environment/Dockerfile, task.toml and '
             'environment/_app/task.toml. Record where the digest came from and what it does not '
             'establish. Leave evaluations/ and reported QC output alone.'),
    dict(id='G13', name='Image reference carries two digests',
         severity='BLOCK', scope='package',
         summary='A FROM line or image = value pins more than one @sha256: digest.',
         why='Two digests on one reference is not a parseable OCI image reference. The build '
             'fails at pull, which surfaces downstream as ImageBuildError and then as an oracle '
             'that never ran - so the package reads as a grading failure rather than as the '
             'packaging defect it is. G01 alone does not catch it: a doubled reference contains '
             '@sha256: and passes any check that asks only whether a digest is present.',
         fix='Keep the last digest and drop everything between the image name and it, including '
             'any stray character left behind by a partially consumed tag. A digest alone is a '
             'complete reference; the tag is not needed once it is pinned. Verify the result '
             'parses before repackaging - do not assume the substitution matched.'),
    dict(id='G02', name='Internal infrastructure address',
         severity='BLOCK', scope='package',
         summary='A routable address appears in a host position in package text.',
         why='Internal service endpoints do not belong in a delivered artifact. They leak topology '
             'and they are meaningless to whoever receives the package.',
         fix='Replace with a neutral placeholder. Grading never resolves these, so behaviour is '
             'unaffected.'),
    dict(id='G03', name='Authoring-machine path',
         severity='BLOCK', scope='package',
         summary='A personal home directory path appears in package text.',
         why='Local paths name individuals and expose the authoring environment. Container and '
             'service accounts are generic infrastructure and are deliberately excluded.',
         fix='Replace with a neutral placeholder.'),
    dict(id='G04', name='Undeclared connector data provenance',
         severity='BLOCK', scope='package',
         summary='A connector task declares no dataset although the package itself determines one.',
         why='Whether a connector runs against a real or synthetic corpus changes what the task '
             'proves. When the package states the answer in its own runtime configuration, leaving '
             'the declared field empty is an omission, not an open question.',
         fix='Declare the value the package already states. Where the package says both, or says '
             'nothing, leave it undeclared and record why: that is an observation about the source, '
             'not a defect to close by guessing.'),
    dict(id='G05', name='Package identity mismatch',
         severity='BLOCK', scope='package',
         summary='Archive name, internal root directory and the name declared in task.toml disagree.',
         why='The recipient gets a filename that does not match what the task calls itself. Usually '
             'the folder is an opaque pipeline id while task.toml carries the real name.',
         fix='Rename paths only. Never touch file content: every entry keeps its bytes, CRC, '
             'timestamp and mode. References under evaluations/ stay pointing at the old path, '
             'because they describe where the runs executed at the time.'),
    dict(id='G06', name='Documentation contradicts packaged evidence',
         severity='BLOCK', scope='package',
         summary='A stated pass rate disagrees with the reward files packaged beside it.',
         why='The packaged rewards are authoritative and drive the difficulty banding. A document '
             'claiming a different rate makes the package argue with itself.',
         fix='Reconcile the document to the evidence, never the reverse. Match the specific claim '
             'wording: a completion count such as "4/4 executions" is not a pass rate.'),
    dict(id='G07', name='Missing package documentation',
         severity='WARN', scope='package',
         summary='The package ships without a README.md at its root.',
         why='Every other package in the set carries one. The gap is visible the moment a reviewer '
             'opens two archives side by side.',
         fix='Generate it strictly from in-package evidence — task.toml, the verifier set, '
             'evaluations/. Assert nothing that cannot be read out of the package, and say in the '
             'file that it was generated.'),
    dict(id='G08', name='Non-task artefact',
         severity='BLOCK', scope='package',
         summary='An editor, OS or download-marker file is present in the archive.',
         why='These are not part of the task. They are noise at best and, in the case of '
             'download markers, evidence of how the file reached the author.',
         fix='Remove them. Never remove a file the task uses. Sweep last: some are recreated '
             'every time a file browser opens the folder.'),
    dict(id='G09', name='Verifier documentation mismatch',
         severity='WARN', scope='package',
         summary='A verifier justification names a file the check does not read.',
         why='The human-readable field and the machine-readable check disagree about which file is '
             'being verified. Grading is unaffected, but a reviewer reading the justification is '
             'told the wrong thing.',
         fix='Correct the description string only. Do not touch the source, assertion, path or '
             'weight.'),
    dict(id='G10', name='Incomplete difficulty battery',
         severity='BLOCK', scope='package',
         summary='The package does not carry exactly four recorded difficulty rewards.',
         why='Difficulty banding is computed from the four-run battery. Without all four the band '
             'is not derivable and the task cannot be placed.',
         fix='Do not ship it. Route to review with the count actually found.'),
    dict(id='G11', name='Difficulty band mismatch',
         severity='BLOCK', scope='delivery',
         summary='The band recomputed from raw rewards disagrees with the folder or the manifest.',
         why='A task filed under the wrong band misrepresents the difficulty mix of the whole '
             'delivery. Recomputing from the reward files is the only check that cannot inherit an '
             'upstream mistake.',
         fix='Recompute from the raw rewards and refile. A pass is exactly 1.0; 3 of 4 is the '
             'lighter band, 0 to 2 is full difficulty, 4 of 4 is out of band.'),
    dict(id='G12', name='Manifest does not reconcile',
         severity='BLOCK', scope='delivery',
         summary='Manifest and disk disagree, or a hash, size, name or id is wrong or duplicated.',
         why='The manifest is what the recipient verifies against. If it disagrees with the tree in '
             'either direction, nothing else in it can be trusted.',
         fix='Recompute every hash and size from the delivered bytes and reconcile in both '
             'directions before shipping.'),
]
GATE_BY_ID = {g['id']: g for g in GATES}


# --------------------------------------------------------------------------- checks

def check_package(zp: Path, enabled: set[str]) -> list[dict]:
    """Run every package-scope gate over one archive. Returns a list of findings."""
    out: list[dict] = []
    try:
        z = zipfile.ZipFile(zp)
    except zipfile.BadZipFile:
        return [dict(gate='G12', task=zp.stem, detail='archive is not readable', evidence=str(zp.name))]

    with z:
        names = [n for n in z.namelist() if not n.endswith('/')]
        roots = {PurePosixPath(n).parts[0] for n in names if PurePosixPath(n).parts}
        root = next(iter(roots)) if len(roots) == 1 else zp.stem
        task = root

        def add(gate, detail, evidence=''):
            if gate in enabled:
                out.append(dict(gate=gate, task=task, detail=detail, evidence=evidence))

        # ---- G08 non-task artefacts
        for n in names:
            if OS_ARTEFACT.search(n):
                add('G08', 'non-task artefact present', n)

        # ---- G05 identity
        toml = {}
        tp = f'{root}/task.toml'
        if tp in names and tomllib is not None:
            try:
                toml = tomllib.loads(z.read(tp).decode('utf-8', 'replace'))
            except Exception:
                toml = {}
        declared_full = ((toml.get('task') or {}).get('name') or '')
        declared = declared_full.split('/')[-1]
        if declared:
            mism = [w for w, v in (('archive name', zp.stem), ('root directory', root)) if v != declared]
            if mism:
                add('G05', f'{" and ".join(mism)} disagree with the declared name',
                    f'declared={declared} archive={zp.stem} root={root}')
        if len(roots) > 1:
            add('G05', 'archive has more than one root directory', ','.join(sorted(roots)))

        # ---- G07 README
        if f'{root}/README.md' not in names:
            add('G07', 'no README.md at package root', '')

        # ---- G01 image references
        for rel in IMAGE_SCOPE:
            n = f'{root}/{rel}'
            if n not in names:
                continue
            try:
                txt = z.read(n).decode('utf-8', 'replace')
            except Exception:
                continue
            refs = IMAGE_IN_DOCKERFILE.findall(txt) if rel.endswith('Dockerfile') else IMAGE_IN_TOML.findall(txt)
            for ref in refs:
                base = ref.split('@')[0]
                if ref.count('@sha256:') > 1:
                    # Checked before the already-pinned skip below: a doubled
                    # reference contains '@sha256:' and would otherwise be read
                    # as correctly pinned. This is how the defect survived the
                    # gate the first time.
                    add('G13', 'image reference carries more than one digest and cannot be '
                               'resolved by any OCI runtime', f'{rel}: {ref}')
                    continue
                if '@sha256:' in ref or base in SCRATCH_BASES or ref.startswith('$'):
                    continue
                add('G01', 'image referenced by a mutable tag rather than a digest', f'{rel}: {ref}')

        # ---- G10 battery
        rewards = {}
        for n in names:
            m = re.search(r'evaluations/difficulty/(r[1-4])/.*reward\.txt$', n)
            if m:
                try:
                    rewards[m.group(1)] = z.read(n).decode('utf-8', 'replace').strip()
                except Exception:
                    pass
        successes = None
        if len(rewards) != 4:
            add('G10', f'{len(rewards)} of 4 difficulty rewards recorded', ','.join(sorted(rewards)))
        else:
            successes = sum(1 for v in rewards.values() if STRICT.match(v))

        # ---- G06 stale pass-rate claims
        if successes is not None:
            for fn in ('review.csv', 'README.md', 'qc_report.html'):
                n = f'{root}/{fn}'
                if n not in names:
                    continue
                try:
                    txt = z.read(n).decode('utf-8', 'replace')
                except Exception:
                    continue
                claims = [int(g) for tup in PASS_CLAIM.findall(txt) for g in tup if g]
                if claims and claims[-1] != successes:
                    add('G06', 'stated pass rate disagrees with the packaged rewards',
                        f'{fn} claims {claims[-1]}/4, packaged battery is {successes}/4')

        # ---- G04 connector data provenance
        ext = (toml.get('metadata') or {}).get('mcp_servers_extended') or []
        envm = (toml.get('environment') or {}).get('mcp_servers') or []
        if ext or envm:
            declared_ds = {s.get('dataset') for s in ext if s.get('dataset')}
            if not declared_ds:
                sig = set()
                for n, b in ((n, z.read(n)) for n in names if f'{root}/environment/' in n + '/'):
                    if Path(n).suffix.lower() in BINARY:
                        continue
                    for m in GYM_DATASET.finditer(b.decode('utf-8', 'replace')):
                        v = next((g for g in m.groups() if g), None)
                        if v:
                            sig.add(v)
                if len(sig) == 1:
                    add('G04', 'connector dataset undeclared although the package states it',
                        f'environment sets GYM_DATASET={sig.pop()}')

        # ---- G09 verifier documentation
        vn = f'{root}/tests/verifier.json'
        if vn in names:
            try:
                vj = json.loads(z.read(vn).decode('utf-8', 'replace'))
            except Exception:
                vj = {}
            for v in vj.get('verifiers') or []:
                hj = ((v.get('metadata') or {}).get('how_justification') or '')
                src = json.dumps(v.get('source') or {})
                for fname in re.findall(r'[\w\-]+\.' + DOC_EXT, hj):
                    if fname in src:
                        continue
                    alt = re.findall(re.escape(fname.rsplit('.', 1)[0]) + r'\.\w+', src)
                    if alt and alt[0] != fname:
                        add('G09', 'verifier justification names a file the check does not read',
                            f'{v.get("name")}: says {fname}, reads {alt[0]}')

        # ---- G02 / G03 sensitive strings
        ip_hits, path_hits = Counter(), Counter()
        for n, b in text_members(z):
            for m in IPV4_HOST.finditer(b):
                if is_routable_ipv4(m):
                    g = [x for x in m.groups() if x is not None]
                    ip_hits[b'.'.join(g).decode()] += 1
            if MAC_PATH.search(b) or WIN_PATH.search(b) or HOME_PATH.search(b):
                path_hits[n] += 1
        for addr, c in sorted(ip_hits.items()):
            add('G02', 'routable address in a host position', f'{addr} x{c}')
        if path_hits:
            add('G03', 'authoring-machine path in package text',
                f'{len(path_hits)} file(s), e.g. {sorted(path_hits)[0]}')

    return out


def check_delivery(root: Path, packages: list[Path], enabled: set[str]) -> list[dict]:
    """Delivery-scope gates: the manifest must reconcile with the tree in both directions."""
    out: list[dict] = []
    mp = root / 'manifest.json'
    if not mp.is_file():
        return out

    def add(gate, detail, evidence=''):
        if gate in enabled:
            out.append(dict(gate=gate, task='(delivery)', detail=detail, evidence=evidence))

    try:
        man = json.loads(mp.read_text())
    except Exception as exc:
        add('G12', 'manifest.json is not readable', str(exc)[:120])
        return out

    tasks = man.get('tasks') or []
    listed = {t.get('package_path') for t in tasks}
    on_disk = {str(p.relative_to(root)) for p in packages}
    for x in sorted(on_disk - listed):
        add('G12', 'archive on disk is not listed in the manifest', x)
    for x in sorted(listed - on_disk):
        add('G12', 'manifest entry has no archive on disk', str(x))
    for field, label in (('task_id', 'task_id'), ('sha256', 'sha256')):
        vals = [t.get(field) for t in tasks]
        dup = [k for k, c in Counter(vals).items() if c > 1]
        if dup:
            add('G12', f'duplicate {label} in the manifest', ','.join(map(str, dup[:4])))
    if man.get('task_count') is not None and man['task_count'] != len(tasks):
        add('G12', 'task_count disagrees with the number of manifest entries',
            f'{man["task_count"]} vs {len(tasks)}')

    for t in tasks:
        p = root / str(t.get('package_path'))
        if not p.is_file():
            continue
        h = hashlib.sha256(p.read_bytes()).hexdigest()
        if t.get('sha256') and h != t['sha256']:
            add('G12', 'archive hash disagrees with the manifest', str(t.get('task_id')))
        if t.get('size_bytes') is not None and p.stat().st_size != t['size_bytes']:
            add('G12', 'archive size disagrees with the manifest', str(t.get('task_id')))
        try:
            with zipfile.ZipFile(p) as z:
                rw = {}
                for n in z.namelist():
                    m = re.search(r'evaluations/difficulty/(r[1-4])/.*reward\.txt$', n)
                    if m:
                        rw[m.group(1)] = z.read(n).decode('utf-8', 'replace').strip()
        except Exception:
            continue
        if len(rw) != 4:
            continue
        succ = sum(1 for v in rw.values() if STRICT.match(v))
        band = 'easier' if succ == 3 else ('harder' if succ < 3 else 'out-of-band')
        declared_band = t.get('difficulty')
        if declared_band and band != declared_band:
            add('G11', 'recomputed band disagrees with the manifest',
                f'{t.get("task_id")}: {band} vs {declared_band}')
        pp = str(t.get('package_path') or '')
        if declared_band and f'/{declared_band}/' not in '/' + pp:
            add('G11', 'archive sits outside its stated band folder', f'{t.get("task_id")}: {pp}')
        ev = t.get('trial_evidence') or {}
        if ev.get('successes') is not None and ev['successes'] != succ:
            add('G11', 'recorded successes disagree with the packaged rewards',
                f'{t.get("task_id")}: {ev["successes"]} vs {succ}')
    return out


# --------------------------------------------------------------------------- driver

def run(target: Path, enabled: set[str]) -> dict:
    packages = sorted(p for p in target.rglob('*.zip'))
    if not packages:
        raise SystemExit(f'no .zip archives found under {target}')
    findings: list[dict] = []
    for p in packages:
        findings += check_package(p, enabled)
    findings += check_delivery(target, packages, enabled)
    for f in findings:
        f['severity'] = GATE_BY_ID.get(f['gate'], {}).get('severity', 'WARN')
        f['gate_name'] = GATE_BY_ID.get(f['gate'], {}).get('name', f['gate'])
    per_gate = Counter(f['gate'] for f in findings)
    tasks_per_gate = {g: len({f['task'] for f in findings if f['gate'] == g}) for g in per_gate}
    return dict(
        tool='qc_gates', version=VERSION, target=str(target),
        packages=len(packages),
        findings=findings,
        summary=dict(
            total_findings=len(findings),
            blocking=sum(1 for f in findings if f['severity'] == 'BLOCK'),
            warnings=sum(1 for f in findings if f['severity'] == 'WARN'),
            packages_clean=len(packages) - len({f['task'] for f in findings if f['task'] != '(delivery)'}),
            findings_per_gate=dict(per_gate),
            tasks_per_gate=tasks_per_gate,
        ))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('target', type=Path, nargs='?')
    ap.add_argument('--gate', action='append', default=None, help='run only these gate ids')
    ap.add_argument('--json', type=Path)
    ap.add_argument('--csv', type=Path)
    ap.add_argument('--warn-only', action='store_true', help='always exit 0')
    ap.add_argument('--list', action='store_true', help='print the gate catalogue and exit')
    a = ap.parse_args(argv)

    if a.list:
        for g in GATES:
            print(f"{g['id']}  {g['severity']:5s}  {g['scope']:8s}  {g['name']}")
            print(f"        {g['summary']}")
        return 0
    if a.target is None:
        ap.error('a target path is required')
    if not a.target.exists():
        print(f'no such path: {a.target}', file=sys.stderr)
        return 2
    if tomllib is None:
        print('warning: no TOML reader available; G01 (task.toml), G04 and G05 are degraded',
              file=sys.stderr)

    enabled = set(a.gate) if a.gate else {g['id'] for g in GATES}
    rep = run(a.target, enabled)
    s = rep['summary']

    by_gate = defaultdict(list)
    for f in rep['findings']:
        by_gate[f['gate']].append(f)
    print(f"qc_gates {VERSION} — {rep['packages']} package(s) under {rep['target']}")
    print(f"{s['blocking']} blocking, {s['warnings']} warning, "
          f"{s['packages_clean']}/{rep['packages']} packages clean\n")
    for g in GATES:
        fs = by_gate.get(g['id'], [])
        mark = 'PASS' if not fs else g['severity']
        n = len({f['task'] for f in fs})
        print(f"  {g['id']}  {mark:5s}  {g['name']:38s} {n if fs else ''}")
        for f in fs[:5]:
            print(f"           - {f['task'][:44]:44s} {f['detail']}"
                  + (f"  [{f['evidence']}]" if f['evidence'] else ''))
        if len(fs) > 5:
            print(f"           … and {len(fs)-5} more")

    if a.json:
        a.json.write_text(json.dumps(rep, indent=2))
        print(f'\nwrote {a.json}')
    if a.csv:
        with a.csv.open('w', newline='') as fh:
            w = csv.DictWriter(fh, ['gate', 'gate_name', 'severity', 'task', 'detail', 'evidence'])
            w.writeheader()
            w.writerows(rep['findings'])
        print(f'wrote {a.csv}')

    return 0 if (a.warn_only or s['blocking'] == 0) else 1


if __name__ == '__main__':
    sys.exit(main())
