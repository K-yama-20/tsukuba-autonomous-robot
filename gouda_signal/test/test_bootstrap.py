from __future__ import annotations

import pytest

from gouda_signal import bootstrap


def test_bootstrap_execs_workspace_runtime_and_preserves_arguments(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    runtime_python = workspace / ".venvs" / "pedestrian_signal" / "bin" / "python"
    runtime_python.parent.mkdir(parents=True)
    # Venv interpreters commonly symlink to the system Python executable.
    runtime_python.symlink_to(bootstrap.sys.executable)
    monkeypatch.setenv("GOUDA_WORKSPACE", str(workspace))
    monkeypatch.setattr(bootstrap.sys, "argv", ["pedestrian_signal", "--camera", "/dev/video7"])
    calls = []

    def fake_execv(path, args):
        calls.append((path, args))
        raise RuntimeError("exec captured")

    monkeypatch.setattr(bootstrap.os, "execv", fake_execv)
    with pytest.raises(RuntimeError, match="exec captured"):
        bootstrap.main()

    assert calls == [
        (
            str(runtime_python),
            [str(runtime_python), "-m", "gouda_signal.app", "--camera", "/dev/video7"],
        )
    ]


def test_bootstrap_reports_missing_runtime(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("GOUDA_WORKSPACE", str(tmp_path))
    monkeypatch.setattr(bootstrap.sys, "argv", ["pedestrian_signal"])

    assert bootstrap.main() == 2
    assert "bash scripts/setup.sh" in capsys.readouterr().err
