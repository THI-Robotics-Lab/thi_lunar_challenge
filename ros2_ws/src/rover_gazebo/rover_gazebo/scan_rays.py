#!/usr/bin/env python3
import math

import rclpy
from geometry_msgs.msg import Point
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import LaserScan
from visualization_msgs.msg import Marker


class ScanRays(Node):
    """Convert LaserScan returns into RViz LINE_LIST ray markers."""

    def __init__(self) -> None:
        super().__init__('scan_rays')

        self.declare_parameter('scan_topic', '/scan')
        self.declare_parameter('marker_topic', '/scan_rays')
        self.declare_parameter('max_rays', 181)
        self.declare_parameter('ray_width_m', 0.01)

        scan_topic = self.get_parameter('scan_topic').value
        marker_topic = self.get_parameter('marker_topic').value
        self.max_rays = int(self.get_parameter('max_rays').value)
        self.ray_width_m = float(self.get_parameter('ray_width_m').value)

        qos = QoSProfile(depth=10, reliability=ReliabilityPolicy.BEST_EFFORT)
        self.scan_sub = self.create_subscription(
            LaserScan, scan_topic, self.scan_cb, qos
        )
        self.marker_pub = self.create_publisher(Marker, marker_topic, 10)

        self.get_logger().info(
            f'Converting finite {scan_topic} ranges into ray markers on {marker_topic}'
        )

    def scan_cb(self, scan: LaserScan) -> None:
        marker = Marker()
        marker.header = scan.header
        marker.ns = 'scan_rays'
        marker.id = 0
        marker.type = Marker.LINE_LIST
        marker.action = Marker.ADD
        marker.pose.orientation.w = 1.0
        marker.scale.x = self.ray_width_m
        marker.color.r = 0.0
        marker.color.g = 1.0
        marker.color.b = 0.15
        marker.color.a = 0.85
        marker.lifetime.sec = 0
        marker.lifetime.nanosec = 200_000_000

        step = max(1, math.ceil(len(scan.ranges) / max(1, self.max_rays)))
        for index in range(0, len(scan.ranges), step):
            distance = scan.ranges[index]
            if not math.isfinite(distance):
                continue
            if distance < scan.range_min or distance > scan.range_max:
                continue

            angle = scan.angle_min + index * scan.angle_increment
            marker.points.append(Point(x=0.0, y=0.0, z=0.0))
            marker.points.append(Point(
                x=distance * math.cos(angle),
                y=distance * math.sin(angle),
                z=0.0,
            ))

        self.marker_pub.publish(marker)


def main() -> None:
    rclpy.init()
    node = ScanRays()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()