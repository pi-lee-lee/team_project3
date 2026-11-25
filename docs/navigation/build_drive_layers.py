"""주행에 쓰는 지도 3겹 설명서(그림): 기존 맵(저장 지도) · 계획 맵(전역 비용 지도) · 제어 맵(지역 비용 지도).

핵심: 주행은 지도 한 장이 아니라 3겹으로 돈다. 맨 아래 기존 맵은 변하지 않고, 그 위에 계획 맵이 건물 전체를 0.05m 칸으로,
맨 위 제어 맵이 로봇 둘레 3×3m 만 2배 촘촘한 0.025m 칸으로 본다. 새 장애물은 기존 맵이 아니라 위 두 겹의 층에 생긴다.

값은 ros/sim/src/config/nav2_params.yaml(global_costmap · local_costmap), ros/maps/site.yaml(0.05m, 183×160칸),
ros/robot/src/nav2_goal_bridge.py(가상 장애물)에서 가져왔다. 평면도는 world_spec.py 그대로다.
실행: python3 docs/navigation/build_drive_layers.py  →  docs/navigation/drive_layers.svg
"""
from pathlib import Path

import build_drive_controller as D        # docs/_lib 를 경로에 넣는다
from svg import C, Svg   # noqa: E402
from build_drive_controller import BLUE, GRAY, INK, ORANGE, PURPLE, RED, SUB, W

OUT = Path(__file__).resolve().parent / 'drive_layers.svg'
S = Svg(1640, 2000)
D.S = S                      # 공용 그리기 함수(card · para · poly · robot · world_map)가 이 도면에 그리게 한다

GREEN = '#248a3d'
L1, L2, L3 = '#3a3a3c', BLUE, C['py'][0]        # 기존 맵 · 계획 맵 · 제어 맵 색
K = 58                                           # 겹 그림의 px/m
MW, MH = (W.X1 - W.X0) * K, (W.Y1 - W.Y0) * K
SHX, SQ = -0.5, 0.5                             # 기울이기: 화면 x = x + SHX·y, 화면 y = SQ·y
ROBOT = (2.75, 5.38)                             # 예시 위치: P3 → P1 로 가며 전기실 문 앞
OBS = W.OBSTACLES['aisle60']                     # 예시 장애물: 문 바로 아래 골목을 반쯤 막은 상자
WIN = 3.0                                        # 제어 맵 한 변(m)
ZONE = (1.35, 6.25, 2.45, 6.85)                  # 예시 금지구역(x1, y1, x2, y2): 전기실 선반 위쪽. 실제로 있는 구역이 아니다
ZRED = '#ff3b30'


def lx(x):
    return (x - W.X0) * K


def ly(y):
    return (W.Y1 - y) * K


def iso(e, f, x, y):
    """겹 안의 좌표(m) → 화면 좌표."""
    return e + lx(x) + SHX * ly(y), f + SQ * ly(y)


def plane(e, f, col, draw, floor='#ffffff'):
    """기울인 지도 한 겹. draw(px, py) 가 겹 안에 그린다(late 를 쓰지 않는다)."""
    S.raw(f'<g transform="matrix(1 0 {SHX} {SQ} {e} {f})">')
    S.raw(f'<clipPath id="pl"><rect x="-10" y="-10" width="{MW + 20:.1f}" height="{MH + 20:.1f}" rx="6"/></clipPath>')
    S.rect(-10, -10, MW + 20, MH + 20, fill=floor, stroke='none', sw=0, rx=6)
    S.raw('<g clip-path="url(#pl)">')
    draw()
    S.raw('</g>')
    S.rect(-10, -10, MW + 20, MH + 20, fill='none', stroke=col, sw=3, rx=6)
    S.raw('</g>')


def rects(fill, grow=0.0, only=None, opacity=None):
    for i, (x, y, sx, sy) in enumerate(W.rects()):
        wall = i < len(W.WALLS)
        if only == 'wall' and not wall:
            continue
        S.rect(lx(x - sx / 2 - grow), ly(y + sy / 2 + grow), (sx + 2 * grow) * K, (sy + 2 * grow) * K,
               fill=fill if wall or only else '#b9b9c0', stroke='none', sw=0, rx=grow * K, opacity=opacity)


def obstacle_box(fill, stroke, grow=0.0, opacity=None, dash=None):
    x, y, sx, sy = OBS
    S.rect(lx(x - sx / 2 - grow), ly(y + sy / 2 + grow), (sx + 2 * grow) * K, (sy + 2 * grow) * K, fill=fill, stroke=stroke,
           sw=1.4 if stroke != 'none' else 0, rx=grow * K, opacity=opacity, dash=dash)


def zone_box(grow=0.0):
    """예시 금지구역. grow > 0 이면 팽창 띠(그만큼 키운 둥근 상자)만 그린다."""
    x1, y1, x2, y2 = ZONE
    if grow:
        return
    S.rect(lx(x1), ly(y2), (x2 - x1) * K, (y2 - y1) * K, fill='url(#zh)', stroke=ZRED, sw=2.4, rx=0)


def zone_band(grow, fill):
    x1, y1, x2, y2 = ZONE
    S.rect(lx(x1 - grow), ly(y2 + grow), (x2 - x1 + 2 * grow) * K, (y2 - y1 + 2 * grow) * K, fill=fill, stroke='none', sw=0, rx=grow * K)


def pts(path):
    return [(lx(a), ly(b)) for a, b in path]


# ------------------------------------------------------------------ 겹마다 그리는 내용
def draw_base():
    rects(L1)


def draw_plan():
    for i, (x, y, sx, sy) in enumerate(W.rects()):           # 팽창 0.45m: 벽 · 설비 둘레의 여유 띠
        S.rect(lx(x - sx / 2 - 0.45), ly(y + sy / 2 + 0.45), (sx + 0.9) * K, (sy + 0.9) * K, fill='#cfe4ff', stroke='none', sw=0, rx=0.45 * K)
    obstacle_box('#cfe4ff', 'none', 0.45)
    zone_band(0.45, '#cfe4ff')
    rects(L1)
    zone_box()                                               # 금지구역: 계획 맵에서는 가상 장애물 층에 합쳐진다
    obstacle_box('url(#lh)', BLUE)                           # 가상 장애물 층: 몸통 채우기
    x, y, sx, sy = OBS
    D.poly([(lx(x - sx / 2), ly(y + sy / 2)), (lx(x + sx / 2), ly(y + sy / 2))], RED, 3, late=False)   # 라이다 층: 본 면
    D.poly(pts(D.PATHS['P3>P1']), BLUE, 3.2, '0.1 7', late=False)
    D.robot(lx(ROBOT[0]), ly(ROBOT[1]), 0.22 * K, 20, late=False)
    for code, (px_, py_, _) in W.POINTS.items():
        S.raw(f'<circle cx="{lx(px_):.1f}" cy="{ly(py_):.1f}" r="7" fill="#ffffff" stroke="#30b0c7" stroke-width="3"/>')


def draw_ctrl():
    rects('#e5e5ea')                                         # 건물 윤곽은 흐리게(이 겹에는 없는 정보)
    x0, y0 = ROBOT[0] - WIN / 2, ROBOT[1] + WIN / 2
    S.raw(f'<clipPath id="win"><rect x="{lx(x0):.1f}" y="{ly(y0):.1f}" width="{WIN * K:.1f}" height="{WIN * K:.1f}"/></clipPath>')
    S.rect(lx(x0), ly(y0), WIN * K, WIN * K, fill='#fffaf2', stroke='none', sw=0, rx=0)
    S.raw('<g clip-path="url(#win)">')
    for x, y, sx, sy in W.rects():                           # 팽창 0.6m
        S.rect(lx(x - sx / 2 - 0.6), ly(y + sy / 2 + 0.6), (sx + 1.2) * K, (sy + 1.2) * K, fill='#ffe0b8', stroke='none', sw=0, rx=0.6 * K)
    obstacle_box('#ffe0b8', 'none', 0.6)
    zone_band(0.6, '#ffe0b8')
    zone_box()                                               # 금지구역: 제어 맵에서는 keepout_layer
    for x, y, sx, sy in list(W.rects()) + [OBS]:             # 라이다가 본 면(벽 · 설비 · 새 장애물 모두 같은 층)
        S.rect(lx(x - sx / 2), ly(y + sy / 2), sx * K, sy * K, fill='#fbe3e0', stroke=RED, sw=2.6, rx=0)
    S.raw('</g>')
    n = 12                                                   # 격자는 실제(120칸)의 1/10 만 그린다
    for i in range(n + 1):
        t = i * WIN * K / n
        S.raw(f'<line x1="{lx(x0) + t:.1f}" y1="{ly(y0):.1f}" x2="{lx(x0) + t:.1f}" y2="{ly(y0) + WIN * K:.1f}" stroke="{L3}" stroke-width=".5" opacity=".45"/>')
        S.raw(f'<line x1="{lx(x0):.1f}" y1="{ly(y0) + t:.1f}" x2="{lx(x0) + WIN * K:.1f}" y2="{ly(y0) + t:.1f}" stroke="{L3}" stroke-width=".5" opacity=".45"/>')
    S.rect(lx(x0), ly(y0), WIN * K, WIN * K, fill='none', stroke=L3, sw=3, rx=0)
    for dx, dy in [(0.9, -0.25), (0.95, -0.55), (0.85, 0.05)]:      # 제어기 후보 궤적 몇 개
        D.poly([(lx(ROBOT[0]), ly(ROBOT[1])), (lx(ROBOT[0] + dx * 0.5), ly(ROBOT[1] + dy * 0.3)), (lx(ROBOT[0] + dx), ly(ROBOT[1] + dy))],
               ORANGE, 2.4, late=False, opacity=.9)
    D.robot(lx(ROBOT[0]), ly(ROBOT[1]), 0.22 * K, 20, late=False)


# ------------------------------------------------------------------ 1. 세 겹
def stack(y):
    D.card(y, 950, '1', '주행에 쓰는 지도는 3겹이다',
           '아래에서 위로: 변하지 않는 기존 맵 → 건물 전체를 보는 계획 맵 → 로봇 둘레만 2배 촘촘하게 보는 제어 맵. 같은 순간(전기실 문 앞, 골목에 상자가 놓인 직후)의 세 겹이다.', 'client')
    S.raw(f'<pattern id="lh" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">'
          f'<rect width="6" height="6" fill="#d6e8ff"/><line x1="0" y1="0" x2="0" y2="6" stroke="{BLUE}" stroke-width="2"/></pattern>')
    S.raw(f'<pattern id="zh" width="7" height="7" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">'
          f'<rect width="7" height="7" fill="#ffe1df"/><line x1="0" y1="0" x2="0" y2="7" stroke="{ZRED}" stroke-width="2"/></pattern>')
    e = 60 - SHX * MH + 10
    f3, f2, f1 = y + 96, y + 372, y + 648
    # 제어 맵 창이 아래 겹의 어디인지 잇는 세로 점선
    x0, y0 = ROBOT[0] - WIN / 2, ROBOT[1] + WIN / 2
    for cx, cy in [(x0, y0), (x0 + WIN, y0), (x0, y0 - WIN), (x0 + WIN, y0 - WIN)]:
        a, b = iso(e, f3, cx, cy), iso(e, f1, cx, cy)
        S.raw(f'<line x1="{a[0]:.1f}" y1="{a[1]:.1f}" x2="{b[0]:.1f}" y2="{b[1]:.1f}" stroke="{L3}" stroke-width="1.3" stroke-dasharray="4 5" opacity=".8"/>', late=True)
    plane(e, f1, L1, draw_base)
    plane(e, f2, L2, draw_plan, floor='#f7fbff')
    plane(e, f3, L3, draw_ctrl, floor='#fbfbfd')
    for f in (f2, f1):                                       # 아래 두 겹에 창 자리 표시
        pts4 = [iso(e, f, cx, cy) for cx, cy in [(x0, y0), (x0 + WIN, y0), (x0 + WIN, y0 - WIN), (x0, y0 - WIN)]]
        d = 'M' + ' L'.join(f'{a:.1f} {b:.1f}' for a, b in pts4) + ' z'
        S.raw(f'<path d="{d}" fill="none" stroke="{L3}" stroke-width="1.6" stroke-dasharray="6 4"/>', late=True)

    tx = 880
    blocks = [
        (f3, L3, '3겹 · 제어 맵', '지역 비용 지도 (local_costmap)', [
            ('칸 크기', '0.025m — 아래 두 겹의 2배 촘촘(같은 넓이에 칸 4배)'),
            ('범위', '로봇 둘레 3×3m 만. 로봇을 따라 움직인다 (120×120칸)'),
            ('담긴 것', '금지구역 + 라이다가 지금 보는 것 + 팽창 0.6m. 저장 지도는 없다'),
            ('갱신', '1초에 5번 · 좌표계 odom(바퀴 기준)'),
            ('쓰는 곳', '제어기 MPPI — 지금 낼 속도를 1초에 10번 정한다'),
        ], '촘촘한 이유: 0.6m 틈에서 로봇 중심이 지날 띠는 0.16m 뿐이다. 0.05m 칸이면 3칸(어긋나면 1칸), 0.025m 칸이면 6칸.'),
        (f2, L2, '2겹 · 계획 맵', '전역 비용 지도 (global_costmap)', [
            ('칸 크기', '0.05m (기존 맵과 같다)'),
            ('범위', '건물 전체 · 고정 (183×160칸)'),
            ('담긴 것', '기존 맵 + 라이다 장애물 + 가상 장애물(금지구역 포함) → 큰 값으로 합침 + 팽창 0.45m'),
            ('갱신', '1초에 1번 · 좌표계 map(지도 기준)'),
            ('쓰는 곳', '전역 계획 Theta* — 목표마다 어느 길로 갈지 한 번 정한다'),
        ], '가상 장애물(파란 빗금)은 이 겹에만 있다. 계획이 장애물을 스치는 길을 내지 않게 하려는 것이다.'),
        (f1, L1, '1겹 · 기존 맵', '저장 지도 (현장: SLAM 으로 만든 site.pgm · 시뮬레이션: 설계도 reference.pgm)', [
            ('칸 크기', '0.05m'),
            ('범위', '건물 전체 · 고정 (183×160칸)'),
            ('담긴 것', '벽 · 고정 설비뿐. 지도를 만들 때 있던 것만'),
            ('갱신', '없음 — 주행 중에는 변하지 않는다'),
            ('쓰는 곳', '위치 추정 AMCL(라이다와 맞춰 봄) · 계획 맵의 바탕 층 · 웹 지도 그림의 원본'),
        ], '월드가 바뀌면 SLAM 으로 다시 만든다. 시험 장애물 · 사람 · 적재물은 여기에 들어가지 않는다.'),
    ]
    for f, col, title, sub, rows, note in blocks:
        by = f - 30
        S.rect(tx, by, 724, 222, fill='#ffffff', stroke=col, sw=1.6, rx=12)
        S.rect(tx, by, 8, 222, fill=col, stroke=col, rx=4)
        S.text(tx + 24, by + 30, title, 17, 700, col)
        S.text(tx + 164, by + 30, sub, 12.5, 500, SUB)
        for i, (k, v) in enumerate(rows):
            S.text(tx + 24, by + 58 + i * 23, k, 12.5, 700, INK)
            S.text(tx + 92, by + 58 + i * 23, v, 12.5, 400, INK)
        S.text(tx + 24, by + 58 + len(rows) * 23 + 14, note, 11.5, 400, SUB)
    # 겹 사이 관계
    for f, s in [(f3, '색이 든 네모 = 제어 맵 전체(3×3m). 바깥의 흐린 윤곽은 이 겹에 없는 정보다'),
                 (f2, '점선 네모 = 지금 제어 맵이 보고 있는 자리'), (f1, '이 겹이 계획 맵의 바탕 층으로 그대로 올라간다. 금지구역은 이 겹에 없다')]:
        S.text(852, f + SQ * MH + 26, s, 11.5, 500, SUB, 'end')
    # 범례
    gy = y + 914
    items = [(L1, None, '벽 · 설비(기존 맵)'), ('#cfe4ff', None, '계획 맵 팽창 0.45m'), ('url(#lh)', BLUE, '가상 장애물(몸통 채우기)'),
             ('#fbe3e0', RED, '라이다가 본 면'), ('#ffe0b8', None, '제어 맵 팽창 0.6m'), ('url(#zh)', ZRED, '금지구역(예시)')]
    gx = 44
    for fill, st, s in items:
        S.rect(gx, gy, 16, 14, fill=fill, stroke=st or '#8e8e93', sw=.8, rx=2)
        S.text(gx + 22, gy + 12, s, 11.5, 400, INK)
        gx += 40 + len(s) * 11.2
    D.poly([(gx, gy + 7), (gx + 34, gy + 7)], BLUE, 3, '0.1 7', late=False)
    S.text(gx + 42, gy + 12, '계획 경로', 11.5, 400, INK)
    D.poly([(gx + 110, gy + 7), (gx + 144, gy + 7)], ORANGE, 2.6, late=False)
    S.text(gx + 152, gy + 12, '제어기 후보 궤적', 11.5, 400, INK)


# ------------------------------------------------------------------ 2. 장애물이 생기는 층
def obstacles(y):
    D.card(y, 704, '2', '새 장애물은 어느 층에 생기나',
           '겹마다 안에 층이 있다. 새 장애물은 기존 맵을 건드리지 않고 "라이다 층"과 "가상 장애물 층"에 생겼다가 사라진다.', 'data')
    x0, cw, lw = 40, 258, 250
    cols = ['① 상자가 놓임', '② 라이다가 앞면을 봄', '③ 브리지가 몸통을 채움', '④ 주행에 미치는 영향', '⑤ 사라질 때']
    hy = y + 80
    for i, c in enumerate(cols):
        S.rect(x0 + lw + i * (cw + 6), hy, cw, 30, fill='#f2f2f7', stroke='none', sw=0, rx=8)
        S.text(x0 + lw + i * (cw + 6) + cw / 2, hy + 20, c, 13, 700, INK, 'middle')
    rows = [
        (L3, '3겹 제어 맵', '라이다 층 (obstacle_layer)', 84, [
            ('아직 없음', SUB), ('0.2초 안에 찍힌다 (1초에 5번)\n보인 면만, 0.025m 칸으로', RED), ('넣지 않는다\n(실제로 보이는 틈을 좁히지 않게)', SUB),
            ('제어기가 바로 비켜 간다\n틈이 0.6m 이상이면 그대로 통과', GREEN), ('라이다 빔이 그 자리를 지나가면\n지워진다 · 창 밖으로 나가면 잊는다', INK)]),
        (L2, '2겹 계획 맵', '라이다 층 (obstacle_layer)', 84, [
            ('아직 없음', SUB), ('1초 안에 찍힌다 (1초에 1번)\n보인 면만 — 얇은 선', RED), ('—', SUB),
            ('계획 경로가 막혔으면\n경로 검사(1초마다)가 다시 계획', GREEN), ('빔이 지나가면 지워진다\n복구 때 "비용 지도 비우기"로도', INK)]),
        (L2, '', '가상 장애물 층 (virtual_layer)', 84, [
            ('비어 있음', SUB), ('—', SUB), ('지도의 벽에서 0.15m 밖의 점 =\n새 장애물 → 뒤로 0.3m 채움', BLUE),
            ('계획이 선 뒤를 빈 곳으로 보고\n스치는 길을 내지 않는다', GREEN), ('목표가 끝나면 모두 지운다\n(브리지가 1초마다 층 전체를 보냄)', INK)]),
        (L3, '금지구역', '계획 맵 · 제어 맵 둘 다', 46,
         [('관리자가 지도에 그린 직사각형(공사 중인 구역 등). 라이다로는 안 보이므로 브리지가 서버에서 받아 계획 맵(가상 장애물 층)과 제어 맵(keepout_layer)에 넣는다. 설정 · 삭제 뒤 1 ~ 2초 안에 반영되고, 지울 때까지 남는다', RED)]),
        (L2, '', '기존 맵 층 (static_layer)', 46, [('변하지 않는다 — 1겹을 그대로 복사한 바탕', SUB)]),
        (L2, '', '팽창 층 (inflation_layer)', 46, [('위 세 층을 큰 값으로 합친 뒤(use_maximum) 0.45m 여유 띠를 두른다. 제어 맵은 라이다 층에 0.6m 를 두른다', SUB)]),
        (L1, '1겹 기존 맵', '저장 지도', 46, [('처음부터 끝까지 변하지 않는다. 그래서 위치 추정(AMCL)이 새 장애물에 흔들리지 않는다', SUB)]),
    ]
    ry = hy + 40
    for col, name, layer, h, cells in rows:
        S.rect(x0, ry, lw - 8, h, fill='#ffffff', stroke=col, sw=1.4, rx=8)
        S.rect(x0, ry, 6, h, fill=col, stroke=col, rx=3)
        if name:
            S.text(x0 + 18, ry + 20, name, 13, 700, col)
        S.text(x0 + 18, ry + (40 if name else h / 2 + 4), layer, 11.5, 500, INK)
        if len(cells) == 1:
            S.rect(x0 + lw, ry, 5 * cw + 24, h, fill='#fafafc', stroke='#e5e5ea', rx=8)
            S.text(x0 + lw + 16, ry + h / 2 + 4, cells[0][0], 12.5, 400, cells[0][1])
        else:
            for i, (s, c) in enumerate(cells):
                cx = x0 + lw + i * (cw + 6)
                S.rect(cx, ry, cw, h, fill='#fafafc', stroke='#e5e5ea', rx=8)
                ls = s.split('\n')
                for j, t in enumerate(ls):
                    S.text(cx + cw / 2, ry + h / 2 + 4 - (len(ls) - 1) * 9 + j * 18, t, 12, 600 if c in (RED, BLUE, GREEN) else 400, c, 'middle')
        ry += h + 8
    D.para(44, ry + 14, [
        '· 라이다 층은 "보이면 찍고(marking), 빔이 지나가면 지운다(clearing)". 찍는 거리는 7.5m, 지우는 거리는 8m 다.',
        '· 가상 장애물 층에는 한 가지가 더 들어간다: 물러났다가 같은 자리에서 또 막히면 그 자리(반지름 0.25m)를 막는다(마지막 안전망).',
        '· 채워서 길이 아예 없어지면(계획 실패) 그 목표 동안은 몸통 채우기를 끈다. 목표 둘레 0.45m 도 채우지 않는다.',
    ], 12.5, INK, 21)


# ------------------------------------------------------------------ 3. 금지구역
def keepout(y):
    D.card(y, 602, '3', '금지구역은 어디에서 동작하나',
           '관리자가 지도에 그린 직사각형(공사 중인 구역 등). 실제 장애물이 없어 라이다로는 안 보이므로, 서버가 목록을 로봇에 보내고 브리지가 두 겹에 직접 넣는다.', 'data')
    bw, bh, gap, x0, by = 204, 92, 40, 44, y + 96
    chain = [
        ('화면 · 관제 지도', 'Monitor.tsx · drawZone', ['끌어서 그림 · 눌러 고름 · 삭제', '붉은 빗금 상자로 표시'], 'client'),
        ('gateway', 'application.yml', ['설정 · 삭제: ADMIN · 1 관리자', '조회: 모든 역할'], 'edge'),
        ('robot-service', 'KeepoutService · keepout_zone', ['저장 · 검사 후 목록 전체를 보냄', '바뀔 때 + 5초마다'], 'spring'),
        ('목표 브리지', 'nav2_goal_bridge.py', ['구역 → 지도와 같은 크기의', '격자 두 장으로 바꿈'], 'bridge'),
    ]
    xs = [x0 + i * (bw + gap) for i in range(len(chain))]
    for x, (t, m, ls, kind) in zip(xs, chain):
        D.box(x, by, bw, bh, t, ls, kind, mono=m)
    for i, a in enumerate(['POST · DELETE', '/api/robots/{id}/zones', '/inspection/keepout']):
        S.line([(xs[i] + bw + 3, by + bh / 2), (xs[i + 1] - 4, by + bh / 2)], color=INK, sw=1.8)
        D.label(xs[i] + bw + gap / 2, by - 8, a, INK, 10, 'middle', 500)
    # 브리지 → 두 겹
    tx = xs[3] + bw + 214
    tw = S.w - 40 - tx
    S.rect(tx, by - 26, tw, 66, fill=C['client'][1], stroke=L2, sw=1.6, rx=10)
    S.text(tx + 14, by - 4, '2겹 계획 맵 — 가상 장애물 층 (virtual_layer)', 13, 700, L2)
    S.text(tx + 14, by + 14, '몸통 채우기 표시와 한 격자에 합쳐진다 → 팽창 0.45m', 11.5, 400, INK)
    S.text(tx + 14, by + 30, '→ Theta* 가 구역을 피해 계획(달리는 중이면 다시 계획)', 11.5, 400, INK)
    S.rect(tx, by + 52, tw, 66, fill=C['py'][1], stroke=L3, sw=1.6, rx=10)
    S.text(tx + 14, by + 74, '3겹 제어 맵 — 금지구역 층 (keepout_layer)', 13, 700, L3)
    S.text(tx + 14, by + 92, '라이다 층보다 앞에 놓인 전용 층 → 팽창 0.6m', 11.5, 400, INK)
    S.text(tx + 14, by + 108, '→ MPPI 가 비켜 가다 구역 모서리를 넘지 않는다', 11.5, 400, INK)
    bx = xs[3] + bw
    S.line([(bx + 3, by + bh / 2 - 12), (bx + 60, by + bh / 2 - 12), (bx + 60, by + 6), (tx - 4, by + 6)], color=L2, sw=1.8)
    S.line([(bx + 3, by + bh / 2 + 12), (bx + 60, by + bh / 2 + 12), (bx + 60, by + 86), (tx - 4, by + 86)], color=L3, sw=1.8)
    D.label(bx + 68, by - 2, '/inspection/virtual_map', L2, 10, 'start', 600)
    D.label(bx + 68, by + 102, '/inspection/keepout_map', L3, 10, 'start', 600)
    # 기존 맵에는 없음
    S.rect(tx, by + 130, tw, 34, fill='#f2f2f7', stroke=L1, sw=1.2, rx=10, dash='5 4')
    S.text(tx + 14, by + 152, '1겹 기존 맵 — 들어가지 않는다 (위치 추정은 그대로)', 12, 600, L1)

    # 어디에서 무엇을 하나
    ty = by + 196
    cols = [(0, '곳'), (230, '금지구역에 대해 하는 일'), (1060, '값 · 근거')]
    S.rect(36, ty - 19, S.w - 72, 28, fill='#f2f2f7', stroke='none', sw=0, rx=6)
    for cx, h in cols:
        S.text(44 + cx, ty, h, 13, 700, SUB)
    rows = [
        (L1, '1겹 기존 맵 (저장 지도)', '동작하지 않는다. 구역을 그려도 저장 지도 · 위치 추정(AMCL) · 웹 지도 그림은 바뀌지 않는다', '—'),
        (L2, '2겹 계획 맵 · 가상 장애물 층', '구역이 덮는 칸을 막힌 칸(100)으로 넣는다. 걸친 칸은 모두 넣는다. 목표와 상관없이 지울 때까지 남는다', '0.05m 칸 · 1초마다 다시 보냄'),
        (L2, '2겹 계획 맵 · 팽창 층', '구역 둘레에 여유 띠를 두른다 → 경로가 구역에 붙지 않는다', '팽창 0.45m'),
        (L2, '2겹 계획 맵 · 라이다 층 / 기존 맵 층', '동작하지 않는다(구역은 실제 장애물이 아니라 라이다에 안 보인다)', '—'),
        (L3, '3겹 제어 맵 · 금지구역 층', '같은 구역을 제어 맵에도 막힌 칸으로 넣는다. 로봇 둘레 3×3m 창에 들어온 부분만 쓰인다', 'keepout_layer · 라이다 층보다 앞'),
        (L3, '3겹 제어 맵 · 팽창 층', '구역 둘레에 여유 띠를 두른다 → 제어기 후보 궤적이 구역으로 들어가지 않는다', '팽창 0.6m'),
        (C['bridge'][0], '목표 브리지', '서버 목록을 두 격자로 바꿔 보낸다. 구역이 없어도 빈 격자를 보낸다(층이 기다리지 않게)', '바뀔 때만 keepout_map 재전송'),
        (C['spring'][0], 'robot-service', '한 변 0.2m 미만 거부(400) · 로봇이 구역 안이거나 둘레 0.35m 안이면 거부(409) · DB 에 보관', 'KeepoutService'),
    ]
    for i, (col, a, b, c) in enumerate(rows):
        ry = ty + 30 + i * 27
        S.raw(f'<circle cx="50" cy="{ry - 4}" r="5" fill="{col}"/>')
        S.text(64, ry, a, 12.5, 700, col)
        S.text(44 + cols[1][0], ry, b, 12.5, 400, INK)
        S.text(44 + cols[2][0], ry, c, 12, 400, SUB)
        S.raw(f'<line x1="36" y1="{ry + 9}" x2="{S.w - 36}" y2="{ry + 9}" stroke="#e5e5ea"/>')
    D.para(44, ty + 30 + len(rows) * 27 + 14, [
        '· 달리는 도중 가던 길 위에 설정: 계획 맵에 1 ~ 2초 안에 들어가고, 경로 검사가 "막힘"을 보고 다시 계획해 돌아간다(E2E Z-5).',
        '· 구역이 목적지를 덮거나 길이 그 구역뿐이면 그 지점은 BLOCKED_NO_PATH(진입 불가)로 끝난다. 구역을 지우면 1 ~ 2초 안에 다시 지나간다(E2E Z-4).',
    ], 12.5, INK, 21)


# ------------------------------------------------------------------ 4. 비교표
def compare(y):
    D.card(y, 400, '4', '세 겹 비교', '같은 건물을 서로 다른 눈으로 본다. 계획은 멀리 · 성기게 · 가끔, 제어는 가까이 · 촘촘하게 · 자주.', 'py')
    x0, hy = 44, y + 84
    cols = [(0, ''), (170, '1겹 기존 맵'), (560, '2겹 계획 맵'), (1010, '3겹 제어 맵')]
    cc = [INK, L1, L2, L3]
    S.rect(x0 - 8, hy - 19, S.w - 72, 28, fill='#f2f2f7', stroke='none', sw=0, rx=6)
    for (cx, h), c in zip(cols, cc):
        S.text(x0 + cx, hy, h, 13.5, 700, c)
    rows = [
        ('정체', '저장 지도 site.pgm', '전역 비용 지도', '지역 비용 지도'),
        ('칸 크기', '0.05m', '0.05m', '0.025m (2배 촘촘 · 칸 넓이 1/4)'),
        ('범위 · 칸 수', '건물 전체 · 183×160', '건물 전체 · 183×160', '로봇 둘레 3×3m · 120×120 (0.05m 였다면 60×60)'),
        ('움직임', '고정', '고정', '로봇을 따라 움직인다'),
        ('안의 층', '— (그림 한 장)', '기존 맵 + 라이다 + 가상 장애물 → 팽창 0.45m', '금지구역 + 라이다 → 팽창 0.6m'),
        ('새 장애물', '생기지 않는다', '라이다 층(선) + 가상 장애물 층(몸통)', '라이다 층(선)'),
        ('금지구역', '들어가지 않는다', '가상 장애물 층에 합친다', '금지구역 층 (keepout_layer)'),
        ('갱신', '없음', '1초에 1번', '1초에 5번'),
        ('쓰는 곳', '위치 추정 AMCL · 웹 지도 원본', '전역 계획 Theta* (목표마다 한 번)', '제어기 MPPI (1초에 10번)'),
        ('바꾸는 곳', 'SLAM 으로 다시 만든다 (save_map.sh)', 'nav2_params.yaml global_costmap', 'nav2_params.yaml local_costmap'),
    ]
    for i, r in enumerate(rows):
        ry = hy + 30 + i * 27
        for (cx, _), s, c in zip(cols, r, cc):
            S.text(x0 + cx, ry, s, 12.5, 700 if cx == 0 else 400, INK)
        S.raw(f'<line x1="{x0 - 8}" y1="{ry + 9}" x2="{S.w - 36}" y2="{ry + 9}" stroke="#e5e5ea"/>')
    S.text(x0, hy + 30 + len(rows) * 27 + 12,
           '웹 화면의 지도(MapRenderer)는 1겹을 보기 좋게 다시 그린 그림이다. 주행에 쓰는 세 겹에는 영향이 없다. 제어기 동작 · 막혔을 때의 순서는 drive_controller.svg 를 본다.',
           12, 400, SUB)


def build():
    S.text(24, 46, '주행 지도 구조 — 3겹', 26, 700)
    S.text(24, 72, '로봇은 지도 한 장으로 달리지 않는다. 변하지 않는 기존 맵 위에 계획 맵과, 2배 촘촘한 제어 맵을 겹쳐 쓴다. 값은 nav2_params.yaml · site.yaml 기준이다.',
           13, 400, SUB)
    y = 92
    for fn, h in ((stack, 950), (obstacles, 704), (keepout, 602), (compare, 400)):
        fn(y)
        y += h + 14
    S.h = y + 10
    S.render(OUT)


if __name__ == '__main__':
    build()
