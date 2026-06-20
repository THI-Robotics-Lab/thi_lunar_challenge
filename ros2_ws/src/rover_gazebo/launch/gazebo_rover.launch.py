from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    ExecuteProcess,
    IncludeLaunchDescription,
    RegisterEventHandler,
    TimerAction,
)
from launch.conditions import IfCondition, UnlessCondition
from launch.event_handlers import OnProcessExit
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import Command, LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from launch_ros.substitutions import FindPackageShare
from launch.substitutions import FindExecutable


def generate_launch_description():
    gui = LaunchConfiguration('gui')
    world = LaunchConfiguration('world')
    camera_bridge_enabled = LaunchConfiguration('camera_bridge')
    rviz = LaunchConfiguration('rviz')

    robot_description = ParameterValue(Command([
        FindExecutable(name='xacro'), ' ',
        PathJoinSubstitution([
            FindPackageShare('rover_description'), 'urdf', 'student_rover.urdf.xacro'
        ])
    ]), value_type=str)

    robot_state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        output='screen',
        parameters=[{'robot_description': robot_description, 'use_sim_time': True}],
    )

    clock_bridge = Node(
        package='ros_gz_bridge',
        executable='parameter_bridge',
        output='screen',
        arguments=['/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock'],
    )

    scan_bridge = Node(
        package='ros_gz_bridge',
        executable='parameter_bridge',
        output='screen',
        arguments=['/scan@sensor_msgs/msg/LaserScan[gz.msgs.LaserScan'],
        parameters=[{'use_sim_time': True}],
    )

    camera_bridge = Node(
        package='ros_gz_bridge',
        executable='parameter_bridge',
        output='screen',
        condition=IfCondition(camera_bridge_enabled),
        arguments=[
            '/front_camera@sensor_msgs/msg/Image[gz.msgs.Image',
            '/camera_info@sensor_msgs/msg/CameraInfo[gz.msgs.CameraInfo',
        ],
        remappings=[
            ('/front_camera', '/front_camera/image_raw'),
            ('/camera_info', '/front_camera/camera_info'),
        ],
        parameters=[{'use_sim_time': True}],
    )

    rviz_node = Node(
        package='rviz2',
        executable='rviz2',
        output='screen',
        condition=IfCondition(rviz),
        arguments=[
            '-d',
            PathJoinSubstitution([
                FindPackageShare('rover_gazebo'), 'rviz', 'participant_rover.rviz'
            ]),
        ],
        parameters=[{'use_sim_time': True}],
    )

    scan_rays = Node(
        package='rover_autonomy',
        executable='scan_rays',
        name='scan_rays',
        output='screen',
        condition=IfCondition(rviz),
        parameters=[{'use_sim_time': True}],
    )

    gz_gui = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([
            FindPackageShare('ros_gz_sim'), '/launch/gz_sim.launch.py'
        ]),
        condition=IfCondition(gui),
        launch_arguments={'gz_args': ['-r ', world, ' -v 4']}.items(),
    )

    gz_headless = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([
            FindPackageShare('ros_gz_sim'), '/launch/gz_sim.launch.py'
        ]),
        condition=UnlessCondition(gui),
        launch_arguments={'gz_args': ['-s -r ', world, ' -v 4']}.items(),
    )

    spawn_rover = Node(
        package='ros_gz_sim',
        executable='create',
        output='screen',
        arguments=['-name', 'student_rover', '-topic', 'robot_description', '-z', '0.30'],
    )

    controller_startup = ExecuteProcess(
        cmd=[
            'bash', '-lc',
            'attempt=1; until '
            'ros2 run controller_manager spawner '
            'joint_state_broadcaster diff_drive_controller leg_position_controller '
            '--controller-manager /controller_manager '
            '--controller-manager-timeout 30 --activate-as-group; do '
            'echo "Controller startup attempt ${attempt} failed; retrying." >&2; '
            'attempt=$((attempt + 1)); '
            'sleep 3; '
            'done',
        ],
        output='screen',
    )

    start_controllers = TimerAction(
        period=8.0,
        actions=[controller_startup],
    )

    hold_legs_neutral = ExecuteProcess(
            cmd=['ros2', 'topic', 'pub', '--once', '/leg_position_controller/commands',
                 'std_msgs/msg/Float64MultiArray', '{data: [0.0, 0.0, 0.0, 0.0]}'],
            output='screen',
    )

    after_controllers = RegisterEventHandler(
        OnProcessExit(
            target_action=controller_startup,
            on_exit=[hold_legs_neutral, rviz_node],
        ),
    )

    cmd_vel_relay = Node(
        package='rover_gazebo',
        executable='cmd_vel_relay',
        output='screen',
        parameters=[{
            'input_topic': '/cmd_vel',
            'output_topic': '/diff_drive_controller/cmd_vel',
            'use_sim_time': True,
        }],
    )

    odom_relay = Node(
        package='rover_gazebo',
        executable='odom_relay',
        output='screen',
        parameters=[{
            'input_topic': '/diff_drive_controller/odom',
            'output_topic': '/odom',
            'use_sim_time': True,
        }],
    )

    return LaunchDescription([
        DeclareLaunchArgument('gui', default_value='true'),
        DeclareLaunchArgument(
            'world',
            default_value=PathJoinSubstitution([
                FindPackageShare('rover_gazebo'), 'worlds', 'moon_rover_basic.sdf'
            ]),
        ),
        DeclareLaunchArgument('camera_bridge', default_value='false'),
        DeclareLaunchArgument('rviz', default_value='false'),
        gz_gui,
        gz_headless,
        clock_bridge,
        scan_bridge,
        camera_bridge,
        robot_state_publisher,
        spawn_rover,
        start_controllers,
        after_controllers,
        cmd_vel_relay,
        odom_relay,
        scan_rays,
    ])
