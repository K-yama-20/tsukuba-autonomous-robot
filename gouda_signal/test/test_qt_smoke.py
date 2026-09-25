import os
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PyQt5")
from PyQt5.QtCore import QPoint, Qt
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication

import gouda_signal.app as app_module
from gouda_signal.app import SignalWindow
from gouda_signal.capture import CaptureSession
from gouda_signal.classifier import Observation, RawColor, SignalState
from gouda_signal.inference import InferenceResult
from gouda_signal.roi import NormalizedROI


def _application():
    return QApplication.instance() or QApplication(["gouda-signal-test"])


def test_window_starts_without_camera_and_closes_unknown():
    app = _application()
    window = SignalWindow(camera="/definitely/missing/gouda-signal-device", classifier="hsv")
    window.show()
    app.processEvents()
    assert not window._camera_active
    assert window._observation.state is SignalState.UNKNOWN

    QTest.mouseClick(window.start_button, Qt.LeftButton)
    deadline = time.monotonic() + 5.0
    while window._camera_active and time.monotonic() < deadline:
        QTest.qWait(50)
        app.processEvents()
    assert not window._camera_active
    assert window._observation.state is SignalState.UNKNOWN
    assert window._observation.reason in {"camera_open_failed", "camera_error"}

    window.close()
    app.processEvents()
    assert window._observation.state is SignalState.UNKNOWN
    assert window._observation.reason == "shutdown"


class _FrameSession:
    def __init__(self):
        self.events = []
        self.frame = None
        self.stopped = False

    def start(self, _source, frame_seq_base=0):
        import numpy as np

        self.stopped = False
        self.events = [("opened",)]
        self.frame = (frame_seq_base + 1, time.monotonic(), np.zeros((480, 640, 3), dtype=np.uint8))

    def stop(self):
        self.stopped = True
        self.frame = None

    def take_events(self):
        events, self.events = self.events, []
        return events

    def take_latest_frame(self):
        frame, self.frame = self.frame, None
        return frame


class _EmptyCaptureSession:
    def stop(self):
        pass

    def take_events(self):
        return []

    def take_latest_frame(self):
        return None


class _IdleInferenceSession:
    def __init__(self):
        self.ready = True
        self.failed = False
        self.running = True
        self.stopped = False

    def stop(self):
        self.running = False
        self.ready = False
        self.stopped = True

    def take_events(self):
        return []

    def take_latest(self):
        return None

    def submit(self, *_args):
        return True


def test_roi_requires_fresh_current_frame_and_source_change_invalidates():
    app = _application()
    session = _FrameSession()
    window = SignalWindow(capture_session=session, classifier="hsv")
    window.show()
    app.processEvents()
    QTest.mouseClick(window.start_button, Qt.LeftButton)
    window.tick()
    app.processEvents()

    fitted = window.preview.displayed_image_rect()
    start = QPoint(round(fitted.x + fitted.width * 0.2), round(fitted.y + fitted.height * 0.2))
    end = QPoint(round(fitted.x + fitted.width * 0.7), round(fitted.y + fitted.height * 0.7))
    QTest.mousePress(window.preview, Qt.LeftButton, pos=start)
    QTest.mouseMove(window.preview, end)
    QTest.mouseRelease(window.preview, Qt.LeftButton, pos=end)
    assert window.confirm_button.isEnabled()
    QTest.mouseClick(window.confirm_button, Qt.LeftButton)
    assert window._confirmed_roi is not None
    assert window._observation.reason == "roi_confirmed"

    window.camera_input.setText("another-source")
    assert not window._camera_active
    assert window._confirmed_roi is None
    assert window.preview._pixmap is None
    assert window._observation.state is SignalState.UNKNOWN
    window.close()
    app.processEvents()


def _learned_result(generation, frame_seq, timestamp, color, box):
    reason = {
        RawColor.GREEN: "classifier_green",
        RawColor.RED: "classifier_red",
        RawColor.NONE: "detector_no_pedestrian",
        RawColor.AMBIGUOUS: "classifier_unknown",
    }[color]
    return InferenceResult(
        generation=generation,
        frame_seq=frame_seq,
        frame_time=timestamp,
        color=color,
        confidence=0.95 if color is RawColor.GREEN else 0.0,
        reason=reason,
        box=box,
        detector_confidence=0.9 if box is not None else 0.0,
        search_bounds=(0, 0, 100, 100),
        search_width=100,
        search_height=100,
    )


def test_learned_green_none_transitions_latch_blink_then_recover(monkeypatch):
    app = _application()
    now = [0.0]
    monkeypatch.setattr(app_module.time, "monotonic", lambda: now[0])
    inference = _IdleInferenceSession()
    window = SignalWindow(
        classifier="learned",
        capture_session=_EmptyCaptureSession(),
        inference_session=inference,
    )
    window._camera_active = True
    window._model_state = "ready"
    window._confirmed_roi = NormalizedROI(0.0, 0.0, 1.0, 1.0)
    window._generation = 4

    seq = 0

    def feed(timestamp, color):
        nonlocal seq
        seq += 1
        now[0] = timestamp + 0.01
        box = (10.0, 10.0, 30.0, 30.0) if color is RawColor.GREEN else None
        window._handle_inference_result(_learned_result(4, seq, timestamp, color, box))

    for timestamp in (0.0, 0.3, 0.6, 0.9, 1.21):
        feed(timestamp, RawColor.GREEN)
    assert window.observation.state is SignalState.GREEN

    feed(1.31, RawColor.NONE)
    for timestamp in (1.41, 1.71, 2.01, 2.31, 2.61):
        feed(timestamp, RawColor.GREEN)
    feed(2.71, RawColor.NONE)
    assert window.observation.state is SignalState.UNKNOWN
    assert window.observation.reason == "green_blink_latched"

    for timestamp in (2.81, 3.11, 3.41, 3.71, 4.01, 4.31, 4.61, 4.91):
        feed(timestamp, RawColor.GREEN)
    assert window.observation.state is SignalState.GREEN
    assert window.observation.reason == "steady_green"

    seq += 1
    now[0] = 5.01
    window._handle_inference_result(
        _learned_result(4, seq, 5.0, RawColor.GREEN, (70.0, 70.0, 90.0, 90.0))
    )
    assert window.observation.state is SignalState.UNKNOWN
    assert window.observation.reason == "target_changed"
    for timestamp in (5.3, 5.6, 5.9, 6.21):
        feed(timestamp, RawColor.GREEN)
    assert window.observation.state is SignalState.GREEN

    window.close()
    app.processEvents()
    assert inference.stopped


def test_live_preview_does_not_refresh_stale_inference(monkeypatch):
    app = _application()
    now = [100.6]
    monkeypatch.setattr(app_module.time, "monotonic", lambda: now[0])
    window = SignalWindow(
        classifier="learned",
        capture_session=_EmptyCaptureSession(),
        inference_session=_IdleInferenceSession(),
    )
    window._camera_active = True
    window._model_state = "ready"
    window._confirmed_roi = NormalizedROI(0.0, 0.0, 1.0, 1.0)
    window._roi_confirmed_time = 100.0
    window._last_observation_frame_time = 100.0
    window._last_observation_frame_seq = 15
    window._last_preview_frame_time = 100.4
    window._show_observation(Observation(SignalState.GREEN, "steady_green", 0.95))

    window.tick()

    assert window.observation.state is SignalState.UNKNOWN
    assert window.observation.reason == "stale_inference"
    window.close()
    app.processEvents()
