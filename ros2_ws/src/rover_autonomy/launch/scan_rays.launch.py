from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        Node(
            package='rover_autonomy',
            executable='scan_rays',
            name='scan_rays',
            output='screen',
            parameters=[{'use_sim_time': True}],
        ),
    ])
