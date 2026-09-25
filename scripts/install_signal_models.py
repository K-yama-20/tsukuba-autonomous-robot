#!/usr/bin/env python3
"""Install the pinned pedestrian signal ONNX models without overwriting data."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import time
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


EXPECTED_MODELS = {
    'detector': ('AutowareFoundation', 'traffic_light_fine_detector',
                 'tlr_car_ped_yolox_s_batch_1.onnx'),
    'classifier': ('AutowareFoundation', 'traffic_light_classifier',
                   'ped_traffic_light_classifier_mobilenetv2_batch_1.onnx'),
}
CHUNK_SIZE = 1024 * 1024
DOWNLOAD_TIMEOUT = 60
MAX_ATTEMPTS = 3


class ModelInstallError(RuntimeError):
    pass


class ExistingModelError(ModelInstallError):
    pass


def _validate_model_url(role: str, filename: str, revision: str, url: str) -> None:
    owner, repository, expected_filename = EXPECTED_MODELS[role]
    try:
        parsed = urlparse(url)
        port = parsed.port
    except ValueError as exc:
        raise ModelInstallError(f'{role}: invalid source URL') from exc
    parts = parsed.path.strip('/').split('/')
    if (parsed.scheme != 'https' or parsed.hostname != 'huggingface.co'
            or parsed.username or parsed.password or port
            or parsed.query not in ('', 'download=true')
            or filename != expected_filename
            or parts[:2] != [owner, repository]
            or len(parts) != 5 or parts[2] != 'resolve'
            or not re.fullmatch(r'[0-9a-f]{40}', parts[3]) or revision != parts[3]
            or parts[4] != filename):
        raise ModelInstallError(f'{role}: expected an immutable official Hugging Face URL for {expected_filename}')


def load_models(manifest_path: Path) -> dict[str, dict[str, object]]:
    try:
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as exc:
        raise ModelInstallError(f'cannot read model manifest {manifest_path}: {exc}') from exc
    if not isinstance(manifest, dict) or manifest.get('schema_version') != 1:
        raise ModelInstallError('unsupported pedestrian signal model manifest schema')
    if manifest.get('license') != 'Apache-2.0':
        raise ModelInstallError('pedestrian signal model manifest must declare Apache-2.0')
    models = manifest.get('models')
    if not isinstance(models, dict) or set(models) != set(EXPECTED_MODELS):
        raise ModelInstallError('model manifest must define exactly detector and classifier')

    checked: dict[str, dict[str, object]] = {}
    filenames: set[str] = set()
    for role in EXPECTED_MODELS:
        model = models[role]
        if not isinstance(model, dict):
            raise ModelInstallError(f'{role}: invalid model manifest entry')
        filename = model.get('filename')
        revision = model.get('revision')
        url = model.get('url')
        sha256 = model.get('sha256')
        size_bytes = model.get('size_bytes')
        if not isinstance(filename, str) or not isinstance(revision, str) or not isinstance(url, str):
            raise ModelInstallError(f'{role}: filename, revision, and url must be strings')
        _validate_model_url(role, filename, revision, url)
        if model.get('license') != 'Apache-2.0':
            raise ModelInstallError(f'{role}: model license must be Apache-2.0')
        if not isinstance(sha256, str) or not re.fullmatch(r'[0-9a-f]{64}', sha256):
            raise ModelInstallError(f'{role}: invalid SHA-256 in model manifest')
        if type(size_bytes) is not int or not (0 < size_bytes <= 256 * 1024 * 1024):
            raise ModelInstallError(f'{role}: invalid model size in model manifest')
        if filename in filenames:
            raise ModelInstallError(f'{role}: duplicate model filename in model manifest')
        filenames.add(filename)
        checked[role] = {
            'filename': filename,
            'revision': revision,
            'url': url,
            'sha256': sha256,
            'size_bytes': size_bytes,
            'license': model['license'],
        }
    return checked


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(CHUNK_SIZE), b''):
            digest.update(chunk)
    return digest.hexdigest()


def verify_model(path: Path, model: dict[str, object]) -> None:
    if path.is_symlink() or not path.is_file():
        raise ExistingModelError(f'existing model path is not a regular file; preserving it: {path}')
    actual_size = path.stat().st_size
    expected_size = model['size_bytes']
    if actual_size != expected_size:
        raise ExistingModelError(
            f'existing model has wrong size; preserving it: {path} '
            f'(expected {expected_size}, found {actual_size})')
    actual_sha = _sha256(path)
    if actual_sha != model['sha256']:
        raise ExistingModelError(
            f'existing model has wrong SHA-256; preserving it: {path} '
            f'(expected {model["sha256"]}, found {actual_sha})')


def _sync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _download_one(
    role: str,
    model: dict[str, object],
    target: Path,
    *,
    opener=urlopen,
    attempts: int = MAX_ATTEMPTS,
    retry_delay: float = 0.5,
) -> None:
    if target.exists() or target.is_symlink():
        verify_model(target, model)
        return

    request = Request(str(model['url']), headers={'User-Agent': 'GoudaPedestrianSignal/1.0'})
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f'.{target.name}.', suffix='.part', dir=target.parent)
        temporary = Path(temporary_name)
        try:
            digest = hashlib.sha256()
            total_bytes = 0
            with os.fdopen(descriptor, 'wb') as destination:
                with opener(request, timeout=DOWNLOAD_TIMEOUT) as response:
                    while True:
                        chunk = response.read(CHUNK_SIZE)
                        if not chunk:
                            break
                        total_bytes += len(chunk)
                        if total_bytes > model['size_bytes']:
                            raise ModelInstallError(f'{role}: download exceeds pinned size')
                        digest.update(chunk)
                        destination.write(chunk)
                destination.flush()
                os.fsync(destination.fileno())

            if total_bytes != model['size_bytes']:
                raise ModelInstallError(
                    f'{role}: wrong downloaded size (expected {model["size_bytes"]}, found {total_bytes})')
            if digest.hexdigest() != model['sha256']:
                raise ModelInstallError(f'{role}: downloaded SHA-256 does not match the pinned manifest')

            try:
                # Publish atomically without replacing a file created concurrently.
                os.link(temporary, target)
            except FileExistsError:
                verify_model(target, model)
            else:
                _sync_directory(target.parent)
            return
        except ExistingModelError:
            raise
        except (OSError, URLError, ModelInstallError) as exc:
            last_error = exc
        finally:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass
        if attempt < attempts:
            time.sleep(retry_delay * attempt)
    raise ModelInstallError(
        f'{role}: failed to install after {attempts} attempts: {last_error}') from last_error


def install_models(
    manifest_path: Path,
    model_dir: Path,
    *,
    opener=urlopen,
    attempts: int = MAX_ATTEMPTS,
    retry_delay: float = 0.5,
) -> dict[str, Path]:
    models = load_models(Path(manifest_path))
    model_dir = Path(model_dir).expanduser().resolve()
    model_dir.mkdir(parents=True, exist_ok=True)
    installed: dict[str, Path] = {}
    for role, model in models.items():
        target = model_dir / str(model['filename'])
        _download_one(role, model, target, opener=opener, attempts=attempts,
                      retry_delay=retry_delay)
        installed[role] = target
    return installed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('model_dir', type=Path)
    args = parser.parse_args()
    try:
        for role, path in install_models(args.manifest, args.model_dir).items():
            print(f'{role}: verified {path}')
    except ModelInstallError as exc:
        print(f'Pedestrian signal model setup failed: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
