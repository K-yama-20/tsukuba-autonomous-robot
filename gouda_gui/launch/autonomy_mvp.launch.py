"""Explicit opt-in profile; the ordinary observation launch never opens vehicle USB."""
from pathlib import Path
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, RegisterEventHandler, EmitEvent
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.event_handlers import OnProcessExit
from launch.events import Shutdown
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory
from gouda_navigation.autonomy_core import load_autonomy_settings, validate_autonomy_settings


def generate_launch_description():
    cfg=load_autonomy_settings()
    errors=validate_autonomy_settings(cfg)
    if errors:raise ValueError('; '.join(errors))
    observer=IncludeLaunchDescription(PythonLaunchDescriptionSource(str(Path(get_package_share_directory('gouda_gui'))/'launch/observation.launch.py')),
        launch_arguments={'sensors':'false','backend':'glim_imu','autonomy_mvp_enabled':'true'}.items())
    controller=Node(package='gouda_navigation',executable='autonomy_mvp',output='screen')
    actions=[observer,controller,RegisterEventHandler(OnProcessExit(target_action=controller,on_exit=[EmitEvent(event=Shutdown(reason='Autonomy controller exited'))]))]
    if cfg['hardware_enabled']:
        bridge=Node(package='gouda_vehicle',executable='hardware_bridge',output='screen',parameters=[{'hardware_enabled':True,'port':cfg['serial_port']}])
        actions.extend([bridge,RegisterEventHandler(OnProcessExit(target_action=bridge,on_exit=[EmitEvent(event=Shutdown(reason='Vehicle bridge exited'))]))])
    return LaunchDescription(actions)
