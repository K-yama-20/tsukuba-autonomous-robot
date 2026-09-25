import os
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PyQt5")
from PyQt5.QtCore import QPoint, Qt
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication

from gouda_signal.app import SignalWindow
from gouda_signal.capture import CaptureSession
from gouda_signal.classifier import SignalState


def _application():
    return QApplication.instance() or QApplication(["gouda-signal-test"])


def test_window_starts_without_camera_and_closes_unknown():
    app = _application()
    window = SignalWindow(camera="/definitely/missing/gouda-signal-device")
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


def test_roi_requires_fresh_current_frame_and_source_change_invalidates():
    app = _application()
    session = _FrameSession()
    window = SignalWindow(capture_session=session)
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
