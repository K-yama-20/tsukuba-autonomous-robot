import math

import numpy as np
import pytest

import synth_bag as sb
import t08_3_tilt as t08


def run(bag, *extra):
    return t08.main([bag, "--reader", "builtin", "--json", *extra])


def test_rp_from_up_matches_rotation():
    for r, p in [(0, 0), (2, -35), (-10, 20), (30, 60), (170, 5)]:
        R = t08.rot_rpy(r, p, 47.0)          # yaw は結果に効かない
        up = R.T @ np.array([0.0, 0.0, 1.0])
        rr, pp = t08.rp_from_up(up)
        assert rr == pytest.approx(r, abs=1e-9) and pp == pytest.approx(p, abs=1e-9)
    assert np.allclose(t08.rot_rpy(2, -35, 0), sb.rot_rpy(2, -35, 0))


def test_default_hint_rejects_steep_ground(basic, capsys):
    rep = run(basic["mcap"], "--frame", "livox_frame")
    capsys.readouterr()
    m1 = rep["method1_ground"]
    assert m1["ok"] is False          # 法線は z から約 35° 傾く（既定の上限 30°）。地面を斜めに切る面も選ばない
    assert rep["verdicts"][0]["result"] == "未判定"
    top = m1["planes"][0]             # 取り出した面の 1 番目は本当の地面（一覧で人が見られる）
    assert top["pitch_deg"] == pytest.approx(basic["truth"].pitch_true, abs=0.05)
    assert top["angle_to_hint_deg"] == pytest.approx(35.0, abs=0.5)


def test_two_methods_follow_synthesis(any_bag, basic, capsys):
    tr = basic["truth"]
    rep = run(any_bag, "--frame", "livox_frame", "--up-hint-imu")
    capsys.readouterr()
    m1, m2, d = rep["method1_ground"], rep["method2_imu"], rep["difference"]
    assert m1["ok"]
    assert m1["roll_deg"] == pytest.approx(tr.roll_true, abs=0.05)
    assert m1["pitch_deg"] == pytest.approx(tr.pitch_true, abs=0.05)
    assert m1["height_m"] == pytest.approx(tr.height_m, abs=0.005)
    assert m1["inlier_ratio"] == pytest.approx(0.7, abs=0.05)   # 外れ値は 30 %（壁の下端の点の一部は地面に入る）
    assert m2["roll_deg"] == pytest.approx(tr.roll_imu, abs=0.02)
    assert m2["pitch_deg"] == pytest.approx(tr.pitch_imu, abs=0.02)
    assert d["roll_ground_minus_imu_deg"] == pytest.approx(tr.roll_true - tr.roll_imu, abs=0.06)
    assert d["pitch_ground_minus_imu_deg"] == pytest.approx(tr.pitch_true - tr.pitch_imu, abs=0.06)
    assert d["angle_between_up_deg"] < 0.5
    assert rep["verdicts"][0]["result"] == "未判定" and "基準 tbd" in rep["verdicts"][0]["reason"]


def test_hint_vector_and_criteria(basic, capsys):
    tr = basic["truth"]
    up = sb.rot_rpy(tr.roll_true, tr.pitch_true).T @ np.array([0, 0, 1.0])
    hint = (up + np.array([0.1, -0.05, 0.0])).tolist()   # おおよその向きで足りる
    rep = run(basic["mcap"], "--frame", "livox_frame", "--up-hint", *map(str, hint), "--max-diff-deg", "0.5")
    assert rep["method1_ground"]["ok"] and rep["verdicts"][0]["result"] == "合格"
    rep = run(basic["mcap"], "--frame", "livox_frame", "--up-hint", *map(str, hint), "--max-diff-deg", "0.1")
    capsys.readouterr()
    assert rep["verdicts"][0]["result"] == "不合格"      # 差は約 0.2°


def test_frame_mismatch_stops(basic):
    with pytest.raises(SystemExit, match="frame"):
        t08.main([basic["mcap"], "--reader", "builtin", "--frame", "mid360_link"])


def test_product_frames_need_rotation(tmp_path, capsys):
    msgs, tr = sb.make_scenario(seed=5, frames=30, cloud_frame="mid360_link", imu_frame="livox_frame", with_xt=False)
    f = tmp_path / "prod.mcap"
    sb.write_mcap(str(f), msgs)
    up = sb.rot_rpy(tr.roll_true, tr.pitch_true).T @ np.array([0, 0, 1.0])
    rep = run(str(f), "--frame", "mid360_link", "--up-hint", *map(str, up))
    assert rep["method1_ground"]["ok"]
    assert rep["verdicts"][0]["result"] == "未判定" and "--imu-in-cloud-rpy-deg" in rep["verdicts"][0]["reason"]
    assert "roll_deg" not in rep["method2_imu"]
    rep = run(str(f), "--frame", "mid360_link", "--up-hint", *map(str, up), "--imu-in-cloud-rpy-deg", "0", "0", "0")
    capsys.readouterr()
    assert rep["difference"]["pitch_ground_minus_imu_deg"] == pytest.approx(tr.pitch_true - tr.pitch_imu, abs=0.08)


def test_imu_rotation_is_applied(tmp_path, capsys):
    """IMU の座標が点群の座標から yaw 90° 回っている場合、回転を渡せば差は合成のとおりになる。"""
    msgs, tr = sb.make_scenario(seed=6, frames=30, cloud_frame="mid360_link", imu_frame="imu_rot", with_xt=False)
    Rci = sb.rot_rpy(0, 0, 90)   # IMU の座標 → 点群の座標
    out = []
    import bagio
    for m in msgs:
        if m.topic == "/livox/imu":
            s = bagio.decode_imu(m.data)
            acc = Rci.T @ np.asarray(s.linear_acceleration)
            m = sb.Msg(m.topic, m.msgtype, m.recv_ns, m.pub_ns, sb.enc_imu(s.stamp_ns, "imu_rot", s.angular_velocity, acc))
        out.append(m)
    f = tmp_path / "rot.db3"
    sb.write_db3(str(f), out)
    up = sb.rot_rpy(tr.roll_true, tr.pitch_true).T @ np.array([0, 0, 1.0])
    rep = run(str(f), "--frame", "mid360_link", "--imu-frame", "imu_rot", "--up-hint", *map(str, up),
              "--imu-in-cloud-rpy-deg", "0", "0", "90")
    capsys.readouterr()
    assert rep["method2_imu"]["roll_deg"] == pytest.approx(tr.roll_imu, abs=0.03)
    assert rep["method2_imu"]["pitch_deg"] == pytest.approx(tr.pitch_imu, abs=0.03)


def test_imu_frame_mismatch_stops(basic):
    with pytest.raises(SystemExit, match="IMU"):
        t08.main([basic["mcap"], "--reader", "builtin", "--frame", "livox_frame", "--imu-frame", "mid360_link"])


def test_flipped_imu_sign_is_flagged(tmp_path, capsys):
    msgs, tr = sb.make_scenario(seed=7, frames=20, accel_scale=-1.0, with_xt=False)
    f = tmp_path / "flip.mcap"
    sb.write_mcap(str(f), msgs)
    up = sb.rot_rpy(tr.roll_true, tr.pitch_true).T @ np.array([0, 0, 1.0])
    rep = run(str(f), "--frame", "livox_frame", "--up-hint", *map(str, up))
    capsys.readouterr()
    assert rep["difference"]["angle_between_up_deg"] > 179 and "warning" in rep["difference"]


def test_per_frame_spread(basic, capsys):
    rep = run(basic["mcap"], "--frame", "livox_frame", "--up-hint-imu", "--per-frame", "5", "--ransac-iters", "300")
    capsys.readouterr()
    pf = rep["method1_ground"]["per_frame"]
    assert pf["frames_ok"] == 5
    assert pf["pitch_deg"]["mean"] == pytest.approx(basic["truth"].pitch_true, abs=0.3)


def test_ground_fit_robust_to_outliers():
    """外れ値 60 % でも地面を選ぶ（壁の点が多くても、法線の向きと高さの条件で外す）。"""
    rng = np.random.default_rng(11)
    R = sb.rot_rpy(-4.0, 12.0)
    P = sb.scene_points(rng, 20000, R, 0.45, outlier_ratio=0.6, noise_m=0.01)
    up = R.T @ np.array([0, 0, 1.0])
    f = t08.fit_ground(P, up, 0.05, 500, 30.0, np.random.default_rng(0))
    assert f["ok"]
    assert f["roll_deg"] == pytest.approx(-4.0, abs=0.1) and f["pitch_deg"] == pytest.approx(12.0, abs=0.1)
    assert f["height_m"] == pytest.approx(0.45, abs=0.005)


def test_ceiling_is_not_taken_as_ground():
    """センサーより上の水平な面（天井）は、点が多くても地面に選ばない。"""
    rng = np.random.default_rng(12)
    floor = np.column_stack([rng.uniform(-5, 5, 3000), rng.uniform(-5, 5, 3000), -0.5 + rng.normal(0, 0.005, 3000)])
    ceil = np.column_stack([rng.uniform(-5, 5, 9000), rng.uniform(-5, 5, 9000), 2.0 + rng.normal(0, 0.005, 9000)])
    f = t08.fit_ground(np.vstack([floor, ceil]), [0, 0, 1], 0.05, 300, 30.0, np.random.default_rng(0))
    assert f["ok"] and f["height_m"] == pytest.approx(0.5, abs=0.005)
    assert math.isclose(f["inliers"], 3000, rel_tol=0.01)
    assert f["plane_index"] == 1 and "warning" in f   # 1 番目の面（天井）は hint に合わない
