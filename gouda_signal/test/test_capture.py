from gouda_signal.capture import parse_camera_source


def test_camera_source_accepts_indices_device_paths_files_and_uris():
    assert parse_camera_source("0") == 0
    assert parse_camera_source("/dev/video12") == 12
    assert parse_camera_source("./walk.mp4") == "./walk.mp4"
    assert parse_camera_source("rtsp://camera.local/stream") == "rtsp://camera.local/stream"


def test_empty_camera_source_is_rejected():
    try:
        parse_camera_source("   ")
    except ValueError as exc:
        assert "empty" in str(exc)
    else:
        raise AssertionError("empty source should fail")
