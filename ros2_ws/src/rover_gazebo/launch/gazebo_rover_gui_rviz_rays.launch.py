from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    gazebo_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([
            FindPackageShare('rover_gazebo'), '/launch/gazebo_rover.launch.py'
        ]),
        launch_arguments={'gui': 'true'}.items(),
    )

    rviz = Node(
        package='rviz2',
        executable='rviz2',
        output='screen',
        arguments=[
            '-d',
            PathJoinSubstitution([
                FindPackageShare('rover_gazebo'), 'rviz', 'rover.rviz'
            ]),
        ],
    )

    scan_rays = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([
            FindPackageShare('rover_autonomy'), '/launch/scan_rays.launch.py'
        ]),
    )

    return LaunchDescription([
        gazebo_launch,
        rviz,
        scan_rays,
    ])
