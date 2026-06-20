"""Compatibility alias; participant scripts launch gazebo_rover.launch.py directly."""

from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    return LaunchDescription([
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource([
                FindPackageShare('rover_gazebo'), '/launch/gazebo_rover.launch.py'
            ]),
        ),
    ])
