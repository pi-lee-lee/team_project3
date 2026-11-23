"""시험용 가상 시설: 소규모 공장(사무실 + 생산동 + 전기실 + ㄱ자 복도).

월드(SDF)와 '설계도 기준 지도'(reference map)를 같은 정의에서 만든다.
실제 운영 지도는 이 월드에서 SLAM 으로 만든다(sim/tools/explore.py → save_map.sh). 설계도 기준 지도는
SLAM 지도가 없을 때의 대체용이고, 스토리보드 그림에도 쓴다.

좌표: 로봇 충전 위치(사무실 안)를 원점 (0,0) 으로 둔다. SLAM 지도의 원점도 시작 위치이므로 두 좌표가 같다.

   y
   7 ┌────────────────────┬──────────────────────┬────┐
     │ 전기실             │ 생산동               │ C2 │ ← 비상구(초록)
     │ 분전반(노랑) P4    │  랙      랙          │폭  │  P3 = 비상구 표시등(C2 끝)
     │            ┌─문    문─┐ P2(랙 앞 사진: 받침만) │1.1 │
   3 ├──── 문 ────┤소화기 사진←P1  설비     설비      │
     │ 사무실     │          │                    문───┤
     │  책상섬    │          └─── 문 ─────────────┘    │
     │ ◎충전      문 ─ C1 복도 (폭 1.4) ─────────────── ┘ (꺾임)
  -1 └────────────────────────────────────────────────┘
     -1                                               8
실행: python3 world_spec.py  → inspection.world, ros/maps/reference.pgm/.yaml

카메라 판독 대상(계기판·표시등·열화상 인쇄물)도 여기서 정의한다. 이것들은 충돌체 없이 모양(visual)만 있어서
라이다(ray 센서는 충돌체만 본다)에 잡히지 않고 지도에도 넣지 않는다 → 넣고 빼도 SLAM 재스캔이 필요 없다.
"""
import math
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
    # 소화기 (생산동 서쪽 벽). 지금은 월드에 세우지 않고 그 자리에 소화기 사진 판(P1)을 건다(PHOTO_PANELS).
    # 저장된 SLAM 지도에는 이 상자가 남아 있어 지도(rects)에는 그대로 둔다 → 지도를 다시 만들 필요가 없다.
    ('target_red', 3.2, 3.9, 0.3, 0.5, (0.8, 0.1, 0.1)),
    ('target_green', 7.65, 7.0, 0.5, 0.2, (0.1, 0.7, 0.2)),     # 비상구 표시 (C2 끝)
    ('target_yellow', -0.8, 4.6, 0.3, 0.6, (0.9, 0.8, 0.1)),    # 분전반 (전기실 서쪽 벽)
]
# 색 상자 높이(m). 라이다 평면(약 0.13m)보다 높기만 하면 지도는 같다.
# 로봇 카메라는 바닥에서 0.10m, 세로 화각 48.7° 라서 0.9m 앞에서는 높이 0.5m 까지만 찍힌다. 초록·노랑 상자를 0.6m 로 두면
# 사진 위쪽이 상자로 꽉 차서 표시등·계기판을 "상자 위"에 둘 수 없다 → 0.2m 로 낮추고 그 위 벽에 붙인다.
TARGET_H = {'target_red': 0.6, 'target_green': 0.2, 'target_yellow': 0.2}

# ---- 카메라 판독 대상 (모양만 있고 충돌체가 없다. 상태는 sim/tools/target.py 로 바꾼다) ----
# 색은 사진 판독기와의 약속이다(0~255). 발광 재질이라 조명과 무관하게 거의 이 색 그대로 찍힌다.
WHITE, BLACK = (255, 255, 255), (0, 0, 0)
GAUGE_HUB_RGB, GAUGE_NEEDLE_RGB = (0, 0, 255), (255, 0, 0)
LAMP_COLORS = {'green': (0, 255, 0), 'yellow': (255, 220, 0), 'red': (255, 0, 0), 'off': (40, 40, 40)}
THERMAL_BG, THERMAL_HOT = (40, 0, 80), ((255, 120, 0), (255, 230, 0), (255, 255, 255))   # 바탕, 뜨거운 부분(밖 → 안)
THERMAL_SIZE = (0.40, 0.30)                                         # 인쇄물 가로, 세로(m)
THERMAL_HOT_RATIO = {'normal': 0.0, 'warning': 0.03, 'emergency': 0.15}   # 뜨거운 부분(주황 원) 넓이 / 판 넓이

# 계기판: 전기실 서쪽 벽, 분전반(노랑 상자) 바로 위. facing = 판이 바라보는 방향(도), z = 중심 높이
GAUGE = {'x': X0 + T / 2, 'y': 4.6, 'z': 0.41, 'facing': 0, 'value': 0.8}
GAUGE_R, GAUGE_RIM_R, GAUGE_HUB_R, GAUGE_NEEDLE = 0.12, 0.13, 0.02, (0.10, 0.015)   # 원판, 테두리, 허브 반지름, 바늘(길이, 굵기)
# 표시등: C2 끝 북쪽 벽, 비상구 표시(초록 상자) 위. 구가 벽에 닿게 중심을 반지름만큼 띄운다
LAMP_R = 0.05
LAMP = {'x': 7.65, 'y': Y1 - T / 2 - LAMP_R, 'z': 0.36, 'color': 'green'}
# 소화기 사진 판(P1)을 "자리에서 벗어남"으로 만들 때 옮겨 놓는 곳: 같은 벽을 따라 남쪽으로 0.5m
EXTINGUISHER_MOVED = (XO + T / 2, 3.4)

# 화재(열화상 인쇄물)를 세우는 자리: 벽면 위 판 중심의 지도 좌표 x, y 와 판이 바라보는 방향(도). sim/tools/fire.py 가 쓴다.
# 로봇은 판 앞 FIRE_STAND_DIST 에 판을 바라보고 선다(fire_stand). 점검 지점과 다른 벽이고 그 앞이 비어 있는 곳만 골랐다.
FIRE_SPOTS = {
    'office_south': (1.5, Y0 + T / 2, 90),     # 사무실 남쪽 벽
    'elec_north': (0.3, Y1 - T / 2, -90),      # 전기실 북쪽 벽
    'hall_east': (XH - T / 2, 3.2, 180),       # 생산동 동쪽 벽(C2 로 나가는 문 아래)
}
FIRE_Z = 0.27            # 판 중심 높이: 1m 앞 카메라(높이 0.10m)에 판 전체(0.12~0.42m)가 들어온다
FIRE_STAND_DIST = 1.0

# 소화기 사진 판(인식 모델 OBJECT detector='model' 이 읽는다): 실제 현장에서 로봇 카메라로 찍은 사진을 건다.
# 이름: (판 중심 x, y, 판이 바라보는 방향(도), 재질 이름). 재질·사진은 /sim/models/photo_panels.
# photo_p1 = 생산동 서쪽 벽, 소화기가 제자리에 있는 사진(→ 정상). target.py extinguisher remove 면 받침만 있는 사진으로 바뀐다.
# photo_p2 = 랙 1 남쪽 면, 받침만 있는 사진(→ 소화기 없음, 경고). 늘 이 상태로 두는 비교용.
PHOTO_MATERIAL = {'present': 'PhotoPanel/Extinguisher', 'empty': 'PhotoPanel/Empty'}
PHOTO_PANELS = {
    'photo_p1': (XO + T / 2, 3.9, 0, PHOTO_MATERIAL['present']),
    'photo_p2': (4.3, 4.4, -90, PHOTO_MATERIAL['empty']),      # 랙 1(4.3, 5.4, 세로 2.0) 남쪽 면 y = 4.4
}
PHOTO_SIZE = (0.60, 0.45)        # 가로, 세로(m). 사진 비율 4:3
PHOTO_Z = 0.28                   # 판 중심 높이: 0.9m 앞 카메라(높이 0.10m)에 판 전체(0.055~0.505m)가 들어온다
PHOTO_STAND_DIST = 0.9
PHOTO_MATERIALS = '/sim/models/photo_panels/materials'


def _stand(panel):
    """사진 판을 정면으로 보는 로봇 자세 (x, y, yaw 도): 판에서 PHOTO_STAND_DIST 앞."""
    x, y, facing, _ = PHOTO_PANELS[panel]
    a = math.radians(facing)
    yaw = (facing + 180) % 360
    return (round(x + PHOTO_STAND_DIST * math.cos(a), 3), round(y + PHOTO_STAND_DIST * math.sin(a), 3),
            yaw - 360 if yaw > 180 else yaw)


# 점검 지점: 로봇이 서서 대상을 촬영할 위치(지도 좌표)와 방향(도). DB(inspection_point)와 같은 값이다.
# P1 · P2 = 소화기 사진 판 앞, P3 = 비상구 표시등(C2 끝), P4 = 분전반 계기판(전기실 서쪽 벽)
POINTS = {'P1': _stand('photo_p1'), 'P2': _stand('photo_p2'), 'P3': (7.65, 6.1, 90), 'P4': (0.3, 4.6, 180)}
# 비상구 점검 지점의 비상구 앞 구역 [x1, y1, x2, y2](DB inspection_point.exit_zone 과 같은 값). 로봇이 이 안에서 막히면
# 복구 · 우회 없이 바로 진입 불가로 끝내고 목적지 쪽 사진을 올린다. P3 = 생산동 → C2 문(y 3.6) 위쪽부터 비상구 벽까지의 C2 복도.
EXIT_ZONES = {'P3': (XH, 3.6, X1, Y1)}

# 시험 때 놓고 치우는 적재물 (sim/tools/obstacle.py): x, y, 크기 x, 크기 y
OBSTACLES = {
    # detour · reroute 는 C1 · C2 복도를 따라갈 때만 경로 위다(예: 충전 위치 → C1 동쪽 끝 7.0, -0.1).
    # 충전 위치 → P3 는 이제 생산동을 가로지르므로 이 둘을 지나지 않는다 → 점검 지점 시험에는 아래 pallet · door 를 쓴다.
    'detour': (5.6, -0.35, 0.5, 0.5),     # C1 복도 가운데 팔레트 → 옆으로 비켜 지나감 (우회 가능)
    'reroute': (7.65, 1.6, 1.1, 0.4),     # C2 아래쪽 막힘 → C2 로 올라가는 길이 생산동 문뿐
    'block': (7.65, 5.2, 1.1, 0.4),       # C2 위쪽(생산동 문보다 위) 막힘 → P3 진입 불가
    # ---- 달리는 도중에 놓는 시험용(계획 경로 위에 놓인다. e2e_test.py 가 놓기 직전에 '경로 위'인지 확인한다) ----
    'pallet': (6.2, 4.1, 0.4, 0.4),       # 생산동 가운데, P1 → P3 직선 경로 위의 팔레트 → 제어기가 옆으로 비켜 지나감
    'door': (7.1, 4.1, 0.2, 1.0),         # 생산동 → C2 문이 막힘 → C1 · C2 아래쪽으로 크게 돌아 P3 로 (다른 경로)
    'pallet2': (1.6, 4.85, 0.4, 0.4),     # 전기실 가운데, P1 → P4(문 → P4) 직선 경로 위의 팔레트 → 비켜 지나감
    # 전기실 → 생산동 문 바로 아래에서 골목(서쪽 벽 ↔ 랙 1, 폭 0.95m)을 막음 → 랙 1 위(폭 0.75m)로 돌아 나와야 P1 에 닿는다.
    # P4 → P1 로 가는 로봇이 문을 지날 때 놓으면 '가던 길이 막혀 다시 계획'하는 시험이 된다.
    'aisle': (3.525, 5.1, 0.95, 0.2),
    # 같은 자리를 서쪽 벽에서부터 일부만 막아 랙 1 쪽에 틈을 남긴다(애매하게 막힌 경우): 남는 폭 0.7m / 0.6m / 0.5m
    'aisle70': (3.175, 5.1, 0.25, 0.3),
    'aisle60': (3.225, 5.1, 0.35, 0.3),
    'aisle50': (3.275, 5.1, 0.45, 0.3),
    # 비상구 앞 적재물(피난 통로 막힘 시험): P3(7.65, 6.1) 바로 앞 C2 복도 안쪽에 낮은 상자(가로 0.7 · 깊이 0.2 · 높이 0.22m).
    # 양옆 틈이 0.15m 라 로봇(폭 약 0.31m)은 못 지나가고, 라이다(높이 약 0.17m)보다 높아 장애물로 잡힌다.
    # 생산동 → C2 문(y 3.6~4.6)에서는 벽에 가려 안 보이는 자리라 로봇이 C2 에 들어와서야 발견한다. 진입 불가가 나면
    # 로봇은 목적지 쪽으로 돌아 사진을 찍으므로(robot-service MissionService) 낮은 상자 전체가 사진에 들어온다.
    'exit': (7.65, 6.0, 0.7, 0.2),
    # C1 → 생산동 문(y = YC, x 4.2~5.2)을 통째로 막음 → 생산동을 가로지르지 못하고 C1 복도 끝까지 가서 C2 로 꺾어 올라가야 한다.
    # 비상구 앞 구역(P3, y 3.6 위) 밖에서 막히는 것이라 기존 복구 · 우회 로직으로 다시 계획하는지 보는 시험용.
    'c1door': (4.7, YC, 1.2, 0.3),
}
OBSTACLE_H = {'exit': 0.22}   # 상자 높이(m). 없으면 0.6
# 좁은 통로 시험(obstacle.sh place gap 폭): C1 복도 양쪽 벽에서 상자 둘을 내밀어 가운데에 폭 width 의 틈을 남긴다.
# 틈은 x 방향으로 GAP_LEN 만큼 이어진다(문틀이 아니라 골목). C2 아래쪽을 reroute 로 함께 막으면 이 틈이 유일한 길이 된다.
GAP_X, GAP_LEN = 5.6, 0.6
GAP_THROUGH = (7.0, -0.1, 0)      # 틈을 지나야 닿는 시험 목표(C1 동쪽 끝)


def gap_boxes(width):
    """틈을 만드는 상자 둘: {이름: (x, y, 크기 x, 크기 y)}. 틈의 중심은 복도 가운데다."""
    lo, hi = Y0 + T / 2, YC - T / 2          # 복도 안쪽 면
    mid = (lo + hi) / 2
    a, b = mid - width / 2, mid + width / 2
    if not 0.3 <= width < hi - lo:
        raise ValueError(f'틈 폭은 0.3 ~ {hi - lo:.2f}m 사이: {width}')
    return {'gap_s': (GAP_X, (lo + a) / 2, GAP_LEN, a - lo), 'gap_n': (GAP_X, (b + hi) / 2, GAP_LEN, hi - b)}


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


def glow(rgb):
    """발광 재질: 조명 성분(ambient·diffuse)을 0 으로 두고 emissive 만 써서 음영 없이 지정한 색 그대로 찍힌다."""
    r, g, b = (c / 255 for c in rgb)
    return ('<material><ambient>0 0 0 1</ambient><diffuse>0 0 0 1</diffuse><specular>0 0 0 1</specular>'
            f'<emissive>{r:.4f} {g:.4f} {b:.4f} 1</emissive></material>')


def _visual(name, pose, geometry, rgb):
    return (f'        <visual name="{name}"><pose>{pose}</pose><cast_shadows>false</cast_shadows>'
            f'<geometry>{geometry}</geometry>{glow(rgb)}</visual>\n')


def _disc(name, depth, radius, rgb):
    """판 앞면에 붙는 얇은 원판. 원기둥 축(z)을 판의 법선(모델 x)으로 눕힌다."""
    return _visual(name, f'{depth:.4f} 0 0 0 {math.pi / 2:.5f} 0',
                   f'<cylinder><radius>{radius:.4f}</radius><length>0.004</length></cylinder>', rgb)


def _visual_model(name, x, y, z, yaw_deg, visuals):
    """충돌체가 없는 고정 모델. 모델 좌표: x = 판이 바라보는 쪽(보는 사람 쪽), y = 보는 사람의 오른쪽, z = 위."""
    return f'''    <model name="{name}">
      <static>true</static>
      <pose>{x:.3f} {y:.3f} {z:.3f} 0 0 {math.radians(yaw_deg):.5f}</pose>
      <link name="link">
{visuals}      </link>
    </model>
'''


def gauge_angle(value):
    """값 0~1 → 바늘 각도(도). 정면에서 봤을 때 오른쪽이 0°, 반시계 +: 0 → 225°(왼쪽 아래), 0.5 → 90°(위), 1 → -45°(오른쪽 아래)."""
    return 225.0 - max(0.0, min(1.0, value)) * 270.0


def gauge_model(value=None, name='target_gauge'):
    a = math.radians(gauge_angle(GAUGE['value'] if value is None else value))
    length, thick = GAUGE_NEEDLE
    v = _disc('rim', 0.003, GAUGE_RIM_R, BLACK) + _disc('face', 0.006, GAUGE_R, WHITE)
    # 바늘: 허브에서 바깥으로 뻗는 막대. 모델 x 축으로 a 만큼 돌리면 막대의 긴 축(y)이 (cos a, sin a) 방향이 된다
    v += _visual('needle', f'0.010 {length / 2 * math.cos(a):.4f} {length / 2 * math.sin(a):.4f} {a:.5f} 0 0',
                 f'<box><size>0.004 {length} {thick}</size></box>', GAUGE_NEEDLE_RGB)
    v += _disc('hub', 0.013, GAUGE_HUB_R, GAUGE_HUB_RGB)
    return _visual_model(name, GAUGE['x'], GAUGE['y'], GAUGE['z'], GAUGE['facing'], v)


def lamp_model(color=None, name='target_lamp'):
    rgb = LAMP_COLORS[color or LAMP['color']]
    v = _visual('bulb', '0 0 0 0 0 0', f'<sphere><radius>{LAMP_R}</radius></sphere>', rgb)
    return _visual_model(name, LAMP['x'], LAMP['y'], LAMP['z'], 0, v)


def thermal_model(spot, variant='emergency', name=None):
    """열화상 인쇄물: 진보라 판 위 가운데에 주황 → 노랑 → 흰색 원을 겹친다(뜨거운 부분 = 주황 원 전체)."""
    x, y, facing = FIRE_SPOTS[spot]
    w, h = THERMAL_SIZE
    v = _visual('sheet', '0.003 0 0 0 0 0', f'<box><size>0.004 {w} {h}</size></box>', THERMAL_BG)
    r = math.sqrt(THERMAL_HOT_RATIO[variant] * w * h / math.pi)
    if r > 0:
        for i, (scale, rgb) in enumerate(zip((1.0, 0.65, 0.3), THERMAL_HOT)):
            v += _disc(f'hot{i}', 0.006 + 0.003 * i, r * scale, rgb)
    return _visual_model(name or f'fire_{spot}', x, y, FIRE_Z, facing, v)


def photo_panel_model(panel, name=None, material=None, x=None, y=None):
    """사진 판: 얇은 상자 앞면에 사진 재질(조명 없음)을 입힌다. 충돌체가 없어 지도·주행에 영향이 없다.
    material·x·y 를 주면 그 값으로 바꿔 만든다(target.py 가 소화기를 치우거나 옮길 때)."""
    px, py, facing, base = PHOTO_PANELS[panel]
    x, y, material = px if x is None else x, py if y is None else y, material or base
    w, h = PHOTO_SIZE
    v = (f'        <visual name="photo"><pose>0.003 0 0 0 0 0</pose><cast_shadows>false</cast_shadows>'
         f'<geometry><box><size>0.004 {w} {h}</size></box></geometry>'
         f'<material><script><uri>file://{PHOTO_MATERIALS}/scripts</uri><uri>file://{PHOTO_MATERIALS}/textures</uri>'
         f'<name>{material}</name></script></material></visual>\n')
    return _visual_model(name or panel, x, y, PHOTO_Z, facing, v)


def fire_stand(spot):
    """그 자리의 판을 정면으로 보는 로봇 자세 (x, y, yaw 도)."""
    x, y, facing = FIRE_SPOTS[spot]
    a = math.radians(facing)
    yaw = (facing + 180) % 360
    return (round(x + FIRE_STAND_DIST * math.cos(a), 3), round(y + FIRE_STAND_DIST * math.sin(a), 3),
            yaw - 360 if yaw > 180 else yaw)


def target_box_model(target, x=None, y=None, name=None):
    """색 상자 하나(기본 위치는 TARGETS). target.py 가 소화기를 옮기거나 되돌릴 때 같은 정의로 다시 만든다."""
    _, tx, ty, sx, sy, rgb = next(t for t in TARGETS if t[0] == target)
    return box_model(name or target, tx if x is None else x, ty if y is None else y, sx, sy, TARGET_H[target], rgb)


def world():
    m = ''.join(box_model(n, x, y, sx, sy, WALL_H, (0.78, 0.78, 0.8)) for n, x, y, sx, sy in WALLS)
    m += ''.join(box_model(n, x, y, sx, sy, h, rgb) for n, x, y, sx, sy, h, rgb in FIXTURES)
    m += ''.join(target_box_model(n) for n, *_ in TARGETS if n != 'target_red')   # 소화기는 사진 판(P1)으로 대신한다
    m += gauge_model() + lamp_model()            # 처음 상태: 계기판 0.8, 표시등 초록 (열화상 인쇄물은 fire.py 로만 세운다)
    m += ''.join(photo_panel_model(p) for p in PHOTO_PANELS)
    return f'''<?xml version="1.0"?>
<!-- world_spec.py 로 생성. 직접 고치지 말고 world_spec.py 를 고친 뒤 다시 생성한다. -->
<sdf version="1.6">
  <world name="factory">
    <include><uri>model://ground_plane</uri></include>
    <include><uri>model://sun</uri></include>
    <scene><shadows>false</shadows><ambient>0.6 0.6 0.6 1</ambient><background>0.8 0.85 0.9 1</background></scene>
    <physics type="ode"><max_step_size>0.004</max_step_size><real_time_update_rate>250</real_time_update_rate></physics>
    <!-- 물체를 즉시 옮기는 서비스(/gazebo/set_entity_state): 시험용 장애물을 정한 순간에 정확히 놓는다(nav_soak.py) -->
    <plugin name="gazebo_ros_state" filename="libgazebo_ros_state.so"><ros><namespace>/gazebo</namespace></ros><update_rate>1.0</update_rate></plugin>
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
