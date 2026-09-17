---
name: google-sheets-task-links
description: Recover, reconcile, validate, and export exact original-task, modified-task, and source-row links from Google Sheets cells, including Drive smart chips whose URLs are not visible in plain cell values.
---

# Google Sheets Task Links

Use this procedure when task URLs appear as smart chips or generic labels such as `OPEN`, or when exact source-row links must be reconstructed without guessing.

## Read The Cells

Use the Google Drive `get_spreadsheet_cells` action rather than a plain range-value read. Request a bounded range and these fields:

```text
formattedValue,effectiveValue,userEnteredValue,hyperlink,chipRuns
```

Include the task identifier, source label, source row, source link, original-task link, and modified-task link columns in the range.

## Extract Each URL

For every link cell, use this precedence:

1. `cell.hyperlink`
2. The first non-empty `cell.chipRuns[].chip.richLinkProperties.uri`
3. The first URL argument in `cell.userEnteredValue.formulaValue` when it contains `HYPERLINK(...)`
4. `NOT AVAILABLE`; never infer a Drive URL from a task name

The displayed value is not authoritative. Values such as `OPEN`, a file name, or a chip label can conceal the actual URL.

```javascript
function cellUrl(cell) {
  if (cell?.hyperlink) return cell.hyperlink;

  for (const run of cell?.chipRuns ?? []) {
    const uri = run?.chip?.richLinkProperties?.uri;
    if (uri) return uri;
  }

  const formula = cell?.userEnteredValue?.formulaValue ?? "";
  const match = formula.match(/HYPERLINK\("([^"]+)"/i);
  return match?.[1] ?? "NOT AVAILABLE";
}
```

## Resolve The Exact Source Row

Prefer the existing source-row hyperlink. If it is absent but a reconciled source row is available, construct the link only from verified spreadsheet metadata:

```text
https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/edit#gid={TAB_GID}&range=A{ROW}:AJ{ROW}
```

Do not construct a row link until all three values are verified:

- The source label identifies the intended workbook.
- The row's task identifier exactly matches the requested or canonical task identifier.
- The tab GID belongs to the authoritative task tab.

For the Tasks Operations workflow, the authoritative sources are:

| Source | Spreadsheet ID | Tasks GID |
|---|---|---|
| NC | `1mmzuhpMsk9WkRgzs1NEdAl6sTWpAcrmlgSMlhzrfKqw` | `2018207718` |
| SY | `14U1C_u-52MxxKqlifDH09XVkxw9aGHK1IscU7Wkp0_c` | `1136182622` |
| IZ | `1ab1-AtlTcStL_-2-uPMs9IwpMMBvpLXwy_TVTg6WVDo` | `2136118787` |

Do not use an archived or historical source unless the user explicitly requests it.

## Reconcile

Match in this order:

1. Exact canonical Task ID.
2. Exact normalized full task name.
3. Requested short task prefix only when it resolves to one row.

If a prefix returns multiple rows, report the ambiguity. Do not choose the first match.

Preserve these fields in the result when available:

```text
Requested Task
Trainer
Pod Lead
EM
Canonical Task ID
Full Task Name
Source
Source Row
Source Row Link
Original Task Link
Modified Task Link
Match Status
```

## Validate Before Export

- Reconcile the exported row count to the requested task count.
- Count missing original and modified links separately.
- Confirm every source-row URL uses the expected source spreadsheet ID and GID.
- Confirm the row range in each source URL equals the recorded source row.
- Spot-check at least one linked row from every represented source.
- Explicitly list ambiguous, unmatched, and missing-link tasks.

Do not report unavailable URLs as recovered links.

## Text Export

Use tab-separated text so URLs remain intact and the file can be pasted into Sheets:

```text
Task\tOriginal Task Link\tModified Task Link
```

Add a short summary with requested row count, available-link counts, and missing task identifiers. Label absent URLs `NOT AVAILABLE`.
