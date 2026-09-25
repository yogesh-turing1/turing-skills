---
name: internal-delivery-report
description: Build the internal edition of a Harbor/Shannon delivery report — the client report plus everything held out of it: the real four-status audit matrix, every change made to the source archives, the provenance behind each, hygiene before and after, and a per-package change log. Use when asked for an internal, engineering, or full-disclosure version of a delivery report, or when a client report needs its repackaging work put back on the record.
---

# Internal delivery report

The client edition of a delivery report states results. The internal edition states results **and
the work that produced them**: what was changed in each archive, on what basis, and what the
evidence says against it.

One command builds it from the delivery's own records. Nothing is typed in by hand.

```bash
python3 build_internal_report.py \
    --mods       MODIFICATIONS.json \
    --manifest   <delivery>/manifest.json \
    --inventory  delivery_manifest.csv \
    --audit      audit-14-factor-findings.csv \
    --out        Harbor-Delivery-Report-INTERNAL \
    --pdf
```

Exit code is non-zero if any page overflows the printed box. Chrome is required — it measures
layout and writes the PDF. Fonts ship in `fonts/`.

---

## What goes in

| Input | What it supplies |
|---|---|
| `MODIFICATIONS.json` | Every change class, its per-package map, and the basis text |

**Only a known change class is rendered.** A key the generator does not recognise is dropped
without a word, so a modification filed under a new name silently disappears from the record —
the one thing this report exists to prevent. The recognised keys are:

`_os_artefacts` · `_image_pinning` · `_image_digest` · `_dataset_declaration` ·
`_stale_qc_claims` · `_verifier_justification` · `_readme_generation` · `_redaction` ·
`_folder_rename` · `_binary_reward`

Adding a class means adding it to `TITLES`, `ORDER` and `ABBR` together. Each entry is a dict of
meta fields (`fix`, `BASIS`, `PROVENANCE`, `CORROBORATION`, `COUNTER_EVIDENCE`,
`CONTENT_UNCHANGED`, `KNOWN_RESIDUAL`, `scope`, `result`) plus `per_task`.

| `manifest.json` | Package count, difficulty, trial evidence; the sanitisation record if the pass kept one there |
| `delivery_manifest.csv` | The 12-column inventory: name, family, execution type, domain, gym, GLM bucket, hashes, sizes |
| `audit-14-factor-findings.csv` | One row per package per factor with `PASS` / `FLAG` / `INFO` / `NA` |

Optional:

- `--hygiene rows.json` — `[[pattern, before, after, verdict], …]`. **Pass this whenever a sweep
  found something it deliberately left in place.** Derived mode can only report what the
  modification record accounts for, so a placeholder that was correctly not redacted, or a
  credential-shaped false positive, will be missing unless you supply it. The report says so
  rather than implying the sweep found nothing.
- `--delta-note "…"` — reconcile a headline that differs from the client edition. Use it, do not
  quietly change the number.
- `--cover-lede`, `--source-line` — override the standfirst and page footer.

---

## What comes out

```
Cover                     the four counts that matter, marked INTERNAL
01 Executive view         dispositions explained, changes at a glance
02 Audit matrix           Pass / Flagged / Info / N-A, per factor, with real denominators
03 Portfolio composition  domains, GLM battery, connector gyms
04 Change control         every deviation from source, by class, with scope
05 Provenance             basis, corroboration, counter-evidence, residuals, substitutions
06 Hygiene                before and after, and what was left alone
07 Per-package change log which package got which change
08 Package inventory      the full delivery
```

---

## The two things the client edition gets wrong, and why this exists

**The audit matrix is not all-pass.** A client report that prints `60 / 0 / 0 / 0` on every row
is claiming all fourteen factors apply to all sixty packages. They do not. Connectors applies to
the connector subset. LLM judge consistency applies to the judged subset. Deliverables and
Verifier fairness apply to packages that ship a verifier specification. Reward hacking is
frequently mostly `Info` — a batch-wide authoring convention, recorded rather than clean.

Printing `N/N` against a factor that applies to twelve packages overstates coverage, not results.
This edition prints the real denominators, and `Info` and `N/A` alongside `Pass`.

**Nothing narrates the repackaging.** Sections 04 to 07 exist for that, and they are the reason
to build this at all. Omission is a legitimate choice for a client report; it is not a legitimate
choice for the record.

---

## Rules the generator holds to

**Before means the archive as pulled from the accepted source. After means the same archive in
the delivered package.** Both come from the pass's own records. Do not put a later re-audit in
the after column — that is a different measurement answering a different question, and mixing
them makes the table meaningless.

**Every figure is read, never carried over.** Package counts, occurrence counts, hashes and
factor tallies come from the four inputs. If a number cannot be derived, it does not appear.

**Occurrence counts are shown only where every source recorded them.** A partial total
understates the batch and is worse than no total. The generator emits a dash instead.

**A headline that disagrees with the client edition gets a note, not a silent correction.** The
delivered figure was usually right when it was written; what changed is the timing.

---

## Layout: measure, never estimate

This is the part that took the longest to get right, and every rule below was earned by
shipping the wrong thing first.

**Pack pages by measured height.** The generator renders content blocks in headless Chrome and
reads their pixel heights before deciding what goes on a page. An earlier version estimated from
character counts with fudge factors for lists and tables; it was off by about a third, which put
one change class on each page and left the rest of every sheet blank.

**Verify row counts by rendering, not by arithmetic.** `fit_rows` binary-searches over an actual
render. Estimating rows from measured row heights gave 26 inventory rows where only 21 fit, and
the pages overflowed the box by 172px — which clips silently in print and looks fine on screen.

**Let a block split rather than break the page early.** When a change class will not fit whole,
its reasoning stays on the current page and its package list carries to the next under a
*continued* label. Without this, one oversized block strands half a sheet.

**The footer is a flex child with `margin-top:auto`, never absolutely positioned.** Absolute
positioning means any page whose content runs long writes straight through the footer. As a flex
child it cannot be overlapped and still sits at the bottom.

**`table-layout: fixed`, with a width on every column.** And never put `white-space: nowrap` on a
cell that holds a sentence: one nowrap scope cell starved the neighbouring column so badly it
wrapped every three words.

**Pages are centred sheets on screen and the page box in print.** `@media print` strips the
backdrop, shadow and margin so the PDF is unaffected by the screen presentation.

**Audit before shipping.** The generator re-opens its own output, measures every page, and exits
non-zero if any exceeds the box. Do not skip it — overflow is invisible in the HTML and only
shows up as clipped content in the PDF.

**Fit to a slightly shorter box than the page.** Chrome lays a page out fractionally taller when
printing than when rendering to screen, because line boxes round differently. A page measured at
exactly 1056px on screen passes the audit and still loses its last row and its footer in the PDF.
Fitting targets `PAGE_PX - PRINT_SLACK` (34px, override with `HARBOR_PRINT_SLACK`). The number is
not a guess to be tuned by eye: prove it by extracting text from the finished PDF and checking
that every page still carries the footer and every package name still appears.

**A package list can itself be taller than the page.** A change class touching a few hundred
packages does not fit whole and does not fit as one carried-over block either. The list is split
across as many continuation blocks as it needs, each sized by render. Before this, the packer
could only move it whole, and it overflowed silently.

---

## Checklist

- [ ] All four inputs come from the same delivery
- [ ] `--hygiene` supplied whenever the sweep left something in place on purpose
- [ ] `--delta-note` supplied wherever a headline differs from the client edition
- [ ] Exit code 0: no page overflows the printed box
- [ ] Audit matrix shows real denominators, not `N/N` on every row
- [ ] Per-package log present, and its names match the modification record
- [ ] Marked `INTERNAL` on the cover and in the footer of every page
- [ ] Not sent to the client
