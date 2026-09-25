from gouda_signal.inference import box_iou, normalized_box


def test_target_boxes_are_normalized_to_search_roi_and_associated_by_overlap():
    first = normalized_box((10, 10, 30, 30), 100, 100)
    nearby = normalized_box((12, 10, 32, 30), 100, 100)
    different = normalized_box((70, 70, 90, 90), 100, 100)

    assert first == (0.1, 0.1, 0.3, 0.3)
    assert box_iou(first, nearby) > 0.3
    assert box_iou(first, different) == 0.0
    assert box_iou(None, first) == 0.0
