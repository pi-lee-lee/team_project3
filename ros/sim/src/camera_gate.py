"""시뮬레이션 카메라를 '누가 볼 때만' 그리게 한다(시뮬레이션 전용).

GPU 가 없으면 Gazebo 가 카메라 화면을 CPU 로 그리는데, 그리는 일의 절반쯤이 카메라다(5Hz 에서 시뮬레이션 속도 0.88 → 거의 끄면 0.96).
그래서 로봇 모델의 카메라를 '신호를 받을 때만 한 장 그리는' 카메라(triggered)로 바꾸고(sim.launch.py), 이 노드가
ROS 쪽 카메라 토픽(/camera/image_raw · /camera/image_raw/compressed 등)을 받는 곳이 있을 때만 CAMERA_HZ 로 신호를 보낸다.
관제 화면 영상 · 점검 촬영(web_video_server 스냅샷)은 받기 시작하면 곧바로 그림이 나온다. 아무도 안 받을 때도 IDLE_HZ(0.5Hz)로
한 장씩 그린다 — robot-service 의 출발 전 점검이 '카메라 정보(camera_info)를 5초 안에 받았는가'를 보기 때문이다.
실제 로봇의 카메라는 계속 내보내므로 이 노드가 없다.
"""
import os
import time

import gz.msgs10.boolean_pb2 as gz_bool
import gz.transport13 as gz_transport
import rclpy
from rclpy.node import Node

CAMERA_HZ = float(os.environ.get('SIM_CAMERA_HZ', '5'))
IDLE_HZ = float(os.environ.get('SIM_CAMERA_IDLE_HZ', '0.5'))   # 아무도 안 볼 때(출발 전 점검의 '카메라 수신' 5초보다 짧게)
IMAGE = '/camera/image_raw'
TRIGGER = '/camera/trigger'


class CameraGate(Node):
    def __init__(self):
        super().__init__('camera_gate')
        self.gz = gz_transport.Node()
        self.pub = self.gz.advertise(TRIGGER, gz_bool.Boolean)
        self.period = 1.0 / CAMERA_HZ
        self.idle_period = 1.0 / IDLE_HZ
        self.last = 0.0
        self.watching = False
        self.create_timer(0.05, self.tick)      # 실제 시간 0.05초마다: 받기 시작한 뒤 첫 장까지 늦어도 한 칸
        self.get_logger().info(f'camera gate ready ({CAMERA_HZ:g}Hz while someone subscribes to {IMAGE}*, else {IDLE_HZ:g}Hz)')

    def viewers(self):
        return sum(self.count_subscribers(name) for name, _ in self.get_topic_names_and_types()
                   if name == IMAGE or name.startswith(IMAGE + '/'))

    def tick(self):
        now = time.monotonic()
        watching = self.viewers() > 0
        if watching != self.watching:
            self.watching = watching
            self.get_logger().info('camera on (someone is watching)' if watching else 'camera off (nobody watching)')
        if now - self.last >= (self.period if watching else self.idle_period):
            self.last = now
            msg = gz_bool.Boolean()
            msg.data = True
            self.pub.publish(msg)


def main():
    rclpy.init()
    node = CameraGate()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
