"""점검 대상(카메라 판독용)의 상태 바꾸기 — Gazebo 의 모델을 지우고 새 모양으로 다시 만든다.

  /sim/tools/target.sh gauge 0.35                    계기판 바늘 (0~1. 0 = 왼쪽 아래, 0.5 = 위, 1 = 오른쪽 아래)
  /sim/tools/target.sh lamp green|yellow|red|off     표시등 색
  /sim/tools/target.sh extinguisher remove|move|restore
                                                     소화기(빨간 상자): 치움 / 벽을 따라 옆으로 옮김 / 원위치
  /sim/tools/target.sh status                        현재 상태(JSON)
  /sim/tools/target.sh reset                         전부 기본값(계기판 0.8, 표시등 green, 소화기 원위치)

모양·위치·색의 원본은 worlds/world_spec.py 다. 계기판·표시등은 충돌체가 없어 주행과 지도에 영향이 없다.
옮긴 소화기는 원래처럼 충돌체가 있다(벽에 붙어 있어 통로를 막지 않는다). 상태는 컨테이너 안 파일에 적어 두며,
sim 을 다시 띄우면 월드와 함께 기본값으로 돌아간다.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'worlds'))
import world_spec as W  # noqa: E402

STATE_FILE = Path('/tmp/sim_target_state.json')
DEFAULT = {'gauge': W.GAUGE['value'], 'lamp': W.LAMP['color'], 'extinguisher': 'restore'}
EXTINGUISHER = 'target_red'


def load():
    try:
        return {**DEFAULT, **json.loads(STATE_FILE.read_text())}
    except (OSError, ValueError):
        return dict(DEFAULT)


def describe(st):
    """상태에 위치 정보를 붙인다(시험 스크립트가 읽는다)."""
    _, rx, ry, *_ = next(t for t in W.TARGETS if t[0] == EXTINGUISHER)
    ex = {'restore': (rx, ry), 'move': W.EXTINGUISHER_MOVED, 'remove': None}[st['extinguisher']]
    return {
        'gauge': {'value': st['gauge'], 'angleDeg': round(W.gauge_angle(st['gauge']), 1),
                  'x': W.GAUGE['x'], 'y': W.GAUGE['y'], 'z': W.GAUGE['z']},
        'lamp': {'color': st['lamp'], 'x': W.LAMP['x'], 'y': round(W.LAMP['y'], 3), 'z': W.LAMP['z']},
        'extinguisher': {'state': {'restore': 'in_place', 'move': 'moved', 'remove': 'removed'}[st['extinguisher']],
                         'x': ex and ex[0], 'y': ex and ex[1]},
    }


def apply(gz, key, value):
    """Gazebo 의 모델을 지우고 새 상태로 다시 만든다(이름 뒤에 번호가 붙는다: target_lamp__123 — gz.py 참고)."""
    if key == 'gauge':
        gz.replace('target_gauge', lambda name: W.gauge_model(value, name))
    elif key == 'lamp':
        gz.replace('target_lamp', lambda name: W.lamp_model(value, name))
    elif value == 'remove':
        gz.remove(EXTINGUISHER)
    elif value == 'move':
        gz.replace(EXTINGUISHER, lambda name: W.target_box_model(EXTINGUISHER, *W.EXTINGUISHER_MOVED, name=name))
    else:
        gz.replace(EXTINGUISHER, lambda name: W.target_box_model(EXTINGUISHER, name=name))


def main():
    args = sys.argv[1:]
    cmd = args[0] if args else ''
    st = load()
    if cmd == 'status':
        print(json.dumps(describe(st), ensure_ascii=False))
        return
    if cmd == 'reset' and len(args) == 1:
        changes = dict(DEFAULT)
    elif cmd == 'gauge' and len(args) == 2:
        try:
            v = float(args[1])
        except ValueError:
            raise SystemExit('gauge 값은 0~1 사이 숫자입니다')
        if not 0.0 <= v <= 1.0:
            raise SystemExit('gauge 값은 0~1 사이 숫자입니다')
        changes = {'gauge': v}
    elif cmd == 'lamp' and len(args) == 2 and args[1] in W.LAMP_COLORS:
        changes = {'lamp': args[1]}
    elif cmd == 'extinguisher' and len(args) == 2 and args[1] in ('remove', 'move', 'restore'):
        changes = {'extinguisher': args[1]}
    else:
        raise SystemExit(__doc__)
    from gz import Gazebo          # ROS 가 필요한 부분은 여기서부터(status 는 ROS 없이도 된다)
    gz = Gazebo('target_tool')
    for key, value in changes.items():
        apply(gz, key, value)
        st[key] = value
        STATE_FILE.write_text(json.dumps(st))      # 하나 바꿀 때마다 적는다(중간에 실패해도 적힌 데까지는 맞다)
    gz.close()
    print(json.dumps(describe(st), ensure_ascii=False))


if __name__ == '__main__':
    main()
