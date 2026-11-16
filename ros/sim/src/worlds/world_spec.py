"""시험용 가상 시설: 소규모 공장(사무실 + 생산동 + 전기실 + ㄱ자 복도).

월드(SDF)와 '설계도 기준 지도'(reference map)를 같은 정의에서 만든다.
실제 운영 지도는 이 월드에서 SLAM 으로 만든다(sim/tools/explore.py → save_map.sh). 설계도 기준 지도는
SLAM 지도가 없을 때의 대체용이고, 스토리보드 그림에도 쓴다.

좌표: 로봇 충전 위치(사무실 안)를 원점 (0,0) 으로 둔다. SLAM 지도의 원점도 시작 위치이므로 두 좌표가 같다.

   y
   7 ┌────────────────────┬──────────────────────┬────┐
     │ 전기실             │ 생산동               │ C2 │ ← 비상구(초록)
     │ 분전반(노랑) P3    │  랙      랙          │폭  │
     │            ┌─문    문─┐                    │1.1 │
   3 ├──── 문 ────┤          │  설비     설비 P1←소화기  │
     │ 사무실     │          │                    문───┤
     │  책상섬    │          └─── 문 ─────────────┘    │
     │ ◎충전      문 ─ C1 복도 (폭 1.4) ─────────────── ┘ (꺾임)
  -1 └────────────────────────────────────────────────┘
     -1                                               8
실행: python3 world_spec.py  → inspection.world, ros/maps/reference.pgm/.yaml
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
WALL_H = 0.6
T = 0.1          # 벽 두께

# 건물 좌표(충전 위치 원점 기준) — 아래 함수가 벽 조각을 만든다
X0, X1, Y0, Y1 = -1.0, 8.2, -0.8, 7.2   # 바깥 벽
XO = 3.0         # 사무실·전기실 동쪽 벽
YO = 3.2         # 사무실 북쪽 벽 (사무실 | 전기실)
YC = 0.6         # C1 복도 북쪽 벽 (C1 폭 = YC - Y0 = 1.4)
XH = 7.1         # 생산동 동쪽 벽 (C2 폭 = X1 - XH = 1.1)
# 처음에는 C2 를 0.9m 로 두었으나, 저장 지도 + AMCL 운영에서 로봇 반경·벽 잡음 때문에 통행 불가로 판정됐다.
# TurtleBot3 Waffle + 기본 Nav2 여유값에서는 1.1m 이상이 필요하다(실제 현장 선정 때도 확인할 값).

DOORS = {  # 벽 이름: [(구간 시작, 끝)] — 문은 벽에 뚫린 틈
    'office_east': [(-0.6, 0.4)],       # 사무실 → C1 (x=XO, y 구간)
    'office_north': [(0.45, 1.45)],     # 사무실 → 전기실 (y=YO, x 구간)  폭 1.0
    'elec_east': [(5.2, 6.1)],          # 전기실 → 생산동 (x=XO, y 구간)
    'c1_north': [(4.2, 5.2)],           # C1 → 생산동 (y=YC, x 구간)
    'hall_east': [(3.6, 4.6)],          # 생산동 → C2 (x=XH, y 구간)
}


def hwall(name, y, xa, xb, doors=()):
    """y 고정, x 구간 [xa, xb] 의 벽을 문 구간을 빼고 조각낸다."""
    segs, cur = [], xa
    for a, b in sorted(doors):
        if a > cur:
            segs.append((cur, a))
        cur = b
    if cur < xb:
        segs.append((cur, xb))
    return [(f'{name}_{i}', (s + e) / 2, y, e - s, T) for i, (s, e) in enumerate(segs)]


def vwall(name, x, ya, yb, doors=()):
    """x 고정, y 구간 [ya, yb] 의 벽."""
    return [(n, x, cy, T, length) for n, cy, _, length, _ in hwall(name, x, ya, yb, doors)]


WALLS = (
    hwall('outer_south', Y0, X0, X1) + hwall('outer_north', Y1, X0, X1)
    + vwall('outer_west', X0, Y0, Y1) + vwall('outer_east', X1, Y0, Y1)
    + vwall('office_east', XO, Y0, YO, DOORS['office_east'])
    + hwall('office_north', YO, X0, XO, DOORS['office_north'])
    + vwall('elec_east', XO, YO, Y1, DOORS['elec_east'])
    + hwall('c1_north', YC, XO, XH, DOORS['c1_north'])
    + vwall('hall_east', XH, YC, Y1, DOORS['hall_east'])
)
# 사무실 동쪽 벽은 C1 복도 쪽(y < YC)에서만 문이 있고, 그 위(YC~YO)는 생산동과의 벽이다.

# 고정 설비·가구 (지도에 그대로 나타난다): 이름, x, y, 크기 x, 크기 y, 높이, 색
FIXTURES = [
    ('desk_island', 1.0, 1.6, 1.6, 0.8, 0.75, (0.55, 0.42, 0.3)),
    ('office_cabinet', -0.7, 2.6, 0.5, 1.0, 1.2, (0.5, 0.5, 0.55)),
    ('elec_shelf', 1.9, 5.8, 1.2, 0.5, 1.5, (0.5, 0.5, 0.55)),
    ('machine_1', 4.3, 2.0, 1.2, 0.8, 1.0, (0.35, 0.45, 0.6)),
    ('machine_2', 6.2, 2.1, 0.8, 1.0, 1.0, (0.35, 0.45, 0.6)),
    ('rack_1', 4.3, 5.4, 0.6, 2.0, 1.6, (0.6, 0.5, 0.3)),
    ('rack_2', 5.9, 5.6, 0.6, 1.6, 1.6, (0.6, 0.5, 0.3)),
]
# 점검 대상(색 상자): 이름, x, y, 크기 x, 크기 y, 색
TARGETS = [
    ('target_red', 3.2, 3.9, 0.3, 0.5, (0.8, 0.1, 0.1)),        # 소화기 (생산동 서쪽 벽)
    ('target_green', 7.65, 7.0, 0.5, 0.2, (0.1, 0.7, 0.2)),     # 비상구 표시 (C2 끝)
    ('target_yellow', -0.8, 4.6, 0.3, 0.6, (0.9, 0.8, 0.1)),    # 분전반 (전기실 서쪽 벽)
]
# 점검 지점: 로봇이 서서 대상을 촬영할 위치(지도 좌표)와 방향(도)
POINTS = {'P1': (4.3, 3.9, 180), 'P2': (7.65, 6.1, 90), 'P3': (0.3, 4.6, 180)}

# 시험 때 놓고 치우는 적재물 (sim/tools/obstacle.py): x, y, 크기 x, 크기 y
OBSTACLES = {
    'detour': (5.6, -0.35, 0.5, 0.5),     # C1 복도 가운데 팔레트 → 옆으로 비켜 지나감 (우회 가능)
    'reroute': (7.65, 1.6, 1.1, 0.4),     # C2 아래쪽 막힘 → 생산동 문으로 돌아서 C2 위쪽으로 (다른 경로)
    'block': (7.65, 5.2, 1.1, 0.4),       # C2 위쪽(생산동 문보다 위) 막힘 → P2 진입 불가
}
START = (0.0, 0.0, 0.0)

RES = 0.05
MX0, MY0, MX1, MY1 = X0 - 0.5, Y0 - 0.5, X1 + 0.5, Y1 + 0.5


def box_model(name, x, y, sx, sy, h, rgb):
    r, g, b = rgb
    return f'''    <model name="{name}">
      <static>true</static>
      <pose>{x:.3f} {y:.3f} {h / 2:.3f} 0 0 0</pose>
      <link name="link">
        <collision name="c"><geometry><box><size>{sx:.3f} {sy:.3f} {h:.3f}</size></box></geometry></collision>
        <visual name="v"><geometry><box><size>{sx:.3f} {sy:.3f} {h:.3f}</size></box></geometry>
          <material><ambient>{r} {g} {b} 1</ambient><diffuse>{r} {g} {b} 1</diffuse></material></visual>
      </link>
    </model>
'''


def world():
    m = ''.join(box_model(n, x, y, sx, sy, WALL_H, (0.78, 0.78, 0.8)) for n, x, y, sx, sy in WALLS)
    m += ''.join(box_model(n, x, y, sx, sy, h, rgb) for n, x, y, sx, sy, h, rgb in FIXTURES)
    m += ''.join(box_model(n, x, y, sx, sy, 0.6, rgb) for n, x, y, sx, sy, rgb in TARGETS)
    return f'''<?xml version="1.0"?>
<!-- world_spec.py 로 생성. 직접 고치지 말고 world_spec.py 를 고친 뒤 다시 생성한다. -->
<sdf version="1.6">
  <world name="factory">
    <include><uri>model://ground_plane</uri></include>
    <include><uri>model://sun</uri></include>
    <scene><shadows>false</shadows><ambient>0.6 0.6 0.6 1</ambient><background>0.8 0.85 0.9 1</background></scene>
    <physics type="ode"><max_step_size>0.004</max_step_size><real_time_update_rate>250</real_time_update_rate></physics>
{m}  </world>
</sdf>
'''


def rects():
    return ([(x, y, sx, sy) for _, x, y, sx, sy in WALLS]
            + [(x, y, sx, sy) for _, x, y, sx, sy, _, _ in FIXTURES]
            + [(x, y, sx, sy) for _, x, y, sx, sy, _ in TARGETS])


def reference_map():
    w = round((MX1 - MX0) / RES)
    h = round((MY1 - MY0) / RES)
    grid = [[205] * w for _ in range(h)]        # 바깥은 미지(회색)
    for row in range(h):
        cy = MY1 - (row + 0.5) * RES
        for col in range(w):
            cx = MX0 + (col + 0.5) * RES
            if X0 <= cx <= X1 and Y0 <= cy <= Y1:
                grid[row][col] = 254
    for x, y, sx, sy in rects():
        for row in range(h):
            cy = MY1 - (row + 0.5) * RES
            if abs(cy - y) > sy / 2 + RES / 2:
                continue
            for col in range(w):
                cx = MX0 + (col + 0.5) * RES
                if abs(cx - x) <= sx / 2 + RES / 2:
                    grid[row][col] = 0
    return w, h, grid


def main():
    maps = HERE.parents[2] / 'maps'      # ros/maps (호스트에서 실행)
    (HERE / 'inspection.world').write_text(world(), encoding='utf-8')
    maps.mkdir(exist_ok=True)
    w, h, grid = reference_map()
    with open(maps / 'reference.pgm', 'wb') as f:
        f.write(f'P5\n{w} {h}\n255\n'.encode())
        f.write(bytes(v for row in grid for v in row))
    (maps / 'reference.yaml').write_text(
        f'image: reference.pgm\nmode: trinary\nresolution: {RES}\norigin: [{MX0}, {MY0}, 0.0]\n'
        'negate: 0\noccupied_thresh: 0.65\nfree_thresh: 0.25\n', encoding='utf-8')
    print(f'world ({len(WALLS)} wall segments) + reference map {w}x{h}')


if __name__ == '__main__':
    main()
