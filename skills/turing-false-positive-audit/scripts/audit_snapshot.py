"""Read-only, task-keyed screening of the existing Harbor JSON snapshots (stdlib only)."""
import argparse
import csv
import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path


def require(condition, message):
    if not condition:
        raise ValueError(message)


def keyed(rows, key):
    result = {row[key]: row for row in rows}
    require(len(result) == len(rows) and all(result), f"Duplicate or empty {key}")
    return result


def ai_flags(text):
    parts = text.split('; ')
    found = []
    for i, part in enumerate(parts):
        match = re.fullmatch(r'AI check failures \((\d+)\): (.+)', part)
        if not match:
            continue
        require(not found, 'Repeated AI failure section')
        found = [match[2]]
        for following in parts[i + 1:]:
            if not re.match(r'^Layer \d+ ', following):
                break
            found.append(following)
        require(len(found) == int(match[1]), 'AI failure count does not match areas')
    require('AI check failures' not in text or found, 'Unknown AI failure format')
    return found


def positive_without_failure(result):
    """Fail closed: only the snapshot's known positive/NA summaries are accepted."""
    positive = False
    for line in result.splitlines():
        if line == 'Not applicable':
            continue
        if re.fullmatch(r'(Task-source|Cross-trial) check: (PASS|NOT APPLICABLE)', line):
            positive |= line.endswith(': PASS')
            continue
        if line.startswith('Trial analyses: '):
            for item in line.removeprefix('Trial analyses: ').split(' · '):
                match = re.fullmatch(r'([1-9]\d*) (PASS|NOT APPLICABLE)', item)
                if not match:
                    return False
                positive |= match[2] == 'PASS'
            continue
        return False
    return positive


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input-dir', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    inputs = {}

    def read(name):
        path = args.input_dir / name
        data = path.read_bytes()
        inputs[name] = hashlib.sha256(data).hexdigest()
        return json.loads(data.decode('utf-8-sig'))

    feedback = keyed(read('feedback.json'), 'task')
    snapshot = read('new-sheet-index-snapshot.json')
    columns = [str(c).strip() for c in snapshot['values'][0]]
    required = {'Task name', 'Trainer', 'Review on GLM battery Runs', 'Review priority', 'Automatic review flags'}
    require(required <= set(columns), f'Missing Index columns: {required - set(columns)}')
    require(len(set(columns)) == len(columns), 'Duplicate Index headers')
    index_rows = []
    by_row = {}
    for row_number, values in enumerate(snapshot['values'][1:], 2):
        if not values or not values[0]:
            continue
        row = dict(zip(columns, values + [''] * (len(columns) - len(values))))
        row['row'] = row_number
        index_rows.append(row)
        by_row[row_number] = row['Task name']
    index = keyed(index_rows, 'Task name')
    require(feedback.keys() <= index.keys(), 'Some detail tasks are absent from Index')
    candidates, screened, conflicts, controls = [], [], [], []
    for task, detail in feedback.items():
        idx = index[task]
        areas = keyed(detail['areas'], 'area')
        flags = ai_flags(idx['Automatic review flags'])
        require(set(flags) <= areas.keys(), f'Unknown AI area for {task}')
        same_flags = idx['Automatic review flags'] == detail['index_flags']
        if not same_flags:
            conflicts.append(task)
        task_candidates = []
        for area in flags:
            item = areas[area]
            positive = positive_without_failure(item['ai_result'])
            record = {'task': task, 'trainer_as_sheet': idx['Trainer'],
                      'glm_display_as_sheet': idx['Review on GLM battery Runs'],
                      'area': area, 'index_row': idx['row'], 'detail_row': item['row'],
                      'detail_ai_result': item['ai_result'],
                      'programmatic_result': item['programmatic_result'],
                      'original_flags_preserved': idx['Automatic review flags'],
                      'detail_source': f"{detail['sheet']}!E{item['row']}",
                      'detail_sheet_id': detail['sheet_id'],
                      'classification': 'reporting_false_alarm', 'confidence': 'Medium',
                      'confidence_limit': 'Independent raw-cell check required before High; snapshot scope only.',
                      'explanation': 'Index says this AI area failed, but its same-task detailed AI result has positive PASS evidence and no failure.',
                      'remaining_issues': 'Other flags remain. This does not establish task acceptance.'}
            if positive and same_flags:
                candidates.append(record)
                task_candidates.append(area)
            elif len(controls) < 12:
                controls.append({'task': task, 'area': area, 'result': item['ai_result'],
                                 'candidate': False, 'reason': 'Summary is not positive-only, or snapshots disagree.'})
        screened.append({'task': task, 'trainer_as_sheet': idx['Trainer'],
                         'priority': idx['Review priority'], 'ai_flags_checked': flags,
                         'reporting_candidates': task_candidates, 'whole_task_verdict': 'not_adjudicated',
                         'original_flags_preserved': idx['Automatic review flags']})

    headers = []
    raw_path = args.input_dir / 'new-sheet-header-cell-evidence.json'
    if raw_path.exists():
        raw = read(raw_path.name)
        batches = raw if isinstance(raw, list) else [raw]
        sheet_tasks = {d['sheet_id']: t for t, d in feedback.items()}
        seen = set()
        for batch in batches:
            require(batch['spreadsheetId'] == snapshot['spreadsheet_id'], 'Header/Index spreadsheet mismatch')
            for sheet in batch['sheets']:
                task = sheet_tasks.get(sheet['properties']['sheetId'])
                if task is None:
                    continue
                for block in sheet.get('data', []):
                    for r, row in enumerate(block.get('rowData', []), block.get('startRow', 0) + 1):
                        for c, cell in enumerate(row.get('values', []), block.get('startColumn', 0) + 1):
                            if (r, c) not in {(3, 2), (3, 5), (4, 2), (5, 2)}:
                                continue
                            formula = cell.get('userEnteredValue', {}).get('formulaValue', '')
                            require((task, r, c) not in seen, 'Duplicate header cell snapshot')
                            seen.add((task, r, c))
                            refs = sorted(set(int(n) for n in re.findall(r"(?:'Index'|Index)!\$?[A-Z]+\$?(\d+)", formula)))
                            require(refs and all(n in by_row for n in refs), f'Unresolved header formula: {task} {r},{c}')
                            headers.append({'task': task, 'cell': f'{chr(64+c)}{r}', 'formula': formula,
                                            'referenced_tasks': [by_row[n] for n in refs],
                                            'wrong_task': any(by_row[n] != task for n in refs)})
        require(len(seen) == 4 * len(feedback), 'Incomplete four-cell header evidence')
        if (args.input_dir / 'header-reference-audit.json').exists():
            prior = read('header-reference-audit.json')['tasks']
            expected = {(x['task'], m['cell']): m['wrong_task'] for x in prior for m in x['mappings']}
            require(expected == {(x['task'], x['cell']): x['wrong_task'] for x in headers}, 'Raw formula check disagrees with earlier mapping')

    comparisons = []
    pod_path = 'pod-reconciliation/pod-normalized.json'
    history_path = 'pod-reconciliation/historical-normalized-conclusions.json'
    pod = keyed(read(pod_path), 'task') if (args.input_dir / pod_path).exists() else {}
    history = keyed(read(history_path)['tasks'], 'task') if (args.input_dir / history_path).exists() else {}
    for task in sorted(index.keys() | pod.keys() | history.keys()):
        p, h = pod.get(task, {}), history.get(task, {})
        comparisons.append({'task': task, 'current_index': task in index, 'high_detail_screened': task in feedback,
                            'pod_status_as_recorded': p.get('status', ''),
                            'pod_false_positive_claim': p.get('false_positive', ''),
                            'historical_claim': h.get('historical_client_specific_claim', ''),
                            'historical_verdict_as_recorded': h.get('historical_verdict_raw', ''),
                            'claim_validation': 'Reviewer labels are not independently verified verdicts.'})
    summary = {'generated_at_ist': datetime.now(timezone(timedelta(hours=5, minutes=30))).isoformat(),
               'index_snapshot_utc': snapshot.get('snapshot_utc'),
               'current_tasks': len(index), 'detail_tasks_screened': len(feedback),
               'ai_claims_screened': sum(len(r['ai_flags_checked']) for r in screened),
               'reporting_candidates': len(candidates), 'snapshot_flag_conflicts': conflicts,
               'header_cells_checked': len(headers), 'wrong_header_cells': sum(x['wrong_task'] for x in headers),
               'wrong_header_tasks': len({x['task'] for x in headers if x['wrong_task']}),
               'pod_tasks': len(pod), 'pod_fp_labelled': sum('False Positive' in p.get('status', '') for p in pod.values()),
               'historical_tasks': len(history), 'historical_exact_current_overlaps': len(history.keys() & index.keys()),
               'unique_tasks_across_sources': len(comparisons),
               'new_runtime_runs': 0, 'external_writes': False,
               'limit': 'Frozen-snapshot screening, not task-quality or acceptance adjudication.'}
    # Runnable checks use only supplied real data, including negative/NA/mixed controls.
    require(all(positive_without_failure(c['detail_ai_result']) for c in candidates), 'Invalid candidate')
    require(all(not positive_without_failure(a['ai_result']) for d in feedback.values() for a in d['areas']
                if re.search(r'\b(FAIL|ERROR)\b', a['ai_result'])), 'A failing summary was accepted')
    require(all(not positive_without_failure(a['ai_result']) for d in feedback.values() for a in d['areas']
                if 'PASS' not in a['ai_result']), 'A result without PASS was accepted')
    result = {'summary': summary, 'input_sha256': inputs, 'reporting_candidates': candidates,
              'header_checks': headers, 'real_negative_controls': controls,
              'screened_tasks': screened, 'cross_sheet_claims': comparisons}
    args.output_dir.mkdir(parents=True, exist_ok=True)
    destinations = [args.output_dir / name for name in ('screening.json', 'reporting-candidates.csv')]
    require(not any(p.exists() for p in destinations), 'Use a new output directory; reports will not be overwritten')
    with destinations[0].open('x', encoding='utf-8') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
    require(json.loads(destinations[0].read_text(encoding='utf-8')) == result, 'JSON readback mismatch')
    if candidates:
        with destinations[1].open('x', encoding='utf-8-sig', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(candidates[0]))
            writer.writeheader()
            for record in candidates:
                writer.writerow({k: "'" + v if isinstance(v, str) and v.startswith(('=', '+', '-', '@')) else v
                                 for k, v in record.items()})
    print(json.dumps(summary, ensure_ascii=True, indent=2))


if __name__ == '__main__':
    main()
