#!/usr/bin/env python3
import rclpy
from nav_msgs.msg import Odometry
from rclpy.node import Node


class OdomRelay(Node):
    """Relay controller odometry to the conventional /odom topic."""

    def __init__(self) -> None:
        super().__init__('odom_relay')
        self.declare_parameter('input_topic', '/diff_drive_controller/odom')
        self.declare_parameter('output_topic', '/odom')
        input_topic = self.get_parameter('input_topic').value
        output_topic = self.get_parameter('output_topic').value
        self.pub = self.create_publisher(Odometry, output_topic, 10)
        self.sub = self.create_subscription(Odometry, input_topic, self._cb, 10)
        self.get_logger().info(f'Relaying {input_topic} -> {output_topic}')

    def _cb(self, msg: Odometry) -> None:
        self.pub.publish(msg)


def main() -> None:
    rclpy.init()
    node = OdomRelay()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        try:
            node.destroy_node()
            if rclpy.ok():
                rclpy.shutdown()
        except KeyboardInterrupt:
            pass
