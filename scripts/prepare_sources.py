"""Fetch pinned sources without replacing existing checkouts or local changes."""
import shutil
import subprocess
import sys
from pathlib import Path
import yaml


def run(*args):
    return subprocess.check_output(args, text=True).strip()


def main():
    installer_repo, ws = map(lambda p: Path(p).expanduser().resolve(), sys.argv[1:])
    source_root = ws / 'src'
    source_root.mkdir(parents=True, exist_ok=True)
    canonical = source_root / 'tsukuba-autonomous-robot'
    replace_alias = False
    if canonical.is_symlink():
        if canonical.resolve() != installer_repo:
            raise SystemExit(f'{canonical} is a symlink to a different or missing checkout; inspect it before changing it.')
        if (installer_repo/'.git').is_file():
            raise SystemExit('Setup source is a Git worktree. Run setup from a regular checkout or archive; refusing to copy its .git pointer.')
        replace_alias = True
    if canonical.exists() and not replace_alias:
        if not canonical.is_dir():
            raise SystemExit(f'{canonical} exists and is not a directory; preserve it and choose GOUDA_WORKSPACE.')
        repo = canonical.resolve()
        if repo != installer_repo:
            raise SystemExit(f'{canonical} is an existing canonical checkout different from the setup source; run setup from that checkout.')
    else:
        git_metadata = installer_repo/'.git'
        if git_metadata.is_file():
            raise SystemExit('Setup source is a Git worktree. Run setup from a regular checkout or archive; refusing to copy its .git pointer.')
        staged = source_root/'.tsukuba-autonomous-robot.installing'
        if staged.exists():
            raise SystemExit(f'{staged} already exists; inspect it before retrying setup.')
        shutil.copytree(installer_repo, staged, symlinks=True)
        if canonical.is_symlink():
            canonical.unlink()
        staged.rename(canonical)
        repo = canonical.resolve()
    specs = yaml.safe_load((repo / 'third_party/external.repos').read_text())['repositories']
    for name, spec in specs.items():
        target = source_root / name
        if not target.exists():
            subprocess.run(['git', 'clone', '--no-checkout', spec['url'], str(target)], check=True)
            subprocess.run(['git', '-C', str(target), 'checkout', '--detach', spec['version']], check=True)
        actual = run('git', '-C', str(target), 'rev-parse', 'HEAD')
        if actual != spec['version']:
            raise SystemExit(f'{target}: expected {spec["version"]}, found {actual}; not replacing existing source.')
        subprocess.run(['git', '-C', str(target), 'submodule', 'update', '--init', '--recursive'], check=True)
    print(repo)




if __name__ == '__main__':
    main()
