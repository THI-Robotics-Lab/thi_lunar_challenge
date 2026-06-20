from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        Node(
            package='rover_autonomy',
            executable='autonomy_controller',
            name='autonomy_controller',
            output='screen',
            parameters=[{'use_sim_time': True}],
        ),
    ])
