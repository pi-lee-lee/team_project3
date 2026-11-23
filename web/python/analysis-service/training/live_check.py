"""학습한 모델(best.pt)을 터틀봇 카메라 영상에 바로 돌려 본다(결과 확인용).

    python3 live_check.py --model ~/models/best.pt
    python3 live_check.py --model ~/models/best.pt --conf 0.5 --save ~/dataset/hard

창에 상자·이름·신뢰도가 그려진다. 스페이스를 누르면 지금 화면 원본을 --save 폴더에 저장한다
(틀리게 잡은 장면을 모아 다시 라벨링 → 재학습할 때 쓴다). q / Esc : 끝.
"""
import argparse
import os
import time

import cv2
import numpy as np
import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import CompressedImage
from ultralytics import YOLO


class Live(Node):
    def __init__(self, topic):
        super().__init__('yolo_live_check')
        self.last = None
        self.create_subscription(CompressedImage, topic, self.on_image, qos_profile_sensor_data)

    def on_image(self, msg):
        data = bytes(msg.data)
        img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
        if img is not None:
            self.last = (data, img)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--model', required=True)
    p.add_argument('--topic', default='/camera/image_raw/compressed')
    p.add_argument('--conf', type=float, default=0.4)
    p.add_argument('--save', default='~/dataset/hard')
    args = p.parse_args()
    model = YOLO(os.path.expanduser(args.model))
    save_dir = os.path.expanduser(args.save)
    rclpy.init()
    node = Live(args.topic)
    t_prev = time.time()
    try:
        while rclpy.ok():
            try:
                rclpy.spin_once(node, timeout_sec=0.03)
            except (KeyboardInterrupt, ExternalShutdownException):
                break
            if node.last is None:
                continue
            data, img = node.last
            res = model.predict(img, conf=args.conf, imgsz=640, verbose=False)[0]
            view = res.plot()
            now = time.time()
            cv2.putText(view, f'{1.0 / max(now - t_prev, 1e-3):.1f} fps  {len(res.boxes)} found', (10, 25),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 200, 0), 2)
            t_prev = now
            cv2.imshow('live_check', view)
            key = cv2.waitKey(1) & 0xFF
            if key == ord(' '):
                os.makedirs(save_dir, exist_ok=True)
                with open(os.path.join(save_dir, f'hard_{time.strftime("%m%d_%H%M%S")}.jpg'), 'wb') as f:
                    f.write(data)
            elif key in (ord('q'), 27):
                break
    finally:
        cv2.destroyAllWindows()
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
