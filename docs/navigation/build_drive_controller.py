"""주행 제어기 설명서(그림): 목표 하나가 어떻게 경로가 되고 속도 명령이 되는지, 막혔을 때 무엇을 하는지.

값은 코드 · 설정 · 측정에서 가져왔다:
  ros/sim/src/config/nav2_params.yaml(계획기 · 제어기 · 비용 지도), navigate_fixed_plan.xml(행동 트리),
  ros/robot/src/nav2_goal_bridge.py(STUCK_* · ESCAPE_* · SHADOW_* · MAX_RETRIES · NO_PROGRESS_SEC),
  ros/sim/src/worlds/world_spec.py(벽 · 설비 · 점검 지점 · 시험 장애물 — 평면도는 여기서 그대로 그린다),
  plan_probe.py --dump(계획 경로 좌표: PATHS), nav_soak.py(장애물별 결과 · 시간).
돌아가는 길(DETOURS)은 지나는 통로만 맞춘 개략선이다(실제 좌표가 아니다).
실행: python3 docs/navigation/build_drive_controller.py  →  docs/navigation/drive_controller.svg
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / '_lib'))   # 공용 그리기 도구 docs/_lib/svg.py
from svg import C, Svg, text_width

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / 'ros/sim/src/worlds'))
import world_spec as W   # noqa: E402

OUT = HERE / 'drive_controller.svg'
S = Svg(1640, 2590)

BLUE, ORANGE, RED, PURPLE, GRAY, INK, SUB = '#007aff', '#ff9500', '#e5352b', '#8944ab', '#8e8e93', '#1c1c1e', '#636366'

# plan_probe.py --dump 로 뽑은 계획 경로(Theta*, 장애물 없음)에서 고른 점
PATHS = {
    'P3>P1': [(0.28, 4.6), (0.66, 4.73), (1.04, 4.86), (1.42, 4.98), (1.83, 5.02), (2.23, 5.04), (2.58, 5.2), (2.93, 5.55),
              (3.33, 5.6), (3.54, 5.2), (3.57, 4.8), (3.63, 4.4), (3.85, 4.03), (4.28, 3.9)],
    'P1>P2': [(4.28, 3.9), (4.67, 3.93), (5.08, 4.01), (5.88, 4.04), (6.68, 4.08), (7.08, 4.1), (7.47, 4.19), (7.63, 4.6),
              (7.63, 5.4), (7.63, 6.1)],
}
# 돌아가는 길(개략): 지나는 통로만 맞춘 선
DETOURS = {
    'aisle': [(3.33, 5.6), (3.5, 6.3), (3.62, 6.78), (4.3, 6.8), (4.95, 6.75), (5.1, 6.2), (5.1, 4.6), (4.85, 4.1), (4.28, 3.9)],
    'door': [(4.28, 3.9), (4.9, 3.2), (5.3, 2.6), (5.3, 1.5), (4.75, 0.6), (5.2, -0.1), (7.3, -0.1), (7.65, 0.5), (7.65, 6.1)],
}


# ------------------------------------------------------------------ 그리기 도우미
def card(y, h, num, title, desc, kind):
    col = C[kind][0]
    S.rect(16, y, S.w - 32, h, fill='#ffffff', stroke='#d1d1d6', rx=14)
    S.rect(16, y, 8, h, fill=col, stroke=col, rx=4)
    S.text(40, y + 32, f'{num}  {title}', 18, 700, col)
    S.text(40, y + 54, desc, 12.5, 400, SUB)


def para(x, y, lines, size=12.5, color=INK, lh=19, weight=400):
    for i, s in enumerate(lines):
        S.text(x, y + i * lh, s, size, weight, color)
    return y + len(lines) * lh


def box(x, y, w, h, title, lines, kind, mono=None):
    col, fill = C[kind]
    S.rect(x, y, w, h, fill=fill, stroke=col, sw=1.5, rx=10)
    S.text(x + w / 2, y + 22, title, 13.5, 700, col, 'middle')
    if mono:
        S.text(x + w / 2, y + 39, mono, 10.5, 500, SUB, 'middle', mono=True)
    for i, s in enumerate(lines):
        S.text(x + w / 2, y + (56 if mono else 42) + i * 16, s, 11.5, 400, INK, 'middle')


def label(x, y, s, color=INK, size=11.5, anchor='middle', weight=600):
    """그림 위에 얹는 글(흰 테두리)."""
    from xml.sax.saxutils import escape
    S.raw(f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" font-weight="{weight}" fill="{color}" text-anchor="{anchor}" '
          f'paint-order="stroke" stroke="#ffffff" stroke-width="4" stroke-linejoin="round">{escape(s)}</text>', late=True)


def badge(x, y, n, color):
    S.raw(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="11" fill="{color}" stroke="#ffffff" stroke-width="2"/>', late=True)
    S.text(x, y + 4, str(n), 11.5, 700, '#ffffff', 'middle', late=True)


def poly(pts, color, sw=3, dash=None, late=True, opacity=1.0):
    d = 'M' + ' L'.join(f'{x:.1f} {y:.1f}' for x, y in pts)
    ds = f' stroke-dasharray="{dash}"' if dash else ''
    S.raw(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{sw}" stroke-linecap="round" stroke-linejoin="round" '
          f'opacity="{opacity}"{ds}/>', late)


def robot(x, y, r, yaw_deg=0, late=True):
    """로봇: 원(반지름 r) + 앞쪽 표시. yaw 는 화면 기준(0 = 오른쪽, 90 = 아래)."""
    import math
    a = math.radians(yaw_deg)
    S.raw(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}" fill="#1c1c1e" stroke="#ffffff" stroke-width="1.5"/>', late)
    S.raw(f'<line x1="{x:.1f}" y1="{y:.1f}" x2="{x + r * math.cos(a):.1f}" y2="{y + r * math.sin(a):.1f}" stroke="#ffffff" '
          f'stroke-width="2.2" stroke-linecap="round"/>', late)


def world_map(ox, oy, k, late=False, wall='#3a3a3c', floor='#ffffff'):
    """world_spec 의 벽 · 설비를 평면도로 그린다. (ox, oy) = 건물 왼쪽 위, k = px/m. 좌표 변환 함수를 돌려준다."""
    def px(x):
        return ox + (x - W.X0) * k

    def py(y):
        return oy + (W.Y1 - y) * k
    S.rect(px(W.X0), py(W.Y1), (W.X1 - W.X0) * k, (W.Y1 - W.Y0) * k, fill=floor, stroke='none', sw=0, rx=0, late=late)
    for i, (x, y, sx, sy) in enumerate(W.rects()):
        fx = i >= len(W.WALLS)
        S.rect(px(x - sx / 2), py(y + sy / 2), sx * k, sy * k, fill='#b9b9c0' if fx else wall, stroke='none', sw=0, rx=0, late=late)
    return px, py


# ------------------------------------------------------------------ 1. 흐름
def flow(y):
    card(y, 318, '1', '목표 하나가 속도 명령이 되기까지',
         '웹은 "어디로 가라"만 보낸다. 길을 정하는 일(계획)과 그 길을 따라 모는 일(제어)은 로봇 쪽에서 나뉘어 돈다.', 'ros')
    bw, gap, x0, by = 196, 74, 44, y + 78
    cols = [
        ('웹 · robot-service', None, ['점검 지점 · 지도 클릭 · 출동', '목표 단위로만 말한다'], 'spring'),
        ('목표 브리지', 'nav2_goal_bridge.py', ['목표를 Nav2 로 옮기고', '실패했을 때 판단한다'], 'bridge'),
        ('행동 트리', 'navigate_fixed_plan.xml', ['처음 계획을 유지', '막히면 복구 뒤 다시 계획'], 'edge'),
        ('전역 계획', 'Theta* (목표마다 한 번)', ['건물 전체에서', '직선 위주 최단 경로'], 'client'),
        ('제어기', 'MPPI (1초에 10번)', ['후보 1000개 × 3초 앞', '가장 좋은 속도를 고른다'], 'py'),
        ('로봇', 'TurtleBot3 Waffle Pi', ['바퀴 최대 0.22 m/s', '반지름 0.22m 원으로 본다'], 'dev'),
    ]
    xs = [x0 + i * (bw + gap) for i in range(len(cols))]
    for x, (t, m, ls, kind) in zip(xs, cols):
        box(x, by, bw, 92, t, ls, kind, mono=m)
    arrows = ['/inspection/goal', 'NavigateToPose', '경로 요청', '경로 (/plan)', '/cmd_vel']
    for i, a in enumerate(arrows):
        S.line([(xs[i] + bw + 3, by + 34), (xs[i + 1] - 4, by + 34)], color=INK, sw=1.8)
        label(xs[i] + bw + gap / 2, by + 26, a, INK, 10, 'middle', 500)
    # 되돌아오는 결과
    S.line([(xs[1] - 4, by + 66), (xs[0] + bw + 3, by + 66)], color=GRAY, sw=1.6, dash='5 4')
    label(xs[0] + bw + gap / 2, by + 84, 'goal_status', SUB, 10, 'middle', 500)
    # 아래 줄: 비용 지도와 라이다
    cy = by + 132
    box(xs[3] - 60, cy, bw + 60, 86, '전역 비용 지도', ['저장 지도 + 라이다 + 가상 장애물', '팽창 0.45m (벽 여유 띠)'], 'client',
        mono='0.05m 칸 · 건물 전체')
    box(xs[4] + 16, cy, bw + 20, 86, '지역 비용 지도', ['라이다만 (지금 보이는 것)', '팽창 0.6m'], 'py', mono='0.025m 칸 · 로봇 둘레 3×3m')
    box(xs[5] + 30, cy + 8, bw - 30, 70, '라이다 /scan', ['최대 8m · 360°'], 'dev')
    S.line([(xs[3] + bw / 2 - 30, cy - 3), (xs[3] + bw / 2 - 30, by + 95)], color=BLUE, sw=1.8)
    S.line([(xs[4] + bw / 2 + 16, cy - 3), (xs[4] + bw / 2 + 16, by + 95)], color=C['py'][0], sw=1.8)
    S.line([(xs[5] + 27, cy + 43), (xs[4] + bw + 39, cy + 43)], color=GRAY, sw=1.6)
    S.line([(xs[5] + 60, cy + 81), (xs[5] + 60, cy + 104), (xs[3] + 60, cy + 104), (xs[3] + 60, cy + 89)], color=GRAY, sw=1.6)
    # 브리지 → 가상 장애물
    S.line([(xs[1] + bw / 2, by + 95), (xs[1] + bw / 2, cy + 43), (xs[3] - 64, cy + 43)], color=C['bridge'][0], sw=1.8)
    label((xs[1] + bw / 2 + xs[3] - 64) / 2 + 30, cy + 35, '/inspection/virtual_map  (가상 장애물: 몸통 채우기 · 막힌 자리)', C['bridge'][0], 10.5, 'middle', 600)
    S.line([(xs[5] + bw / 2, cy + 5), (xs[5] + bw / 2, by + 95)], color=GRAY, sw=1.6, start=True, end=False)
    para(44, cy + 60, ['점선 = 결과가 되돌아오는 길', '사유 코드: BLOCKED_NO_PATH · NAV_FAILED', '· NO_PROGRESS · NAV_UNAVAILABLE'], 11, SUB, 16)


# ------------------------------------------------------------------ 2. 지도
def site(y):
    card(y, 716, '2', '지도 위에서 보기 — 길이 좁아지거나 막혔을 때',
         '평면도는 시뮬레이션 월드 그대로다. 파란 점선은 실제 계획 경로(장애물 없음), 보라 점선은 돌아가는 길의 개략이다.', 'client')
    k = 76
    ox, oy = 52, y + 82
    px, py = world_map(ox, oy, k)
    S.rect(ox, oy, (W.X1 - W.X0) * k, (W.Y1 - W.Y0) * k, fill='none', stroke='#d1d1d6', rx=0)
    for name, (x, yy) in {'사무실': (1.0, 0.45), '전기실': (1.0, 6.75), '생산동': (6.2, 3.15), 'C1 복도': (5.9, 0.2), 'C2': (7.93, 1.3)}.items():
        S.text(px(x), py(yy), name, 12, 600, '#aeaeb2', 'middle')

    def to(pts):
        return [(px(a), py(b)) for a, b in pts]
    # 시험 장애물
    for name, col, dash in [('aisle', RED, '5 3'), ('door', RED, None), ('block', RED, None)]:
        x, yy, sx, sy = W.OBSTACLES[name]
        S.rect(px(x - sx / 2), py(yy + sy / 2), sx * k, sy * k, fill='none' if dash else '#fbd3cf', stroke=col, sw=1.8, rx=2, dash=dash)
    for name in ('aisle60', 'pallet'):
        x, yy, sx, sy = W.OBSTACLES[name]
        S.rect(px(x - sx / 2), py(yy + sy / 2), sx * k, sy * k, fill='#ffd9a3', stroke=ORANGE, sw=1.8, rx=2)
    # 경로
    poly(to(DETOURS['aisle']), PURPLE, 2.6, '7 5')
    poly(to(DETOURS['door']), PURPLE, 2.6, '7 5')
    poly(to(PATHS['P3>P1']), BLUE, 3.4, '0.1 8')
    poly(to(PATHS['P1>P2']), BLUE, 3.4, '0.1 8')
    for code, (x, yy, _) in W.POINTS.items():
        S.raw(f'<circle cx="{px(x):.1f}" cy="{py(yy):.1f}" r="8" fill="#ffffff" stroke="#30b0c7" stroke-width="3"/>', late=True)
        label(px(x), py(yy) - 14, code, '#0e8aa0', 13, 'middle', 700)
    robot(px(0), py(0), 0.22 * k)
    label(px(0), py(0) + 34, '충전 위치', SUB, 11)
    # 번호
    badge(px(3.62), py(5.1), 1, ORANGE)
    badge(px(4.3), py(6.8) - 16, 2, RED)
    badge(px(6.2), py(4.1) - 28, 3, ORANGE)
    badge(px(7.1) - 20, py(4.75), 4, RED)
    badge(px(7.65), py(5.2) + 24, 5, RED)

    # 오른쪽: 범례와 표
    rx = ox + (W.X1 - W.X0) * k + 44
    ty = y + 96
    S.text(rx, ty, '선과 표시', 14, 700, INK)
    lg = [(BLUE, '0.1 8', '계획 경로 — 목표를 받을 때 한 번 계산한 직선 위주 최단 경로'),
          (PURPLE, '7 5', '돌아가는 길 — 가던 길이 막힌 것을 보고 다시 계획한 경로(개략)')]
    for i, (col, dash, s) in enumerate(lg):
        poly([(rx, ty + 22 + i * 22), (rx + 46, ty + 22 + i * 22)], col, 3.2, dash, late=False)
        S.text(rx + 58, ty + 26 + i * 22, s, 12, 400, INK)
    S.rect(rx + 8, ty + 58, 30, 14, fill='#ffd9a3', stroke=ORANGE, sw=1.6, rx=2)
    S.text(rx + 58, ty + 70, '지날 수 있게 남는 장애물 — 비켜서 그대로 간다', 12, 400, INK)
    S.rect(rx + 8, ty + 80, 30, 14, fill='#fbd3cf', stroke=RED, sw=1.6, rx=2)
    S.text(rx + 58, ty + 92, '길을 막는 장애물 — 다른 길로 가거나, 길이 없으면 끝낸다', 12, 400, INK)

    ty += 134
    S.text(rx, ty, '장애물별 맞는 결과와 측정 시간', 14, 700, INK)
    S.text(rx, ty + 19, '반복 시험 nav_soak.py · 놓는 시점 3가지(출발 전 · 1.2m 앞 · 0.6m 앞) · 연속 3회 126번 주행에서 틀린 결과 0', 11.5, 400, SUB)
    cols = [0, 36, 250, 396, 560]
    head = ['', '장애물 (구간)', '남는 폭', '맞는 결과', '걸린 시간']
    rows = [
        ('', GRAY, '없음 (P3 ↔ P1)', '0.95m', '직행', '25 ~ 32초'),
        ('1', ORANGE, '골목 반쯤 막힘 aisle70 · aisle60', '0.7 · 0.6m', '틈으로 직행', '25 ~ 32초 (같음)'),
        ('2', RED, '골목 더 막힘 aisle50', '0.5m', '랙 위로 돌아감', '41 ~ 62초'),
        ('2', RED, '골목 완전 막힘 aisle', '0', '랙 위로 돌아감', '41 ~ 62초'),
        ('', GRAY, '없음 (P1 → P2)', '—', '직행', '26초'),
        ('3', ORANGE, '경로 위 팔레트 pallet', '양옆 열림', '비켜서 직행', '27 ~ 29초'),
        ('4', RED, '생산동 → C2 문 막힘 door', '0', 'C1 · C2 로 돌아감', '58 ~ 74초'),
        ('5', RED, 'C2 위쪽 막힘 block', '0 (길 없음)', 'BLOCKED_NO_PATH 로 끝냄', '42 ~ 54초'),
    ]
    hy = ty + 46
    S.rect(rx - 8, hy - 17, 760, 26, fill='#f2f2f7', stroke='none', sw=0, rx=6)
    for cx, h in zip(cols, head):
        S.text(rx + cx, hy, h, 12, 700, SUB)
    for i, (n, col, a, b, c, d) in enumerate(rows):
        ry = hy + 30 + i * 30
        if n:
            S.raw(f'<circle cx="{rx + 10}" cy="{ry - 4}" r="10" fill="{col}"/>')
            S.text(rx + 10, ry, n, 11, 700, '#ffffff', 'middle')
        S.text(rx + cols[1], ry, a, 12.5, 500, INK)
        S.text(rx + cols[2], ry, b, 12.5, 400, INK)
        S.text(rx + cols[3], ry, c, 12.5, 600, RED if 'BLOCKED' in c else (PURPLE if '돌아' in c else '#248a3d'))
        S.text(rx + cols[4], ry, d, 12.5, 400, INK)
        S.raw(f'<line x1="{rx - 8}" y1="{ry + 10}" x2="{rx + 752}" y2="{ry + 10}" stroke="#e5e5ea"/>')
    ny = hy + 30 + len(rows) * 30 + 18
    para(rx, ny, [
        '읽는 법',
        '· 로봇은 반지름 0.22m 원이다. 틈이 0.6m 면 양쪽에 0.08m 씩 남아 지나간다(돌아가지 않는다).',
        '· 틈이 0.5m 이하면 계획이 막힌 것으로 보고 돌아간다. 0.44m(지름) 아래로는 물리적으로 못 지난다.',
        '· 길이 아예 없으면 끼인 채 멈추지 않고 "진입 불가"로 끝낸 뒤 다음 지점으로 간다.',
        '· 달리는 도중 코앞(0.6m)에 생겨도 결과는 같다. 문 막힘은 가던 거리만큼 2 ~ 3m 더 달린다.',
    ], 12.5, INK, 21)
    S.text(rx, ny - 0, '읽는 법', 12.5, 700, INK)


# ------------------------------------------------------------------ 3. 브리지가 돕는 세 가지
def helpers(y):
    card(y, 452, '3', '목표 브리지가 계획을 돕는 세 가지',
         'Nav2 기본 동작만으로는 새 장애물 앞에서 헛도는 경우가 있었다. 브리지가 라이다를 보고 세 가지를 보탠다.', 'bridge')
    pw, x0, py0 = 510, 40, y + 76
    titles = [('가', '장애물의 몸통 채우기', '라이다는 앞면만 선으로 본다 → 뒤 0.3m 를 막힌 것으로'),
              ('나', '물러나 자세 잡기', '장애물에 붙어 계획이 안 되면 → 멀어지는 쪽으로 빠져나옴'),
              ('다', '두 번 막힌 자리 막기', '물러났다 다시 와서 또 막히면 → 그 자리를 막고 다른 길')]
    for i, (n, t, d) in enumerate(titles):
        x = x0 + i * (pw + 14)
        S.rect(x, py0, pw, 356, fill='#faf7fc', stroke='#e3d3ee', rx=12)
        S.raw(f'<circle cx="{x + 24}" cy="{py0 + 26}" r="13" fill="{C["bridge"][0]}"/>')
        S.text(x + 24, py0 + 30.5, n, 12, 700, '#ffffff', 'middle')
        S.text(x + 46, py0 + 31, t, 15, 700, C['bridge'][0])
        S.text(x + 20, py0 + 54, d, 12, 400, SUB)

    # --- 가: 몸통 채우기 (골목: 왼쪽 벽 ↔ 오른쪽 랙, 폭 0.95m, k = 200px/m)
    x, gy = x0 + 40, py0 + 78
    k = 200
    S.rect(x, gy, 16, 176, fill='#3a3a3c', stroke='none', sw=0, rx=0)                       # 서쪽 벽
    S.rect(x + 16 + 0.95 * k, gy, 44, 176, fill='#b9b9c0', stroke='none', sw=0, rx=0)        # 랙
    bx, bw, bh = x + 16, 0.35 * k, 0.3 * k
    S.rect(bx, gy + 40, bw, bh, fill='#d6e8ff', stroke=BLUE, sw=1.6, rx=0, dash='4 3')      # 실제 장애물(= 채운 몸통)
    S.raw(f'<pattern id="hb" width="7" height="7" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">'
          f'<line x1="0" y1="0" x2="0" y2="7" stroke="{BLUE}" stroke-width="2" opacity=".55"/></pattern>')
    S.rect(bx, gy + 40, bw, bh, fill='url(#hb)', stroke='none', sw=0, rx=0)
    poly([(bx, gy + 40 + bh), (bx + bw, gy + 40 + bh)], '#f5c400', 5, late=False)            # 라이다가 본 면
    rx_, ry_ = x + 16 + 0.62 * k, gy + 150
    for tx in (bx + 6, bx + bw / 2, bx + bw - 4):
        S.raw(f'<line x1="{rx_}" y1="{ry_}" x2="{tx}" y2="{gy + 40 + bh + 3}" stroke="{RED}" stroke-width="1" opacity=".6"/>')
    robot(rx_, ry_, 0.22 * k * 0.5, -90, late=False)
    S.line([(bx + bw + 4, gy + 22), (x + 16 + 0.95 * k - 4, gy + 22)], color=ORANGE, sw=1.6, start=True)
    label(bx + bw + 0.3 * k, gy + 14, '틈 0.6m — 그대로 열림', ORANGE, 11)
    tx0 = x + 290
    para(tx0, gy + 14, ['노란 선 = 라이다가 본 면', '파란 빗금 = 브리지가 채운 몸통', '(면에 수직으로 0.3m, 같은 폭)'], 12, INK, 19)
    para(tx0, gy + 86, ['채우지 않으면 계획기가 선 바로', '뒤를 빈 곳으로 보고 장애물을', '스치는 길을 낸다 → 제어기 실패'], 12, SUB, 19)
    para(x0 + 20, py0 + 284, ['· 저장 지도의 벽에서 0.15m 안의 점은 벽으로 보고 채우지 않는다.',
                              '· 목표 둘레 0.45m 는 채우지 않는다. 채워서 길이 없어지면 그 목표 동안 끈다.',
                              '· 빔 방향으로 끝까지 막거나 0.9m 깊이는 버렸다(틈 · 문까지 막아 먼 길로 돌았다).'], 11.5, INK, 19)

    # --- 나: 빠져나오기
    x = x0 + (pw + 14) + 40
    S.rect(x, gy + 6, 150, 60, fill='#ffd9a3', stroke=ORANGE, sw=1.6, rx=2)
    S.rect(x, gy + 6, 16, 180, fill='#3a3a3c', stroke='none', sw=0, rx=0)
    cx, cyy = x + 96, gy + 106
    S.raw(f'<circle cx="{cx}" cy="{cyy}" r="80" fill="none" stroke="{GRAY}" stroke-width="1" stroke-dasharray="3 4"/>')
    for dx, dy in [(-78, -30), (-78, 0), (-78, 30), (-50, -42), (-20, -42), (10, -42), (40, -42)]:
        S.raw(f'<circle cx="{cx + dx}" cy="{cyy + dy}" r="3" fill="{RED}"/>')
    robot(cx, cyy, 30, 180, late=False)
    S.line([(cx + 22, cyy + 20), (cx + 66, cyy + 50)], color='#248a3d', sw=3.4)
    S.raw(f'<circle cx="{cx + 82}" cy="{cyy + 62}" r="24" fill="none" stroke="#248a3d" stroke-width="1.6" stroke-dasharray="5 4"/>')
    label(cx + 112, cyy + 72, '여기서 다시 계획', '#248a3d', 11, 'start')
    tx0 = x + 250
    para(tx0, gy + 14, ['빨간 점 = 0.7m 안의 라이다 점', '초록 화살표 = 점들에서 멀어지는', '방향(가까울수록 세게 민다)'], 12, INK, 19)
    para(tx0, gy + 86, ['전진 · 후진 중 덜 도는 쪽으로', '0.10 m/s, 최대 0.45m', '사방 0.40m 가 트이면 멈춤', '가는 쪽이 0.22m 안이면 멈춤'], 12, SUB, 19)
    para(x0 + (pw + 14) + 20, py0 + 284, ['· 언제: 같은 자리(0.4m)에서 제어기가 3번 실패 / 목표 실패 뒤 장애물이 0.4m 안.',
                                          '· 왜: 로봇 중심이 충돌 구역에 들면 Nav2 의 후진 · 회전은 "Collision Ahead" 로 시작도 못 한다.',
                                          '· 지나온 길을 되짚는 후진은 버렸다(뒤가 막혀 있으면 한 뼘도 못 움직였다).'], 11.5, INK, 19)

    # --- 다: 두 번 막힌 자리
    x = x0 + 2 * (pw + 14) + 40
    S.rect(x, gy + 6, 16, 180, fill='#3a3a3c', stroke='none', sw=0, rx=0)
    S.rect(x + 190, gy + 40, 34, 146, fill='#b9b9c0', stroke='none', sw=0, rx=0)
    S.raw(f'<pattern id="hr" width="7" height="7" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">'
          f'<line x1="0" y1="0" x2="0" y2="7" stroke="{RED}" stroke-width="2" opacity=".6"/></pattern>')
    S.raw(f'<circle cx="{x + 104}" cy="{gy + 110}" r="34" fill="url(#hr)" stroke="{RED}" stroke-width="1.8"/>')
    poly([(x + 104, gy + 12), (x + 104, gy + 76)], BLUE, 3.2, '0.1 8', late=False)
    S.text(x + 104, gy + 115, '✕', 18, 700, RED, 'middle')
    poly([(x + 104, gy + 12), (x + 150, gy + 22), (x + 250, gy + 24), (x + 262, gy + 80), (x + 262, gy + 180)], PURPLE, 2.6, '7 5', late=False)
    robot(x + 104, gy + 14, 13, 90, late=False)
    tx0 = x + 290
    para(tx0, gy + 14, ['빨간 원 = 가상 장애물', '(반지름 0.25m)'], 12, INK, 19)
    para(tx0, gy + 66, ['물러났다가 0.5m 안에서', '또 막히면 그 자리를 막아', '계획이 다른 길을 내게 한다', '목표가 끝나면 지운다'], 12, SUB, 19)
    para(x0 + 2 * (pw + 14) + 20, py0 + 284, ['· 마지막 안전망이다. 반복 시험 126번에서는 한 번도 필요하지 않았다.',
                                              '· "3번 실패하면 경로 앞자리를 막기"는 버렸다',
                                              '  (돌아갈 길 · 물러날 길을 막아 로봇을 가두는 일이 거듭됐다).'], 11.5, INK, 19)


# ------------------------------------------------------------------ 4. 실패했을 때
def failure(y):
    card(y, 372, '4', '막혔을 때의 순서 — 끼인 채 멈추지 않게',
         '위 줄은 달리는 도중, 아래 줄은 Nav2 가 목표를 포기한 뒤다. 어느 쪽이든 끝은 "도착" 아니면 "사유 코드"다.', 'data')

    def chain(yy, items, x0=44, bw=236, gap=32):
        xs = []
        for i, (t, ls, kind) in enumerate(items):
            x = x0 + i * (bw + gap)
            box(x, yy, bw, 84, t, ls, kind)
            xs.append(x)
            if i:
                S.line([(x - gap + 3, yy + 42), (x - 4, yy + 42)], color=INK, sw=1.8)
        return xs
    S.text(44, y + 86, '달리는 도중', 13, 700, INK)
    chain(y + 96, [
        ('제어기가 길을 못 찾음', ['후보 1000개가 모두 충돌', '(FollowPath 실패)'], 'py'),
        ('Nav2 복구', ['지역 비용 지도 비우고 다시 계획', '→ 회전 · 대기 · 후진 차례로'], 'edge'),
        ('같은 자리에서 3번', ['0.4m 안에서 되풀이되면', '브리지가 넘겨받는다'], 'bridge'),
        ('빠져나와 다시 계획', ['장애물에서 멀어진 자리에서', '새 경로 (3-나)'], 'bridge'),
        ('또 같은 자리면 막기', ['0.5m 안에서 두 번째면', '그 자리를 막고 다른 길 (3-다)'], 'bridge'),
        ('도착', ['막힌 원인이 풀리면', '원래 목표로 이어 간다'], 'spring'),
    ])
    S.text(44, y + 222, 'Nav2 가 목표를 포기한 뒤 (복구 6회를 다 씀 · 계획 실패)', 13, 700, INK)
    xs = chain(y + 232, [
        ('붙어 있으면 빠져나옴', ['라이다 최소 거리 0.4m 아래면', '먼저 멀어진다'], 'bridge'),
        ('비용 지도 비우고 3초', ['옛 장애물 표시를 지우고', '라이다로 다시 채운다'], 'bridge'),
        ('경로가 있는지 확인', ['로봇을 움직이지 않고', '계획만 해 본다'], 'client'),
        ('있으면 다시 보냄', ['같은 목표를 최대 3번', '(자세가 달라져 풀린다)'], 'spring'),
        ('없으면 진입 불가', ['BLOCKED_NO_PATH', '다음 지점으로 넘어감'], 'data'),
    ])
    lx = xs[-1] + 236 + 24
    para(lx, y + 250, ['그 밖의 끝', '3번 다 실패 → NAV_FAILED', '90초 동안 전진 없음 → NO_PROGRESS', 'Nav2 가 준비 안 됨 → NAV_UNAVAILABLE'], 11.5, INK, 18)
    S.text(lx, y + 250, '그 밖의 끝', 11.5, 700, INK)
    S.text(44, y + 348, '경로가 없는데 장애물에 붙어 있으면(0.4m 안) "길 없음"으로 단정하지 않고, 한 번 더 빠져나와 다시 본다 — 붙은 자리에서는 출발점이 충돌 구역이라 계획 자체가 거부되기 때문이다.',
           12, 400, SUB)


# ------------------------------------------------------------------ 5. 격자 · 화면 · 설정
def bottom(y):
    card(y, 610, '5', '좁은 틈, 화면에서 읽는 법, 주요 값',
         '0.6m 틈을 멈칫거리지 않고 지나게 한 것은 제어기가 보는 지도의 칸 크기다.', 'py')
    # --- 격자 비교: 틈 0.6m, 로봇 반지름 0.22 → 중심이 지날 수 있는 띠 0.16m
    gx, gy, k = 44, y + 96, 320       # 320px/m
    S.text(gx, gy - 12, '틈 0.6m 를 두 가지 칸 크기로 본 모습', 13.5, 700, INK)
    for j, (res, tag, note) in enumerate([(0.05, '지역 비용 지도 0.05m (전)', '한 칸 어긋나면 띠가 3칸 → 1칸: 15 ~ 31초 멈칫하거나 실패'),
                                          (0.025, '지역 비용 지도 0.025m (지금)', '어긋나도 4 ~ 6칸 남는다: 막지 않았을 때와 같은 시간')]):
        oy = gy + 16 + j * 226
        w, h = 1.0 * k, 0.5 * k
        S.text(gx, oy - 4, tag, 12.5, 700, C['py'][0])
        S.rect(gx, oy, w, h, fill='#ffffff', stroke='#d1d1d6', rx=0)
        a, b = gx + 0.2 * k, gx + 0.8 * k                    # 틈의 양 끝
        S.rect(gx, oy, 0.2 * k, h, fill='#3a3a3c', stroke='none', sw=0, rx=0)
        S.rect(b, oy, 0.2 * k, h, fill='#3a3a3c', stroke='none', sw=0, rx=0)
        S.rect(a, oy, 0.22 * k, h, fill='#c7c7cc', stroke='none', sw=0, rx=0)        # 충돌 구역(반지름만큼)
        S.rect(b - 0.22 * k, oy, 0.22 * k, h, fill='#c7c7cc', stroke='none', sw=0, rx=0)
        S.rect(a + 0.22 * k, oy, 0.16 * k, h, fill='#d9f2e1', stroke='none', sw=0, rx=0)
        n = round(1.0 / res)
        for i in range(n + 1):
            S.raw(f'<line x1="{gx + i * res * k:.1f}" y1="{oy}" x2="{gx + i * res * k:.1f}" y2="{oy + h}" stroke="#8e8e93" stroke-width=".6" opacity=".7"/>')
        for i in range(round(0.5 / res) + 1):
            S.raw(f'<line x1="{gx}" y1="{oy + i * res * k:.1f}" x2="{gx + w}" y2="{oy + i * res * k:.1f}" stroke="#8e8e93" stroke-width=".6" opacity=".7"/>')
        robot(gx + 0.5 * k, oy + h / 2, 0.22 * k * 0.0 + 9, -90, late=False)
        S.raw(f'<circle cx="{gx + 0.5 * k}" cy="{oy + h / 2}" r="{0.22 * k}" fill="none" stroke="#1c1c1e" stroke-width="1.4" stroke-dasharray="4 3"/>')
        S.text(gx, oy + h + 18, note, 12, 400, INK)
    ly = gy + 16 + 2 * 226 - 8
    for i, (col, s) in enumerate([('#3a3a3c', '장애물'), ('#c7c7cc', '충돌 구역 (0.22m)'), ('#d9f2e1', '로봇 중심이 지날 수 있는 띠 0.16m')]):
        lx = gx + [0, 70, 196][i]
        S.rect(lx, ly, 14, 14, fill=col, stroke='#8e8e93', sw=.6, rx=2)
        S.text(lx + 20, ly + 12, s, 11.5, 400, INK)

    # --- 화면에서 읽는 법
    sx, sy = 500, y + 84
    S.text(sx, sy, '화면에서 읽는 법 (관제 지도 · 대시보드)', 13.5, 700, INK)
    S.rect(sx, sy + 14, 500, 190, fill='#f7f7fa', stroke='#d1d1d6', rx=10)
    S.rect(sx + 20, sy + 34, 12, 150, fill='#3a3a3c', stroke='none', sw=0, rx=0)
    S.rect(sx + 250, sy + 34, 120, 40, fill='#3a3a3c', stroke='none', sw=0, rx=0)
    poly([(sx + 90, sy + 170), (sx + 150, sy + 120), (sx + 300, sy + 110), (sx + 460, sy + 100)], BLUE, 3.2, '0.1 8', late=False)
    poly([(sx + 90, sy + 170), (sx + 118, sy + 146), (sx + 150, sy + 130), (sx + 184, sy + 124)], ORANGE, 4, late=False)
    S.raw(f'<path d="M{sx + 196} {sy + 122} L{sx + 182} {sy + 117} L{sx + 184} {sy + 131} z" fill="{ORANGE}"/>')
    poly([(sx + 250, sy + 76), (sx + 370, sy + 76)], RED, 2, late=False)
    poly([(sx + 34, sy + 40), (sx + 34, sy + 180)], RED, 2, late=False)
    robot(sx + 90, sy + 170, 14, -40, late=False)
    S.raw(f'<circle cx="{sx + 460}" cy="{sy + 100}" r="8" fill="#ffffff" stroke="#30b0c7" stroke-width="3"/>')
    para(sx, sy + 228, [
        '· 파란 점선 = 계획 경로. 목표 동안 유지되고, 지나온 부분은 지워진다.',
        '· 주황 실선 + 화살촉 = 제어기 방향. 지금 속도를 3초 유지하면 갈 호다.',
        '  점선과 어긋난 만큼이 제어기의 판단(장애물 비켜 가기)이다.',
        '· 빨간 선 = 라이다가 지금 보는 것.',
        '· 주황 실선은 기본으로 숨김이다. admin → 설정 → 화면 →',
        '  "주행 경로 표시 (제어기 방향)" 에서 켠다.',
        '· 로봇과 겹친 점검 지점 단추는 반투명해져 로봇이 비쳐 보인다.',
    ], 12, INK, 20)

    # --- 주요 값
    vx, vy = 1040, y + 84
    S.text(vx, vy, '주요 값 (어디서 바꾸나)', 13.5, 700, INK)
    rows = [
        ('계획기', 'Theta* · w_traversal_cost 2.0', 'nav2_params.yaml'),
        ('전역 비용 지도', '0.05m · 팽창 0.45 · 가상 장애물 층', 'nav2_params.yaml'),
        ('지역 비용 지도', '0.025m · 3×3m · 팽창 0.6', 'nav2_params.yaml'),
        ('제어기', 'MPPI 10Hz · 후보 1000 · 30단계 × 0.1초', 'nav2_params.yaml'),
        ('속도', '직진 0.22 m/s · 회전 1.2 rad/s · 후진 없음', 'nav2_params.yaml'),
        ('도착 판정', '위치 0.12m · 방향 0.15rad', 'nav2_params.yaml'),
        ('로봇 크기', '반지름 0.22m 원', 'nav2_params.yaml'),
        ('몸통 채우기', '깊이 0.3m · 벽 허용 0.15m', 'SHADOW_*'),
        ('같은 자리 판정', '3번 · 0.4m 안', 'STUCK_*'),
        ('빠져나오기', '0.45m · 0.10 m/s · 10초 제한', 'ESCAPE_*'),
        ('다시 보내기', '최대 3번', 'MAX_RETRIES'),
        ('전진 없음 제한', '90초', 'NO_PROGRESS_SEC'),
    ]
    for i, (a, b, c) in enumerate(rows):
        ry = vy + 30 + i * 25
        S.text(vx, ry, a, 12, 600, INK)
        S.text(vx + 112, ry, b, 12, 400, INK)
        S.text(vx + 570, ry, c, 10.5, 500, SUB, 'end', mono=True)
        S.raw(f'<line x1="{vx}" y1="{ry + 8}" x2="{vx + 570}" y2="{ry + 8}" stroke="#e5e5ea"/>')
    by = vy + 30 + len(rows) * 25 + 16
    S.text(vx, by, '대문자 이름은 ros/robot/src/nav2_goal_bridge.py 의 상수다.', 11.5, 400, SUB)
    S.text(vx, by + 34, '확인하는 법', 13.5, 700, INK)
    cmds = ['python3 /sim/tools/nav_soak.py --rounds 3     # 장애물 × 시점 반복 시험',
            'python3 /sim/tools/plan_probe.py              # 계획 경로 길이 · 꺾임 · 벽 여유',
            'python3 scripts/e2e_test.py --only-obstacles  # 장애물 시나리오 9-1 ~ 9-6']
    S.rect(vx, by + 46, 570, 76, fill='#1c1c1e', stroke='none', sw=0, rx=8)
    for i, c in enumerate(cmds):
        S.text(vx + 12, by + 68 + i * 20, c, 10.5, 400, '#e5e5ea', mono=True)
    S.text(vx, by + 140, '위 두 줄은 sim 컨테이너 안에서(docker compose exec sim …), 셋째는 저장소 루트에서.', 11.5, 400, SUB)


def build():
    S.text(24, 46, '주행 제어기 설명서', 26, 700)
    S.text(24, 72, '목표 하나가 경로가 되고 속도 명령이 되는 과정, 길이 좁아지거나 막혔을 때의 동작. 시뮬레이션(Nav2 Humble, TurtleBot3 Waffle Pi) 기준이고 '
                   '값은 코드 · 설정 · 반복 시험에서 가져왔다.', 13, 400, SUB)
    y = 92
    for fn, h in ((flow, 318), (site, 716), (helpers, 452), (failure, 372), (bottom, 610)):
        fn(y)
        y += h + 14
    S.h = y + 10
    S.render(OUT)


if __name__ == '__main__':
    build()
