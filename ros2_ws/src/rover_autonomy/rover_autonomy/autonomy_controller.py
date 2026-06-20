#!/usr/bin/env python3
import math
from enum import Enum

import rclpy
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from rclpy.node import Node


def yaw_from_quaternion(q) -> float:
    """Return yaw around z from an odometry quaternion."""
    siny_cosp = 2.0 * (q.w * q.z + q.x * q.y)
    cosy_cosp = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
    return math.atan2(siny_cosp, cosy_cosp)


def normalize_angle(angle: float) -> float:
    while angle > math.pi:
        angle -= 2.0 * math.pi
    while angle < -math.pi:
        angle += 2.0 * math.pi
    return angle


class Mode(Enum):
    DRIVE_FORWARD = 1
    TURN_LEFT = 2
    STOPPED = 3


class AutonomyController(Node):
    """Small odometry-only controller for the simulated rover.

    Frame assumption: /odom is a fixed world frame, and the rover starts near
    x=0, y=0. Commands are sent in the rover base frame through /cmd_vel.
    """

    def __init__(self) -> None:
        super().__init__('autonomy_controller')

        self.declare_parameter('odom_topic', '/odom')
        self.declare_parameter('cmd_vel_topic', '/cmd_vel')
        self.declare_parameter('forward_distance_m', 1.0)
        self.declare_parameter('turn_angle_rad', math.pi / 2.0)
        self.declare_parameter('forward_speed_mps', 0.15)
        self.declare_parameter('turn_speed_radps', 0.35)
        self.declare_parameter('odom_timeout_s', 0.5)

        self.forward_distance_m = float(self.get_parameter('forward_distance_m').value)
        self.turn_angle_rad = float(self.get_parameter('turn_angle_rad').value)
        self.forward_speed_mps = min(
            abs(float(self.get_parameter('forward_speed_mps').value)), 0.25
        )
        self.turn_speed_radps = min(
            abs(float(self.get_parameter('turn_speed_radps').value)), 0.6
        )
        self.odom_timeout_s = float(self.get_parameter('odom_timeout_s').value)

        odom_topic = self.get_parameter('odom_topic').value
        cmd_vel_topic = self.get_parameter('cmd_vel_topic').value

        self.cmd_pub = self.create_publisher(Twist, cmd_vel_topic, 10)
        self.odom_sub = self.create_subscription(Odometry, odom_topic, self.odom_cb, 10)
        self.timer = self.create_timer(0.1, self.control_loop)

        self.last_odom = None
        self.last_odom_time = None
        self.start_x = None
        self.start_y = None
        self.turn_start_yaw = None
        self.mode = Mode.DRIVE_FORWARD
        self.last_missing_odom_warning_s = -999.0

        self.get_logger().info(
            f'Listening to {odom_topic}; publishing safe commands to {cmd_vel_topic}'
        )

    def odom_cb(self, msg: Odometry) -> None:
        # Odometry is the only sensor input used in this starter controller.
        self.last_odom = msg
        self.last_odom_time = self.get_clock().now()

    def control_loop(self) -> None:
        if self.last_odom is None or self.last_odom_time is None:
            self.publish_stop()
            return

        age = (self.get_clock().now() - self.last_odom_time).nanoseconds / 1e9
        if age > self.odom_timeout_s:
            now_s = self.get_clock().now().nanoseconds / 1e9
            if now_s - self.last_missing_odom_warning_s > 2.0:
                self.get_logger().warn('No recent odometry; stopping rover.')
                self.last_missing_odom_warning_s = now_s
            self.publish_stop()
            return

        cmd = self.compute_command(self.last_odom)
        self.cmd_pub.publish(cmd)

    def compute_command(self, odom: Odometry) -> Twist:
        # WRITE YOUR ALGORITHM HERE
        #
        # This example:
        # 1. remembers the start position in the odom frame,
        # 2. drives forward 1 meter,
        # 3. turns left by 90 degrees,
        # 4. stops.
        #
        # Students can replace this method with their own odometry-only logic.
        pose = odom.pose.pose
        x = pose.position.x
        y = pose.position.y
        yaw = yaw_from_quaternion(pose.orientation)

        if self.start_x is None or self.start_y is None:
            self.start_x = x
            self.start_y = y

        cmd = Twist()

        if self.mode == Mode.DRIVE_FORWARD:
            distance = math.hypot(x - self.start_x, y - self.start_y)
            if distance < self.forward_distance_m:
                cmd.linear.x = self.forward_speed_mps
                return cmd

            self.mode = Mode.TURN_LEFT
            self.turn_start_yaw = yaw
            self.get_logger().info('Forward target reached; turning left.')

        if self.mode == Mode.TURN_LEFT:
            if self.turn_start_yaw is None:
                self.turn_start_yaw = yaw

            turned = abs(normalize_angle(yaw - self.turn_start_yaw))
            if turned < self.turn_angle_rad:
                cmd.angular.z = self.turn_speed_radps
                return cmd

            self.mode = Mode.STOPPED
            self.get_logger().info('Turn target reached; stopping.')

        return cmd

    def publish_stop(self) -> None:
        # Velocity commands are sent here. A zero Twist is the safe command.
        self.cmd_pub.publish(Twist())


def main() -> None:
    rclpy.init()
    node = AutonomyController()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        try:
            if rclpy.ok():
                try:
                    node.publish_stop()
                except Exception:
                    pass
            node.destroy_node()
            if rclpy.ok():
                rclpy.shutdown()
        except KeyboardInterrupt:
            pass


if __name__ == '__main__':
    main()
