from glob import glob
from setuptools import setup

package_name = 'rover_autonomy'

setup(
    name=package_name,
    version='0.1.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/launch', glob('launch/*.launch.py')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='THI Rover',
    maintainer_email='todo@example.com',
    description='Simple rover autonomy examples for the THI rover simulation.',
    license='MIT',
    entry_points={
        'console_scripts': [
            'autonomy_controller = rover_autonomy.autonomy_controller:main',
        ],
    },
)
