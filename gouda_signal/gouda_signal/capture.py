"""Killable subprocess camera reader with one latest-frame slot."""

from __future__ import annotations

import multiprocessing as mp
import math
import queue
import re
import time
from typing import Any


MAX_PREVIEW_WIDTH = 1280
MAX_PREVIEW_HEIGHT = 960


def parse_camera_source(value: str) -> int | str:
    """Convert camera indices and /dev/videoN paths; preserve file/URI inputs."""

    source = value.strip()
    if not source:
        raise ValueError("camera source cannot be empty")
    if source.isdecimal():
        return int(source)
    match = re.fullmatch(r"/dev/video(\d+)", source)
    if match:
        return int(match.group(1))
    return source


def _send_status(events: Any, status: tuple[str, str] | tuple[str]) -> None:
    try:
        events.put_nowait(status)
    except queue.Full:
        # Status messages are low-volume. Remove an obsolete state so failures
        # remain visible even if the GUI was briefly busy.
        try:
            events.get_nowait()
        except queue.Empty:
            pass
        try:
            events.put_nowait(status)
        except queue.Full:
            pass


def _offer_latest(frames: Any, item: tuple[float, Any]) -> None:
    try:
        frames.put_nowait(item)
        return
    except queue.Full:
        pass
    try:
        frames.get_nowait()
    except queue.Empty:
        pass
    try:
        frames.put_nowait(item)
    except queue.Full:
        # The GUI drained and another frame arrived between the two operations.
        pass


def _camera_worker(source_text: str, frame_seq_base: int, frames: Any, events: Any) -> None:
    """OpenCV reader; all potentially blocking OpenCV calls stay in this child."""

    cap = None
    try:
        import cv2

        cv2.setNumThreads(1)
        source = parse_camera_source(source_text)
        try:
            if isinstance(source, int):
                cap = cv2.VideoCapture(source, cv2.CAP_V4L2)
            else:
                cap = cv2.VideoCapture(source)
        except Exception as exc:
            _send_status(events, ("error", f"camera_open_failed: {exc}"))
            return
        if not cap.isOpened():
            _send_status(events, ("error", "camera_open_failed"))
            return

        file_interval = None
        if isinstance(source, str) and "://" not in source:
            fps = float(cap.get(cv2.CAP_PROP_FPS))
            if not math.isfinite(fps) or fps < 1.0 or fps > 120.0:
                fps = 30.0
            file_interval = 1.0 / fps
        next_file_frame_at = time.monotonic()

        # Camera drivers may ignore this setting. The bounded IPC queue still
        # prevents the GUI from accumulating frames if it falls behind.
        try:
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        except Exception:
            pass
        _send_status(events, ("opened",))

        frame_seq = frame_seq_base
        while True:
            if file_interval is not None:
                delay = next_file_frame_at - time.monotonic()
                if delay > 0:
                    time.sleep(delay)
            ok, frame = cap.read()
            frame_time = time.monotonic()  # read-completion time, not exposure time
            if file_interval is not None:
                next_file_frame_at = max(next_file_frame_at + file_interval, frame_time)
            if not ok or frame is None:
                _send_status(events, ("eof", "camera_read_failed"))
                return
            height, width = frame.shape[:2]
            scale = min(
                1.0,
                MAX_PREVIEW_WIDTH / max(1, width),
                MAX_PREVIEW_HEIGHT / max(1, height),
            )
            if scale < 1.0:
                frame = cv2.resize(
                    frame,
                    (max(1, round(width * scale)), max(1, round(height * scale))),
                    interpolation=cv2.INTER_AREA,
                )
            frame_seq += 1
            _offer_latest(frames, (frame_seq, frame_time, frame))
    except BaseException as exc:
        _send_status(events, ("error", f"camera_error: {type(exc).__name__}: {exc}"))
    finally:
        if cap is not None:
            try:
                cap.release()
            except Exception:
                pass


class CaptureSession:
    """Own one isolated reader process and its bounded output queues."""

    def __init__(self) -> None:
        self._context = mp.get_context("spawn")
        self._process: mp.Process | None = None
        self._frames: Any = None
        self._events: Any = None

    @property
    def running(self) -> bool:
        return self._process is not None and self._process.is_alive()

    def start(self, source: str, frame_seq_base: int = 0) -> None:
        self.stop()
        self._frames = self._context.Queue(maxsize=1)
        self._events = self._context.Queue(maxsize=8)
        self._process = self._context.Process(
            target=_camera_worker,
            args=(source, frame_seq_base, self._frames, self._events),
            name="gouda-signal-camera",
            daemon=True,
        )
        self._process.start()

    def take_latest_frame(self) -> tuple[float, Any] | None:
        if self._frames is None:
            return None
        latest = None
        # The capacity is one; a second bounded read catches a replacement that
        # arrived just after the first read without starving Qt on fast inputs.
        for _ in range(2):
            try:
                latest = self._frames.get_nowait()
            except queue.Empty:
                return latest
        return latest

    def take_events(self) -> list[tuple[str, ...]]:
        if self._events is None:
            return []
        received: list[tuple[str, ...]] = []
        for _ in range(8):
            try:
                received.append(self._events.get_nowait())
            except queue.Empty:
                return received
        return received

    def stop(self) -> None:
        process = self._process
        self._process = None
        if process is not None:
            if process.is_alive():
                process.terminate()
                process.join(timeout=0.25)
                if process.is_alive():
                    process.kill()
                    process.join(timeout=0.25)
            else:
                process.join(timeout=0.0)
            if process.is_alive():
                # Keep the GUI bounded even if the OS cannot reap immediately;
                # a daemon child will not hold the main process open on exit.
                process.kill()
                process.join(timeout=0.25)

        for channel in (self._frames, self._events):
            if channel is not None:
                try:
                    channel.cancel_join_thread()
                    channel.close()
                except (OSError, ValueError):
                    pass
        self._frames = None
        self._events = None
