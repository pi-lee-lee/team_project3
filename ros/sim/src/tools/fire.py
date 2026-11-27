"""열화상 사진 판의 상태 바꾸기 + (오탐 시험용) 가짜 감지 보고.

  /sim/tools/fire.sh list                                  자리 이름 · 좌표 · 지금 상태 · 그 앞에 설 자세 (JSON)
  /sim/tools/fire.sh set <자리> normal|warning|emergency    사진만 바꾼다: 꺼짐(정상) · 과열(경고) · 화재(비상)
  /sim/tools/fire.sh reset                                 모든 자리를 꺼짐(정상)으로
  /sim/tools/fire.sh extinguish                            화재(emergency)인 자리를 꺼짐으로(투척 뒤 sim_control 이 부른다)
  /sim/tools/fire.sh detect <자리> [warning|emergency]      가짜 감지 보고만 보낸다(기본 emergency) — 오탐 시험용

사진 판은 월드에 늘 걸려 있다(worlds/world_spec.py 의 THERMAL_SPOTS · thermal_model, 사진은 worlds/demo_images.py).
순찰 중인 로봇이 그 앞을 지나가며 사진을 판독해 스스로 찾는다(서버의 순찰 감시). 그래서 화재 · 과열은 사진만 바꾸면 되고
감지 보고를 따로 보내지 않는다. detect 는 '사진은 정상인데 보고만 온' 오탐을 만들 때만 쓴다:
/patrol/detection (std_msgs/String JSON) 에 같은 detId 로 1초 간격 3번 — docs/design/INTERFACES.md 2.3 절.
상태는 컨테이너 안 파일에 적어 두며, sim 을 다시 띄우면 월드와 함께 꺼짐으로 돌아간다.
"""
import json
import math
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'worlds'))
import world_spec as W  # noqa: E402

STATE_FILE = Path('/tmp/sim_fire_state.json')
REPORTABLE = ('warning', 'emergency')                 # NORMAL 은 보고하지 않는다(계약)
REPORT_COUNT, REPORT_INTERVAL = 3, 1.0
HOT_RATIO = {'normal': 0.0, 'warning': 0.009, 'emergency': 0.07}   # 사진 속 뜨거운 영역 비율(가짜 보고의 value)


def load():
    try:
        st = json.loads(STATE_FILE.read_text())
        return {s: st.get(s, 'normal') if st.get(s) in W.THERMAL_STATES else 'normal' for s in W.THERMAL_SPOTS}
    except (OSError, ValueError):
        return {s: 'normal' for s in W.THERMAL_SPOTS}


def save(st):
    STATE_FILE.write_text(json.dumps(st))


def spots(st):
    out = {}
    for name, (x, y, facing) in W.THERMAL_SPOTS.items():
        sx, sy, syaw = W.thermal_stand(name)
        out[name] = {'x': round(x, 3), 'y': round(y, 3), 'z': W.THERMAL_Z, 'facingDeg': facing, 'state': st[name],
                     'stand': {'x': sx, 'y': sy, 'yaw': round(math.radians(syaw), 4), 'yawDeg': syaw}}
    return out


def detection(spot, grade, det_id):
    # 판 앞 0.1m(판이 바라보는 쪽)를 열원 자리로 보낸다 — 순찰 감시(raycast)와 같은 기준. 벽면 위를 보내면 벽 반대편 방에서도
    # 보인다고 판단해(투척 위치 계산) 판 뒷면 쪽으로 로봇이 간다
    px, py, facing = W.THERMAL_SPOTS[spot]
    x, y = px + 0.1 * math.cos(math.radians(facing)), py + 0.1 * math.sin(math.radians(facing))
    return {'detId': det_id or f'sim-{spot}-{int(time.time())}', 'kind': 'THERMAL', 'grade': grade.upper(),
            'value': HOT_RATIO[grade], 'confidence': 0.9, 'x': round(x, 3), 'y': round(y, 3),
            'poseQuality': 1.0, 'stamp': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}


def report(node, spot, grade, det_id):
    import rclpy
    from std_msgs.msg import String
    pub = node.create_publisher(String, '/patrol/detection', 10)
    end = time.monotonic() + 3.0                      # 받는 쪽(rosbridge)과 연결될 때까지 잠깐 기다린다
    while pub.get_subscription_count() == 0 and time.monotonic() < end:
        rclpy.spin_once(node, timeout_sec=0.1)
    body = json.dumps(detection(spot, grade, det_id), ensure_ascii=False)
    for i in range(REPORT_COUNT):
        pub.publish(String(data=body))
        rclpy.spin_once(node, timeout_sec=0.05)
        if i < REPORT_COUNT - 1:
            time.sleep(REPORT_INTERVAL)
    print(f'detect {spot}: {body} (구독자 {pub.get_subscription_count()})')


def main():
    det_id = next((a[5:] for a in sys.argv[1:] if a.startswith('--id=')), None)
    args = [a for a in sys.argv[1:] if not a.startswith('--id=')]
    cmd, rest = (args[0], args[1:]) if args else ('', [])
    st = load()
    if cmd == 'list' and not rest:
        print(json.dumps({'standDistance': W.THERMAL_STAND_DIST, 'size': list(W.THERMAL_SIZE), 'spots': spots(st)},
                         ensure_ascii=False))
        return
    changes = {}
    if cmd == 'set' and len(rest) == 2:
        spot, state = rest
        if spot not in W.THERMAL_SPOTS:
            raise SystemExit(f'모르는 자리 {spot}: {list(W.THERMAL_SPOTS)}')
        if state not in W.THERMAL_STATES:
            raise SystemExit(f'모르는 상태 {state}: {list(W.THERMAL_STATES)}')
        changes = {spot: state}
    elif cmd == 'reset' and not rest:
        changes = {s: 'normal' for s in W.THERMAL_SPOTS}
    elif cmd == 'extinguish' and not rest:
        changes = {s: 'normal' for s, v in st.items() if v == 'emergency'}
    elif cmd == 'detect' and 1 <= len(rest) <= 2:
        spot, grade = rest[0], (rest[1] if len(rest) > 1 else 'emergency')
        if spot not in W.THERMAL_SPOTS:
            raise SystemExit(f'모르는 자리 {spot}: {list(W.THERMAL_SPOTS)}')
        if grade not in REPORTABLE:
            raise SystemExit('감지 보고는 warning 또는 emergency 만 보낸다')
    else:
        raise SystemExit(__doc__)

    from gazebo import Gazebo          # ROS 가 필요한 부분은 여기서부터(list 는 ROS 없이도 된다)
    gz = Gazebo('fire_tool')
    for spot, state in changes.items():
        gz.replace(f'thermal_{spot}', lambda name, s=spot, v=state: W.thermal_model(s, v, name))
        st[spot] = state
        print(f'{spot} → {state}')
    if changes or cmd in ('reset', 'extinguish'):
        save(st)
        if not changes:
            print('바꿀 자리 없음')
    if cmd == 'detect':
        report(gz.node, rest[0], grade, det_id)
    gz.close()


if __name__ == '__main__':
    main()
