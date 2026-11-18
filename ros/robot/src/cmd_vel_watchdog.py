"""로봇 측 워치독: 원격 조종 명령이 끊기면 로봇을 세운다.

서버의 원격 조종은 /cmd_vel_teleop 으로 들어오고, 이 노드가 /cmd_vel 로 전달한다.
마지막 명령 이후 TIMEOUT_SEC 동안 새 명령이 없으면 정지 명령을 한 번 발행한다.
서버나 네트워크가 끊겨도 로봇이 계속 움직이지 않게 하는 안전장치다.
"""
import time

import rclpy
from geometry_msgs.msg import Twist
from rclpy.node import Node

TIMEOUT_SEC = 0.5


class CmdVelWatchdog(Node):
    def __init__(self):
        super().__init__('cmd_vel_watchdog')
        self.pub = self.create_publisher(Twist, '/cmd_vel', 10)
        self.create_subscription(Twist, '/cmd_vel_teleop', self.on_cmd, 10)
        self.last = None
        self.create_timer(0.1, self.check)

    def on_cmd(self, msg):
        self.last = time.monotonic()
        self.pub.publish(msg)

    def check(self):
        if self.last is not None and time.monotonic() - self.last > TIMEOUT_SEC:
            self.pub.publish(Twist())
            self.get_logger().info('teleop timeout -> stop')
            self.last = None


def main():
    rclpy.init()
    rclpy.spin(CmdVelWatchdog())


if __name__ == '__main__':
    main()
