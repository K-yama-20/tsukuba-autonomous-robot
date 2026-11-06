import csv

import numpy as np
import pytest

import bagstats as bs
import t05_4_xt32_offset as t05


def run(bag, *extra):
    return t05.main([bag, "--reader", "builtin", "--json", *extra])


def test_offset_and_latency_follow_synthesis(any_bag, basic, tmp_path, capsys):
    tr = basic["truth"]
    out = tmp_path / "pairs.csv"
    rep = run(any_bag, "--pairs-csv", str(out))
    capsys.readouterr()
    p = rep["pairs"]
    assert p["pairs"] == 100 and p["unpaired_mid360"] == 0 and p["xt32_frames_used"] == 100
    off = (tr.cloud_stamp_ns - tr.xt_stamp_ns) * 1e-6       # 合成では i 番どうしが最も近い（差は約 -23 ms）
    exp = bs.describe(off)
    assert p["offset_mid_minus_xt_ms"]["mean"] == pytest.approx(exp["mean"], abs=1e-9)
    assert p["offset_mid_minus_xt_ms"]["std"] == pytest.approx(exp["std"], abs=1e-9)
    assert p["offset_mid_minus_xt_ms"]["mean"] == pytest.approx(-23.0, abs=0.3)
    assert p["offset_wraps"] == 0
    lat_m = (tr.cloud_recv_ns - tr.cloud_stamp_ns) * 1e-6
    lat_x = (tr.xt_recv_ns - tr.xt_stamp_ns) * 1e-6
    assert rep["mid360"]["latency_recv_minus_stamp_ms"]["mean"] == pytest.approx(lat_m.mean(), abs=1e-9)
    assert rep["xt32"]["latency_recv_minus_stamp_ms"]["mean"] == pytest.approx(lat_x.mean(), abs=1e-9)
    assert p["latency_mid360_minus_xt32_ms"]["mean"] == pytest.approx((lat_m - lat_x).mean(), abs=1e-9)
    rows = list(csv.DictReader(open(out)))
    assert len(rows) == 100 and float(rows[0]["offset_ms"]) == pytest.approx(off[0], abs=1e-3)
    assert all(v["result"] == "未判定" for v in rep["verdicts"])
    assert "記録のみ" in rep["verdicts"][0]["reason"]


def test_optional_criteria(basic, capsys):
    rep = run(basic["mcap"], "--offset-std-max-ms", "5", "--latency-std-max-ms", "0.1")
    capsys.readouterr()
    assert rep["verdicts"][0]["result"] == "合格"
    assert rep["verdicts"][1]["result"] == "不合格"   # MID-360 の遅れは 30 ms/分で増えるので標準偏差は 0.1 ms を超える


def test_max_gap_drops_pairs(basic, capsys):
    rep = run(basic["mcap"], "--max-pair-gap-ms", "10")
    capsys.readouterr()
    assert rep["pairs"]["pairs"] == 0 and rep["pairs"]["unpaired_mid360"] == 100


def test_pair_frames_nearest():
    mid = np.array([0, 100, 200, 300], dtype=np.int64)
    xt = np.array([290, 10, 95, 900], dtype=np.int64)   # 並びはばらばら
    idx = t05.pair_frames(mid, xt, max_gap_ns=50)
    assert idx.tolist() == [1, 2, -1, 0]


def test_unwrap_sawtooth():
    period = 100.0
    true = np.linspace(-40, 160, 81)                    # 位相が 1 周以上回る
    wrapped = (true + 50) % period - 50
    un, jumps = t05.unwrap(wrapped, period)
    assert jumps == 2
    assert np.allclose(un - un[0], true - true[0])


def test_missing_xt_topic(basic, capsys):
    rep = run(basic["mcap"], "--xt-topic", "/nope")
    capsys.readouterr()
    assert rep["verdicts"][0]["result"] == "未判定" and "データなし" in rep["verdicts"][0]["reason"]
