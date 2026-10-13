"""Run every check with the project virtual environment and persist the record.

Order: input integrity → fidelity validator → design-consistency checker →
unit tests (validator + design rules). Exit code is non-zero if any step fails.
Fidelity and design consistency are reported separately and never merged.
"""
import hashlib, json, os, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
DESIGN = ROOT / 'design'
REPORT = DESIGN / 'reports'


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()


def input_integrity():
    manifest = json.loads((DESIGN / 'migration_manifest.json').read_text())
    snapshot = json.loads((DESIGN / 'baselines/migration_v1/snapshot.json').read_text())
    rows = []; ok = True
    for path, expected in manifest['protected_files'].items():
        p = ROOT / path; actual = sha(p) if p.exists() else None
        status = '一致' if actual == expected else ('intent新版（AR-002として記録・検証）' if path == 'design/intent.md' else '不一致')
        if status == '不一致': ok = False
        rows.append({'path': path, 'baseline_sha256': expected, 'current_sha256': actual, 'status': status})
    for rel, expected in snapshot.items():
        p = DESIGN / 'baselines/migration_v1' / Path(rel).relative_to('design'); actual = sha(p) if p.exists() else None
        if actual != expected: ok = False
        rows.append({'path': 'design/baselines/migration_v1/' + str(Path(rel).relative_to('design')), 'baseline_sha256': expected, 'current_sha256': actual, 'status': '一致' if actual == expected else '不一致'})
    report = {'result': '合格' if ok else '違反', 'note': '原資料・抽出結果・初回移行baselineは変更されていないこと。intent.md は人が編集した新版で、差分は authority_revisions で機械検証する。', 'files': rows}
    (REPORT / 'input_integrity.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print('input_integrity.json', 'PASS' if ok else 'FAIL')
    return 0 if ok else 1


def main():
    REPORT.mkdir(parents=True, exist_ok=True)
    runs = [{'step': 'input integrity', 'exit_code': input_integrity(), 'output': 'design/reports/input_integrity.json'}]
    commands = [
        ('generate params', [sys.executable, 'design/tools/generate_params.py'], 'generate_params.txt'),
        ('intent identity', [sys.executable, 'design/tools/check_intent_identity.py'], 'intent_identity.txt'),
        ('fidelity validator', [sys.executable, 'design/tools/validate_model.py'], 'migration_validator.txt'),
        ('design consistency', [sys.executable, 'design/tools/check_design.py'], 'design_check.txt'),
        ('unit tests', [sys.executable, '-m', 'unittest', 'discover', '-s', 'design/rules', '-p', 'test_*.py', '-v'], 'migration_tests.txt'),
    ]
    for step, command, filename in commands:
        r = subprocess.run(command, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        (REPORT / filename).write_text(r.stdout)
        runs.append({'step': step, 'command': command, 'cwd': str(ROOT), 'exit_code': r.returncode, 'output': str((REPORT / filename).relative_to(ROOT))})
        print(filename, 'PASS' if r.returncode == 0 else 'FAIL')
    paths = [DESIGN / 'model.yaml', DESIGN / 'schema.json', DESIGN / 'migration_manifest.json', DESIGN / 'intent.md'] + sorted((DESIGN / 'tools').glob('*.py')) + sorted((DESIGN / 'rules').rglob('*.py')) + sorted((DESIGN / 'rules/fixtures').glob('*')) + sorted((DESIGN / 'revisions').glob('*.yaml'))
    report = {'run_time_utc': datetime.now(timezone.utc).isoformat(), 'python': sys.executable, 'PYTHONPATH': os.environ.get('PYTHONPATH', ''), 'runs': runs,
              'sha256': {str(p.relative_to(ROOT)): sha(p) for p in paths}, 'scope': '移行忠実性・設計整合性・検査器試験のみ。ROS動作・実車試験は実行していない。'}
    (REPORT / 'check_run.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    return int(any(r['exit_code'] for r in runs))


if __name__ == '__main__': sys.exit(main())
