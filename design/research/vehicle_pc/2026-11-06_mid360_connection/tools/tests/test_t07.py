import csv

import numpy as np
import pytest

import synth_bag as sb
import t07_timeseries as t07


def run(bag, out, *extra):
    return t07.main([bag, "--reader", "builtin", "--json", "--csv-out", str(out), *extra])


def test_csv_follows_synthesis(any_bag, basic, tmp_path, capsys):
    tr = basic["truth"]
    out = tmp_path / "frames.csv"
    bins_out = tmp_path / "bins.csv"
    rep = run(any_bag, out, "--bin-s", "2", "--bins-csv-out", str(bins_out))
    capsys.readouterr()
    rows = list(csv.DictReader(open(out)))
    assert len(rows) == 100
    assert [int(r["points"]) for r in rows] == tr.cloud_npts.tolist()
    lat = (tr.cloud_recv_ns - tr.cloud_stamp_ns) * 1e-6
    assert np.allclose([float(r["latency_ms"]) for r in rows], lat, atol=1e-3)
    assert rows[0]["recv_interval_ms"] == ""
    assert float(rows[1]["stamp_interval_ms"]) == pytest.approx((tr.cloud_stamp_ns[1] - tr.cloud_stamp_ns[0]) * 1e-6,
                                                                 abs=1e-3)
    b = rep["bins"]
    assert b["count"] == 5 and sum(r["frames"] for r in b["rows"]) == 100
    assert all(r["rate_hz_recv"] == pytest.approx(10.0, rel=0.02) for r in b["rows"])
    assert len(list(csv.DictReader(open(bins_out)))) == 5
    assert rep["temperature_topics_in_bag"] == []
    assert all(v["result"] == "未判定" and "基準 tbd" in v["reason"] for v in rep["verdicts"])


def test_criteria(basic, tmp_path, capsys):
    rep = run(basic["mcap"], tmp_path / "f.csv", "--bin-s", "2", "--ref-hz", "10", "--ref-points", "1530", "--tol-pct", "5")
    assert [v["result"] for v in rep["verdicts"]] == ["合格", "合格"]
    rep = run(basic["mcap"], tmp_path / "f.csv", "--bin-s", "2", "--ref-hz", "10", "--ref-points", "3000", "--tol-pct", "5")
    capsys.readouterr()
    assert [v["result"] for v in rep["verdicts"]] == ["合格", "不合格"]


def test_ref_needs_tol(basic, tmp_path):
    with pytest.raises(SystemExit):
        t07.main([basic["mcap"], "--csv-out", str(tmp_path / "x.csv"), "--ref-hz", "10"])


def test_temperature_topic_listed(tmp_path, capsys):
    msgs, _ = sb.make_scenario(seed=4, frames=10, with_xt=False, with_temperature_topic=True)
    f = tmp_path / "t.mcap"
    sb.write_mcap(str(f), msgs)
    rep = run(str(f), tmp_path / "f.csv")
    capsys.readouterr()
    assert rep["temperature_topics_in_bag"] == ["/livox/temperature"]
