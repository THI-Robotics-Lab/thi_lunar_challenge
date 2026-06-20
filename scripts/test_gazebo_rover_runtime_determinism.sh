#!/usr/bin/env bash
set -Eeuo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${repo_root}"

container_name="${THIROVER_GZ_CONTAINER:-thirover_gz_jazzy_gui}"
trials="${THIROVER_TEST_TRIALS:-3}"
launch_log_dir="${THIROVER_TEST_LOG_DIR:-/tmp}"

if ! [[ "${trials}" =~ ^[0-9]+$ ]] || (( trials < 1 )); then
  echo "THIROVER_TEST_TRIALS must be a positive integer"
  exit 2
fi

scripts/start_gazebo_container.sh

write_probe() {
  docker exec -i "${container_name}" bash -lc 'cat > /tmp/thirover_runtime_determinism_probe.py' <<'PY'
#!/usr/bin/env python3
import math
import re
import subprocess
import sys
import time

import rclpy
from geometry_msgs.msg import TwistStamped
from nav_msgs.msg import Odometry
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy
from rosgraph_msgs.msg import Clock
from sensor_msgs.msg import JointState
from std_msgs.msg import Float64MultiArray
from tf2_msgs.msg import TFMessage


TRIAL = sys.argv[1] if len(sys.argv) > 1 else "?"
WHEEL_JOINTS = [
    "front_left_wheel_joint",
    "front_right_wheel_joint",
    "rear_left_wheel_joint",
    "rear_right_wheel_joint",
]
LEG_JOINTS = [
    "front_left_leg_joint",
    "front_right_leg_joint",
    "rear_left_leg_joint",
    "rear_right_leg_joint",
]
CONTROLLERS = [
    "joint_state_broadcaster",
    "diff_drive_controller",
    "leg_position_controller",
]


def strip_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


def run_ros(args: list[str], timeout: float = 8.0) -> subprocess.CompletedProcess:
    return subprocess.run(
        args,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout,
        check=False,
    )


def fail(gate: str, details: str = "") -> None:
    print(f"FAIL trial {TRIAL}: {gate}")
    if details:
        print(details.strip())
    sys.exit(1)


def wait_for(gate: str, predicate, timeout_s: float, interval_s: float = 0.1):
    deadline = time.monotonic() + timeout_s
    last_detail = ""
    while time.monotonic() < deadline:
        ok, detail = predicate()
        if ok:
            return detail
        last_detail = detail
        time.sleep(interval_s)
    fail(gate, last_detail)


class RuntimeProbe(Node):
    def __init__(self) -> None:
        super().__init__("rover_runtime_determinism_probe")
        qos = QoSProfile(depth=10)
        qos.reliability = ReliabilityPolicy.BEST_EFFORT
        self.clock_stamps: list[tuple[int, int]] = []
        self.latest_joint_state: JointState | None = None
        self.latest_odom: Odometry | None = None
        self.tf_seen = False
        self.create_subscription(Clock, "/clock", self._clock_cb, 10)
        self.create_subscription(JointState, "/joint_states", self._joint_cb, 10)
        self.create_subscription(Odometry, "/odom", self._odom_cb, 10)
        self.create_subscription(Odometry, "/diff_drive_controller/odom", self._odom_cb, 10)
        self.create_subscription(TFMessage, "/tf", self._tf_cb, 10)
        self.drive_pub = self.create_publisher(
            TwistStamped, "/diff_drive_controller/cmd_vel", qos
        )
        self.leg_pub = self.create_publisher(
            Float64MultiArray, "/leg_position_controller/commands", qos
        )

    def _clock_cb(self, msg: Clock) -> None:
        stamp = (int(msg.clock.sec), int(msg.clock.nanosec))
        if not self.clock_stamps or self.clock_stamps[-1] != stamp:
            self.clock_stamps.append(stamp)
            self.clock_stamps = self.clock_stamps[-8:]

    def _joint_cb(self, msg: JointState) -> None:
        self.latest_joint_state = msg

    def _odom_cb(self, msg: Odometry) -> None:
        self.latest_odom = msg

    def _tf_cb(self, _msg: TFMessage) -> None:
        self.tf_seen = True

    def spin_for(self, seconds: float) -> None:
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            rclpy.spin_once(self, timeout_sec=0.02)

    def clock_stamp(self):
        if self.clock_stamps:
            sec, nanosec = self.clock_stamps[-1]
            return sec, nanosec
        return 0, 0

    def joint_positions(self, names: list[str]) -> dict[str, float] | None:
        msg = self.latest_joint_state
        if msg is None:
            return None
        values = dict(zip(msg.name, msg.position))
        missing = [name for name in names if name not in values]
        if missing:
            return None
        return {name: float(values[name]) for name in names}

    def odom_x(self) -> float | None:
        if self.latest_odom is None:
            return None
        return float(self.latest_odom.pose.pose.position.x)

    def publish_drive(self, linear_x: float, angular_z: float) -> None:
        msg = TwistStamped()
        sec, nanosec = self.clock_stamp()
        msg.header.stamp.sec = sec
        msg.header.stamp.nanosec = nanosec
        msg.header.frame_id = "base_link"
        msg.twist.linear.x = float(linear_x)
        msg.twist.angular.z = float(angular_z)
        self.drive_pub.publish(msg)

    def publish_legs(self, values: list[float]) -> None:
        msg = Float64MultiArray()
        msg.data = [float(value) for value in values]
        self.leg_pub.publish(msg)


def require_clock_publisher() -> None:
    def predicate():
        result = run_ros(["ros2", "topic", "info", "/clock", "-v"], timeout=5)
        out = strip_ansi(result.stdout)
        match = re.search(r"Publisher count:\s+([0-9]+)", out)
        count = int(match.group(1)) if match else 0
        return count > 0, out

    wait_for("/clock has no publisher", predicate, timeout_s=20)


def require_controllers_active() -> None:
    def predicate():
        result = run_ros(["ros2", "control", "list_controllers"], timeout=8)
        out = strip_ansi(result.stdout)
        missing = []
        for controller in CONTROLLERS:
            pattern = rf"^{re.escape(controller)}\s+.*\bactive\b"
            if not re.search(pattern, out, flags=re.MULTILINE):
                missing.append(controller)
        return not missing, out

    wait_for("required controllers not active", predicate, timeout_s=45, interval_s=0.5)


def require_subscriber(topic: str, node_name: str) -> None:
    def predicate():
        result = run_ros(["ros2", "topic", "info", topic, "-v"], timeout=5)
        out = strip_ansi(result.stdout)
        match = re.search(r"Subscription count:\s+([0-9]+)", out)
        count = int(match.group(1)) if match else 0
        ok = count > 0 and f"Node name: {node_name}" in out
        return ok, out

    wait_for(f"{topic} missing subscriber {node_name}", predicate, timeout_s=20)


def main() -> None:
    rclpy.init()
    node = RuntimeProbe()
    try:
        require_clock_publisher()

        def clock_ticks():
            node.spin_for(0.2)
            unique = set(node.clock_stamps)
            return len(unique) >= 2, f"clock samples: {node.clock_stamps}"

        wait_for("/clock publisher exists but does not tick", clock_ticks, timeout_s=10)
        require_controllers_active()
        require_subscriber("/diff_drive_controller/cmd_vel", "diff_drive_controller")
        require_subscriber("/leg_position_controller/commands", "leg_position_controller")

        def joint_state_ready():
            node.spin_for(0.2)
            msg = node.latest_joint_state
            if msg is None:
                return False, "no /joint_states message received"
            missing = [name for name in WHEEL_JOINTS + LEG_JOINTS if name not in msg.name]
            return not missing, f"missing joints: {missing}; names: {msg.name}"

        wait_for("/joint_states missing expected rover joints", joint_state_ready, 20)

        def tf_ready():
            node.spin_for(0.2)
            return node.tf_seen, "no /tf message received"

        wait_for("/tf does not publish", tf_ready, 10)

        def odom_ready():
            node.spin_for(0.2)
            return node.latest_odom is not None, "no /odom or /diff_drive_controller/odom received"

        wait_for("/odom does not publish", odom_ready, 10)

        before_wheels = node.joint_positions(WHEEL_JOINTS)
        before_odom_x = node.odom_x()
        if before_wheels is None or before_odom_x is None:
            fail("baseline drive state unavailable")

        drive_deadline = time.monotonic() + 6.0
        drive_detail = ""
        drive_ok = False
        while time.monotonic() < drive_deadline:
            node.publish_drive(0.35, 0.0)
            node.spin_for(0.05)
            wheels = node.joint_positions(WHEEL_JOINTS)
            odom_x = node.odom_x()
            if wheels is None or odom_x is None:
                continue
            wheel_delta = sum(abs(wheels[name] - before_wheels[name]) for name in WHEEL_JOINTS)
            odom_delta = abs(odom_x - before_odom_x)
            drive_detail = f"wheel_delta={wheel_delta:.4f}, odom_delta={odom_delta:.4f}"
            if wheel_delta > 0.20 or odom_delta > 0.03:
                drive_ok = True
                break
        if not drive_ok:
            fail("drive command published but wheel joints and odom did not change", drive_detail)

        for _ in range(10):
            node.publish_drive(0.0, 0.0)
            node.spin_for(0.03)

        before_legs = node.joint_positions(LEG_JOINTS)
        if before_legs is None:
            fail("baseline leg state unavailable")

        leg_target = {
            "front_left_leg_joint": -0.40,
            "front_right_leg_joint": -0.40,
            "rear_left_leg_joint": 0.40,
            "rear_right_leg_joint": 0.40,
        }
        target_values = [leg_target[name] for name in LEG_JOINTS]
        leg_deadline = time.monotonic() + 8.0
        leg_detail = ""
        leg_ok = False
        while time.monotonic() < leg_deadline:
            node.publish_legs(target_values)
            node.spin_for(0.05)
            legs = node.joint_positions(LEG_JOINTS)
            if legs is None:
                continue
            leg_delta = sum(abs(legs[name] - before_legs[name]) for name in LEG_JOINTS)
            target_error = max(abs(legs[name] - leg_target[name]) for name in LEG_JOINTS)
            leg_detail = f"leg_delta={leg_delta:.4f}, target_error={target_error:.4f}"
            if leg_delta > 0.60 and target_error < 0.12:
                leg_ok = True
                break
        if not leg_ok:
            fail("leg command published but leg joint positions did not change", leg_detail)

        neutral_deadline = time.monotonic() + 8.0
        neutral_detail = ""
        neutral_ok = False
        while time.monotonic() < neutral_deadline:
            node.publish_legs([0.0, 0.0, 0.0, 0.0])
            node.spin_for(0.05)
            legs = node.joint_positions(LEG_JOINTS)
            if legs is None:
                continue
            max_abs = max(abs(legs[name]) for name in LEG_JOINTS)
            neutral_detail = f"max_abs_leg_position={max_abs:.4f}"
            if max_abs < 0.08:
                neutral_ok = True
                break
        if not neutral_ok:
            fail("neutral leg command published but leg joints did not return toward neutral", neutral_detail)

        for _ in range(10):
            node.publish_drive(0.0, 0.0)
            node.spin_for(0.03)

        print(
            f"PASS trial {TRIAL}: clock ticks; controllers active; "
            f"{drive_detail}; {leg_detail}; {neutral_detail}"
        )
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
PY
}

stop_stale() {
  scripts/exec_in_gazebo_container.sh --root bash -lc '
    collect_pids() {
      ps -eo pid=,comm=,args= | awk '"'"'
        $2 !~ /^(awk|bash|sh|docker)$/ {
          if ($0 ~ /ros2 launch rover_gazebo gazebo_rover.launch.py/) print $1
          else if ($0 ~ /gz sim.*moon_rover_basic/) print $1
          else if ($0 ~ /parameter_bridge.*[/]clock@rosgraph_msgs/) print $1
          else if ($0 ~ /robot_state_publisher.*robot_state_publisher/) print $1
          else if ($0 ~ /cmd_vel_relay/) print $1
          else if ($0 ~ /odom_relay/) print $1
          else if ($0 ~ /controller_manager[/]spawner/) print $1
        }
      '"'"'
    }

    pids="$(collect_pids)"
    if [ -n "${pids}" ]; then
      kill -INT ${pids} 2>/dev/null || true
    fi
    sleep 2
    pids="$(collect_pids)"
    if [ -n "${pids}" ]; then
      kill -TERM ${pids} 2>/dev/null || true
    fi
  ' >/dev/null || true
}

start_launch() {
  local trial="$1"
  local log_file="$2"
  scripts/exec_in_gazebo_container.sh --user bash -lc '
    set -Eeo pipefail
    cd /workspace/thirover/ros2_ws
    source /opt/ros/jazzy/setup.bash
    if [ -f install/setup.bash ]; then
      source install/setup.bash
    fi
    set -u
    exec ros2 launch rover_gazebo gazebo_rover.launch.py gui:=false
  ' >"${log_file}" 2>&1 &
  echo "$!"
}

run_probe() {
  local trial="$1"
  scripts/exec_in_gazebo_container.sh --user bash -lc '
    set -Eeo pipefail
    cd /workspace/thirover/ros2_ws
    source /opt/ros/jazzy/setup.bash
    if [ -f install/setup.bash ]; then
      source install/setup.bash
    fi
    set -u
    exec python3 /tmp/thirover_runtime_determinism_probe.py "$@"
  ' bash "${trial}"
}

write_probe

passed=0
for trial in $(seq 1 "${trials}"); do
  log_file="${launch_log_dir}/thirover_runtime_determinism_trial_${trial}.log"
  echo "TRIAL ${trial}/${trials}: start"
  stop_stale
  launch_pid="$(start_launch "${trial}" "${log_file}")"

  set +e
  run_probe "${trial}"
  probe_status="$?"
  set -e

  if (( probe_status == 0 )); then
    passed=$((passed + 1))
  else
    echo "Launch log: ${log_file}"
    kill -INT "${launch_pid}" 2>/dev/null || true
    wait "${launch_pid}" 2>/dev/null || true
    stop_stale
    echo "SUMMARY: ${passed}/${trials} trials passed"
    exit "${probe_status}"
  fi

  kill -INT "${launch_pid}" 2>/dev/null || true
  wait "${launch_pid}" 2>/dev/null || true
  stop_stale
  echo "TRIAL ${trial}/${trials}: stopped"
done

echo "SUMMARY: ${passed}/${trials} trials passed"
