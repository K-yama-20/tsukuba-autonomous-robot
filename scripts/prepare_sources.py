"""Fetch pinned sources without replacing existing checkouts or local changes."""
import subprocess
import sys
from pathlib import Path
import yaml


def run(*args):
    return subprocess.check_output(args, text=True).strip()


def main():
    repo, ws = map(lambda p: Path(p).resolve(), sys.argv[1:])
    alias = ws / 'src/tsukuba-autonomous-robot'
    if alias.exists() and alias.resolve() != repo:
        raise SystemExit(f'{alias} already belongs to another checkout; choose GOUDA_WORKSPACE.')
    if not alias.exists():
        alias.symlink_to(repo, target_is_directory=True)
    specs = yaml.safe_load((repo / 'third_party/external.repos').read_text())['repositories']
    for name, spec in specs.items():
        target = ws / 'src' / name
        if not target.exists():
            subprocess.run(['git', 'clone', '--no-checkout', spec['url'], str(target)], check=True)
            subprocess.run(['git', '-C', str(target), 'checkout', '--detach', spec['version']], check=True)
        actual = run('git', '-C', str(target), 'rev-parse', 'HEAD')
        if actual != spec['version']:
            raise SystemExit(f'{target}: expected {spec["version"]}, found {actual}; not replacing existing source.')
        subprocess.run(['git', '-C', str(target), 'submodule', 'update', '--init', '--recursive'], check=True)


if __name__ == '__main__':
    main()
