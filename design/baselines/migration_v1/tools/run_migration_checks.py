"""Persist the actual validator/test commands, outputs and artifact hashes."""
import hashlib, json, os, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
REPORT=ROOT/'design/reports'
def main():
    commands=[[sys.executable,'design/tools/validate_model.py'],[sys.executable,'-m','unittest','discover','-s','design/rules','-p','test_*.py','-v']]
    runs=[]
    for command,filename in zip(commands,['migration_validator.txt','migration_tests.txt']):
        r=subprocess.run(command,cwd=ROOT,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        (REPORT/filename).write_text(r.stdout)
        runs.append({'command':command,'cwd':str(ROOT),'exit_code':r.returncode,'output':str((REPORT/filename).relative_to(ROOT))})
        print(filename, 'PASS' if r.returncode==0 else 'FAIL')
    paths=[ROOT/'design/model.yaml',ROOT/'design/schema.json',ROOT/'design/migration_manifest.json']+sorted((ROOT/'design/tools').glob('*.py'))+sorted((ROOT/'design/rules').rglob('*.py'))+sorted((ROOT/'design/rules/fixtures').glob('*'))
    report={'run_time_utc':datetime.now(timezone.utc).isoformat(),'PYTHONPATH':os.environ.get('PYTHONPATH',''),'runs':runs,'sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},'scope':'移行と検査器のみ。ロボット/ROS/実車試験は実行していない。'}
    (REPORT/'migration_check_run.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    return int(any(r['exit_code'] for r in runs))
if __name__=='__main__': sys.exit(main())
