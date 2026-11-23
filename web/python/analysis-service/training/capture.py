"""터틀봇 카메라로 학습용 사진을 모은다(WSL Ubuntu 24.04 + ROS 2 Jazzy, 도메인 99).

    python3 capture.py                      # 저장 폴더 기본: ~/dataset/raw
    python3 capture.py --out ~/dataset/raw --tag extinguisher   # 태그는 영어(WSL 터미널은 한글 입력이 안 됨)

창이 뜨면
    스페이스 : 한 장 저장
    a        : 자동 저장 켜기/끄기(0.5초마다, --every 로 바꿈)
    q / Esc  : 끝

토픽은 /camera/image_raw/compressed(JPEG)를 받는다. 받은 JPEG 를 다시 압축하지 않고 그대로 저장한다
(판독 서버가 받는 사진과 같은 화질).
"""
import argparse
import os
import time

import cv2
import numpy as np
import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import HistoryPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import CompressedImage


class Capture(Node):
    def __init__(self, args):
        super().__init__('dataset_capture')
        self.args = args
        self.out = os.path.expanduser(args.out)
        os.makedirs(self.out, exist_ok=True)
        self.last = None            # 마지막 영상 JPEG
        self.fresh = False          # 화면에 아직 안 그린 새 영상이 왔는가
        self.saved_last = False     # 마지막 영상을 이미 저장했는가(같은 영상을 두 번 저장하지 않게)
        self.auto = False
        self.auto_stamp = None      # 자동 저장한 마지막 영상의 촬영 시각(초)
        self.count = len([f for f in os.listdir(self.out) if f.endswith('.jpg')])
        # 와이파이에서 영상이 몇 초씩 밀렸다가 한꺼번에 오는 일이 있어, 밀린 영상을 버리지 않게 큐를 길게 둔다
        qos = QoSProfile(reliability=ReliabilityPolicy.BEST_EFFORT, history=HistoryPolicy.KEEP_LAST, depth=120)
        self.create_subscription(CompressedImage, args.topic, self.on_image, qos)
        self.get_logger().info(f'{args.topic} 구독, 저장 폴더 {self.out} (이미 {self.count}장)')

    def on_image(self, msg):
        self.last = bytes(msg.data)
        self.fresh = True
        self.saved_last = False
        # 자동 저장은 받은 시각이 아니라 촬영 시각 기준 간격으로(밀려서 한꺼번에 와도 고르게 저장)
        stamp = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9
        if self.auto and (self.auto_stamp is None or stamp - self.auto_stamp >= self.args.every
                          or stamp < self.auto_stamp):
            self.auto_stamp = stamp
            self.save()

    def save(self):
        if self.last is None or self.saved_last:
            return
        self.saved_last = True
        name = f'{self.args.tag}_{time.strftime("%m%d_%H%M%S")}_{self.count:04d}.jpg'
        with open(os.path.join(self.out, name), 'wb') as f:
            f.write(self.last)
        self.count += 1

    def show(self):
        # 새 영상이 왔을 때만 그린다(WSL 화면 전송이 밀리면 키 입력까지 느려진다)
        if not self.fresh:
            return
        self.fresh = False
        view = cv2.imdecode(np.frombuffer(self.last, np.uint8), cv2.IMREAD_COLOR)
        if view is None:
            return
        cv2.putText(view, f'{self.count} saved  {"AUTO" if self.auto else ""}', (10, 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255) if self.auto else (0, 200, 0), 2)
        cv2.putText(view, 'space=save  a=auto  q=quit', (10, 470),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        cv2.imshow('capture', view)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--topic', default='/camera/image_raw/compressed')
    p.add_argument('--out', default='~/dataset/raw')
    p.add_argument('--tag', default='cap', help='파일 이름 앞부분(예: 소화기_노트북, 빈벽)')
    p.add_argument('--every', type=float, default=0.5, help='자동 저장 간격(초)')
    args = p.parse_args()
    rclpy.init()
    node = Capture(args)
    try:
        while rclpy.ok():
            try:
                rclpy.spin_once(node, timeout_sec=0.01)
                for _ in range(60):                    # 밀려 온 영상을 화면 한 번 그리기 전에 모두 처리
                    rclpy.spin_once(node, timeout_sec=0)
            except (KeyboardInterrupt, ExternalShutdownException):
                break
            node.show()
            key = cv2.waitKey(1) & 0xFF
            if key == ord(' '):
                node.save()
            elif key == ord('a'):
                node.auto = not node.auto
                node.auto_stamp = None
                node.fresh = node.last is not None     # AUTO 표시를 바로 바꿔 그린다
                print('자동 저장', '켬' if node.auto else '끔', f'(지금 {node.count}장)', flush=True)
            elif key in (ord('q'), 27):
                break
    finally:
        print(f'끝: {node.count}장 ({node.out})')
        cv2.destroyAllWindows()
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
