import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))  # tools/
sys.path.insert(0, HERE)                   # tests/（synth_bag）

import synth_bag as sb  # noqa: E402


@pytest.fixture(scope="session")
def basic(tmp_path_factory):
    """既定の合成：MID-360 10 Hz・100 枚、IMU 200 Hz、XT-32 10 Hz。MCAP（chunk あり・なし）と SQLite3。"""
    msgs, truth = sb.make_scenario(seed=1)
    root = tmp_path_factory.mktemp("basic")
    d_mcap = root / "bag_mcap"
    d_mcap.mkdir()
    sb.write_mcap(str(d_mcap / "bag_mcap_0.mcap"), msgs, chunk_size=300)
    sb.write_metadata(str(d_mcap), "mcap", ["bag_mcap_0.mcap"])
    f_plain = root / "plain.mcap"
    sb.write_mcap(str(f_plain), msgs, chunk_size=None)
    d_db3 = root / "bag_db3"
    d_db3.mkdir()
    sb.write_db3(str(d_db3 / "bag_db3_0.db3"), msgs)
    sb.write_metadata(str(d_db3), "sqlite3", ["bag_db3_0.db3"])
    return {"msgs": msgs, "truth": truth, "mcap": str(d_mcap), "mcap_plain": str(f_plain), "db3": str(d_db3),
            "root": root}


@pytest.fixture(params=["mcap", "mcap_plain", "db3"])
def any_bag(request, basic):
    return basic[request.param]
