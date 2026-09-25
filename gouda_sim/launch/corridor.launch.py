"""Separate simulation settings/domain; never loads a hardware serial bridge."""
import json
import os
from pathlib import Path
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction, ExecuteProcess, RegisterEventHandler, EmitEvent, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.event_handlers import OnProcessExit
from launch.events import Shutdown
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory


def start(context):
    if os.environ.get('ROS_DOMAIN_ID')!='101':raise RuntimeError('Use scripts/gazebo.sh (isolated domain 101)')
    root=Path(os.environ['GOUDA_WORKSPACE'])
    if not (root/'.gouda-simulation').is_file():raise RuntimeError('Separate simulation data directory required')
    from gouda_navigation.autonomy_core import DEFAULT_SETTINGS,save_autonomy_settings
    from gouda_navigation.mapping import DEFAULT_SETTINGS as M,save_mapping_settings
    import copy
    a=copy.deepcopy(DEFAULT_SETTINGS)
    a.update(simulation_fixture=True,hardware_enabled=False,body_to_lidar={'translation_m':[0.,0.,1.1],'quaternion_xyzw':[0.,0.,0.,1.]},max_sensor_age_sec=2.,max_sensor_skew_sec=.15)
    # Known synthetic plant gains, not measurements or changes to hardware settings.
    a['controller'].update(linear_ff_norm_per_mps=1.,linear_kp_norm_per_mps=.4,yaw_ff_norm_per_rps=.5,yaw_kp_norm_per_rps=.3)
    save_autonomy_settings(a)
    m={**M,'clock_policy':'simulation','clock_evidence':'Gazebo /clock shared sensor timestamps','backend':'glim_imu','extrinsic_lidar_imu':{'translation_m':[0.,0.,-.6],'quaternion_xyzw':[0.,0.,0.,1.]},'point_time_field':'time','point_time_datatype':'float32','point_time_mode':'relative','point_time_unit':'seconds','imu_accel_unit':'m/s^2','imu_gyro_unit':'rad/s','imu_clock_offset_sec':0.,'lidar_clock_offset_sec':0.}
    save_mapping_settings(m)
    share=Path(get_package_share_directory('gouda_sim'))
    backend=LaunchConfiguration('lidar_backend').perform(context)
    if backend not in ('cpu_ray','gpu'):raise ValueError('lidar_backend must be cpu_ray or gpu')
    world='corridor.sdf' if backend=='cpu_ray' else 'corridor_gpu.sdf'
    import xml.etree.ElementTree as ET
    factor=float(LaunchConfiguration('real_time_factor').perform(context))
    if not 0<factor<=1:raise ValueError('real_time_factor must be in (0,1]')
    tree=ET.parse(share/'worlds'/world);tree.getroot().find('world/physics/real_time_factor').text=str(factor)
    world_path=root/'world.sdf';tree.write(world_path)
    gui=LaunchConfiguration('gui').perform(context)=='true'
    gz=ExecuteProcess(cmd=['gz','sim','-r','--render-engine','ogre']+([] if gui else ['-s'])+[str(world_path)],output='log')
    controller=Node(package='gouda_navigation',executable='autonomy_mvp',parameters=[{'use_sim_time':True,'gazebo_simulation':True}],output='screen')
    actions=[gz,Node(package='ros_gz_bridge',executable='parameter_bridge',parameters=[{'use_sim_time':True,'config_file':str(share/'config/bridge.yaml')}]),
      Node(package='gouda_sim',executable='virtual_vehicle',parameters=[{'use_sim_time':True,'left_gain':float(LaunchConfiguration('left_gain').perform(context))}]),
      Node(package='gouda_sim',executable='sensor_adapter',parameters=[{'use_sim_time':True,'estimator':LaunchConfiguration('estimator').perform(context),'lidar_backend':backend}]),controller,
      RegisterEventHandler(OnProcessExit(target_action=gz,on_exit=[EmitEvent(event=Shutdown(reason='Gazebo exited'))]))]
    if LaunchConfiguration('estimator').perform(context)=='glim':
        from gouda_navigation.mapping import make_glim_config
        make_glim_config(m,root/'glim_config')
        actions.append(IncludeLaunchDescription(PythonLaunchDescriptionSource(str(Path(get_package_share_directory('gouda_navigation'))/'launch/glim_mapping.launch.py')),launch_arguments={'settings_file':str(root/'bags/gouda/mapping.json'),'config_path':str(root/'glim_config'),'dump_path':str(root/'glim_map'),'use_sim_time':'true'}.items()))
    return actions

def generate_launch_description():
    return LaunchDescription([DeclareLaunchArgument('real_time_factor',default_value='0.5'),DeclareLaunchArgument('gui',default_value='false'),DeclareLaunchArgument('estimator',default_value='ground_truth'),DeclareLaunchArgument('lidar_backend',default_value='cpu_ray'),DeclareLaunchArgument('left_gain',default_value='.96'),OpaqueFunction(function=start)])
