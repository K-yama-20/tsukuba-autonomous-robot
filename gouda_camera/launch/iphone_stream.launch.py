"""Publish an iPhone RTSP/HTTP camera stream through the ROS camera API."""
import os

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

from gouda_camera.pipeline import build_pipeline


def start_camera(context):
    stream_url = LaunchConfiguration("stream_url").perform(context).strip()
    if not stream_url:
        stream_url = os.environ.get("GOUDA_IPHONE_STREAM_URL", "").strip()
    if not stream_url:
        raise ValueError(
            "Set GOUDA_IPHONE_STREAM_URL to the RTSP or HTTP stream shown by the iPhone app"
        )
    transport = LaunchConfiguration("transport").perform(context)
    latency_ms = int(LaunchConfiguration("latency_ms").perform(context))
    width = int(LaunchConfiguration("width").perform(context))
    height = int(LaunchConfiguration("height").perform(context))
    pipeline = build_pipeline(stream_url, transport, latency_ms, width, height)
    return [Node(
        package="gscam",
        executable="gscam_node",
        name="iphone_camera",
        output="screen",
        parameters=[{
            "camera_name": "iphone_front",
            "frame_id": LaunchConfiguration("frame_id"),
            "gscam_config": pipeline,
            "image_encoding": "rgb8",
            # Phone and vehicle-PC clocks are not synchronized. Stamp frames
            # when they arrive instead of presenting the sender clock as ROS time.
            "use_gst_timestamps": False,
            "sync_sink": False,
            "preroll": False,
            "reopen_on_eof": True,
            "use_sensor_data_qos": True,
        }],
        remappings=[
            ("camera/image_raw", "/camera/front/image_raw"),
            ("camera/camera_info", "/camera/front/camera_info"),
            ("camera/set_camera_info", "/camera/front/set_camera_info"),
        ],
    )]


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument("stream_url", default_value=""),
        DeclareLaunchArgument("transport", default_value="auto",
                              description="auto, rtsp, http_mjpeg, or uri"),
        DeclareLaunchArgument("latency_ms", default_value="500"),
        DeclareLaunchArgument("width", default_value="0",
                              description="0 preserves the source width"),
        DeclareLaunchArgument("height", default_value="0",
                              description="0 preserves the source height"),
        DeclareLaunchArgument("frame_id", default_value="iphone_camera_optical_frame"),
        OpaqueFunction(function=start_camera),
    ])
