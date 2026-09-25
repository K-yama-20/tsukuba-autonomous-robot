#!/usr/bin/env python3
"""Apply reviewed USB reconnection changes without overwriting unexpected source edits."""
from pathlib import Path
import os,json
REPO=Path(__file__).resolve().parents[1]

def changes():
    return json.loads((REPO/'patches/imu_reconnect_changes.json').read_text())

def transform(text,pairs):
    for old,new in pairs:
        if text.count(old)!=1:
            raise RuntimeError('Unexpected IMU source anchor: '+old[:90])
        text=text.replace(old,new,1)
    return text

def main():
    workspace=Path(os.environ.get('GOUDA_WORKSPACE',str(Path.home()/'gouda_ws')))
    root=Path(os.environ.get('IMU_DRIVER_ROOT',str(workspace/'src/ADI_IMU_TR_Driver_ROS2')))
    backup=root/'.imu_reconnect_patch_backup';pending=[]
    for rel,pairs in changes().items():
        path=root/rel;current=path.read_text();saved=backup/rel
        if saved.exists():
            expected=transform(saved.read_text(),pairs)
            if current==expected:continue
            if current!=saved.read_text():raise RuntimeError('Refusing to overwrite edited IMU source: '+str(path))
        else:
            expected=transform(current,pairs)
        pending.append((path,saved,current,expected))
    for path,saved,current,expected in pending:
        if not saved.exists():saved.parent.mkdir(parents=True,exist_ok=True);saved.write_text(current)
        path.write_text(expected)
    print('IMU reconnect patch verified/applied; original source retained in',backup)

if __name__=='__main__':main()
