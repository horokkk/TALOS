import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    IncludeLaunchDescription,
    SetEnvironmentVariable,
)
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    pkg_talos_gazebo = get_package_share_directory('talos_gazebo')
    pkg_gazebo_ros = get_package_share_directory('gazebo_ros')
    pkg_turtlebot3_gazebo = get_package_share_directory('turtlebot3_gazebo')

    world_file = os.path.join(pkg_talos_gazebo, 'worlds', 'disaster_building.world')
    model_path = os.path.join(pkg_talos_gazebo, 'models')

    # TurtleBot3 model
    turtlebot3_model = os.environ.get('TURTLEBOT3_MODEL', 'waffle')
    urdf_file = os.path.join(
        get_package_share_directory('turtlebot3_gazebo'),
        'models',
        'turtlebot3_' + turtlebot3_model,
        'model.sdf',
    )

    # Spawn position (base)
    x_pose = LaunchConfiguration('x_pose', default='0.0')
    y_pose = LaunchConfiguration('y_pose', default='0.0')

    # Append custom model path to GAZEBO_MODEL_PATH
    gazebo_model_path = SetEnvironmentVariable(
        'GAZEBO_MODEL_PATH',
        model_path + ':' + os.environ.get('GAZEBO_MODEL_PATH', ''),
    )

    # Use headless mode by default (set use_sim_gui:=true for GUI)
    use_sim_gui = LaunchConfiguration('use_sim_gui', default='true')

    gzserver = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(pkg_gazebo_ros, 'launch', 'gzserver.launch.py')
        ),
        launch_arguments={'world': world_file}.items(),
    )

    gzclient = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(pkg_gazebo_ros, 'launch', 'gzclient.launch.py')
        ),
        condition=IfCondition(use_sim_gui),
    )

    robot_state_publisher = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(pkg_turtlebot3_gazebo, 'launch', 'robot_state_publisher.launch.py')
        ),
        launch_arguments={'use_sim_time': 'true'}.items(),
    )

    spawn_turtlebot = Node(
        package='gazebo_ros',
        executable='spawn_entity.py',
        arguments=[
            '-entity', 'turtlebot3_' + turtlebot3_model,
            '-file', urdf_file,
            '-x', x_pose,
            '-y', y_pose,
            '-z', '0.01',
        ],
        output='screen',
    )

    return LaunchDescription([
        DeclareLaunchArgument('x_pose', default_value='0.0'),
        DeclareLaunchArgument('y_pose', default_value='-6.5'),
        DeclareLaunchArgument('use_sim_gui', default_value='true'),
        gazebo_model_path,
        gzserver,
        gzclient,
        robot_state_publisher,
        spawn_turtlebot,
    ])
