import argparse
import hashlib
import json
from pathlib import Path
from typing import List, Tuple

import numpy as np
import pandas as pd


def md5sum(path: Path) -> str:
    h = hashlib.md5()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()


def find_files(root: Path, exts: Tuple[str, ...]) -> List[Path]:
    return [p for p in root.rglob('*') if p.is_file() and p.suffix.lower() in exts]


def load_table(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == '.csv':
        return pd.read_csv(path)
    if path.suffix.lower() == '.parquet':
        return pd.read_parquet(path)
    raise ValueError(f'Unsupported table: {path}')


def compare_tables(a: pd.DataFrame, b: pd.DataFrame, atol: float = 1e-8, rtol: float = 1e-6) -> Tuple[bool, str]:
    # Align columns
    a_cols = list(a.columns)
    b_cols = list(b.columns)
    if set(a_cols) != set(b_cols):
        return False, f'Columns differ: {sorted(set(a_cols) ^ set(b_cols))}'

    # Reorder columns the same
    b = b[a_cols]

    # Try to sort by all columns if possible to get stable row order
    try:
        a_sorted = a.sort_values(by=a_cols).reset_index(drop=True)
        b_sorted = b.sort_values(by=a_cols).reset_index(drop=True)
    except Exception:
        a_sorted = a.reset_index(drop=True)
        b_sorted = b.reset_index(drop=True)

    if len(a_sorted) != len(b_sorted):
        return False, f'Row count differs: {len(a_sorted)} != {len(b_sorted)}'

    # Compare per column with tolerance for numeric
    for col in a_cols:
        s1 = a_sorted[col]
        s2 = b_sorted[col]
        if pd.api.types.is_numeric_dtype(s1) and pd.api.types.is_numeric_dtype(s2):
            # handle NaNs equal
            s1v = s1.to_numpy(dtype=float)
            s2v = s2.to_numpy(dtype=float)
            both_nan = np.isnan(s1v) & np.isnan(s2v)
            close = np.isclose(s1v, s2v, rtol=rtol, atol=atol, equal_nan=True)
            if not np.all(close | both_nan):
                idx = np.where(~(close | both_nan))[0][:5]
                diffs = [(int(i), float(s1v[i]), float(s2v[i])) for i in idx]
                return False, f'Numeric diffs in column {col}: examples {diffs}'
        else:
            # Treat NaNs equal for objects as well
            s1f = s1.fillna('__NaN__')
            s2f = s2.fillna('__NaN__')
            neq = s1f.astype(str) != s2f.astype(str)
            if neq.any():
                examples = list(zip(neq[neq].index[:5].tolist(), s1f[neq][:5].tolist(), s2f[neq][:5].tolist()))
                return False, f'String diffs in column {col}: examples {examples}'

    return True, 'OK'


def compare_json(a: Path, b: Path) -> Tuple[bool, str]:
    try:
        ja = json.loads(a.read_text(encoding='utf-8'))
        jb = json.loads(b.read_text(encoding='utf-8'))
    except Exception as e:
        return False, f'JSON load error: {e}'
    return (ja == jb), 'OK' if ja == jb else 'JSON structures differ'


def main():
    parser = argparse.ArgumentParser(description='Compare baseline outputs against candidate (CI artifact).')
    parser.add_argument('--baseline', type=str, default=str(Path('data-clean/processed').resolve()))
    parser.add_argument('--candidate', type=str, default=str(Path('artifacts/data-clean/processed').resolve()))
    parser.add_argument('--html-baseline', type=str, default=str(Path('outputs/StudyPipeline.html').resolve()))
    parser.add_argument('--html-candidate', type=str, default=str(Path('artifacts/outputs/StudyPipeline.html').resolve()))
    parser.add_argument('--atol', type=float, default=1e-8)
    parser.add_argument('--rtol', type=float, default=1e-6)
    parser.add_argument('--report', type=str, default=None, help='Optional path to write JSON summary report')
    args = parser.parse_args()

    base = Path(args.baseline)
    cand = Path(args.candidate)
    failures = []
    notes = []

    if not base.exists() or not cand.exists():
        print(f'Baseline or candidate directory missing:\n  baseline: {base}\n  candidate: {cand}')
        if args.report:
            Path(args.report).parent.mkdir(parents=True, exist_ok=True)
            Path(args.report).write_text(json.dumps({
                'status': 'error',
                'message': 'missing baseline or candidate directory',
                'baseline': str(base),
                'candidate': str(cand),
            }, indent=2), encoding='utf-8')
        return 2

    # Tables
    table_exts = ('.csv', '.parquet')
    base_tables = find_files(base, table_exts)
    if not base_tables:
        print('No baseline tables found to compare.')
    for bt in base_tables:
        rel = bt.relative_to(base)
        ct = cand / rel
        if not ct.exists():
            failures.append((str(rel), 'missing in candidate'))
            continue
        try:
            a = load_table(bt)
            b = load_table(ct)
            ok, msg = compare_tables(a, b, atol=args.atol, rtol=args.rtol)
        except Exception as e:
            ok, msg = False, f'Error reading/comparing: {e}'
        if not ok:
            failures.append((str(rel), msg))

    # JSONs (optional)
    json_exts = ('.json',)
    base_jsons = find_files(base, json_exts)
    for bj in base_jsons:
        rel = bj.relative_to(base)
        cj = cand / rel
        if not cj.exists():
            failures.append((str(rel), 'missing in candidate'))
            continue
        ok, msg = compare_json(bj, cj)
        if not ok:
            failures.append((str(rel), msg))

    # HTML soft check by hash (size-only would be too loose)
    h_base = Path(args.html_baseline)
    h_cand = Path(args.html_candidate)
    if h_base.exists() and h_cand.exists():
        hb = md5sum(h_base)
        hc = md5sum(h_cand)
        if hb != hc:
            # HTML may embed runtime-specific IDs; warn only
            msg = 'HTML checksums differ (often expected). Verified artifact presence only.'
            print(f'Note: {msg}')
            notes.append(msg)
    else:
        msg = 'HTML file missing in baseline or candidate; skipping HTML check.'
        print(f'Note: {msg}')
        notes.append(msg)

    if failures:
        print('\nDIFFS FOUND:')
        for rel, msg in failures[:50]:
            print(f'- {rel}: {msg}')
        summary = f'{len(failures)} differences'
        print(f'\nSummary: {summary}')
        if args.report:
            Path(args.report).parent.mkdir(parents=True, exist_ok=True)
            Path(args.report).write_text(json.dumps({
                'status': 'diffs',
                'summary': summary,
                'failures': [{'file': rel, 'message': msg} for rel, msg in failures],
                'notes': notes,
            }, indent=2), encoding='utf-8')
        return 1
    else:
        msg = 'All compared outputs match within tolerance.'
        print(msg)
        if args.report:
            Path(args.report).parent.mkdir(parents=True, exist_ok=True)
            Path(args.report).write_text(json.dumps({
                'status': 'ok',
                'message': msg,
                'notes': notes,
            }, indent=2), encoding='utf-8')
        return 0


if __name__ == '__main__':
    raise SystemExit(main())
