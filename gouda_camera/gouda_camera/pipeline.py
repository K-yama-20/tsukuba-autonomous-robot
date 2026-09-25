"""Validated GStreamer pipelines for network camera sources."""
from __future__ import annotations

from urllib.parse import urlsplit


SUPPORTED_TRANSPORTS = ("auto", "rtsp", "http_mjpeg", "uri")


def _quote(value: str) -> str:
    """Quote a GStreamer property value without allowing pipeline injection."""
    if not isinstance(value, str) or not value:
        raise ValueError("stream URL is required")
    if any(char in value for char in ("\0", "\r", "\n")):
        raise ValueError("stream URL contains an invalid control character")
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _validate_url(url: str) -> str:
    parsed = urlsplit(url)
    if parsed.scheme not in ("rtsp", "rtsps", "http", "https"):
        raise ValueError("stream URL must use rtsp, rtsps, http, or https")
    if not parsed.hostname:
        raise ValueError("stream URL must include a host")
    return parsed.scheme


def build_pipeline(url: str, transport: str = "auto", latency_ms: int = 500,
                   width: int = 0, height: int = 0) -> str:
    """Build a gscam pipeline for an iPhone network-camera application.

    Width and height must either both be zero (preserve the source size) or both
    be positive. The resulting pipeline intentionally has no appsink because
    gscam appends its own sink.
    """
    scheme = _validate_url(url)
    if transport not in SUPPORTED_TRANSPORTS:
        raise ValueError("transport must be auto, rtsp, http_mjpeg, or uri")
    if type(latency_ms) is not int or not 0 <= latency_ms <= 10_000:
        raise ValueError("latency_ms must be an integer between 0 and 10000")
    if type(width) is not int or type(height) is not int:
        raise ValueError("width and height must be integers")
    if (width == 0) != (height == 0) or width < 0 or height < 0:
        raise ValueError("width and height must both be zero or both be positive")

    selected = transport
    if selected == "auto":
        selected = "rtsp" if scheme in ("rtsp", "rtsps") else "uri"
    if selected == "rtsp" and scheme not in ("rtsp", "rtsps"):
        raise ValueError("rtsp transport requires an rtsp:// or rtsps:// URL")
    if selected == "http_mjpeg" and scheme not in ("http", "https"):
        raise ValueError("http_mjpeg transport requires an http:// or https:// URL")

    location = _quote(url)
    if selected == "rtsp":
        source = (f"rtspsrc location={location} protocols=tcp latency={latency_ms} "
                  "drop-on-latency=true ! decodebin")
    elif selected == "http_mjpeg":
        source = (f"souphttpsrc location={location} is-live=true do-timestamp=true "
                  "! multipartdemux ! jpegdec")
    else:
        source = f"uridecodebin uri={location}"

    stages = [source, "queue leaky=downstream max-size-buffers=2", "videoconvert"]
    if width:
        stages.extend(["videoscale", f"video/x-raw,format=RGB,width={width},height={height}"])
    else:
        stages.append("video/x-raw,format=RGB")
    return " ! ".join(stages)
