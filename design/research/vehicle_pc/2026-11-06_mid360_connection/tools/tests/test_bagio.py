import os
import shutil

import numpy as np
import pytest

import bagio
import bagstats as bs
import synth_bag as sb

TOPICS = {"/livox/lidar": "sensor_msgs/msg/PointCloud2", "/livox/imu": "sensor_msgs/msg/Imu",
          "/sensors/xt32/points": "sensor_msgs/msg/PointCloud2"}


def test_topics_all_formats(any_bag):
    bag = bagio.open_bag(any_bag, "builtin")
    assert bag.topics() == TOPICS


def test_storage_detected(basic):
    assert bagio.open_bag(basic["mcap"], "builtin").storage == "mcap"
    assert bagio.open_bag(basic["mcap_plain"], "builtin").storage == "mcap"
    assert bagio.open_bag(basic["db3"], "builtin").storage == "sqlite3"


def test_same_series_all_formats(any_bag, basic):
    tr = basic["truth"]
    d = bs.collect(bagio.open_bag(any_bag, "builtin"), clouds=["/livox/lidar", "/sensors/xt32/points"],
                   imus=["/livox/imu"])
    c = d["/livox/lidar"]
    assert np.array_equal(c.recv_ns, tr.cloud_recv_ns)
    assert np.array_equal(c.stamp_ns, tr.cloud_stamp_ns)
    assert np.array_equal(c.n_points, tr.cloud_npts)
    assert c.frame_ids == {"livox_frame": 100}
    i = d["/livox/imu"]
    assert np.array_equal(i.stamp_ns, tr.imu_stamp_ns)
    assert np.allclose(i.acc, tr.imu_acc, atol=0, rtol=0)
    x = d["/sensors/xt32/points"]
    assert np.array_equal(x.stamp_ns, tr.xt_stamp_ns)


def test_publish_time_only_from_mcap(basic):
    tr = basic["truth"]
    m = bs.collect(bagio.open_bag(basic["mcap"], "builtin"), clouds=["/livox/lidar"])["/livox/lidar"]
    assert np.array_equal(m.pub_ns, tr.cloud_pub_ns)
    s = bs.collect(bagio.open_bag(basic["db3"], "builtin"), clouds=["/livox/lidar"])["/livox/lidar"]
    assert s.pub_ns is None


@pytest.mark.parametrize("comp,mod", [("zstd", "zstandard"), ("lz4", "lz4")])
def test_compressed_chunks(tmp_path, basic, comp, mod):
    pytest.importorskip(mod)
    f = tmp_path / f"c_{comp}.mcap"
    sb.write_mcap(str(f), basic["msgs"], chunk_size=250, compression=comp)
    c = bs.collect(bagio.open_bag(str(f), "builtin"), clouds=["/livox/lidar"])["/livox/lidar"]
    assert np.array_equal(c.stamp_ns, basic["truth"].cloud_stamp_ns)


def test_truncated_mcap_reads_what_it_can(tmp_path, basic):
    src = basic["mcap_plain"]
    data = open(src, "rb").read()
    f = tmp_path / "cut.mcap"
    f.write_bytes(data[: int(len(data) * 0.6)])
    bag = bagio.open_bag(str(f), "builtin")
    c = bs.collect(bag, clouds=["/livox/lidar"])["/livox/lidar"]
    assert 30 < c.count < 100
    assert np.array_equal(c.stamp_ns, basic["truth"].cloud_stamp_ns[: c.count])
    assert bag.truncated_files == ["cut.mcap"]


def test_bad_crc_is_error(tmp_path, basic):
    f = tmp_path / "crc.mcap"
    sb.write_mcap(str(f), basic["msgs"][:50], chunk_size=20, bad_crc=True)
    with pytest.raises(bagio.BagError, match="CRC"):
        list(bagio.open_bag(str(f), "builtin").messages())


def test_split_files_in_directory(tmp_path, basic):
    msgs = basic["msgs"]
    d = tmp_path / "split"
    d.mkdir()
    half = len(msgs) // 2
    sb.write_mcap(str(d / "split_0.mcap"), msgs[:half])
    sb.write_mcap(str(d / "split_1.mcap"), msgs[half:])
    sb.write_metadata(str(d), "mcap", ["split_0.mcap", "split_1.mcap"])
    c = bs.collect(bagio.open_bag(str(d), "builtin"), clouds=["/livox/lidar"])["/livox/lidar"]
    assert np.array_equal(c.stamp_ns, basic["truth"].cloud_stamp_ns)


def test_directory_without_metadata(tmp_path, basic):
    d = tmp_path / "nometa"
    d.mkdir()
    shutil.copy(os.path.join(basic["db3"], "bag_db3_0.db3"), d / "x.db3")
    assert bagio.open_bag(str(d), "builtin").storage == "sqlite3"


def test_metadata_storage_mismatch(tmp_path, basic):
    d = tmp_path / "mismatch"
    d.mkdir()
    shutil.copy(basic["mcap_plain"], d / "a.mcap")
    sb.write_metadata(str(d), "sqlite3", ["a.mcap"])
    with pytest.raises(bagio.BagError, match="storage_identifier"):
        bagio.open_bag(str(d), "builtin")


def test_not_a_bag(tmp_path):
    f = tmp_path / "x.mcap"
    f.write_bytes(b"hello world, not a bag")
    with pytest.raises(bagio.BagError):
        bagio.open_bag(str(f), "builtin")


def test_big_endian_cdr():
    a = np.zeros(3, dtype=sb.LIVOX_DTYPE)
    a["x"] = [1.5, -2.0, 3.25]
    a["timestamp"] = [1e18, 2e18, 3e18]
    data = sb.enc_cloud(123_456_789_012, "livox_frame", a, sb.LIVOX_FIELDS, big=True)
    meta = bagio.decode_cloud_meta(data)
    assert meta.is_bigendian and meta.stamp_ns == 123_456_789_012 and meta.n_points == 3
    col = bagio.cloud_columns(data, meta, ["x", "timestamp"])
    assert np.allclose(col["x"], [1.5, -2.0, 3.25]) and np.allclose(col["timestamp"], [1e18, 2e18, 3e18])
    imu = bagio.decode_imu(sb.enc_imu(5_000_000_001, "livox_frame", (0.1, 0.2, 0.3), (0.0, 0.0, 1.0), big=True))
    assert imu.stamp_ns == 5_000_000_001 and imu.linear_acceleration == (0.0, 0.0, 1.0)
    assert imu.angular_velocity == (0.1, 0.2, 0.3)


def test_unknown_reader_name():
    with pytest.raises(bagio.BagError):
        bagio.open_bag("x", "nope")


def test_rosbag2_py_matches_builtin(basic):
    pytest.importorskip("rosbag2_py")
    for key in ("mcap_plain", "db3"):
        path = basic[key] if key == "mcap_plain" else os.path.join(basic[key], "bag_db3_0.db3")
        a = bs.collect(bagio.open_bag(path, "rosbag2_py"), clouds=["/livox/lidar"], imus=["/livox/imu"])
        b = bs.collect(bagio.open_bag(path, "builtin"), clouds=["/livox/lidar"], imus=["/livox/imu"])
        for t in a:
            assert np.array_equal(a[t].recv_ns, b[t].recv_ns)
            assert np.array_equal(a[t].stamp_ns, b[t].stamp_ns)


def test_auto_falls_back_with_note(basic):
    try:
        import rosbag2_py  # noqa: F401
        pytest.skip("rosbag2_py がある環境では auto は rosbag2_py を使う")
    except ImportError:
        pass
    bag = bagio.open_bag(basic["db3"], "auto")
    assert bag.backend == "builtin" and "rosbag2_py" in bagio.bag_summary(bag)["reader_note"]
    with pytest.raises(bagio.BagError, match="rosbag2_py"):
        bagio.open_bag(basic["db3"], "rosbag2_py")


def test_non_cdr_payload_is_error():
    """rosbag2 のメッセージ単位の圧縮（--compression-mode message）などで CDR でない中身は、黙って読まない。"""
    with pytest.raises(bagio.BagError, match="encapsulation"):
        bagio.decode_imu(b"\x28\xb5\x2f\xfd" + b"\x00" * 400)   # zstd の frame の先頭
