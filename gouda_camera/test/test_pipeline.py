import pytest

from gouda_camera.pipeline import build_pipeline


def test_rtsp_pipeline_uses_tcp_and_receive_queue():
    pipeline = build_pipeline("rtsp://192.0.2.1:8554/live", "auto", 750, 1280, 720)
    assert "rtspsrc" in pipeline
    assert "protocols=tcp" in pipeline
    assert "latency=750" in pipeline
    assert "max-size-buffers=2" in pipeline
    assert "format=RGB,width=1280,height=720" in pipeline


def test_http_mjpeg_pipeline():
    pipeline = build_pipeline("http://192.0.2.1:8080/video", "http_mjpeg")
    assert "souphttpsrc" in pipeline
    assert "multipartdemux ! jpegdec" in pipeline
    assert pipeline.endswith("video/x-raw,format=RGB")


def test_url_is_quoted_instead_of_becoming_pipeline_syntax():
    pipeline = build_pipeline('rtsp://example.invalid/live!branch?label="front"', "rtsp")
    assert 'location="rtsp://example.invalid/live!branch?label=\\"front\\""' in pipeline


@pytest.mark.parametrize("url", ["", "file:///tmp/video.mp4", "rtsp:///missing-host", "rtsp://host\nother"])
def test_invalid_urls_are_rejected(url):
    with pytest.raises(ValueError):
        build_pipeline(url)


def test_dimensions_must_be_a_complete_pair():
    with pytest.raises(ValueError):
        build_pipeline("rtsp://192.0.2.1/live", width=1280, height=0)
