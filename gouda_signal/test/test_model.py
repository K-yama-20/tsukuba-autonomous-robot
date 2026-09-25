import math

import numpy as np
import pytest

from gouda_signal.classifier import RawColor
from gouda_signal.model import (
    PedestrianModel,
    _classify_probabilities,
    _decode_yolox_output,
    _letterbox_bgr_detector,
    _letterbox_rgb_classifier,
    default_model_directory,
)


def _prediction_tensor():
    return np.zeros((1, 3549, 8), dtype=np.float32)


def _add_detection(predictions, grid_x, grid_y, *, vehicle=0.0, pedestrian=0.0):
    anchor = grid_y * 52 + grid_x
    predictions[0, anchor] = (
        0.5,
        0.5,
        math.log(4.0),
        math.log(4.0),
        0.99,
        0.0,
        vehicle,
        pedestrian,
    )


def test_yolox_decoder_decodes_stride_grid_objectness_and_pedestrian_class():
    predictions = _prediction_tensor()
    _add_detection(predictions, 10, 10, pedestrian=0.9)

    detections = _decode_yolox_output(predictions, (416, 416))

    assert len(detections) == 1
    assert detections[0].class_id == 2
    assert detections[0].score == pytest.approx(0.99 * 0.9)
    assert detections[0].box == pytest.approx((68.0, 68.0, 100.0, 100.0))


def test_yolox_decoder_keeps_vehicle_filtered_and_reports_separate_pedestrians():
    vehicle_only = _prediction_tensor()
    _add_detection(vehicle_only, 10, 10, vehicle=0.9)
    detections = _decode_yolox_output(vehicle_only, (416, 416))
    assert [item.class_id for item in detections] == [1]

    two_pedestrians = _prediction_tensor()
    _add_detection(two_pedestrians, 10, 10, pedestrian=0.9)
    _add_detection(two_pedestrians, 30, 30, pedestrian=0.85)
    detections = _decode_yolox_output(two_pedestrians, (416, 416))
    assert [item.class_id for item in detections] == [2, 2]


def test_yolox_decoder_rejects_bad_shape_and_non_finite_outputs():
    with pytest.raises(ValueError, match="shape"):
        _decode_yolox_output(np.zeros((1, 10, 8), dtype=np.float32), (416, 416))

    predictions = _prediction_tensor()
    predictions[0, 0, 4] = np.nan
    with pytest.raises(ValueError, match="non-finite"):
        _decode_yolox_output(predictions, (416, 416))


def test_yolox_decoder_clips_only_sigmoid_roundoff_at_probability_boundaries():
    predictions = _prediction_tensor()
    _add_detection(predictions, 10, 10, pedestrian=0.9)
    predictions[0, 10 * 52 + 10, 5] = -5.9604645e-08

    detections = _decode_yolox_output(predictions, (416, 416))

    assert len(detections) == 1
    assert detections[0].class_id == 2


def test_detector_preprocessing_preserves_bgr_and_uses_114_padding():
    image = np.zeros((2, 4, 3), dtype=np.uint8)
    image[0, 0] = (10, 20, 30)

    tensor = _letterbox_bgr_detector(image, width=4, height=4)

    assert tensor.shape == (1, 3, 4, 4)
    assert tensor[0, :, 0, 0].tolist() == [10.0, 20.0, 30.0]
    assert tensor[0, :, 3, 0].tolist() == [114.0, 114.0, 114.0]


def test_classifier_preprocessing_swaps_to_rgb_and_normalizes_before_inference():
    image = np.zeros((2, 4, 3), dtype=np.uint8)
    image[:] = (0, 0, 255)  # BGR red.

    tensor = _letterbox_rgb_classifier(image, width=4, height=4)

    assert tensor.shape == (1, 3, 4, 4)
    assert tensor[0, 0, 0, 0] == pytest.approx((255.0 - 123.675) / 58.395)
    assert tensor[0, 2, 0, 0] == pytest.approx((0.0 - 103.53) / 57.375)
    assert tensor[0, 0, 3, 0] == pytest.approx((0.0 - 123.675) / 58.395)


@pytest.mark.parametrize(
    ("scores", "expected_color", "expected_reason"),
    [
        ([0.91, 0.05, 0.04], RawColor.RED, "classifier_red"),
        ([0.05, 0.91, 0.04], RawColor.GREEN, "classifier_green"),
        ([0.05, 0.04, 0.91], RawColor.NONE, "classifier_unknown"),
        ([0.41, 0.36, 0.23], RawColor.NONE, "classifier_low_confidence"),
    ],
)
def test_classifier_probabilities_map_labels_and_reject_low_confidence(
    scores, expected_color, expected_reason
):
    color, confidence, reason = _classify_probabilities(
        np.asarray([scores], dtype=np.float32), ["red", "green", "unknown"], 0.8
    )
    assert color is expected_color
    assert confidence == pytest.approx(max(scores))
    assert reason == expected_reason


def test_classifier_probabilities_rejects_non_finite_or_non_probability_outputs():
    with pytest.raises(ValueError, match="non-finite"):
        _classify_probabilities(
            np.asarray([[np.nan, 0.0, 1.0]], dtype=np.float32),
            ["red", "green", "unknown"],
            0.8,
        )
    with pytest.raises(ValueError, match="probability distribution"):
        _classify_probabilities(
            np.asarray([[0.8, 0.8, 0.1]], dtype=np.float32),
            ["red", "green", "unknown"],
            0.8,
        )
    with pytest.raises(ValueError, match=r"outside \[0, 1\]"):
        _classify_probabilities(
            np.asarray([[1.00001, 0.0, 0.0]], dtype=np.float32),
            ["red", "green", "unknown"],
            0.8,
        )


def test_classifier_probabilities_tolerate_and_clip_float_roundoff():
    color, confidence, reason = _classify_probabilities(
        np.asarray([[0.9, 0.1, -5.9604645e-08]], dtype=np.float32),
        ["red", "green", "unknown"],
        0.8,
    )
    assert color is RawColor.RED
    assert confidence == pytest.approx(0.9)
    assert reason == "classifier_red"


def test_model_missing_artifacts_fails_closed_without_hsv_fallback(tmp_path):
    model = PedestrianModel(tmp_path)

    result = model.classify(np.zeros((32, 32, 3), dtype=np.uint8))

    assert not model.available
    assert model.load_error
    assert result.color is RawColor.NONE
    assert result.confidence == 0.0
    assert result.reason == "model_unavailable"
    assert result.box is None


def test_default_model_directory_obeys_launcher_environment(monkeypatch, tmp_path):
    override = tmp_path / "explicit-model-dir"
    workspace = tmp_path / "workspace"
    monkeypatch.setenv("GOUDA_SIGNAL_MODEL_DIR", str(override))
    monkeypatch.setenv("GOUDA_WORKSPACE", str(workspace))
    assert default_model_directory() == override

    monkeypatch.delenv("GOUDA_SIGNAL_MODEL_DIR")
    assert default_model_directory() == workspace / "models" / "pedestrian_signal"
