---
name: harbor-delivery-report
description: Build the Harbor FINALIZATION DELIVERY PDF - the dark-cover A4 delivery and verification report covering a batch of QC'd task packages, with audit matrix, portfolio composition, evidence, factor pass rate and the complete package inventory. Use when asked for a Harbor report, a finalization delivery or closeout report for a batch, or to regenerate one for a new batch in the same design.
---

# Harbor delivery report

One PDF that lets a client assess a delivery: what was shipped, how the QC factors landed, the
portfolio mix, the package evidence, and every archive listed by name, hash, GLM result and size.

**The design is fixed.** Every batch renders identically; only the numbers change. Do not redesign
it, do not add sections, do not rename the ones that exist.

---

## Authority

The batch's own **delivery manifest** is the data authority. Recalculate every batch-level figure
from it — never carry a count, hash, size or date over from a previous report.

Treat `x`, `unnamed`, or an unspecified domain on a connector task as **Connector** in client-visible
tables.

Client status columns are **Pass**, **Flagged**, **Failed** and **Not Applicable** only. There is no
`Info` status. Do not write a hygiene, modification, provenance or security claim the batch's own
record does not supply.

---

## Design tokens

```
navy      #102c35     cover ground, table headers, rules
teal      #137c75     accent, bar fill, section labels, ring
lime      #c3e356     cover accent, hero number, cover labels
paper     #f9faf8     interior ground
panel     #eef4f0     callouts and the disposition band
bar track #d7e1dd     unfilled bar
ink       #1d2b30     body      mute #5d6f72  secondary
```

Segoe UI throughout — Light for display numbers and headings, Semibold/Bold for labels — with
Consolas for hashes and page numbers. A4 portrait, 15mm top / 16mm sides / 12mm bottom.

Every page carries the same header (`H A R B O R` left, section right, hairline rule under) and the
same footer (`Sources: … | <date>` left, `NN / NN` right in mono).

---

## Structure

Seven fixed sections, then the inventory:

```
01  cover                    Every package. / The full picture.
                             lime task count beside the teal outcomes ring,
                             then checks passed / flagged-failed / not applicable
02  EXECUTIVE VIEW           Delivery at a glance
03  AUDIT MATRIX             Fourteen factors. N outcomes.
04  PORTFOLIO COMPOSITION    The delivery, by shape.
05  EVIDENCE CHECKED         The evidence behind each package.
06  DELIVERY PROFILE         What the QC record says.
07  FACTOR PASS RATE         Every applicable check passed.
08+ PACKAGE INVENTORY        The complete delivery.
```

The fourteen factors, in this order and wording: Package consistency, Clarity and scope, Realism and
leakage, Difficulty, Solvability, Stability, Oracle, Environment and files, Connectors, Deliverables,
Verifier fairness, LLM judge consistency, Reward hacking, Cross-trial calibration.

Outcomes are `task_count × 14`. Connectors is scored against the connector count on the pass-rate
page; every other factor against all N.

---

## The inventory scales, the layout does not

**20 rows per page.** That row height — task name with its SHA-256 prefix beneath in mono, type and
domain stacked, GLM result, MB — is what makes the page readable, and it is not negotiable to fit a
bigger batch onto three pages.

So the page count is a function of the batch:

```
inventory pages = ceil(task_count / 20)
total pages     = 7 + inventory pages
```

A 60-task batch is 3 inventory pages and 10 total. A 232-task batch is 12 and 19. Header reads
`07 / PACKAGE INVENTORY k OF n`, and the footer's page total follows. **Do not compress rows to hold
a ten-page count** — the fixed thing is the design, not the length.

Sort by package name. Every task appears exactly once.

---

## Building it

Author HTML with `@page { size:A4; margin:0 }` and one `.page` div per page at `210mm × 297mm`, then
render with headless Chrome:

```bash
chrome --headless --disable-gpu --no-pdf-header-footer \
  --virtual-time-budget=20000 --print-to-pdf=OUT.pdf "file://IN.html"
```

Set `-webkit-print-color-adjust: exact` or the navy cover and every filled bar print white.

---

## QA before handing it over

1. **Every task name and every SHA prefix** appears in the extracted PDF text. Compare against the
   manifest, whitespace-stripped — letter-spaced labels extract with gaps.
2. **Margin scan every page.** No text block past the page box on any side. A row overflowing the
   last inventory page is the usual failure and it is invisible in the HTML.
3. **Totals reconcile**: outcomes = N × 14; the disposition figures sum to it; the cover, executive
   view and audit matrix all state the same N.
4. **Render and look** at the cover, a chart page and one inventory page. Rebuild after any fix and
   inspect the new file, never a cached preview.
5. **Leak scan** the text for bucket URIs, host paths, VM addresses, image digests, internal tooling
   names and any remediation or modification language. None of it belongs in a client report.

---

## What the report may and may not claim

Stating the delivery is clean is legitimate when the batch's record supports it. Omitting the
finalization fixes is equally legitimate — a client report need not narrate internal process.

What is **not** acceptable is asserting the opposite: that nothing was found, or that packages are
untouched as authored, when archives were modified.

And be precise about whose verdict it is. When the fourteen-factor result comes from the upstream QC
record carried in the manifest, the report is reporting that verdict — not an audit performed during
this delivery. If someone asks whether the fourteen factors were re-audited for this batch, the
honest answer must still be available.
