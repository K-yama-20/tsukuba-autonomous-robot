import json
import os
import subprocess
import sys

import numpy as np
import pytest

import bagstats as bs
import synth_bag as sb
import t04_driver_topics as t04

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run(bag, *extra):
    return t04.main([bag, "--reader", "builtin", "--json", *extra])


def verdict(rep, prefix):
    return [v for v in rep["verdicts"] if v["item"].startswith(prefix)]


def test_values_follow_synthesis(any_bag, basic, capsys):
    tr = basic["truth"]
    rep = run(any_bag)
    capsys.readouterr()
    c = rep["cloud"]
    n = len(tr.cloud_recv_ns)
    assert c["count"] == n
    assert c["rate_hz_recv"] == pytest.approx((n - 1) / ((tr.cloud_recv_ns[-1] - tr.cloud_recv_ns[0]) * 1e-9), rel=1e-12)
    assert c["rate_hz_recv"] == pytest.approx(10.0, rel=0.01)
    exp = bs.describe(np.diff(tr.cloud_stamp_ns) * 1e-6)
    for k in ("mean", "std", "min", "max", "p5", "p50", "p95", "p99"):
        assert c["stamp_interval_ms"][k] == pytest.approx(exp[k], abs=1e-9)
    exp = bs.describe(np.diff(tr.cloud_recv_ns) * 1e-6)
    assert c["recv_interval_ms"]["std"] == pytest.approx(exp["std"], abs=1e-9)
    lat = (tr.cloud_recv_ns - tr.cloud_stamp_ns) * 1e-6
    assert c["latency_recv_minus_stamp_ms"]["mean"] == pytest.approx(lat.mean(), abs=1e-9)
    b, _a = np.polyfit((tr.cloud_recv_ns - tr.cloud_recv_ns[0]) * 1e-9, lat, 1)
    assert c["latency_drift"]["slope_per_min"] == pytest.approx(b * 60, rel=1e-9)
    assert c["latency_drift"]["slope_per_min"] == pytest.approx(tr.params["drift_ms_per_min"], abs=3.0)
    assert c["points_per_frame"]["mean"] == pytest.approx(tr.cloud_npts.mean())
    assert c["stamp_backward"]["count"] == 0 and c["stamp_duplicate"] == 0
    names = [f["name"] for f in c["layouts"][0]["fields"]]
    assert names == ["x", "y", "z", "intensity", "tag", "line", "timestamp"]
    assert c["layouts"][0]["point_step"] == 26 and not c["layout_changed"]
    i = rep["imu"]
    assert i["rate_hz_recv"] == pytest.approx(200.0, rel=0.01)
    assert i["frame_ids"] == {"livox_frame": 2000}
    assert i["values"]["unit_guess"]["nearest"] == "g"
    assert i["values"]["accel_norm"]["mean"] == pytest.approx(np.linalg.norm(tr.imu_acc, axis=1).mean(), abs=1e-12)


def test_point_time_field(basic, capsys):
    tr = basic["truth"]
    rep = run(basic["mcap"])
    capsys.readouterr()
    pt = rep["cloud"]["point_time"]
    assert pt["unit_guess"] == "ns（絶対時刻）"
    assert abs(pt["first_point_minus_stamp_ms"]["max"]) < 1e-3   # float64 の丸め（約 256 ns）の内
    span = (tr.cloud_npts - 1) * tr.point_interval_ns * 1e-6
    assert pt["span_in_frame_ms"]["mean"] == pytest.approx(span.mean(), abs=1e-3)


def test_publish_time_split_mcap_only(basic, capsys):
    tr = basic["truth"]
    rep = run(basic["mcap"])
    assert rep["cloud"]["publish_minus_stamp_ms"]["mean"] == pytest.approx(
        ((tr.cloud_pub_ns - tr.cloud_stamp_ns) * 1e-6).mean(), abs=1e-9)
    assert rep["cloud"]["recv_minus_publish_ms"]["mean"] == pytest.approx(
        ((tr.cloud_recv_ns - tr.cloud_pub_ns) * 1e-6).mean(), abs=1e-9)
    rep2 = run(basic["db3"])
    capsys.readouterr()
    assert "publish_minus_stamp_ms" not in rep2["cloud"] and "publish_time" in rep2["cloud"]


def test_no_criteria_is_undecided(basic, capsys):
    rep = run(basic["mcap"])
    capsys.readouterr()
    for v in rep["verdicts"]:
        assert v["result"] == "未判定"
        assert "基準 tbd" in v["reason"] or "記録のみ" in v["reason"]


def test_criteria_pass_and_fail(basic, capsys):
    rep = run(basic["mcap"], "--cloud-hz-expected", "10", "--cloud-hz-tol-pct", "5", "--imu-hz-expected", "200",
              "--imu-hz-tol-pct", "5", "--points-expected", "1530", "--points-tol-pct", "10",
              "--latency-drift-max-ms-per-min", "100", "--expect-cloud-frame", "livox_frame")
    assert all(v["result"] == "合格" for v in rep["verdicts"] if not v["item"].startswith("T04-1 IMU"))
    rep = run(basic["mcap"], "--cloud-hz-expected", "12", "--cloud-hz-tol-pct", "5", "--points-expected", "20000",
              "--points-tol-pct", "10", "--latency-drift-max-ms-per-min", "1", "--expect-cloud-frame", "mid360_link")
    capsys.readouterr()
    for prefix in ("T04-1 点群", "T04-2 点群", "T04-3", "T04-5 点群"):
        assert verdict(rep, prefix)[0]["result"] == "不合格", prefix
    assert rep["cloud"]["frames_outside_points_range"] == 100


def test_pair_args_required(basic):
    with pytest.raises(SystemExit):
        t04.main([basic["mcap"], "--cloud-hz-expected", "10"])


def test_backward_and_duplicate_stamps(tmp_path, capsys):
    msgs, _tr = sb.make_scenario(seed=2, frames=100, backward_at=50, duplicate_at=70, with_xt=False)
    f = tmp_path / "bd.mcap"
    sb.write_mcap(str(f), msgs)
    rep = run(str(f))
    capsys.readouterr()
    c = rep["cloud"]
    assert c["stamp_backward"]["count"] == 1
    assert c["stamp_backward"]["first_indices"] == [50]
    assert c["stamp_backward"]["max_ms"] == pytest.approx(5.0)
    assert c["stamp_repeat_consecutive"] == 1 and c["stamp_duplicate"] == 1


def test_accel_in_ms2_is_recognised(tmp_path, capsys):
    msgs, _tr = sb.make_scenario(seed=3, frames=20, accel_scale=9.80665, with_xt=False)
    f = tmp_path / "ms2.db3"
    sb.write_db3(str(f), msgs)
    rep = run(str(f))
    capsys.readouterr()
    assert rep["imu"]["values"]["unit_guess"]["nearest"] == "m/s^2"


def test_window_and_static_window(basic, capsys):
    rep = run(basic["mcap"], "--window", "2", "6", "--static-window", "3", "4")
    capsys.readouterr()
    assert 38 <= rep["cloud"]["count"] <= 42
    assert 195 <= rep["imu"]["values"]["samples"] <= 205


def test_missing_topic(basic, capsys):
    rep = run(basic["mcap"], "--cloud-topic", "/nope", "--imu-topic", "/nope2")
    capsys.readouterr()
    assert rep["verdicts"][0]["result"] == "未判定"


def test_cli_isolated_mode_and_json_file(basic, tmp_path):
    out = tmp_path / "t04.json"
    r = subprocess.run([sys.executable, "-I", "-B", os.path.join(TOOLS, "t04_driver_topics.py"), basic["db3"],
                        "--reader", "builtin", "--json-out", str(out), "--sha256"],
                       capture_output=True, text=True, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
    assert r.returncode == 0, r.stderr
    assert "T04 の解析" in r.stdout and "判定：" in r.stdout
    rep = json.loads(out.read_text())
    assert rep["bag"]["storage"] == "sqlite3" and len(rep["bag"]["sha256"]["bag_db3_0.db3"]) == 64
    assert "/" not in rep["bag"]["name"]


def test_frame_expectation_without_data_is_undecided(basic, capsys):
    rep = run(basic["mcap"], "--imu-topic", "/nope", "--expect-imu-frame", "livox_frame")
    capsys.readouterr()
    v = verdict(rep, "T04-1 IMU")[0]
    assert v["result"] == "未判定" and "データなし" in v["reason"]
