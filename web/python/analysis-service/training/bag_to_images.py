"""ros2 bag 으로 녹화한 카메라 영상에서 사진을 뽑는다(JPEG 그대로, 다시 압축하지 않음).

녹화(촬영 중 켜 두기, 끝낼 때 Ctrl+C):
    ros2 bag record -o ~/bags/소화기_1 /camera/image_raw/compressed

뽑기:
    python3 bag_to_images.py ~/bags/소화기_1                       # 0.5초마다 한 장 → ~/dataset/raw
    python3 bag_to_images.py ~/bags/소화기_1 --every 0.3 --tag 소화기

연속 프레임은 거의 같은 사진이라 전부 쓰면 학습에 도움이 적다. --every 로 간격을 두고 뽑는다.
"""
import argparse
import os

import rosbag2_py
from rclpy.serialization import deserialize_message
from sensor_msgs.msg import CompressedImage


def main():
    p = argparse.ArgumentParser()
    p.add_argument('bag', help='ros2 bag 폴더')
    p.add_argument('--topic', default='/camera/image_raw/compressed')
    p.add_argument('--out', default='~/dataset/raw')
    p.add_argument('--tag', default=None, help='파일 이름 앞부분(기본: bag 폴더 이름)')
    p.add_argument('--every', type=float, default=0.5, help='뽑는 간격(초)')
    args = p.parse_args()
    bag = os.path.expanduser(args.bag).rstrip('/')
    out = os.path.expanduser(args.out)
    tag = args.tag or os.path.basename(bag)
    os.makedirs(out, exist_ok=True)

    reader = rosbag2_py.SequentialReader()
    reader.open(rosbag2_py.StorageOptions(uri=bag, storage_id=''),
                rosbag2_py.ConverterOptions(input_serialization_format='cdr', output_serialization_format='cdr'))
    reader.set_filter(rosbag2_py.StorageFilter(topics=[args.topic]))
    last, total, saved = None, 0, 0
    while reader.has_next():
        _, data, t_ns = reader.read_next()
        total += 1
        if last is not None and (t_ns - last) / 1e9 < args.every:
            continue
        msg = deserialize_message(data, CompressedImage)
        with open(os.path.join(out, f'{tag}_{saved:05d}.jpg'), 'wb') as f:
            f.write(bytes(msg.data))
        last, saved = t_ns, saved + 1
    print(f'{bag}: 프레임 {total}개 중 {saved}장 저장 → {out}')


if __name__ == '__main__':
    main()
