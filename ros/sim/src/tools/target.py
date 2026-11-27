"""점검 대상(카메라 판독용)의 상태 바꾸기 — Gazebo 의 모델을 지우고 새 모양으로 다시 만든다.

  /sim/tools/target.sh gauge normal|warning|danger   압력계 사진: 정상(바늘 0.35, 초록) · 주의(0.70, 노랑) · 위험(0.90, 빨강)
  /sim/tools/target.sh lamp green|yellow|red|off     표시등 색
  /sim/tools/target.sh extinguisher remove|move|restore
                                                     소화기 사진 판(P1): 받침만 있는 사진으로 바꿈 / 벽을 따라 옆으로 옮김 / 원위치
  /sim/tools/target.sh status                        현재 상태(JSON)
  /sim/tools/target.sh reset                         전부 기본값(압력계 정상, 표시등 green, 소화기 원위치)

모양·위치·색의 원본은 worlds/world_spec.py 다(압력계 사진은 worlds/demo_images.py). 압력계 · 표시등은 충돌체가 없어
주행과 지도에 영향이 없다.
소화기는 사진 판이라 충돌체가 없다(인식 모델이 사진 속 소화기를 찾는다). 상태는 컨테이너 안 파일에 적어 두며,
sim 을 다시 띄우면 월드와 함께 기본값으로 돌아간다.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'worlds'))
import world_spec as W  # noqa: E402

STATE_FILE = Path('/tmp/sim_target_state.json')
DEFAULT = {'gauge': W.GAUGE['state'], 'lamp': W.LAMP['color'], 'extinguisher': 'restore'}
EXTINGUISHER = 'photo_p1'


def load():
    try:
        st = {**DEFAULT, **json.loads(STATE_FILE.read_text())}
        if st['gauge'] not in W.GAUGE_VALUES:        # 예전 파일(바늘 값 숫자)
            st['gauge'] = DEFAULT['gauge']
        return st
    except (OSError, ValueError):
        return dict(DEFAULT)


def describe(st):
    """상태에 위치 정보를 붙인다(시험 스크립트가 읽는다)."""
    rx, ry, *_ = W.PHOTO_PANELS[EXTINGUISHER]
    ex = {'restore': (rx, ry), 'move': W.EXTINGUISHER_MOVED, 'remove': None}[st['extinguisher']]
    return {
        'gauge': {'state': st['gauge'], 'value': W.GAUGE_VALUES[st['gauge']],
                  'angleDeg': round(W.gauge_angle(W.GAUGE_VALUES[st['gauge']]), 1),
                  'x': W.GAUGE['x'], 'y': W.GAUGE['y'], 'z': W.GAUGE['z']},
        'lamp': {'color': st['lamp'], 'x': W.LAMP['x'], 'y': round(W.LAMP['y'], 3), 'z': W.LAMP['z']},
        'extinguisher': {'state': {'restore': 'in_place', 'move': 'moved', 'remove': 'removed'}[st['extinguisher']],
                         'x': ex and ex[0], 'y': ex and ex[1]},
    }


def apply(gz, key, value):
    """Gazebo 의 모델을 지우고 새 상태로 다시 만든다(이름 뒤에 번호가 붙는다: target_lamp__123 — gazebo.py 참고)."""
    if key == 'gauge':
        gz.replace('target_gauge', lambda name: W.gauge_model(value, name))
    elif key == 'lamp':
        gz.replace('target_lamp', lambda name: W.lamp_model(value, name))
    elif value == 'remove':        # 같은 자리, 받침만 있는 사진
        gz.replace(EXTINGUISHER, lambda name: W.photo_panel_model(EXTINGUISHER, name, W.PHOTO_MATERIAL['empty']))
    elif value == 'move':
        gz.replace(EXTINGUISHER, lambda name: W.photo_panel_model(EXTINGUISHER, name, None, *W.EXTINGUISHER_MOVED))
    else:
        gz.replace(EXTINGUISHER, lambda name: W.photo_panel_model(EXTINGUISHER, name))


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
        if args[1] not in W.GAUGE_VALUES:
            raise SystemExit(f'gauge 는 {" | ".join(W.GAUGE_VALUES)} 중 하나입니다(정상 · 주의 · 위험 사진)')
        changes = {'gauge': args[1]}
    elif cmd == 'lamp' and len(args) == 2 and args[1] in W.LAMP_COLORS:
        changes = {'lamp': args[1]}
    elif cmd == 'extinguisher' and len(args) == 2 and args[1] in ('remove', 'move', 'restore'):
        changes = {'extinguisher': args[1]}
    else:
        raise SystemExit(__doc__)
    from gazebo import Gazebo          # ROS 가 필요한 부분은 여기서부터(status 는 ROS 없이도 된다)
    gz = Gazebo('target_tool')
    for key, value in changes.items():
        apply(gz, key, value)
        st[key] = value
        STATE_FILE.write_text(json.dumps(st))      # 하나 바꿀 때마다 적는다(중간에 실패해도 적힌 데까지는 맞다)
    gz.close()
    print(json.dumps(describe(st), ensure_ascii=False))


if __name__ == '__main__':
    main()
