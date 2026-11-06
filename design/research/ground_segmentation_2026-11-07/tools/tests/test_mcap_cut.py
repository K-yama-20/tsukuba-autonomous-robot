import io
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import mcap_cut  # noqa: E402
from mcap.reader import NonSeekingReader  # noqa: E402
from mcap.writer import Writer  # noqa: E402


def make_bag():
    b = io.BytesIO()
    w = Writer(b, chunk_size=200, compression=None)
    w.start(profile='ros2', library='test')
    s = w.register_schema('std_msgs/msg/String', 'ros2msg', b'string data')
    c1 = w.register_channel('/a', 'cdr', s)
    c2 = w.register_channel('/b', 'cdr', s)
    for i in range(100):
        w.add_message(c1 if i % 2 else c2, log_time=10 ** 9 * 1000 + i * 10 ** 8, data=bytes([i]) * 50,
                      publish_time=10 ** 9 * 1000 + i * 10 ** 8)
    w.finish()
    return b.getvalue()


def test_cut_window_reads_back():
    bag = make_bag()
    size = len(bag)
    tail = bag[-4096:]; head = bag[:4096]
    s, n, chosen = mcap_cut.select_range(mcap_cut.chunk_indexes(tail, size), 2.0, 3.0)
    out = mcap_cut.assemble(head, tail, size, bag[s:s + n])
    msgs = [(c.topic, m.log_time) for _, c, m in NonSeekingReader(io.BytesIO(out)).iter_messages()]
    ts = [(t - 10 ** 12) / 1e9 for _, t in msgs]
    assert msgs and min(ts) <= 2.0 and max(ts) >= 3.0           # whole chunks around the window
    assert set(tp for tp, _ in msgs) == {'/a', '/b'}
    assert all(ts[i] < ts[i + 1] for i in range(len(ts) - 1))
    allt = [round((10 ** 12 + i * 10 ** 8 - 10 ** 12) / 1e9, 1) for i in range(100)]
    got = [round(x, 1) for x in ts]
    assert got == allt[allt.index(got[0]):allt.index(got[-1]) + 1]   # nothing lost inside the copied range


def test_short_tail_is_refused():
    bag = make_bag()
    try:
        mcap_cut.chunk_indexes(bag[-40:], len(bag))
    except ValueError as e:
        assert 'too short' in str(e)
    else:
        raise AssertionError('accepted a tail without the summary')
