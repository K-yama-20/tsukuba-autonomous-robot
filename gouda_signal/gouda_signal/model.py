"""Fail-closed learned pedestrian-signal detector and color classifier.

The model artifacts are installed separately from the source package. Their
immutable identities, tensor contracts, and preprocessing parameters live in
``gouda_signal/model_manifest.json``.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import numbers
import os
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from .classifier import RawColor

try:
    import numpy as np
except Exception:  # pragma: no cover - exercised on the target runtime
    np = None  # type: ignore[assignment]

try:
    import cv2
except Exception:  # pragma: no cover - exercised on the target runtime
    cv2 = None  # type: ignore[assignment]

_PROBABILITY_ROUNDING_TOLERANCE = 1e-6


@dataclass(frozen=True)
class ModelEvidence:
    """One frame of detector and classifier evidence.

    ``box`` is an exclusive pixel ``(x0, y0, x1, y1)`` rectangle relative to
    the BGR ROI passed to :meth:`PedestrianModel.classify`.
    """

    color: RawColor
    confidence: float
    reason: str
    box: tuple[int, int, int, int] | None = None
    detector_confidence: float = 0.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "confidence", _unit_score(self.confidence))
        object.__setattr__(self, "detector_confidence", _unit_score(self.detector_confidence))


@dataclass(frozen=True)
class _Detection:
    class_id: int
    score: float
    box: tuple[float, float, float, float]


def _unit_score(value: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    if not math.isfinite(number):
        return 0.0
    return min(1.0, max(0.0, number))


def _manifest_candidates() -> list[Path]:
    candidates: list[Path] = []
    module_dir = Path(__file__).resolve().parent
    candidates.extend(
        [module_dir / "model_manifest.json", module_dir.parent / "model_manifest.json"]
    )
    try:
        from ament_index_python.packages import get_package_share_directory

        candidates.append(Path(get_package_share_directory("gouda_signal")) / "model_manifest.json")
    except Exception:
        pass
    return candidates


def _load_manifest() -> dict[str, Any]:
    path = next((item for item in _manifest_candidates() if item.is_file()), None)
    if path is None:
        raise RuntimeError("model manifest is missing")
    with path.open("r", encoding="utf-8") as stream:
        manifest = json.load(stream)
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1:
        raise RuntimeError("unsupported model manifest")
    if manifest.get("license") != "Apache-2.0":
        raise RuntimeError("unexpected model license metadata")
    models = manifest.get("models")
    if not isinstance(models, dict) or not {"detector", "classifier"}.issubset(models):
        raise RuntimeError("model manifest is incomplete")
    return manifest


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _version_tuple(value: str) -> tuple[int, ...]:
    match = re.match(r"^(\d+(?:\.\d+)+)", value)
    if match is None:
        return ()
    return tuple(int(part) for part in match.group(1).split("."))


def _shape_matches(actual: Sequence[Any], expected: Sequence[Any]) -> bool:
    if len(actual) != len(expected):
        return False
    for actual_dim, expected_dim in zip(actual, expected):
        if not isinstance(actual_dim, numbers.Integral) or int(actual_dim) != int(expected_dim):
            return False
    return True


def _require_nchw_float(session: Any, input_shape: Sequence[int], output_shape: Sequence[int]) -> tuple[str, str]:
    inputs = session.get_inputs()
    outputs = session.get_outputs()
    if len(inputs) != 1 or len(outputs) != 1:
        raise RuntimeError("model must expose exactly one input and one output")
    input_meta, output_meta = inputs[0], outputs[0]
    if input_meta.type != "tensor(float)" or output_meta.type != "tensor(float)":
        raise RuntimeError("model input and output must be float tensors")
    if not _shape_matches(input_meta.shape, input_shape):
        raise RuntimeError("model input tensor shape does not match manifest")
    if not _shape_matches(output_meta.shape, output_shape):
        raise RuntimeError("model output tensor shape does not match manifest")
    return input_meta.name, output_meta.name


def _validate_u8_bgr(image: Any) -> tuple[int, int]:
    if np is None or not isinstance(image, np.ndarray):
        raise ValueError("image must be a NumPy array")
    if image.ndim != 3 or image.shape[2] != 3 or image.dtype != np.uint8:
        raise ValueError("image must be a uint8 BGR image with three channels")
    height, width = int(image.shape[0]), int(image.shape[1])
    if height < 2 or width < 2:
        raise ValueError("image is too small")
    return height, width


def _letterbox_bgr_detector(image: Any, width: int = 416, height: int = 416) -> Any:
    """Autoware YOLOX detector input: BGR, raw scale, 114-valued padding."""

    source_height, source_width = _validate_u8_bgr(image)
    if cv2 is None or np is None:
        raise RuntimeError("OpenCV and NumPy are required")
    scale = min(float(width) / source_width, float(height) / source_height)
    resized_width = int(source_width * scale)
    resized_height = int(source_height * scale)
    if resized_width < 2 or resized_height < 2:
        raise ValueError("resized image is too small")
    resized = cv2.resize(image, (resized_width, resized_height), interpolation=cv2.INTER_LINEAR)
    canvas = np.full((height, width, 3), 114, dtype=np.uint8)
    canvas[:resized_height, :resized_width] = resized
    tensor = canvas.astype(np.float32).transpose(2, 0, 1)[None, ...]
    return np.ascontiguousarray(tensor)


def _letterbox_rgb_classifier(
    image: Any,
    width: int = 224,
    height: int = 224,
    mean: Sequence[float] = (123.675, 116.28, 103.53),
    std: Sequence[float] = (58.395, 57.12, 57.375),
) -> Any:
    """Autoware CNN input: RGB, top-left letterbox, then channel normalization."""

    source_height, source_width = _validate_u8_bgr(image)
    if cv2 is None or np is None:
        raise RuntimeError("OpenCV and NumPy are required")
    if (
        len(mean) != 3
        or len(std) != 3
        or any(not math.isfinite(float(value)) for value in (*mean, *std))
        or any(float(value) <= 0.0 for value in std)
    ):
        raise ValueError("classifier normalization metadata is invalid")
    scale = min(float(width) / source_width, float(height) / source_height)
    resized_width = int(source_width * scale)
    resized_height = int(source_height * scale)
    if resized_width < 2 or resized_height < 2:
        raise ValueError("resized image is too small")
    rgb = np.ascontiguousarray(image[..., ::-1])
    resized = cv2.resize(rgb, (resized_width, resized_height), interpolation=cv2.INTER_LINEAR)
    canvas = np.zeros((height, width, 3), dtype=np.uint8)
    canvas[:resized_height, :resized_width] = resized
    mean_array = np.asarray(mean, dtype=np.float32).reshape(1, 1, 3)
    std_array = np.asarray(std, dtype=np.float32).reshape(1, 1, 3)
    tensor = ((canvas.astype(np.float32) - mean_array) / std_array).transpose(2, 0, 1)[None, ...]
    return np.ascontiguousarray(tensor, dtype=np.float32)


def _iou(left: _Detection, right: _Detection) -> float:
    lx0, ly0, lx1, ly1 = left.box
    rx0, ry0, rx1, ry1 = right.box
    ix0, iy0 = max(lx0, rx0), max(ly0, ry0)
    ix1, iy1 = min(lx1, rx1), min(ly1, ry1)
    intersection = max(0.0, ix1 - ix0) * max(0.0, iy1 - iy0)
    left_area = max(0.0, lx1 - lx0) * max(0.0, ly1 - ly0)
    right_area = max(0.0, rx1 - rx0) * max(0.0, ry1 - ry0)
    union = left_area + right_area - intersection
    return intersection / union if union > 0.0 else 0.0


def _nms_class_agnostic(candidates: Sequence[_Detection], threshold: float) -> list[_Detection]:
    kept: list[_Detection] = []
    for candidate in sorted(candidates, key=lambda item: item.score, reverse=True):
        if all(_iou(candidate, previous) <= threshold for previous in kept):
            kept.append(candidate)
    return kept


def _decode_yolox_output(
    output: Any,
    image_shape: tuple[int, int],
    *,
    input_size: tuple[int, int] = (416, 416),
    strides: Sequence[int] = (8, 16, 32),
    score_threshold: float = 0.3,
    nms_threshold: float = 0.65,
) -> list[_Detection]:
    """Decode Autoware's raw YOLOX output and map boxes into the source ROI."""

    if np is None:
        raise RuntimeError("NumPy is required")
    values = np.asarray(output, dtype=np.float32)
    if values.ndim == 3 and values.shape[0] == 1:
        values = values[0]
    input_width, input_height = int(input_size[0]), int(input_size[1])
    expected_rows = sum((input_width // stride) * (input_height // stride) for stride in strides)
    if values.shape != (expected_rows, 8):
        raise ValueError("YOLOX output tensor shape does not match manifest")
    if not np.isfinite(values).all():
        raise ValueError("YOLOX output contains non-finite values")
    if not math.isfinite(score_threshold) or not 0.0 <= score_threshold <= 1.0:
        raise ValueError("invalid detector score threshold")
    if not math.isfinite(nms_threshold) or not 0.0 <= nms_threshold <= 1.0:
        raise ValueError("invalid detector NMS threshold")

    candidates: list[_Detection] = []
    anchor = 0
    for stride in strides:
        grid_width, grid_height = input_width // stride, input_height // stride
        for grid_y in range(grid_height):
            for grid_x in range(grid_width):
                row = values[anchor]
                anchor += 1
                objectness = float(row[4])
                class_scores = row[5:8]
                if (
                    objectness < -_PROBABILITY_ROUNDING_TOLERANCE
                    or objectness > 1.0 + _PROBABILITY_ROUNDING_TOLERANCE
                    or np.any(class_scores < -_PROBABILITY_ROUNDING_TOLERANCE)
                    or np.any(class_scores > 1.0 + _PROBABILITY_ROUNDING_TOLERANCE)
                ):
                    raise ValueError("YOLOX confidence values are outside [0, 1]")
                objectness = min(1.0, max(0.0, objectness))
                class_scores = np.clip(class_scores, 0.0, 1.0)
                center_x = (float(row[0]) + grid_x) * stride
                center_y = (float(row[1]) + grid_y) * stride
                try:
                    box_width = math.exp(float(row[2])) * stride
                    box_height = math.exp(float(row[3])) * stride
                except OverflowError as exc:
                    raise ValueError("YOLOX box dimensions overflow") from exc
                if not math.isfinite(box_width) or not math.isfinite(box_height):
                    raise ValueError("YOLOX box dimensions are non-finite")
                x0, y0 = center_x - box_width * 0.5, center_y - box_height * 0.5
                x1, y1 = center_x + box_width * 0.5, center_y + box_height * 0.5
                for class_id, class_score in enumerate(class_scores):
                    score = objectness * float(class_score)
                    if score > score_threshold:
                        candidates.append(_Detection(class_id, score, (x0, y0, x1, y1)))

    height, width = image_shape
    if height < 2 or width < 2:
        raise ValueError("source image dimensions are invalid")
    scale = min(float(input_width) / width, float(input_height) / height)
    detections: list[_Detection] = []
    for item in _nms_class_agnostic(candidates, nms_threshold):
        x0, y0, x1, y1 = item.box
        x0 = min(float(width - 1), max(0.0, x0 / scale))
        y0 = min(float(height - 1), max(0.0, y0 / scale))
        x1 = min(float(width - 1), max(0.0, x1 / scale))
        y1 = min(float(height - 1), max(0.0, y1 / scale))
        if x1 > x0 and y1 > y0:
            detections.append(_Detection(item.class_id, item.score, (x0, y0, x1, y1)))
    return detections


def _classify_probabilities(
    output: Any, labels: Sequence[str], confidence_threshold: float
) -> tuple[RawColor, float, str]:
    if np is None:
        raise RuntimeError("NumPy is required")
    probabilities = np.asarray(output, dtype=np.float32)
    if probabilities.shape == (1, len(labels)):
        probabilities = probabilities[0]
    if probabilities.shape != (len(labels),) or len(labels) != 3:
        raise ValueError("classifier output tensor shape does not match manifest")
    if not np.isfinite(probabilities).all():
        raise ValueError("classifier output contains non-finite values")
    if (
        np.any(probabilities < -_PROBABILITY_ROUNDING_TOLERANCE)
        or np.any(probabilities > 1.0 + _PROBABILITY_ROUNDING_TOLERANCE)
    ):
        raise ValueError("classifier probabilities are outside [0, 1]")
    probabilities = np.clip(probabilities, 0.0, 1.0)
    if not math.isfinite(float(probabilities.sum())) or not math.isclose(
        float(probabilities.sum()), 1.0, rel_tol=1e-3, abs_tol=1e-3
    ):
        raise ValueError("classifier output is not a probability distribution")
    index = int(np.argmax(probabilities))
    confidence = float(probabilities[index])
    if confidence < confidence_threshold:
        return RawColor.NONE, confidence, "classifier_low_confidence"
    label = labels[index]
    if label == "red":
        return RawColor.RED, confidence, "classifier_red"
    if label == "green":
        return RawColor.GREEN, confidence, "classifier_green"
    if label == "unknown":
        return RawColor.NONE, confidence, "classifier_unknown"
    raise ValueError("classifier label is unsupported")


def default_model_directory() -> Path:
    """Return the model store selected by the installer/launcher environment."""

    override = os.environ.get("GOUDA_SIGNAL_MODEL_DIR")
    if override:
        return Path(override).expanduser()
    workspace = os.environ.get("GOUDA_WORKSPACE")
    root = Path(workspace).expanduser() if workspace else Path.home() / "gouda_ws"
    return root / "models" / "pedestrian_signal"


class PedestrianModel:
    """Find one pedestrian signal in a confirmed BGR ROI, then classify its lamp."""

    def __init__(self, model_dir: Path | None = None, confidence_threshold: float = 0.8) -> None:
        if not math.isfinite(float(confidence_threshold)) or not 0.0 <= float(confidence_threshold) <= 1.0:
            raise ValueError("confidence_threshold must be finite and between 0 and 1")
        self.model_dir = (
            Path(model_dir).expanduser() if model_dir is not None else default_model_directory()
        )
        self.confidence_threshold = float(confidence_threshold)
        self.available = False
        self.load_error: str | None = None
        self._manifest: dict[str, Any] = {}
        self._detector_session: Any = None
        self._classifier_session: Any = None
        self._detector_input_name = ""
        self._detector_output_name = ""
        self._classifier_input_name = ""
        self._classifier_output_name = ""

        try:
            self._load()
            self.available = True
        except Exception as exc:
            # Startup and per-frame failures are represented as UNKNOWN to the
            # existing observation state machine. There is no HSV fallback.
            self.load_error = f"{type(exc).__name__}: {exc}"
            self._detector_session = None
            self._classifier_session = None

    def _load(self) -> None:
        if np is None or cv2 is None:
            raise RuntimeError("NumPy and OpenCV are required")
        manifest = _load_manifest()
        backend = manifest.get("backend")
        if not isinstance(backend, Mapping):
            raise RuntimeError("backend metadata is missing")
        if backend.get("name") != "onnxruntime" or backend.get("providers") != ["CPUExecutionProvider"]:
            raise RuntimeError("manifest does not request ONNX Runtime CPU")

        import onnxruntime as ort

        actual_version = _version_tuple(str(ort.__version__))
        minimum_version = _version_tuple(str(backend.get("minimum_version", "")))
        if not actual_version or not minimum_version or actual_version < minimum_version:
            raise RuntimeError("ONNX Runtime is missing or older than the manifest requirement")

        detector_spec = manifest["models"]["detector"]
        classifier_spec = manifest["models"]["classifier"]
        paths = {
            "detector": self._verified_model_path(detector_spec),
            "classifier": self._verified_model_path(classifier_spec),
        }
        options = ort.SessionOptions()
        options.intra_op_num_threads = int(backend.get("intra_op_threads", 2))
        options.inter_op_num_threads = int(backend.get("inter_op_threads", 1))
        options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL

        detector_session = ort.InferenceSession(
            str(paths["detector"]), sess_options=options, providers=["CPUExecutionProvider"]
        )
        classifier_session = ort.InferenceSession(
            str(paths["classifier"]), sess_options=options, providers=["CPUExecutionProvider"]
        )
        detector_input, detector_output = _require_nchw_float(
            detector_session,
            detector_spec["input"]["shape"],
            detector_spec["output"]["shape"],
        )
        classifier_input, classifier_output = _require_nchw_float(
            classifier_session,
            classifier_spec["input"]["shape"],
            classifier_spec["output"]["shape"],
        )
        self._manifest = manifest
        self._detector_session = detector_session
        self._classifier_session = classifier_session
        self._detector_input_name, self._detector_output_name = detector_input, detector_output
        self._classifier_input_name, self._classifier_output_name = classifier_input, classifier_output

    def _verified_model_path(self, spec: Mapping[str, Any]) -> Path:
        filename = spec.get("filename")
        if not isinstance(filename, str) or Path(filename).name != filename:
            raise RuntimeError("model filename is invalid")
        path = self.model_dir / filename
        if not path.is_file():
            raise FileNotFoundError(f"model file is missing: {filename}")
        expected_size = int(spec["size_bytes"])
        if path.stat().st_size != expected_size:
            raise RuntimeError(f"model file size mismatch: {filename}")
        if _sha256(path) != str(spec["sha256"]).lower():
            raise RuntimeError(f"model SHA-256 mismatch: {filename}")
        return path

    def classify(self, bgr_roi: Any) -> ModelEvidence:
        """Return color evidence for one fresh, manually confirmed BGR search ROI."""

        if not self.available:
            return ModelEvidence(RawColor.NONE, 0.0, "model_unavailable")
        try:
            height, width = _validate_u8_bgr(bgr_roi)
            detector_spec = self._manifest["models"]["detector"]
            detector_width = int(detector_spec["input"]["shape"][3])
            detector_height = int(detector_spec["input"]["shape"][2])
            detector_tensor = _letterbox_bgr_detector(bgr_roi, detector_width, detector_height)
            detector_values = self._detector_session.run(
                [self._detector_output_name], {self._detector_input_name: detector_tensor}
            )[0]
            detections = _decode_yolox_output(
                detector_values,
                (height, width),
                input_size=(detector_width, detector_height),
                strides=detector_spec["output"]["strides"],
                score_threshold=float(detector_spec["score_threshold"]),
                nms_threshold=float(detector_spec["nms_threshold"]),
            )
        except Exception:
            return ModelEvidence(RawColor.NONE, 0.0, "detector_inference_error")

        pedestrian_id = int(self._manifest["models"]["detector"]["class_ids"]["pedestrian_traffic_light"])
        pedestrians = [item for item in detections if item.class_id == pedestrian_id]
        if not pedestrians:
            return ModelEvidence(RawColor.NONE, 0.0, "detector_no_pedestrian")
        if len(pedestrians) != 1:
            return ModelEvidence(
                RawColor.NONE,
                0.0,
                "detector_multiple_pedestrians",
                detector_confidence=max(item.score for item in pedestrians),
            )

        detection = pedestrians[0]
        x0 = max(0, min(width - 1, math.floor(detection.box[0])))
        y0 = max(0, min(height - 1, math.floor(detection.box[1])))
        x1 = max(x0 + 1, min(width, math.ceil(detection.box[2])))
        y1 = max(y0 + 1, min(height, math.ceil(detection.box[3])))
        box = (x0, y0, x1, y1)
        signal_crop = bgr_roi[y0:y1, x0:x1]

        try:
            classifier_spec = self._manifest["models"]["classifier"]
            classifier_width = int(classifier_spec["input"]["shape"][3])
            classifier_height = int(classifier_spec["input"]["shape"][2])
            normalization = classifier_spec["input"]["normalization"]
            classifier_tensor = _letterbox_rgb_classifier(
                signal_crop,
                classifier_width,
                classifier_height,
                mean=normalization["mean"],
                std=normalization["std"],
            )
            classifier_values = self._classifier_session.run(
                [self._classifier_output_name], {self._classifier_input_name: classifier_tensor}
            )[0]
            color, confidence, reason = _classify_probabilities(
                classifier_values,
                classifier_spec["output"]["labels"],
                self.confidence_threshold,
            )
            return ModelEvidence(color, confidence, reason, box, detection.score)
        except Exception:
            return ModelEvidence(
                RawColor.NONE,
                0.0,
                "classifier_inference_error",
                box,
                detection.score,
            )
