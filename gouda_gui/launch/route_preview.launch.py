"""Short-lived, planner-only Nav2 instance for saved-grid preview."""
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, SetEnvironmentVariable
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.actions import SetParameter


def generate_launch_description():
    params = LaunchConfiguration('params_file')
    return LaunchDescription([
        DeclareLaunchArgument('params_file'),
        SetParameter(name='use_sim_time', value=False),
        SetEnvironmentVariable('ROS_AUTOMATIC_DISCOVERY_RANGE', 'LOCALHOST'),
        Node(package='nav2_planner', executable='planner_server', name='planner_server',
             namespace='gouda_route_preview', output='screen', parameters=[params],
             remappings=[('/map', '/gouda/route_preview/map'), ('/tf', 'tf'), ('/tf_static', 'tf_static')]),
        Node(package='nav2_lifecycle_manager', executable='lifecycle_manager',
             name='lifecycle_manager_planner', namespace='gouda_route_preview', output='screen',
             parameters=[{'autostart': True, 'node_names': ['planner_server'],
                          'bond_timeout': 2.0}]),
    ])
