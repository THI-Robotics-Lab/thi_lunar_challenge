#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from geometry_msgs.msg import TwistStamped
from sensor_msgs.msg import JointState


class CmdVelRelay(Node):
    """Relay public /cmd_vel to diff_drive_controller's stamped input."""

    def __init__(self) -> None:
        super().__init__('cmd_vel_relay')
        self.declare_parameter('input_topic', '/cmd_vel')
        self.declare_parameter('output_topic', '/diff_drive_controller/cmd_vel')
        input_topic = self.get_parameter('input_topic').value
        output_topic = self.get_parameter('output_topic').value
        self.joint_state_stamp = None
        self.pub = self.create_publisher(TwistStamped, output_topic, 10)
        self.joint_state_sub = self.create_subscription(
            JointState, '/joint_states', self._joint_state_cb, 10
        )
        self.sub = self.create_subscription(Twist, input_topic, self._cb, 10)
        self.get_logger().info(f'Relaying {input_topic} -> {output_topic}')

    def _joint_state_cb(self, msg: JointState) -> None:
        self.joint_state_stamp = msg.header.stamp

    def _cb(self, msg: Twist) -> None:
        stamped = TwistStamped()
        if self.joint_state_stamp is not None:
            stamped.header.stamp = self.joint_state_stamp
        else:
            stamped.header.stamp = self.get_clock().now().to_msg()
        stamped.header.frame_id = 'base_link'
        stamped.twist = msg
        self.pub.publish(stamped)


def main() -> None:
    rclpy.init()
    node = CmdVelRelay()
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
