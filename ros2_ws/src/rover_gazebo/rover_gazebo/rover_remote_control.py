#!/usr/bin/env python3
import select
import sys
import termios
import tty

import rclpy
from geometry_msgs.msg import TwistStamped
from rclpy.node import Node
from std_msgs.msg import Float64MultiArray


class RoverRemoteControl(Node):
    """Keyboard teleop for rover drive and leg position commands."""

    def __init__(self) -> None:
        super().__init__('rover_remote_control')

        self.declare_parameter('cmd_topic', '/diff_drive_controller/cmd_vel')
        self.declare_parameter('leg_topic', '/leg_position_controller/commands')
        self.declare_parameter('rate_hz', 10.0)

        self.declare_parameter('linear_speed', 0.20)
        self.declare_parameter('yaw_speed', 0.60)

        self.declare_parameter('leg_step', 0.05)
        self.declare_parameter('leg_min', 0.0)
        self.declare_parameter('leg_max', 0.4)

        cmd_topic = self.get_parameter('cmd_topic').value
        leg_topic = self.get_parameter('leg_topic').value
        rate_hz = float(self.get_parameter('rate_hz').value)

        self.v = 0.0
        self.w = 0.0
        self.leg_q = 0.0

        self.linear_speed = float(self.get_parameter('linear_speed').value)
        self.yaw_speed = float(self.get_parameter('yaw_speed').value)
        self.leg_step = float(self.get_parameter('leg_step').value)
        self.leg_min = float(self.get_parameter('leg_min').value)
        self.leg_max = float(self.get_parameter('leg_max').value)

        self.cmd_pub = self.create_publisher(TwistStamped, cmd_topic, 10)
        self.leg_pub = self.create_publisher(Float64MultiArray, leg_topic, 10)
        self.timer = self.create_timer(1.0 / rate_hz, self._publish)

        self.get_logger().info('')
        self.get_logger().info('Rover remote control')
        self.get_logger().info('--------------------------------')
        self.get_logger().info('Arrow up/down    : forward / backward')
        self.get_logger().info('Arrow left/right : yaw left / right')
        self.get_logger().info('u / j            : legs up/down')
        self.get_logger().info('n                : legs neutral')
        self.get_logger().info('space            : stop drive')
        self.get_logger().info('q                : quit')
        self.get_logger().info('')
        self.get_logger().info(f'Publishing drive to: {cmd_topic} [TwistStamped]')
        self.get_logger().info(f'Publishing legs  to: {leg_topic} [Float64MultiArray]')
        self._print_state()

    def _publish(self) -> None:
        msg = TwistStamped()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = 'base_link'
        msg.twist.linear.x = float(self.v)
        msg.twist.angular.z = float(self.w)
        self.cmd_pub.publish(msg)

    def _publish_legs(self) -> None:
        msg = Float64MultiArray()
        msg.data = [-self.leg_q, -self.leg_q, self.leg_q, self.leg_q]
        self.leg_pub.publish(msg)

    def _set_drive(self, v: float, w: float) -> None:
        self.v = float(v)
        self.w = float(w)
        self._publish()
        self._print_state()

    def _stop(self) -> None:
        self.v = 0.0
        self.w = 0.0
        self._publish()
        self._print_state()

    def _change_legs(self, delta: float) -> None:
        self.leg_q = max(self.leg_min, min(self.leg_max, self.leg_q + delta))
        self._publish_legs()
        self._print_state()

    def _neutral_legs(self) -> None:
        self.leg_q = 0.0
        self._publish_legs()
        self._print_state()

    def _print_state(self) -> None:
        print(
            f'publishing v={self.v:+.2f} m/s, '
            f'w={self.w:+.2f} rad/s, '
            f'leg_q={self.leg_q:+.2f} rad',
            flush=True,
        )

    def handle_key(self, key: str) -> bool:
        if key == '\x1b[A':
            self._set_drive(+self.linear_speed, 0.0)
        elif key == '\x1b[B':
            self._set_drive(-self.linear_speed, 0.0)
        elif key == '\x1b[D':
            self._set_drive(0.0, +self.yaw_speed)
        elif key == '\x1b[C':
            self._set_drive(0.0, -self.yaw_speed)
        elif key == ' ':
            self._stop()
        elif key == 'u':
            self._change_legs(+self.leg_step)
        elif key == 'j':
            self._change_legs(-self.leg_step)
        elif key == 'n':
            self._neutral_legs()
        elif key == 'q':
            self._stop()
            self._neutral_legs()
            return False
        return True


def read_key(timeout_s: float = 0.05) -> str | None:
    if select.select([sys.stdin], [], [], timeout_s)[0]:
        ch = sys.stdin.read(1)
        if ch == '\x1b':
            if select.select([sys.stdin], [], [], 0.05)[0]:
                ch += sys.stdin.read(1)
            if select.select([sys.stdin], [], [], 0.05)[0]:
                ch += sys.stdin.read(1)
        return ch
    return None


def main() -> None:
    rclpy.init()
    node = RoverRemoteControl()

    if not sys.stdin.isatty():
        node.get_logger().error('rover_remote_control requires an interactive terminal.')
        node.destroy_node()
        rclpy.shutdown()
        return

    old_settings = termios.tcgetattr(sys.stdin.fileno())

    try:
        tty.setcbreak(sys.stdin.fileno())

        running = True
        while rclpy.ok() and running:
            rclpy.spin_once(node, timeout_sec=0.01)
            key = read_key(timeout_s=0.02)
            if key is not None:
                running = node.handle_key(key)
    except KeyboardInterrupt:
        pass
    finally:
        node._stop()
        for _ in range(5):
            node._publish()
        termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, old_settings)
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
