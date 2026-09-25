"""Native Qt5 manual-ROI pedestrian-signal color prototype."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import signal
import sys
import time
import uuid
from typing import Any

from PyQt5.QtCore import QPointF, QRectF, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QImage, QPainter, QPen, QPixmap
from PyQt5.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .capture import CaptureSession, parse_camera_source
from .classifier import Observation, RawColor, SignalClassifier, SignalState
from .inference import InferenceResult, InferenceSession, box_iou, normalized_box
from .roi import (
    NormalizedROI,
    Rect,
    aspect_fit_rect,
    normalized_rect,
    point_to_normalized,
    roi_to_pixels,
)
from .vision import measure_bgr


def default_model_directory() -> Path:
    configured = os.environ.get("GOUDA_SIGNAL_MODEL_DIR")
    if configured:
        return Path(configured).expanduser()
    workspace = Path(os.environ.get("GOUDA_WORKSPACE", Path.home() / "gouda_ws"))
    return workspace / "models" / "pedestrian_signal"


class RosBridge:
    """Publish compact JSON snapshots through ROS 2 std_msgs/String."""

    def __init__(self, topic: str) -> None:
        import rclpy
        from rclpy.signals import SignalHandlerOptions
        from std_msgs.msg import String

        self._rclpy = rclpy
        self._message_type = String
        rclpy.init(args=None, signal_handler_options=SignalHandlerOptions.NO)
        self._node = rclpy.create_node("pedestrian_signal_classifier")
        self._publisher = self._node.create_publisher(String, topic, 10)

    def publish(self, payload: dict[str, Any]) -> None:
        message = self._message_type()
        message.data = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        self._publisher.publish(message)
        self._rclpy.spin_once(self._node, timeout_sec=0.0)

    def close(self) -> None:
        try:
            self._node.destroy_node()
        finally:
            if self._rclpy.ok():
                self._rclpy.shutdown()


class PreviewWidget(QWidget):
    """Aspect-fit frame display with normalized drag-to-select ROI."""

    roi_editing_started = pyqtSignal()
    roi_selected = pyqtSignal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(540, 320)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self._pixmap: QPixmap | None = None
        self._image_width = 0
        self._image_height = 0
        self._selection: NormalizedROI | None = None
        self._drag_start: tuple[float, float] | None = None
        self._drag_end: tuple[float, float] | None = None
        self._confirmed = False

    def set_frame(self, frame: Any) -> None:
        rgb = frame[..., ::-1].copy()
        self._image_height, self._image_width = rgb.shape[:2]
        image = QImage(
            rgb.data,
            self._image_width,
            self._image_height,
            rgb.strides[0],
            QImage.Format_RGB888,
        ).copy()
        self._pixmap = QPixmap.fromImage(image)
        self.update()

    def clear_selection(self) -> None:
        self._selection = None
        self._drag_start = None
        self._drag_end = None
        self._confirmed = False
        self.update()

    def clear_frame(self) -> None:
        self._pixmap = None
        self._image_width = 0
        self._image_height = 0
        self.clear_selection()

    def set_confirmed(self, confirmed: bool) -> None:
        self._confirmed = confirmed
        self.update()

    def displayed_image_rect(self) -> Rect:
        return aspect_fit_rect(self.width(), self.height(), self._image_width, self._image_height)

    def _view_to_normalized(self, point: QPointF) -> tuple[float, float] | None:
        rect = self.displayed_image_rect()
        return point_to_normalized(point.x(), point.y(), rect)

    def paintEvent(self, _event: Any) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#15191f"))
        if self._pixmap is None:
            painter.setPen(QColor("#d5dbe2"))
            painter.drawText(self.rect(), Qt.AlignCenter, "開始を押してカメラ映像を表示")
            return

        fitted = self.displayed_image_rect()
        target = QRectF(fitted.x, fitted.y, fitted.width, fitted.height)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        painter.drawPixmap(target, self._pixmap, QRectF(self._pixmap.rect()))
        roi = self._selection
        if self._drag_start is not None and self._drag_end is not None:
            roi = normalized_rect(self._drag_start, self._drag_end)
        if roi is not None:
            selection_rect = QRectF(
                fitted.x + roi.x * fitted.width,
                fitted.y + roi.y * fitted.height,
                roi.width * fitted.width,
                roi.height * fitted.height,
            )
            color = QColor("#65e572" if self._confirmed else "#ffbd4a")
            painter.setPen(QPen(color, 2.5, Qt.SolidLine if self._confirmed else Qt.DashLine))
            painter.drawRect(selection_rect)

    def mousePressEvent(self, event: Any) -> None:
        if event.button() != Qt.LeftButton or self._pixmap is None:
            return
        point = self._view_to_normalized(event.localPos())
        if point is None:
            return
        self.roi_editing_started.emit()
        self._confirmed = False
        self._drag_start = point
        self._drag_end = point
        self._selection = None
        self.update()

    def mouseMoveEvent(self, event: Any) -> None:
        if self._drag_start is None:
            return
        point = self._view_to_normalized(event.localPos())
        if point is not None:
            self._drag_end = point
            self.update()

    def mouseReleaseEvent(self, event: Any) -> None:
        if event.button() != Qt.LeftButton or self._drag_start is None:
            return
        point = self._view_to_normalized(event.localPos())
        if point is not None:
            self._drag_end = point
        roi = normalized_rect(self._drag_start, self._drag_end or self._drag_start)
        self._drag_start = None
        self._drag_end = None
        self._selection = roi
        self._confirmed = False
        self.roi_selected.emit(roi)
        self.update()


class SignalWindow(QMainWindow):
    def __init__(
        self,
        camera: str = "0",
        topic: str = "/perception/pedestrian_signal",
        ros: RosBridge | None = None,
        *,
        classifier: str = "learned",
        model_dir: Path | str | None = None,
        confidence_threshold: float = 0.8,
        capture_session: CaptureSession | None = None,
        inference_session: InferenceSession | None = None,
    ) -> None:
        super().__init__()
        self.setWindowTitle("Gouda 歩行者信号認識プロトタイプ")
        self.resize(1040, 740)
        self._ros = ros
        self._session = capture_session or CaptureSession()
        self._inference = inference_session or InferenceSession()
        self._classifier_mode = classifier
        self._model_dir = Path(model_dir) if model_dir is not None else default_model_directory()
        self._confidence_threshold = float(confidence_threshold)
        self._model_state = "not_started"
        self._camera_active = False
        self._closing = False
        self._classifier = SignalClassifier()
        self._confirmed_roi: NormalizedROI | None = None
        self._selected_roi: NormalizedROI | None = None
        self._last_preview_frame_time: float | None = None
        self._last_preview_frame_seq: int | None = None
        self._last_observation_frame_time: float | None = None
        self._last_observation_frame_seq: int | None = None
        self._last_target_box: tuple[float, float, float, float] | None = None
        self._last_inference_time: float | None = None
        self._last_inference_seq: int | None = None
        self._roi_confirmed_time: float | None = None
        self._generation = 0
        self._minimum_frame_time = 0.0
        self._camera_start_time: float | None = None
        self._last_unknown_publish = 0.0
        self._session_id = str(uuid.uuid4())
        self._seq = 0
        self._frame_seq = 0
        self._observation = Observation(SignalState.UNKNOWN, "startup", 0.0)
        self._target_id = ""

        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        title = QLabel("歩行者信号の手動ROI色判定")
        title.setStyleSheet("font-size: 20px; font-weight: 600;")
        layout.addWidget(title)
        explanation = QLabel(
            "画面に歩行者信号を映し、信号器全体をドラッグで囲んでから「ROIを確定」を押してください。"
            "学習済みモデルがROI内の信号器を検出して点灯状態を分類します。開始時と入力変更時にはROIの再確認が必要です。"
        )
        explanation.setWordWrap(True)
        layout.addWidget(explanation)

        input_row = QHBoxLayout()
        input_row.addWidget(QLabel("カメラ入力"))
        self.camera_input = QLineEdit(camera)
        self.camera_input.setPlaceholderText("0 または /dev/video0、動画ファイル、ネットワークURI")
        self.camera_input.setToolTip("V4L2番号 /dev/videoN、動画ファイル、またはOpenCVが対応するURI")
        input_row.addWidget(self.camera_input, 1)
        self.start_button = QPushButton("開始")
        self.start_button.clicked.connect(self.start_camera)
        input_row.addWidget(self.start_button)
        self.stop_button = QPushButton("停止")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.stop_camera)
        input_row.addWidget(self.stop_button)
        layout.addLayout(input_row)

        self.preview = PreviewWidget()
        self.preview.roi_editing_started.connect(self.roi_editing_started)
        self.preview.roi_selected.connect(self.roi_selected)
        layout.addWidget(self.preview, 1)

        actions = QHBoxLayout()
        self.confirm_button = QPushButton("ROIを確定")
        self.confirm_button.setEnabled(False)
        self.confirm_button.clicked.connect(self.confirm_roi)
        actions.addWidget(self.confirm_button)
        self.state_label = QLabel("UNKNOWN")
        self.state_label.setMinimumWidth(250)
        self.state_label.setAlignment(Qt.AlignCenter)
        self.state_label.setStyleSheet(
            "font-size: 25px; font-weight: 700; padding: 8px; color: white; background: #555b64;"
        )
        actions.addWidget(self.state_label)
        self.reason_label = QLabel("起動しました。カメラは自動で開始しません。")
        self.reason_label.setWordWrap(True)
        actions.addWidget(self.reason_label, 1)
        layout.addLayout(actions)

        limitation = QLabel(
            "手動で指定した範囲内で学習済みモデルが信号器を検出します。対象物の追跡、横断可否判断、車両制御には使えません。"
        )
        limitation.setWordWrap(True)
        limitation.setStyleSheet("color: #5d6670;")
        layout.addWidget(limitation)
        self.setCentralWidget(root)

        self.camera_input.textChanged.connect(self.camera_source_changed)
        self._timer = QTimer(self)
        self._timer.setInterval(100)
        self._timer.timeout.connect(self.tick)
        self._timer.start()
        self._publish_snapshot(force=True)

    @property
    def observation(self) -> Observation:
        return self._observation

    @property
    def camera_active(self) -> bool:
        return self._camera_active

    @property
    def confirmed_roi(self) -> NormalizedROI | None:
        return self._confirmed_roi

    def _show_observation(self, observation: Observation, detail: str | None = None) -> None:
        self._observation = observation
        labels = {
            SignalState.GREEN: "青 (GREEN)",
            SignalState.RED: "赤 (RED)",
            SignalState.UNKNOWN: "未検出 (UNKNOWN)",
        }
        self.state_label.setText(labels[observation.state])
        colors = {
            SignalState.GREEN: "#138c37",
            SignalState.RED: "#c33535",
            SignalState.UNKNOWN: "#555b64",
        }
        self.state_label.setStyleSheet(
            f"font-size: 25px; font-weight: 700; padding: 8px; color: white; background: {colors[observation.state]};"
        )
        messages = {
            "startup": "起動しました。カメラは自動で開始しません。",
            "camera_starting": "カメラを開始しています。映像が出たらROIを指定してください。",
            "camera_opened": "映像を受信しています。信号器全体をドラッグしてください。",
            "model_loading": "学習済みONNXモデルをロードしています。画面はUNKNOWNのままです。",
            "model_pending": "新しい判定を待っています。画面はUNKNOWNのままです。",
            "model_unavailable": "学習済みモデルをロードできません。モデルの配置を確認してください。",
            "model_inference_error": "学習済みモデルの推論に失敗しました。画面はUNKNOWNです。",
            "detector_no_pedestrian": "ROI内に歩行者信号を検出できません。",
            "detector_multiple_pedestrians": "ROI内に複数の対象があります。単一の信号器が映るようROIを調整してください。",
            "detector_inference_error": "信号器の検出に失敗しました。画面はUNKNOWNです。",
            "classifier_low_confidence": "信号の色を十分な確かさで分類できません。画面はUNKNOWNです。",
            "classifier_unknown": "信号の状態を分類できません。画面はUNKNOWNです。",
            "classifier_inference_error": "信号の分類に失敗しました。画面はUNKNOWNです。",
            "target_unconfirmed": "ROIをドラッグして「ROIを確定」を押してください。",
            "target_changed": "ROI内の検出対象が変わりました。新しい対象を続けて確認します。",
            "no_pedestrian": "ROI内に歩行者信号を検出できません。",
            "multiple_pedestrians": "ROI内に複数の対象があります。単一の信号器が映るようROIを調整してください。",
            "stale_inference": "新しい判定が0.5秒以上ありません。状態をUNKNOWNにしました。",
            "roi_green_pixels": "ROI内に緑色を検出しています。点灯が1.2秒続くまでUNKNOWNです。",
            "roi_red_pixels": "ROI内に赤色を検出しています。",
            "roi_color_ambiguous": "ROI内で赤色と緑色の両方を検出しました。ROIを見直してください。",
            "roi_color_not_found": "ROI内に判定対象の赤色・緑色がありません。",
            "green_warmup": "緑色の連続確認中です。",
            "steady_green": "ROI内の緑色が連続して確認されました。",
            "green_blink_latched": "緑色の点滅を検出しました。2秒間の安定を確認中です。",
            "stale_frame": "0.5秒以上新しい映像がありません。状態をUNKNOWNにしました。",
            "camera_open_failed": "カメラを開けません。入力を確認して開始を押し、再試行してください。",
            "camera_read_failed": "カメラから映像を読めません。入力を確認して開始を押し、再試行してください。",
            "camera_error": "カメラ処理でエラーが発生しました。入力を確認して開始を押し、再試行してください。",
            "camera_stopped": "カメラを停止しました。",
            "camera_source_changed": "入力変更によりカメラとROI確認をリセットしました。開始を押してください。",
            "roi_editing": "ROIを編集しています。新しい範囲を囲んでください。",
            "roi_confirmed": "ROIを確定しました。次の新しい映像から判定します。",
            "invalid_camera_source": "カメラ入力が空または不正です。入力を確認してください。",
            "shutdown": "アプリを終了しています。",
        }
        self.reason_label.setText(detail if detail is not None else messages.get(observation.reason, observation.reason))

    def _publish_snapshot(self, *, force: bool = False) -> None:
        if self._ros is None:
            return
        now = time.monotonic()
        if (
            self._observation.state != SignalState.UNKNOWN
            and self._last_observation_frame_time is not None
            and now - self._last_observation_frame_time > 0.5
        ):
            self._classifier.invalidate("stale_inference")
            self._show_observation(Observation(SignalState.UNKNOWN, "stale_inference", 0.0))
            force = True
        if not force and self._observation.state != SignalState.UNKNOWN:
            return
        frame_age = None
        if self._last_observation_frame_time is not None:
            frame_age = max(0.0, (now - self._last_observation_frame_time) * 1000.0)
        payload = {
            "version": 1,
            "session_id": self._session_id,
            "seq": self._seq,
            "state": self._observation.state.value,
            "reason": self._observation.reason,
            "target_id": self._target_id,
            "confidence": self._observation.confidence,
            "source": "autoware_pedestrian_onnx_v1" if self._classifier_mode == "learned" else "ubuntu_roi_color_v1",
            "frame_seq": self._last_observation_frame_seq,
            "processing_age_ms": frame_age,
        }
        try:
            self._ros.publish(payload)
            self._seq += 1
            self._last_unknown_publish = now
        except Exception as exc:
            self.reason_label.setText(f"ROS発行エラー: {exc}")

    def _set_unknown(
        self,
        reason: str,
        detail: str | None = None,
        publish: bool = True,
        preserve_frame: bool = False,
    ) -> None:
        self._classifier.invalidate(reason)
        if not preserve_frame:
            self._last_observation_frame_time = None
            self._last_observation_frame_seq = None
        self._show_observation(Observation(SignalState.UNKNOWN, reason, 0.0), detail)
        if publish:
            self._publish_snapshot(force=True)

    def _clear_roi(self) -> None:
        self._generation += 1
        self._confirmed_roi = None
        self._selected_roi = None
        self._target_id = ""
        self._last_target_box = None
        self._last_observation_frame_time = None
        self._last_observation_frame_seq = None
        self._last_inference_time = None
        self._last_inference_seq = None
        self._roi_confirmed_time = None
        self.preview.clear_selection()
        self.confirm_button.setEnabled(False)

    def start_camera(self) -> None:
        if self._camera_active:
            self.stop_camera()
        source = self.camera_input.text().strip()
        try:
            parse_camera_source(source)
        except ValueError:
            self._set_unknown("invalid_camera_source")
            return
        self._clear_roi()
        self.preview.clear_frame()
        self._classifier.reset()
        self._last_preview_frame_time = None
        self._last_preview_frame_seq = None
        self._minimum_frame_time = time.monotonic()
        self._camera_start_time = self._minimum_frame_time
        self._camera_active = True
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        start_reason = "camera_starting"
        start_detail = None
        if self._classifier_mode == "learned":
            try:
                if not self._inference.running:
                    self._inference.start(self._model_dir, self._confidence_threshold)
                self._model_state = "ready" if self._inference.ready else "loading"
                if self._model_state == "loading":
                    start_reason = "model_loading"
            except Exception as exc:
                self._model_state = "failed"
                start_reason = "model_unavailable"
                start_detail = f"モデルワーカーを開始できません: {exc}"
        self._set_unknown(start_reason, detail=start_detail, publish=True)
        try:
            self._session.start(source, frame_seq_base=self._frame_seq)
        except Exception as exc:
            self._camera_active = False
            self.start_button.setEnabled(True)
            self.stop_button.setEnabled(False)
            self._set_unknown("camera_error", f"カメラプロセスを開始できません: {exc}")

    def stop_camera(self) -> None:
        self._stop_camera("camera_stopped")

    def _stop_camera(self, reason: str, *, publish: bool = True) -> None:
        was_active = self._camera_active
        self._camera_active = False
        self._session.stop()
        if self._classifier_mode == "learned":
            self._inference.stop()
            self._model_state = "not_started"
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self._clear_roi()
        self.preview.clear_frame()
        self._minimum_frame_time = time.monotonic()
        if was_active or reason != "camera_stopped":
            self._set_unknown(reason, publish=publish)

    def camera_source_changed(self, _text: str) -> None:
        if self._closing:
            return
        # Editing the source immediately invalidates both ROI and any pending
        # observation. The new source starts only when the user presses Start.
        self._stop_camera("camera_source_changed")
        self._last_preview_frame_time = None
        self._last_preview_frame_seq = None
        self.preview.clear_frame()

    def roi_editing_started(self) -> None:
        self._clear_roi()
        self._minimum_frame_time = time.monotonic()
        self._set_unknown("roi_editing")

    def roi_selected(self, roi: NormalizedROI | None) -> None:
        self._selected_roi = roi
        fresh = (
            self._last_preview_frame_time is not None
            and time.monotonic() - self._last_preview_frame_time <= 0.5
        )
        self.confirm_button.setEnabled(self._camera_active and roi is not None and fresh)
        self._set_unknown("target_unconfirmed")

    def confirm_roi(self) -> None:
        if not self._camera_active:
            return
        roi = getattr(self, "_selected_roi", None)
        if (
            roi is None
            or self._last_preview_frame_time is None
            or time.monotonic() - self._last_preview_frame_time > 0.5
        ):
            self.confirm_button.setEnabled(False)
            self._set_unknown("stale_frame")
            return
        self._confirmed_roi = roi
        self._target_id = "manual_roi"
        self._generation += 1
        self._minimum_frame_time = time.monotonic()
        self._classifier.reset()
        self._last_target_box = None
        self._last_observation_frame_time = None
        self._last_observation_frame_seq = None
        self._last_inference_time = None
        self._last_inference_seq = None
        self._roi_confirmed_time = self._minimum_frame_time
        self.preview.set_confirmed(True)
        self.confirm_button.setEnabled(False)
        if self._classifier_mode == "learned" and self._model_state == "failed":
            reason = "model_unavailable"
        elif self._classifier_mode == "learned" and self._model_state == "loading":
            reason = "model_loading"
        elif self._classifier_mode == "learned":
            reason = "model_pending"
        else:
            reason = "roi_confirmed"
        self._set_unknown(reason)

    def _handle_inference_event(self, event: tuple[Any, ...]) -> None:
        if not event:
            return
        kind = event[0]
        if kind == "ready":
            self._inference.ready = True
            self._inference.failed = False
            self._model_state = "ready"
            if self._camera_active and self._confirmed_roi is not None:
                self._set_unknown("model_pending")
            return
        if kind == "error":
            self._inference.ready = False
            self._inference.failed = True
            self._model_state = "failed"
            detail = str(event[2]) if len(event) > 2 else "model unavailable"
            self._last_target_box = None
            self._set_unknown("model_unavailable", detail=detail)
            return
        if kind == "inference_error":
            detail = str(event[2]) if len(event) > 2 else "model inference failed"
            self._last_target_box = None
            self._set_unknown("model_inference_error", detail=detail)

    def _handle_inference_result(self, result: InferenceResult) -> None:
        if result.generation != self._generation or self._confirmed_roi is None:
            return
        if self._last_inference_seq is not None and result.frame_seq <= self._last_inference_seq:
            return
        self._last_inference_seq = result.frame_seq
        self._last_inference_time = result.frame_time
        self._last_observation_frame_seq = result.frame_seq
        self._last_observation_frame_time = result.frame_time
        now = time.monotonic()
        if now - result.frame_time > 0.5:
            self._last_target_box = None
            self._set_unknown("stale_inference", publish=True, preserve_frame=True)
            return

        if result.color not in (RawColor.GREEN, RawColor.RED) or result.box is None:
            self._last_target_box = None
            temporal_color = result.color if result.color in (RawColor.NONE, RawColor.AMBIGUOUS) else RawColor.NONE
            temporal = self._classifier.process(temporal_color, result.frame_time, 0.0)
            reason = (
                "green_blink_latched"
                if temporal.reason == "green_blink_latched"
                else result.reason or "no_pedestrian"
            )
            observation = Observation(
                SignalState.UNKNOWN,
                reason,
                temporal.confidence if reason == "green_blink_latched" else 0.0,
            )
            self._show_observation(observation)
            self._publish_snapshot(force=True)
            return

        current_box = normalized_box(result.box, result.search_width, result.search_height)
        target_changed = self._last_target_box is not None and box_iou(self._last_target_box, current_box) < 0.3
        self._last_target_box = current_box
        if target_changed:
            self._classifier.reset()
        observation = self._classifier.process(result.color, result.frame_time, result.confidence)
        if target_changed:
            observation = Observation(SignalState.UNKNOWN, "target_changed", 0.0)

        self._show_observation(observation)
        self._publish_snapshot(force=True)

    def _process_hsv_frame(
        self,
        frame: Any,
        frame_seq: int,
        timestamp: float,
        bounds: tuple[int, int, int, int],
    ) -> None:
        x0, y0, x1, y1 = bounds
        evidence = measure_bgr(frame[y0:y1, x0:x1])
        self._last_observation_frame_seq = frame_seq
        self._last_observation_frame_time = timestamp
        observation = self._classifier.process(evidence.color, timestamp, evidence.confidence)
        if time.monotonic() - timestamp > 0.5:
            self._set_unknown("stale_inference", preserve_frame=True)
            return
        self._show_observation(observation)
        self._publish_snapshot(force=True)

    def _handle_capture_event(self, event: tuple[str, ...]) -> None:
        if not self._camera_active or not event:
            return
        kind = event[0]
        if kind == "opened":
            self._show_observation(Observation(SignalState.UNKNOWN, "camera_opened", 0.0))
        elif kind in ("error", "eof"):
            code = (
                "camera_open_failed"
                if kind == "error" and "open_failed" in (event[1] if len(event) > 1 else "")
                else "camera_read_failed" if kind == "eof" else "camera_error"
            )
            detail = event[1] if len(event) > 1 else code
            self._stop_camera(code, publish=False)
            self._set_unknown(code, detail=detail, publish=True)

    def tick(self) -> None:
        now = time.monotonic()
        for event in self._inference.take_events():
            self._handle_inference_event(event)
        result = self._inference.take_latest()
        if result is not None:
            self._handle_inference_result(result)
        if self._camera_active and self._model_state == "ready" and not self._inference.running:
            self._model_state = "failed"
            self._inference.failed = True
            self._set_unknown("model_unavailable", "推論プロセスが終了しました。Startで再試行してください。")

        for event in self._session.take_events():
            self._handle_capture_event(event)
        if self._camera_active:
            item = self._session.take_latest_frame()
            if item is not None:
                frame_seq, timestamp, frame = item
                if timestamp > self._minimum_frame_time and (
                    self._last_preview_frame_time is None or timestamp > self._last_preview_frame_time
                ):
                    if now - timestamp <= 0.5:
                        self._last_preview_frame_time = timestamp
                        self._last_preview_frame_seq = int(frame_seq)
                        self._frame_seq = max(self._frame_seq, int(frame_seq))
                        self.preview.set_frame(frame)
                        if self._confirmed_roi is None:
                            self._set_unknown("target_unconfirmed", publish=False)
                        else:
                            bounds = roi_to_pixels(self._confirmed_roi, frame.shape[1], frame.shape[0])
                            if bounds is not None:
                                if self._classifier_mode == "hsv":
                                    self._process_hsv_frame(frame, int(frame_seq), timestamp, bounds)
                                elif self._model_state == "ready":
                                    x0, y0, x1, y1 = bounds
                                    submitted = self._inference.submit(
                                        self._generation,
                                        int(frame_seq),
                                        timestamp,
                                        bounds,
                                        frame[y0:y1, x0:x1],
                                    )
                                    if not submitted:
                                        self._model_state = "failed"
                                        self._set_unknown("model_unavailable")
                                elif self._model_state == "failed":
                                    self._set_unknown("model_unavailable", publish=False)
                                else:
                                    self._set_unknown("model_loading", publish=False)

            preview_age = None if self._last_preview_frame_time is None else now - self._last_preview_frame_time
            if self._last_preview_frame_time is not None and preview_age is not None and preview_age > 0.5:
                if self._observation.reason != "stale_frame":
                    self._set_unknown("stale_frame", preserve_frame=True)
                self.confirm_button.setEnabled(False)
            elif (
                self._last_preview_frame_time is None
                and self._camera_start_time is not None
                and now - self._camera_start_time > 0.5
            ):
                if self._observation.reason not in ("stale_frame", "camera_open_failed"):
                    self._set_unknown("stale_frame", preserve_frame=True)

            if self._confirmed_roi is not None and self._classifier_mode == "learned":
                watchdog_time = self._last_observation_frame_time or self._roi_confirmed_time
                if (
                    watchdog_time is not None
                    and now - watchdog_time > 0.5
                    and self._model_state == "ready"
                    and self._observation.reason not in ("stale_inference", "stale_frame")
                ):
                    self._set_unknown("stale_inference", preserve_frame=True)

        if self._observation.state == SignalState.UNKNOWN and now - self._last_unknown_publish >= 0.5:
            self._publish_snapshot(force=True)

    def closeEvent(self, event: Any) -> None:
        self.shutdown()
        event.accept()

    def shutdown(self) -> None:
        if self._closing:
            return
        self._closing = True
        self._timer.stop()
        self._stop_camera("shutdown", publish=False)
        self._set_unknown("shutdown", publish=True)
        if self._ros is not None:
            self._ros.close()
            self._ros = None


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pedestrian_signal",
        description="Native Ubuntu GUI for manual-ROI pedestrian signal color observation.",
    )
    parser.add_argument(
        "--camera",
        default="0",
        metavar="SOURCE",
        help="V4L2 index or /dev/videoN, video file, or OpenCV-supported URI (default: 0)",
    )
    parser.add_argument(
        "--no-ros",
        action="store_true",
        help="run the camera GUI without initializing ROS 2 (standalone/testing)",
    )
    parser.add_argument(
        "--ros-topic",
        default="/perception/pedestrian_signal",
        metavar="TOPIC",
        help="ROS 2 std_msgs/String topic for compact JSON snapshots",
    )
    parser.add_argument(
        "--classifier",
        choices=("learned", "hsv"),
        default="learned",
        help="learned ONNX detector/classifier (default) or explicit HSV debugging mode",
    )
    parser.add_argument(
        "--model-dir",
        default=str(default_model_directory()),
        metavar="PATH",
        help="directory containing the installed pedestrian-signal ONNX models",
    )
    parser.add_argument(
        "--confidence",
        type=_confidence_argument,
        default=0.8,
        metavar="THRESHOLD",
        help="minimum classifier score from 0 through 1 (default: 0.8)",
    )
    return parser


def _confidence_argument(value: str) -> float:
    try:
        threshold = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("confidence must be a number from 0 through 1") from exc
    if not 0.0 <= threshold <= 1.0:
        raise argparse.ArgumentTypeError("confidence must be between 0 and 1")
    return threshold


def main(argv: list[str] | None = None) -> int:
    args = build_argument_parser().parse_args(argv)
    ros = None
    if not args.no_ros:
        if not args.ros_topic.startswith("/"):
            print("--ros-topic must be an absolute topic name", file=sys.stderr)
            return 2
        try:
            ros = RosBridge(args.ros_topic)
        except Exception as exc:
            print(
                f"ROS 2を初期化できません: {exc}\n"
                "ROS 2環境をsourceするか、単体表示には --no-ros を指定してください。",
                file=sys.stderr,
            )
            return 2

    app = QApplication([sys.argv[0]])
    app.setApplicationName("Gouda Pedestrian Signal")
    window = SignalWindow(
        args.camera,
        args.ros_topic,
        ros,
        classifier=args.classifier,
        model_dir=args.model_dir,
        confidence_threshold=args.confidence,
    )
    window.show()

    def request_quit(_signum: int, _frame: Any) -> None:
        app.quit()

    signal.signal(signal.SIGINT, request_quit)
    signal.signal(signal.SIGTERM, request_quit)
    try:
        return app.exec_()
    finally:
        window.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())


MainWindow = SignalWindow
