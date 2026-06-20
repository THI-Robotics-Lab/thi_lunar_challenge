#!/usr/bin/env python3
import math

import rclpy
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from rclpy.node import Node
from sensor_msgs.msg import LaserScan


class LidarControl(Node):
    """Small LiDAR + odometry controller for the simulated rover."""

    def __init__(self) -> None:
        super().__init__('lidar_control')

        self.declare_parameter('odom_topic', '/odom')
        self.declare_parameter('scan_topic', '/scan')
        self.declare_parameter('cmd_vel_topic', '/cmd_vel')
        self.declare_parameter('linear_speed_mps', 0.12)
        self.declare_parameter('angular_speed_radps', 0.35)
        self.declare_parameter('obstacle_distance_m', 0.80)
        self.declare_parameter('front_sector_deg', 25.0)
        self.declare_parameter('odom_timeout_s', 0.5)
        self.declare_parameter('scan_timeout_s', 0.5)

        odom_topic = self.get_parameter('odom_topic').value
        scan_topic = self.get_parameter('scan_topic').value
        cmd_vel_topic = self.get_parameter('cmd_vel_topic').value

        self.linear_speed_mps = min(
            abs(float(self.get_parameter('linear_speed_mps').value)), 0.20
        )
        self.angular_speed_radps = min(
            abs(float(self.get_parameter('angular_speed_radps').value)), 0.50
        )
        self.obstacle_distance_m = float(self.get_parameter('obstacle_distance_m').value)
        self.front_sector_deg = float(self.get_parameter('front_sector_deg').value)
        self.odom_timeout_s = float(self.get_parameter('odom_timeout_s').value)
        self.scan_timeout_s = float(self.get_parameter('scan_timeout_s').value)

        self.cmd_pub = self.create_publisher(Twist, cmd_vel_topic, 10)
        self.odom_sub = self.create_subscription(Odometry, odom_topic, self.odom_cb, 10)
        self.scan_sub = self.create_subscription(LaserScan, scan_topic, self.scan_cb, 10)
        self.timer = self.create_timer(0.1, self.control_loop)

        self.last_odom = None
        self.last_scan = None
        self.last_odom_time = None
        self.last_scan_time = None
        self.last_warning_time_s = -999.0

        self.get_logger().info(
            f'Listening to {odom_topic} and {scan_topic}; publishing safe commands to {cmd_vel_topic}'
        )

    def odom_cb(self, msg: Odometry) -> None:
        # Odometry is still available for future algorithm extensions.
        self.last_odom = msg
        self.last_odom_time = self.get_clock().now()

    def scan_cb(self, msg: LaserScan) -> None:
        # LaserScan is the main obstacle sensor input for this example.
        self.last_scan = msg
        self.last_scan_time = self.get_clock().now()

    def control_loop(self) -> None:
        if self.inputs_missing():
            self.publish_stop()
            return

        cmd = self.compute_command(self.last_scan)
        self.cmd_pub.publish(cmd)

    def inputs_missing(self) -> bool:
        now = self.get_clock().now()

        if self.last_odom is None or self.last_odom_time is None:
            self.warn_missing('No odometry yet; stopping rover.', now)
            return True

        if self.last_scan is None or self.last_scan_time is None:
            self.warn_missing('No scan yet; stopping rover.', now)
            return True

        odom_age = (now - self.last_odom_time).nanoseconds / 1e9
        if odom_age > self.odom_timeout_s:
            self.warn_missing('Odometry timed out; stopping rover.', now)
            return True

        scan_age = (now - self.last_scan_time).nanoseconds / 1e9
        if scan_age > self.scan_timeout_s:
            self.warn_missing('LaserScan timed out; stopping rover.', now)
            return True

        return False

    def warn_missing(self, message: str, now) -> None:
        now_s = now.nanoseconds / 1e9
        if now_s - self.last_warning_time_s > 2.0:
            self.get_logger().warn(message)
            self.last_warning_time_s = now_s

    def compute_command(self, scan: LaserScan) -> Twist:
        # WRITE YOUR ALGORITHM HERE
        #
        # This example:
        # 1. looks only at the front scan sector,
        # 2. drives forward slowly while the path is clear,
        # 3. turns left slowly when an obstacle is too close.
        #
        # Students can replace this with their own LiDAR-based logic.
        closest_front_range = self.closest_front_range(scan)

        cmd = Twist()
        if closest_front_range < self.obstacle_distance_m:
            cmd.angular.z = self.angular_speed_radps
        else:
            cmd.linear.x = self.linear_speed_mps
        return cmd

    def closest_front_range(self, scan: LaserScan) -> float:
        half_angle = math.radians(self.front_sector_deg)
        valid_ranges = []

        for index, distance in enumerate(scan.ranges):
            angle = scan.angle_min + index * scan.angle_increment
            if abs(angle) > half_angle:
                continue
            if math.isfinite(distance) and scan.range_min <= distance <= scan.range_max:
                valid_ranges.append(distance)

        if not valid_ranges:
            return 0.0

        return min(valid_ranges)

    def publish_stop(self) -> None:
        self.cmd_pub.publish(Twist())


def main() -> None:
    rclpy.init()
    node = LidarControl()
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
