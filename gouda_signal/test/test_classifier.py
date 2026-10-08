from gouda_signal.classifier import RawColor, SignalClassifier, SignalState


def test_green_requires_continuous_1_2_seconds():
    classifier = SignalClassifier()
    assert classifier.process(RawColor.GREEN, 0.0, 0.7).state is SignalState.UNKNOWN
    assert classifier.process(RawColor.GREEN, 0.4, 0.7).state is SignalState.UNKNOWN
    assert classifier.process(RawColor.GREEN, 0.8, 0.7).state is SignalState.UNKNOWN
    result = classifier.process(RawColor.GREEN, 1.2, 0.7)
    assert result.state is SignalState.GREEN
    assert result.reason == "steady_green"
    assert result.confidence == 0.7


def test_gap_over_450ms_resets_green_warmup():
    classifier = SignalClassifier()
    classifier.process(RawColor.GREEN, 0.0, 0.8)
    classifier.process(RawColor.GREEN, 0.4, 0.8)
    result = classifier.process(RawColor.GREEN, 0.9, 0.8)
    assert result.state is SignalState.UNKNOWN
    assert result.reason == "green_warmup"
    for timestamp in (1.3, 1.7, 2.1):
        result = classifier.process(RawColor.GREEN, timestamp, 0.8)
    assert result.state is SignalState.GREEN


def test_two_green_falls_latch_blink_until_two_seconds_steady():
    classifier = SignalClassifier()
    for timestamp in (0.0, 0.4, 0.8, 1.2):
        classifier.process(RawColor.GREEN, timestamp, 0.9)
    classifier.process(RawColor.NONE, 1.3)
    classifier.process(RawColor.GREEN, 1.4, 0.9)
    latched = classifier.process(RawColor.NONE, 1.5)
    assert latched.state is SignalState.UNKNOWN
    assert latched.reason == "green_blink_latched"

    result = None
    for timestamp in (1.6, 1.8, 2.0, 2.2, 2.4, 2.6, 2.8, 3.0, 3.2, 3.4, 3.6):
        result = classifier.process(RawColor.GREEN, timestamp, 0.9)
    assert result is not None
    assert result.state is SignalState.GREEN


def test_red_is_immediate_and_clears_blink_history():
    classifier = SignalClassifier()
    result = classifier.process(RawColor.RED, 5.0, 0.6)
    assert result.state is SignalState.RED
    assert result.reason == "roi_red_pixels"
    assert result.confidence == 0.6


def test_invalidation_and_non_monotonic_time_never_keep_green():
    classifier = SignalClassifier()
    classifier.process(RawColor.GREEN, 10.0, 1.0)
    invalid = classifier.invalidate("camera_stalled")
    assert invalid.state is SignalState.UNKNOWN
    assert invalid.reason == "camera_stalled"

    classifier.process(RawColor.GREEN, 11.0, 1.0)
    backwards = classifier.process(RawColor.GREEN, 10.9, 1.0)
    assert backwards.state is SignalState.UNKNOWN
    assert backwards.reason == "non_monotonic_timestamp"
