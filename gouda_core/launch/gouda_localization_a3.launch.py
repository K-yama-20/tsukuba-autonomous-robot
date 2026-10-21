"""The upstream parts of the global localization trial A3 (ND-07; REV-128, DEC-115 / DEC-203). Started and stopped ONLY by
gouda_global_localization (configure / cleanup), never by gouda.sh directly (the one start path stays gouda.sh start: DEC-090).

All parts are unmodified upstream packages with their installed parameter files; only the map location, the point filter sizes
(PRM-79..81, passed by gouda_global_localization from the generated parameter file) and the interface names are added:
  sensors/xt32/points (IFD-21) -> pcl_ros CropBox (keep inside +-points_far_crop_m) -> pcl_ros CropBox (drop inside
  +-points_near_crop_m, the vehicle and very near points) -> pcl_ros VoxelGrid (points_voxel_leaf_m) -> points_downsampled
  autoware_pointcloud_map_loader: <map_directory>/pointcloud_map/ (tiles and metadata.yaml, map conversion PRM-94 / PRM-95);
    partial loading only, as in the evaluation (FILE-LOCALIZATION-EVAL: map_175857.param.yaml)
  autoware_ndt_scan_matcher: points_downsampled + the EKF pose -> ndt_pose_with_covariance; ndt_align_srv; ndt_trigger_node
  autoware_ekf_localizer: ndt_pose_with_covariance + twist_with_covariance (from gouda_global_localization) ->
    ekf_pose_with_covariance; initialpose3d; ekf_trigger_node
Every topic and service is inside the namespace localization/a3. The EKF's and the NDT's /tf are remapped to tf_ekf / tf_ndt
inside the namespace and nobody reads them: map->odom is published by gouda_global_localization alone (D-17, RQ-I004). Their
TF listeners then see only /tf_static (base_link -> sensors, ND-13), which is all they need. /diagnostics is not remapped.
"""
import os
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

NS = 'localization/a3'


def _nodes(context, *args, **kwargs):
    from ament_index_python.packages import get_package_share_directory
    arg = lambda n: LaunchConfiguration(n).perform(context)
    map_dir = arg('map_directory')
    near, far, leaf = float(arg('points_near_crop_m')), float(arg('points_far_crop_m')), float(arg('points_voxel_leaf_m'))
    share = get_package_share_directory
    box = lambda h: {'min_x': -h, 'max_x': h, 'min_y': -h, 'max_y': h, 'min_z': -h, 'max_z': h, 'keep_organized': False}
    tiles = os.path.join(map_dir, 'pointcloud_map')
    return [
        Node(package='pcl_ros', executable='filter_crop_box_node', name='points_crop_far', namespace=NS, output='screen',
             parameters=[dict(box(far), negative=False)], remappings=[('input', '/sensors/xt32/points'), ('output', 'points_cropped_far')]),
        Node(package='pcl_ros', executable='filter_crop_box_node', name='points_crop_near', namespace=NS, output='screen',
             parameters=[dict(box(near), negative=True)], remappings=[('input', 'points_cropped_far'), ('output', 'points_cropped')]),
        Node(package='pcl_ros', executable='filter_voxel_grid_node', name='points_voxel', namespace=NS, output='screen',
             parameters=[{'leaf_size': leaf, 'filter_field_name': ''}], remappings=[('input', 'points_cropped'), ('output', 'points_downsampled')]),
        Node(package='autoware_map_loader', executable='autoware_pointcloud_map_loader', name='pointcloud_map_loader', namespace=NS, output='screen',
             parameters=[os.path.join(share('autoware_map_loader'), 'config', 'pointcloud_map_loader.param.yaml'),
                         {'pcd_paths_or_directory': [tiles + '/'], 'pcd_metadata_path': os.path.join(tiles, 'metadata.yaml'),
                          'enable_whole_load': False, 'enable_downsampled_whole_load': False, 'enable_partial_load': True, 'enable_selected_load': False}]),
        Node(package='autoware_ndt_scan_matcher', executable='autoware_ndt_scan_matcher_node', name='ndt_scan_matcher', namespace=NS, output='screen',
             parameters=[os.path.join(share('autoware_ndt_scan_matcher'), 'config', 'ndt_scan_matcher.param.yaml')],
             remappings=[('points_raw', 'points_downsampled'), ('trigger_node_srv', 'ndt_trigger_node'),
                         ('pcd_loader_service', 'service/get_differential_pcd_map'), ('/tf', 'tf_ndt')]),
        Node(package='autoware_ekf_localizer', executable='autoware_ekf_localizer_node', name='ekf_localizer', namespace=NS, output='screen',
             parameters=[os.path.join(share('autoware_ekf_localizer'), 'config', 'ekf_localizer.param.yaml')],
             remappings=[('in_pose_with_covariance', 'ndt_pose_with_covariance'), ('in_twist_with_covariance', 'twist_with_covariance'),
                         ('initialpose', 'initialpose3d'), ('trigger_node_srv', 'ekf_trigger_node'), ('/tf', 'tf_ekf')]),
    ]


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('map_directory', description='converted map revision (with pointcloud_map/), set by gouda_global_localization'),
        DeclareLaunchArgument('points_near_crop_m', description='PRM-79 (from gouda_global_localization)'),
        DeclareLaunchArgument('points_far_crop_m', description='PRM-80'),
        DeclareLaunchArgument('points_voxel_leaf_m', description='PRM-81'),
        OpaqueFunction(function=_nodes),
    ])
