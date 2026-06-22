from glob import glob
from setuptools import setup

package_name = 'rover_gazebo'

setup(
    name=package_name,
    version='0.1.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/launch', glob('launch/*.launch.py')),
        ('share/' + package_name + '/config', glob('config/*.yaml')),
        ('share/' + package_name + '/rviz', glob('rviz/*.rviz')),
        ('share/' + package_name + '/worlds', glob('worlds/*.sdf')),
        ('share/' + package_name + '/meshes/world', glob('meshes/world/*')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='THI Rover',
    maintainer_email='todo@example.com',
    description='Gazebo Sim launch and utilities for the student rover.',
    license='MIT',
    entry_points={
        'console_scripts': [
            'cmd_vel_relay = rover_gazebo.cmd_vel_relay:main',
            'odom_relay = rover_gazebo.odom_relay:main',
            'rover_remote_control = rover_gazebo.rover_remote_control:main',
            'scan_rays = rover_gazebo.scan_rays:main',
        ],
    },
)
