import hashlib
import importlib.util
import io
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location(
    'install_signal_models', ROOT / 'scripts/install_signal_models.py')
installer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(installer)


MODEL_INFO = {
    'detector': ('traffic_light_fine_detector', 'tlr_car_ped_yolox_s_batch_1.onnx'),
    'classifier': ('traffic_light_classifier', 'ped_traffic_light_classifier_mobilenetv2_batch_1.onnx'),
}


def make_manifest(tmp_path, payloads, *, corrupt_detector_hash=False):
    models = {}
    urls = {}
    for role, (repository, filename) in MODEL_INFO.items():
        url = (f'https://huggingface.co/AutowareFoundation/{repository}/resolve/'
               f'{"a" * 40}/{filename}')
        payload = payloads[role]
        sha256 = hashlib.sha256(payload).hexdigest()
        if corrupt_detector_hash and role == 'detector':
            sha256 = '0' * 64
        models[role] = {
            'filename': filename,
            'revision': 'a' * 40,
            'url': url,
            'sha256': sha256,
            'size_bytes': len(payload),
            'license': 'Apache-2.0',
        }
        urls[url] = payload
    manifest_path = tmp_path / 'model_manifest.json'
    manifest_path.write_text(json.dumps({
        'schema_version': 1,
        'license': 'Apache-2.0',
        'source_repositories': {},
        'models': models,
    }), encoding='utf-8')
    return manifest_path, urls, models


def make_opener(urls, calls):
    def open_url(request, timeout):
        assert timeout == installer.DOWNLOAD_TIMEOUT
        calls.append(request.full_url)
        return io.BytesIO(urls[request.full_url])
    return open_url


def test_downloads_verified_models_and_reuses_them(tmp_path):
    payloads = {'detector': b'detector test model', 'classifier': b'classifier test model'}
    manifest, urls, models = make_manifest(tmp_path, payloads)
    calls = []
    model_dir = tmp_path / 'workspace/models/pedestrian_signal'

    paths = installer.install_models(manifest, model_dir, opener=make_opener(urls, calls), retry_delay=0)
    assert paths['detector'].read_bytes() == payloads['detector']
    assert paths['classifier'].read_bytes() == payloads['classifier']
    assert len(calls) == 2

    installer.install_models(manifest, model_dir, opener=make_opener(urls, calls), retry_delay=0)
    assert len(calls) == 2
    for role, path in paths.items():
        installer.verify_model(path, models[role])


def test_different_existing_model_is_preserved_and_rejected(tmp_path):
    payloads = {'detector': b'expected detector', 'classifier': b'expected classifier'}
    manifest, urls, _ = make_manifest(tmp_path, payloads)
    model_dir = tmp_path / 'models'
    model_dir.mkdir()
    target = model_dir / MODEL_INFO['detector'][1]
    target.write_bytes(b'x' * len(payloads['detector']))
    before = target.read_bytes()
    calls = []

    with pytest.raises(installer.ExistingModelError, match='wrong SHA-256.*preserving it'):
        installer.install_models(manifest, model_dir, opener=make_opener(urls, calls), retry_delay=0)

    assert target.read_bytes() == before
    assert calls == []


def test_bad_download_hash_retries_and_leaves_no_partial_file(tmp_path):
    detector = b'correct detector bytes'
    payloads = {'detector': detector, 'classifier': b'classifier'}
    manifest, urls, _ = make_manifest(tmp_path, payloads, corrupt_detector_hash=True)
    wrong_urls = dict(urls)
    detector_url = next(url for url in wrong_urls if 'traffic_light_fine_detector' in url)
    wrong_urls[detector_url] = b'x' * len(detector)
    calls = []
    model_dir = tmp_path / 'models'

    with pytest.raises(installer.ModelInstallError, match='SHA-256'):
        installer.install_models(manifest, model_dir, opener=make_opener(wrong_urls, calls),
                                 attempts=2, retry_delay=0)

    assert calls == [detector_url, detector_url]
    assert not (model_dir / MODEL_INFO['detector'][1]).exists()
    assert list(model_dir.glob('*.part')) == []
    assert list(model_dir.glob('.*.part')) == []


def test_manifest_rejects_moving_branch_urls(tmp_path):
    payloads = {'detector': b'detector', 'classifier': b'classifier'}
    manifest, urls, _ = make_manifest(tmp_path, payloads)
    document = json.loads(manifest.read_text(encoding='utf-8'))
    document['models']['detector']['url'] = document['models']['detector']['url'].replace('a' * 40, 'main')
    manifest.write_text(json.dumps(document), encoding='utf-8')
    calls = []

    with pytest.raises(installer.ModelInstallError, match='immutable'):
        installer.install_models(manifest, tmp_path / 'models', opener=make_opener(urls, calls))

    assert calls == []
