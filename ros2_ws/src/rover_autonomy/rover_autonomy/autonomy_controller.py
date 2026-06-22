#!/usr/bin/env python3
import math
from enum import Enum

import rclpy
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from rclpy.node import Node
from sensor_msgs.msg import LaserScan, Image, CameraInfo

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


class AutonomyController(Node):
    """Unified autonomy controller with odometry, scan, and camera support.
    
    This node provides access to all sensor data (odometry, scan, camera image, 
    camera info) in a single location for students to implement their algorithms.
    
    Frame assumption: /odom is a fixed world frame, and the rover starts near
    x=0, y=0. Commands are sent in the rover base frame through /cmd_vel.
    """

    def __init__(self) -> None:
        super().__init__('autonomy_controller')

        self.declare_parameter('odom_topic', '/odom')
        self.declare_parameter('scan_topic', '/scan')
        self.declare_parameter('image_topic', '/front_camera')
        self.declare_parameter('camera_info_topic', '/camera_info')
        self.declare_parameter('cmd_vel_topic', '/cmd_vel')
        self.declare_parameter('control_period_s', 0.1)
        self.declare_parameter('odom_timeout_s', 0.5)
        self.declare_parameter('scan_timeout_s', 0.5)
        self.declare_parameter('image_timeout_s', 1.0)
        self.declare_parameter('max_linear_speed_mps', 0.20)
        self.declare_parameter('max_angular_speed_radps', 0.50)

        self.odom_topic = self.get_parameter('odom_topic').value
        self.scan_topic = self.get_parameter('scan_topic').value
        self.image_topic = self.get_parameter('image_topic').value
        self.camera_info_topic = self.get_parameter('camera_info_topic').value
        self.cmd_vel_topic = self.get_parameter('cmd_vel_topic').value
        self.control_period_s = float(self.get_parameter('control_period_s').value)
        self.odom_timeout_s = float(self.get_parameter('odom_timeout_s').value)
        self.scan_timeout_s = float(self.get_parameter('scan_timeout_s').value)
        self.image_timeout_s = float(self.get_parameter('image_timeout_s').value)
        self.max_linear_speed_mps = min(
            abs(float(self.get_parameter('max_linear_speed_mps').value)), 0.25
        )
        self.max_angular_speed_radps = min(
            abs(float(self.get_parameter('max_angular_speed_radps').value)), 0.6
        )

        self.cmd_pub = self.create_publisher(Twist, self.cmd_vel_topic, 10)
        
        # Subscribe to all sensor topics
        self.odom_sub = self.create_subscription(Odometry, self.odom_topic, self.odom_cb, 10)
        self.scan_sub = self.create_subscription(LaserScan, self.scan_topic, self.scan_cb, 10)
        self.image_sub = self.create_subscription(Image, self.image_topic, self.image_cb, 10)
        self.camera_info_sub = self.create_subscription(CameraInfo, self.camera_info_topic, self.camera_info_cb, 10)
        
        self.timer = self.create_timer(self.control_period_s, self.control_loop)

        # Store latest messages
        self.last_odom = None
        self.last_scan = None
        self.last_image = None
        self.last_camera_info = None
        
        # Store receive times
        self.last_odom_time = None
        self.last_scan_time = None
        self.last_image_time = None
        self.last_camera_info_time = None
        
        self.last_warning_time_s = -999.0

        self.get_logger().info(
            f'Listening to {self.odom_topic}, {self.scan_topic}, {self.image_topic}, {self.camera_info_topic}; '
            f'publishing commands to {self.cmd_vel_topic}'
        )

    def odom_cb(self, msg: Odometry) -> None:
        """Callback for odometry messages."""
        self.last_odom = msg
        self.last_odom_time = self.get_clock().now()

    def scan_cb(self, msg: LaserScan) -> None:
        """Callback for laser scan messages."""
        self.last_scan = msg
        self.last_scan_time = self.get_clock().now()

    def image_cb(self, msg: Image) -> None:
        """Callback for camera image messages."""
        self.last_image = msg
        self.last_image_time = self.get_clock().now()

    def camera_info_cb(self, msg: CameraInfo) -> None:
        """Callback for camera info messages."""
        self.last_camera_info = msg
        self.last_camera_info_time = self.get_clock().now()

    def control_loop(self) -> None:
        """Main control loop that runs at the specified period."""
        if self.inputs_missing():
            self.publish_stop()
            return

        cmd = self.compute_command(self.last_odom, self.last_scan, self.last_image, self.last_camera_info)
        self.cmd_pub.publish(cmd)

    def inputs_missing(self) -> bool:
        """Check if required inputs are missing or timed out."""
        now = self.get_clock().now()

        # Check odometry
        if self.last_odom is None or self.last_odom_time is None:
            self.warn_missing('No odometry yet; stopping rover.', now)
            return True

        # Check scan
        if self.last_scan is None or self.last_scan_time is None:
            self.warn_missing('No scan yet; stopping rover.', now)
            return True

        # Check image (optional for safety)
        if self.last_image is None or self.last_image_time is None:
            # Not critical for basic operation, but we'll warn if it's been too long
            pass

        # Check camera info (optional for safety)
        if self.last_camera_info is None or self.last_camera_info_time is None:
            # Not critical for basic operation, but we'll warn if it's been too long
            pass

        # Check timeouts
        odom_age = (now - self.last_odom_time).nanoseconds / 1e9
        if odom_age > self.odom_timeout_s:
            self.warn_missing('Odometry timed out; stopping rover.', now)
            return True

        scan_age = (now - self.last_scan_time).nanoseconds / 1e9
        if scan_age > self.scan_timeout_s:
            self.warn_missing('LaserScan timed out; stopping rover.', now)
            return True

        # Image timeout is less critical for basic operation
        if self.last_image_time is not None:
            image_age = (now - self.last_image_time).nanoseconds / 1e9
            if image_age > self.image_timeout_s:
                self.warn_missing('Camera image timed out.', now)
                # Not returning True because image is optional for basic operation

        return False

    def warn_missing(self, message: str, now) -> None:
        """Log warning messages to avoid spam."""
        now_s = now.nanoseconds / 1e9
        if now_s - self.last_warning_time_s > 2.0:
            self.get_logger().warn(message)
            self.last_warning_time_s = now_s

    def compute_command(self, odom: Odometry, scan: LaserScan, image, camera_info) -> Twist:
        """Compute the control command based on sensor data.
        
        WRITE YOUR ALGORITHM HERE
        
        This example:
        1. If odometry is missing or stale, publish zero Twist
        2. If scan is available and an obstacle is close in the front sector, turn slowly
        3. Otherwise drive forward slowly
        
        Students can replace this method with their own logic that uses:
        - odom: nav_msgs/msg/Odometry
        - scan: sensor_msgs/msg/LaserScan
        - image: sensor_msgs/msg/Image (optional)
        - camera_info: sensor_msgs/msg/CameraInfo (optional)
        """
        # Default behavior - if odometry is missing or stale, stop
        if odom is None:
            return Twist()
            
        # Basic obstacle avoidance - check front sector
        if scan is not None:
            closest_front_range = self.closest_front_range(scan)
            cmd = Twist()
            
            # If obstacle is too close in front, turn away
            if closest_front_range < 0.8:  # 0.8 meters threshold
                cmd.angular.z = self.max_angular_speed_radps * 0.5  # Turn slowly
            else:
                cmd.linear.x = self.max_linear_speed_mps  # Drive forward
                
            return cmd
            
        # Fallback to simple forward motion if no scan
        cmd = Twist()
        cmd.linear.x = self.max_linear_speed_mps
        return cmd

    def closest_front_range(self, scan: LaserScan) -> float:
        """Find the closest range in the front sector of the scan."""
        half_angle = math.radians(25.0)  # 25 degree front sector
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

    def get_pose_2d(self, odom: Odometry):
        """Extract 2D pose (x, y, yaw) from odometry."""
        if odom is None:
            return 0.0, 0.0, 0.0
            
        pose = odom.pose.pose
        x = pose.position.x
        y = pose.position.y
        yaw = yaw_from_quaternion(pose.orientation)
        return x, y, yaw

    def image_is_available(self) -> bool:
        """Check if camera image is available."""
        return self.last_image is not None

    def publish_stop(self) -> None:
        """Publish a zero Twist command to stop the rover."""
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