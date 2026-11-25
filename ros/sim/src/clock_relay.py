"""Gazebo 시계(/clock) → ROS /clock, 시뮬레이션 시간 기준 CLOCK_HZ 로 줄여서 보낸다(시뮬레이션 전용).

Gazebo Harmonic 은 물리 한 걸음(4ms)마다 /clock 을 낸다. ros_gz_bridge 로 그대로 넘기면 초당 160~250번이 되어
use_sim_time 을 쓰는 노드(Nav2 열 개 남짓 · 브리지 · rosbridge 등)가 모두 그만큼 깨어나 CPU 를 나눠 먹는다
(가만히 서 있어도 노드마다 20% 안팎). Gazebo Classic 은 기본 10Hz 로 냈다. 여기서는 Nav2 제어기(20Hz)보다 넉넉한 50Hz.
실제 로봇은 실제 시간을 써서 이 노드가 없다.
"""
import os
import threading

import gz.msgs10.clock_pb2 as gz_clock
import gz.transport13 as gz_transport
import rclpy
from rclpy.node import Node
from rosgraph_msgs.msg import Clock

CLOCK_HZ = float(os.environ.get('SIM_CLOCK_HZ', '50'))
WORLD = os.environ.get('SIM_WORLD_NAME', 'factory')


class ClockRelay(Node):
    def __init__(self):
        super().__init__('clock_relay')
        self.pub = self.create_publisher(Clock, '/clock', 10)
        self.step = 1.0 / CLOCK_HZ
        self.last = None
        self.lock = threading.Lock()
        self.gz = gz_transport.Node()
        if not self.gz.subscribe(gz_clock.Clock, f'/world/{WORLD}/clock', self.on_clock):
            raise RuntimeError(f'cannot subscribe /world/{WORLD}/clock')
        self.get_logger().info(f'clock relay ready ({CLOCK_HZ:g}Hz of sim time)')

    def on_clock(self, msg):
        t = msg.sim.sec + msg.sim.nsec * 1e-9
        with self.lock:
            if self.last is not None and self.last <= t < self.last + self.step:
                return                       # 아직 한 칸이 안 지났다(시간이 되돌아가면 바로 보낸다: 월드 리셋)
            self.last = t
        out = Clock()
        out.clock.sec, out.clock.nanosec = msg.sim.sec, msg.sim.nsec
        self.pub.publish(out)


def main():
    rclpy.init()
    node = ClockRelay()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
