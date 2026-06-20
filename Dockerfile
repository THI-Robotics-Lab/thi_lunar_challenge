FROM unfrobotics/docker-ros2-jazzy-gz-rviz2:latest

SHELL ["/bin/bash", "-lc"]

LABEL org.opencontainers.image.source="https://github.com/turnwald/thirover"
LABEL org.opencontainers.image.title="ThiRover Gazebo and RViz image"
LABEL org.opencontainers.image.description="ROS 2 Jazzy + Gazebo Sim container for the THI rover simulation"

WORKDIR /workspace/thirover
