"""Killable, latest-only process boundary for learned signal classification."""

from __future__ import annotations

from dataclasses import dataclass
import multiprocessing as mp
from pathlib import Path
import queue
import time
from typing import Any

import numpy as np

from .classifier import RawColor


@dataclass(frozen=True)
class InferenceResult:
    generation: int
    frame_seq: int
    frame_time: float
    color: RawColor
    confidence: float
    reason: str
    box: tuple[float, float, float, float] | None
    detector_confidence: float
    search_bounds: tuple[int, int, int, int]
    search_width: int
    search_height: int


def _number(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return default
    return result if np.isfinite(result) else default


def normalize_color(value: Any) -> RawColor:
    if isinstance(value, RawColor):
        return value
    name = getattr(value, "value", value)
    text = str(name).strip().lower()
    if text == "green":
        return RawColor.GREEN
    if text == "red":
        return RawColor.RED
    if text == "ambiguous":
        return RawColor.AMBIGUOUS
    return RawColor.NONE


def normalize_box(value: Any) -> tuple[float, float, float, float] | None:
    if value is None:
        return None
    try:
        coords = tuple(_number(part, float("nan")) for part in value)
    except (TypeError, ValueError):
        return None
    if len(coords) != 4 or not np.isfinite(coords).all():
        return None
    x0, y0, x1, y1 = coords
    if x1 <= x0 or y1 <= y0:
        return None
    return coords  # type: ignore[return-value]


def normalize_evidence(evidence: Any) -> tuple[RawColor, float, str, tuple[float, float, float, float] | None, float]:
    """Adapt the small model interface into stable GUI/temporal values."""

    color = normalize_color(getattr(evidence, "color", "unknown"))
    confidence = min(1.0, max(0.0, _number(getattr(evidence, "confidence", 0.0))))
    reason = str(getattr(evidence, "reason", "model_unknown"))[:256] or "model_unknown"
    box = normalize_box(getattr(evidence, "box", None))
    detector_confidence = min(
        1.0,
        max(0.0, _number(getattr(evidence, "detector_confidence", confidence))),
    )
    return color, confidence, reason, box, detector_confidence


def normalized_box(
    box: tuple[float, float, float, float] | None, width: int, height: int
) -> tuple[float, float, float, float] | None:
    if box is None or width <= 0 or height <= 0:
        return None
    return (box[0] / width, box[1] / height, box[2] / width, box[3] / height)


def box_iou(
    left: tuple[float, float, float, float] | None,
    right: tuple[float, float, float, float] | None,
) -> float:
    """Intersection-over-union for normalized ROI-relative boxes."""

    if left is None or right is None:
        return 0.0
    x0 = max(left[0], right[0])
    y0 = max(left[1], right[1])
    x1 = min(left[2], right[2])
    y1 = min(left[3], right[3])
    intersection = max(0.0, x1 - x0) * max(0.0, y1 - y0)
    left_area = max(0.0, left[2] - left[0]) * max(0.0, left[3] - left[1])
    right_area = max(0.0, right[2] - right[0]) * max(0.0, right[3] - right[1])
    union = left_area + right_area - intersection
    return intersection / union if union > 0.0 else 0.0


def _offer_latest(channel: Any, item: Any) -> None:
    try:
        channel.put_nowait(item)
        return
    except queue.Full:
        pass
    try:
        channel.get_nowait()
    except queue.Empty:
        pass
    try:
        channel.put_nowait(item)
    except queue.Full:
        pass


def _emit_event(events: Any, *item: Any) -> None:
    _offer_latest(events, tuple(item))


def _inference_worker(
    model_dir: str,
    confidence_threshold: float,
    requests: Any,
    results: Any,
    events: Any,
) -> None:
    """Load the ONNX-backed wrapper and service one pending crop at a time."""

    try:
        import cv2
        from .model import PedestrianModel

        cv2.setNumThreads(1)
        model = PedestrianModel(Path(model_dir), confidence_threshold=confidence_threshold)
        if not getattr(model, "available", False):
            load_error = getattr(model, "load_error", None) or "model unavailable"
            raise RuntimeError(str(load_error))
    except BaseException as exc:
        _emit_event(events, "error", "model_unavailable", f"{type(exc).__name__}: {exc}")
        return

    _emit_event(events, "ready")
    while True:
        request = requests.get()
        if request is None:
            return
        generation, frame_seq, frame_time, search_bounds, crop = request
        try:
            evidence = model.classify(crop)
            color, confidence, reason, box, detector_confidence = normalize_evidence(evidence)
            result = InferenceResult(
                generation=int(generation),
                frame_seq=int(frame_seq),
                frame_time=float(frame_time),
                color=color,
                confidence=confidence,
                reason=reason,
                box=box,
                detector_confidence=detector_confidence,
                search_bounds=tuple(int(value) for value in search_bounds),
                search_width=int(crop.shape[1]),
                search_height=int(crop.shape[0]),
            )
            _offer_latest(results, result)
        except BaseException as exc:
            _emit_event(events, "inference_error", "model_inference_error", f"{type(exc).__name__}: {exc}")


class InferenceSession:
    """Own one long-lived inference child with one latest request/result slot."""

    def __init__(self) -> None:
        self._context = mp.get_context("spawn")
        self._process: mp.Process | None = None
        self._requests: Any = None
        self._results: Any = None
        self._events: Any = None
        self.ready = False
        self.failed = False

    @property
    def running(self) -> bool:
        return self._process is not None and self._process.is_alive()

    def start(self, model_dir: Path, confidence_threshold: float = 0.8) -> None:
        if self.running:
            return
        self.stop()
        self._requests = self._context.Queue(maxsize=1)
        self._results = self._context.Queue(maxsize=1)
        self._events = self._context.Queue(maxsize=8)
        self.ready = False
        self.failed = False
        self._process = self._context.Process(
            target=_inference_worker,
            args=(
                str(model_dir),
                float(confidence_threshold),
                self._requests,
                self._results,
                self._events,
            ),
            name="gouda-signal-inference",
            daemon=True,
        )
        self._process.start()

    def submit(
        self,
        generation: int,
        frame_seq: int,
        frame_time: float,
        search_bounds: tuple[int, int, int, int],
        crop: np.ndarray,
    ) -> bool:
        if not self.ready or not self.running or self._requests is None:
            return False
        request = (generation, frame_seq, frame_time, search_bounds, np.ascontiguousarray(crop))
        _offer_latest(self._requests, request)
        return True

    def take_latest(self) -> InferenceResult | None:
        if self._results is None:
            return None
        latest = None
        for _ in range(2):
            try:
                latest = self._results.get_nowait()
            except queue.Empty:
                return latest
        return latest

    def take_events(self) -> list[tuple[Any, ...]]:
        if self._events is None:
            return []
        items = []
        for _ in range(8):
            try:
                items.append(self._events.get_nowait())
            except queue.Empty:
                return items
        return items

    def stop(self) -> None:
        process = self._process
        self._process = None
        self.ready = False
        if process is not None:
            if process.is_alive():
                try:
                    if self._requests is not None:
                        self._requests.put_nowait(None)
                except queue.Full:
                    pass
                process.join(timeout=0.2)
                if process.is_alive():
                    process.terminate()
                    process.join(timeout=0.25)
                if process.is_alive():
                    process.kill()
                    process.join(timeout=0.25)
            else:
                process.join(timeout=0.0)

        for channel in (self._requests, self._results, self._events):
            if channel is not None:
                try:
                    channel.cancel_join_thread()
                    channel.close()
                except (OSError, ValueError):
                    pass
        self._requests = None
        self._results = None
        self._events = None
