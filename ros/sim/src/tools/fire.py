"""화재 흉내: 열화상 인쇄물을 벽에 세우고, (젯봇이 없으므로) 젯봇의 감지 보고를 대신 보낸다.

  /sim/tools/fire.sh list                                        자리 이름·좌표·그 앞에 설 자세 (JSON)
  /sim/tools/fire.sh place <자리> [normal|warning|emergency] [--detect]
                                                                 인쇄물 세우기(기본 emergency). --detect 면 바로 보고까지
  /sim/tools/fire.sh detect <자리> [warning|emergency]            감지 보고만 보내기(기본 emergency)
  /sim/tools/fire.sh clear [자리]                                 인쇄물 치우기(자리가 없으면 전부)

자리·판 모양의 원본은 worlds/world_spec.py (FIRE_SPOTS, thermal_model). 판은 충돌체가 없어 주행과 지도에 영향이 없다.
감지 보고: /patrol/detection (std_msgs/String JSON) 에 같은 detId 로 1초 간격 3번 — docs/design/INTERFACES.md 2.3 절.
"""
import json
import math
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'worlds'))
import world_spec as W  # noqa: E402

VARIANTS = tuple(W.THERMAL_HOT_RATIO)                 # normal, warning, emergency
REPORTABLE = ('warning', 'emergency')                 # NORMAL 은 보고하지 않는다(계약)
REPORT_COUNT, REPORT_INTERVAL = 3, 1.0


def spots():
    out = {}
    for name, (x, y, facing) in W.FIRE_SPOTS.items():
        sx, sy, syaw = W.fire_stand(name)
        out[name] = {'x': round(x, 3), 'y': round(y, 3), 'z': W.FIRE_Z, 'facingDeg': facing,
                     'stand': {'x': sx, 'y': sy, 'yaw': round(math.radians(syaw), 4), 'yawDeg': syaw}}
    return out


DET_ID = None      # --id=<detId>: 같은 화재를 계속 보고 있는 것처럼 같은 ID 로 다시 보고할 때


def detection(spot, variant):
    x, y, _ = W.FIRE_SPOTS[spot]
    return {'detId': DET_ID or f'sim-{spot}-{int(time.time())}', 'kind': 'THERMAL', 'grade': variant.upper(),
            'value': W.THERMAL_HOT_RATIO[variant], 'confidence': 0.9, 'x': round(x, 3), 'y': round(y, 3),
            'poseQuality': 1.0, 'stamp': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}


def report(node, spot, variant):
    import rclpy
    from std_msgs.msg import String
    pub = node.create_publisher(String, '/patrol/detection', 10)
    end = time.monotonic() + 3.0                      # 받는 쪽(rosbridge)과 연결될 때까지 잠깐 기다린다
    while pub.get_subscription_count() == 0 and time.monotonic() < end:
        rclpy.spin_once(node, timeout_sec=0.1)
    body = json.dumps(detection(spot, variant), ensure_ascii=False)
    for i in range(REPORT_COUNT):
        pub.publish(String(data=body))
        rclpy.spin_once(node, timeout_sec=0.05)
        if i < REPORT_COUNT - 1:
            time.sleep(REPORT_INTERVAL)
    print(f'detect {spot}: {body} (구독자 {pub.get_subscription_count()})')


def main():
    global DET_ID
    DET_ID = next((a[5:] for a in sys.argv[1:] if a.startswith('--id=')), None)
    args = [a for a in sys.argv[1:] if a != '--detect' and not a.startswith('--id=')]
    with_detect = '--detect' in sys.argv[1:]
    cmd = args[0] if args else ''
    if cmd == 'list' and len(args) == 1:
        print(json.dumps({'standDistance': W.FIRE_STAND_DIST, 'size': list(W.THERMAL_SIZE), 'spots': spots()}, ensure_ascii=False))
        return
    if cmd not in ('place', 'detect', 'clear') or len(args) > 3 or (cmd != 'clear' and len(args) < 2):
        raise SystemExit(__doc__)
    names = args[1:2] or list(W.FIRE_SPOTS)
    for n in names:
        if n not in W.FIRE_SPOTS:
            raise SystemExit(f'모르는 자리 {n}: {list(W.FIRE_SPOTS)}')
    variant = args[2] if len(args) > 2 else 'emergency'
    if cmd == 'clear' and len(args) > 2:
        raise SystemExit(__doc__)
    if variant not in VARIANTS:
        raise SystemExit(f'모르는 종류 {variant}: {list(VARIANTS)}')
    if (cmd == 'detect' or with_detect) and variant not in REPORTABLE:
        raise SystemExit('normal 은 감지 보고를 보내지 않습니다 (warning 또는 emergency)')

    from gazebo import Gazebo          # ROS 가 필요한 부분은 여기서부터(list 는 ROS 없이도 된다)
    gz = Gazebo('fire_tool')
    for n in names if cmd in ('place', 'clear') else ():
        if cmd == 'clear':
            print(f'clear {n}: {gz.remove(f"fire_{n}") > 0}')
        else:                      # 이미 서 있으면 치우고 새 종류로 세운다
            gz.replace(f'fire_{n}', lambda name, n=n: W.thermal_model(n, variant, name))
            print(f'place {n} {variant}: {json.dumps(spots()[n])}')
    if cmd == 'detect' or (cmd == 'place' and with_detect):
        report(gz.node, names[0], variant)
    gz.close()


if __name__ == '__main__':
    main()
