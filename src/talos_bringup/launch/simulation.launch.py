import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    IncludeLaunchDescription,
    LogInfo,
)
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    pkg_talos_bringup = get_package_share_directory('talos_bringup')
    pkg_talos_gazebo = get_package_share_directory('talos_gazebo')
    pkg_nav2_bringup = get_package_share_directory('nav2_bringup')

    use_sim_time = LaunchConfiguration('use_sim_time', default='true')
    map_file = LaunchConfiguration('map')
    use_yolo = LaunchConfiguration('use_yolo')

    nav2_params_file = os.path.join(pkg_talos_bringup, 'config', 'nav2_params.yaml')

    # 1. Gazebo simulation
    gazebo_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(pkg_talos_gazebo, 'launch', 'gazebo.launch.py')
        ),
    )

    # 2. Nav2 navigation stack
    nav2_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(pkg_nav2_bringup, 'launch', 'bringup_launch.py')
        ),
        launch_arguments={
            'map': map_file,
            'use_sim_time': use_sim_time,
            'params_file': nav2_params_file,
        }.items(),
    )

    # 3. RViz
    rviz_config = os.path.join(
        pkg_nav2_bringup, 'rviz', 'nav2_default_view.rviz'
    )

    use_rviz = LaunchConfiguration('use_rviz')

    rviz_node = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2',
        arguments=['-d', rviz_config],
        parameters=[{'use_sim_time': True}],
        output='screen',
        condition=IfCondition(use_rviz),
    )

    # 4. YOLO detection node (optional)
    yolo_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(
                get_package_share_directory('yolo_bringup'),
                'launch',
                'yolo.launch.py',
            )
        ),
        launch_arguments={
            'model': 'yolov8n.pt',
            'input_image_topic': '/camera/image_raw',
            'threshold': '0.5',
            'use_sim_time': 'true',
        }.items(),
        condition=IfCondition(use_yolo),
    )

    yolo_skip_msg = LogInfo(
        msg='YOLO disabled. Launch with use_yolo:=true to enable.',
        condition=IfCondition(LaunchConfiguration('use_yolo', default='false')),
    )

    return LaunchDescription([
        DeclareLaunchArgument(
            'map',
            default_value=os.path.join(
                pkg_talos_bringup, 'maps', 'disaster_map.yaml'
            ),
            description='Full path to map yaml file',
        ),
        DeclareLaunchArgument(
            'use_sim_time',
            default_value='true',
        ),
        DeclareLaunchArgument(
            'use_yolo',
            default_value='false',
            description='Enable YOLO detection node',
        ),
        DeclareLaunchArgument(
            'use_rviz',
            default_value='true',
            description='Launch RViz2 visualization',
        ),
        gazebo_launch,
        nav2_launch,
        rviz_node,
        yolo_launch,
    ])
