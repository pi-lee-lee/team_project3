"""Theta* 계획기 설명서(그림): A* 가 무엇이고, Theta* 가 거기서 무엇 하나를 바꿨으며, 그 결과 경로가 어떻게 달라지는지.

값은 ros/sim/src/config/nav2_params.yaml(planner_server · global_costmap)에서 읽어 쓴다.
경로 그림은 theta_sim.py 가 Nav2 의 식 그대로 계산한 것이다(Nav2 실행 기록이 아니다). 건물 그림은 world_spec.py 의 설계도에서
계산했고, 그 위의 점은 실제 Nav2 가 낸 경로다(plan_probe.py --dump → build_drive_controller.PATHS).
실행: python3 docs/navigation/build_theta_star.py  →  docs/navigation/nav_03_theta_star.svg
"""
import math
from pathlib import Path

import build_drive_controller as D        # docs/_lib 를 경로에 넣는다
import nav2cfg
import theta_sim as T
from build_drive_controller import BLUE, GRAY, INK, ORANGE, PURPLE, RED, SUB, W
from nav2cfg import num
from svg import C, Svg

OUT = Path(__file__).resolve().parent / 'nav_03_theta_star.svg'
S = Svg(1640, 4000)
D.S = S

GREEN, TEAL = '#248a3d', '#30b0c7'
CFG = nav2cfg.load()
G = CFG['global_costmap']['global_costmap']['ros__parameters']
P = CFG['planner_server']['ros__parameters']['GridBased']
RES, R = G['resolution'], G['robot_radius']
INFL, SCALE = G['inflation_layer']['inflation_radius'], G['inflation_layer']['cost_scaling_factor']
WT = P['w_traversal_cost']
WT_LOW = 0.2                               # 낮춰 보았다가 버린 값(nav2_params.yaml 머리 6)

# ------------------------------------------------------------------ 예시 격자(28 × 14칸)
GW, GH = 28, 14
BLOCKS = [(9, 0, 2, 9), (18, 6, 2, 8)]    # (x, y, 폭, 높이): 위에서 내려온 벽, 아래에서 올라온 벽
START, GOAL = (1, 6), (26, 8)
TOY = [[0] * GW for _ in range(GH)]
for bx, by, bw, bh in BLOCKS:
    for yy in range(by, by + bh):
        for xx in range(bx, bx + bw):
            TOY[yy][xx] = 254
RUN = {m: T.plan(TOY, START, GOAL, m, strict=True) for m in ('dijkstra', 'astar', 'theta')}

# ------------------------------------------------------------------ 건물(설계도 → 비용 지도 → 경로)
COST, DIST = T.costmap(W.rects(), W.MX0, W.MY0, W.MX1, W.MY1, RES, R, INFL, SCALE)
COSTL = COST.tolist()
SPOTS = dict({k: v[:2] for k, v in W.POINTS.items()}, 충전=W.START[:2])
ROUTES = [('P3', 'P1'), ('P1', 'P2'), ('충전', 'P3'), ('충전', 'P2')]


def cell(x, y):
    return int((x - W.MX0) / RES), int((y - W.MY0) / RES)


def world(c):
    return W.MX0 + (c[0] + 0.5) * RES, W.MY0 + (c[1] + 0.5) * RES


def clearance(path):
    """경로가 벽 · 설비에 가장 가까이 간 거리(m)."""
    best = 9.0
    for a, b in zip(path, path[1:]):
        n = max(1, int(math.hypot(b[0] - a[0], b[1] - a[1]) * 2))
        for i in range(n + 1):
            best = min(best, DIST[round(a[1] + (b[1] - a[1]) * i / n)][round(a[0] + (b[0] - a[0]) * i / n)])
    return best


def route(a, b, mode, wt):
    r = T.plan(COSTL, cell(*SPOTS[a]), cell(*SPOTS[b]), mode, P['w_euc_cost'], wt, P['w_heuristic_cost'])
    return dict(pts=[world(c) for c in r['path']], len=T.length(r['path']) * RES, turn=T.turning(r['path']), clear=clearance(r['path']),
                opened=len(r['order']))


SITE = {(a, b, m, wt): route(a, b, m, wt) for a, b in ROUTES for m, wt in (('astar', WT), ('theta', WT), ('theta', WT_LOW))}


# ------------------------------------------------------------------ 그리기 도우미
def stroke(pts, color, sw=3, op=1.0, dash=None):
    D.poly(pts, color, sw, dash, late=False, opacity=op)


def dot(x, y, r, fill, ring='#ffffff', sw=2):
    S.raw(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="{fill}" stroke="{ring}" stroke-width="{sw}"/>')


def tag(x, y, s, color, size=11.5):
    D.label(x, y, s, color, size, 'middle', 700)


def grid(ox, oy, cs, run=None, shade=None, links=False, path_color=BLUE, sw=4, marks=True):
    """예시 격자. run = 계획 결과. shade = 연 칸을 칠할 색. links = 칸 → 부모 선. 칸 중심 좌표 함수를 돌려준다."""
    def c(p):
        return ox + (p[0] + 0.5) * cs, oy + (p[1] + 0.5) * cs
    S.rect(ox, oy, GW * cs, GH * cs, fill='#ffffff', stroke='none', sw=0, rx=0)
    if run and shade:
        gmax = max(run['g'][p] for p in run['order'])
        for p in run['order']:
            S.rect(ox + p[0] * cs, oy + p[1] * cs, cs, cs, fill=shade, stroke='none', sw=0, rx=0, opacity=0.10 + 0.34 * run['g'][p] / gmax)
    for i in range(GW + 1):
        S.raw(f'<line x1="{ox + i * cs}" y1="{oy}" x2="{ox + i * cs}" y2="{oy + GH * cs}" stroke="#d9d9de" stroke-width=".7"/>')
    for j in range(GH + 1):
        S.raw(f'<line x1="{ox}" y1="{oy + j * cs}" x2="{ox + GW * cs}" y2="{oy + j * cs}" stroke="#d9d9de" stroke-width=".7"/>')
    for bx, by, bw, bh in BLOCKS:
        S.rect(ox + bx * cs, oy + by * cs, bw * cs, bh * cs, fill='#3a3a3c', stroke='none', sw=0, rx=0)
    if run and links:
        for p in run['order']:
            q = run['parent'][p]
            if q != p:
                (x1, y1), (x2, y2) = c(p), c(q)
                S.raw(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{path_color}" stroke-width=".9" opacity=".38"/>')
    if run:
        pts = [c(p) for p in run['path']]
        stroke(pts, '#ffffff', sw + 3, 0.9)
        stroke(pts, path_color, sw)
        for x, y in pts[1:-1]:
            dot(x, y, max(3, sw), path_color, '#ffffff', 1.6)
    S.rect(ox, oy, GW * cs, GH * cs, fill='none', stroke='#8e8e93', sw=1.2, rx=0)
    if marks:
        dot(*c(START), max(4, cs * 0.3), INK)
        dot(*c(GOAL), max(4, cs * 0.3), '#ffffff', TEAL, 3)
        if cs >= 20:
            tag(c(START)[0], c(START)[1] - cs * 0.62, '출발', INK)
            tag(c(GOAL)[0], c(GOAL)[1] + cs * 0.95, '목표', TEAL)
    return c


def stat_row(x, y, items):
    for i, (k, v, col) in enumerate(items):
        xx = x + i * 180
        S.text(xx, y, k, 11.5, 500, SUB)
        S.text(xx, y + 24, v, 19, 700, col)


def toy_stats(run):
    return T.length(run['path']), len(run['path']) - 2, T.turning(run['path']), len(run['order'])


# ------------------------------------------------------------------ 0. 한 문장
def idea(y):
    D.card(y, 268, '0', 'Theta* 는 무엇인가', '지도에서 출발 → 목표까지의 길(경로)을 찾는 "계획기"다. 목표마다 한 번 돌고, 그 길을 따라 모는 것은 제어기(MPPI)의 일이다.', 'client')
    S.rect(40, y + 72, 760, 178, fill=C['client'][1], stroke=BLUE, sw=1.4, rx=12)
    D.para(60, y + 102, ['A* 와 똑같이 찾는다.', '다만 길을 "옆 칸"에 잇지 않고 "보이는 가장 먼 점"에 잇는다.'], 17, BLUE, 27, 700)
    D.para(60, y + 164, [
        '그래서 A* 계열이다(A* 의 변형). 찾는 순서 · 비용 계산 · 끝나는 조건이 모두 A* 그대로이고,',
        '칸을 꺼낼 때 "부모를 누구로 할까" 한 줄만 다르다. 그 한 줄 때문에 계단 모양(0° · 45° · 90°)이던 경로가',
        '아무 각도의 직선(any-angle)이 된다. 이름의 Theta(θ)가 그 각도다.',
    ], 12.5, INK, 20)
    # 계보
    bx, by = 836, y + 78
    S.text(bx, by + 4, 'A* 계열 — 무엇을 하나씩 더했나', 13.5, 700, INK)
    fam = [('Dijkstra', '1959', ['가까운 칸부터', '사방으로 넓힌다'], 'dev'),
           ('A*', '1968', ['+ 목표까지 남은 거리', '→ 목표 쪽부터 넓힌다'], 'edge'),
           ('Theta*', '2007', ['+ 보이는 점에 바로 잇기', '→ 아무 각도의 직선'], 'client'),
           ('Nav2 Theta*', '지금 쓰는 것', ['+ 벽 가까운 칸에 비용', '시야 확인은 꺼낼 때만'], 'spring')]
    for i, (t, m, ls, kind) in enumerate(fam):
        x = bx + i * 192
        D.box(x, by + 18, 168, 92, t, ls, kind, mono=m)
        if i:
            S.line([(x - 22, by + 64), (x - 3, by + 64)], color=INK, sw=1.8)
    D.para(bx, by + 136, ['이 프로젝트가 거친 계획기: NavFn(Dijkstra) → Smac 2D(A* + 경로 다듬기) → Theta*.',
                          'Smac 은 벽 비용을 따라 통로 가운데로 휘어 열린 곳에서도 S 자로 출렁였다. Theta* 는 곧은 구간 + 모퉁이만 낸다.'], 12, SUB, 19)


# ------------------------------------------------------------------ 1. A*
def astar(y):
    D.card(y, 640, '1', '먼저 A* — 격자에서 길을 찾는 법',
           '지도를 칸으로 나누고, 출발 칸에서 이웃 칸으로 번져 나가며 "여기까지 가장 싸게 오는 길"을 칸마다 적어 둔다. 목표에 닿으면 적어 둔 것을 거슬러 올라간다.', 'client')
    run = RUN['astar']
    cs = 30
    ox, oy = 44, y + 104
    S.text(ox, oy - 12, f'A* 가 찾은 길 (예시 격자 {GW} × {GH}칸, 검은 칸 = 벽)', 13.5, 700, INK)
    c = grid(ox, oy, cs, run, shade=PURPLE, path_color=PURPLE)
    star = run['raw'][len(run['raw']) * 2 // 3]
    sx, sy = c(star)
    S.rect(sx - cs / 2, sy - cs / 2, cs, cs, fill='none', stroke=ORANGE, sw=2.6, rx=0)
    gv, hv = run['g'][star], math.hypot(star[0] - GOAL[0], star[1] - GOAL[1])
    D.para(ox, oy + GH * cs + 24, [
        f'보라색 칸 = A* 가 꺼내 본 칸({len(run["order"])}개, 진할수록 출발에서 멀다). 굵은 선 = 찾은 길. 이웃 8칸으로만 움직이므로 길은 가로 · 세로 · 45° 대각선의 이어 붙임이다.',
    ], 12, INK)
    D.para(ox, oy + GH * cs + 46, [f'주황 테두리 칸의 계산:  g(출발에서 온 거리) {gv:.1f}  +  h(목표까지 직선 거리) {hv:.1f}  =  f {gv + hv:.1f}   — f 가 작은 칸부터 꺼낸다.'], 12, ORANGE, 19, 600)
    # 오른쪽: 이웃 · 순서 · Dijkstra 비교
    rx = ox + GW * cs + 40
    S.text(rx, oy - 12, '한 칸에서 갈 수 있는 곳', 13.5, 700, INK)
    n = 44
    for j in range(3):
        for i in range(3):
            S.rect(rx + i * n, oy + j * n, n, n, fill='#f2ecf7' if (i, j) == (1, 1) else '#ffffff', stroke='#c7c7cc', rx=0)
    mx, my = rx + 1.5 * n, oy + 1.5 * n
    for i in (-1, 0, 1):
        for j in (-1, 0, 1):
            if (i, j) != (0, 0):
                S.line([(mx + i * 9, my + j * 9), (mx + i * (n - 12), my + j * (n - 12))], color=PURPLE, sw=1.5, late=False)
                S.text(mx + i * n, my + j * n + (17 if j >= 0 else -9) * (1 if j else 0.3), '1.41' if i and j else '1', 10, 600, SUB, 'middle')
    D.para(rx + 3 * n + 18, oy + 18, ['이웃 8칸 (how_many_corners 8).', '곧게 1칸 = 거리 1,', '대각선 = 1.41(√2).', '벽 칸으로는 못 간다.'], 12, INK, 19)
    sy0 = oy + 3 * n + 34
    S.text(rx, sy0, 'A* 의 순서', 13.5, 700, INK)
    D.para(rx, sy0 + 24, [
        '① 열린 칸 중 f = g + h 가 가장 작은 칸을 꺼낸다.',
        '② 그 칸의 이웃마다 "이 칸을 거쳐 가는 값"을 낸다.',
        '③ 적어 둔 값보다 싸면 고쳐 적고, 부모를 이 칸으로.',
        '④ 목표 칸을 꺼내면 끝. 부모를 거슬러 가면 길이다.',
    ], 12, INK, 20)
    D.para(rx, sy0 + 112, ['g = 출발에서 이 칸까지 실제로 온 값(확정)', 'h = 이 칸에서 목표까지 직선 거리(짐작)'], 12, PURPLE, 20, 600)
    # Dijkstra 와 비교(작은 그림 둘)
    ty = sy0 + 168
    S.text(rx, ty, 'h 가 하는 일: 덜 뒤진다', 13.5, 700, INK)
    ms = 9
    for i, (m, name) in enumerate([('dijkstra', 'Dijkstra (h 없음)'), ('astar', 'A* (h 있음)')]):
        gx = rx + i * (GW * ms + 26)
        grid(gx, ty + 14, ms, RUN[m], shade=PURPLE, path_color=PURPLE, sw=2, marks=False)
        S.text(gx, ty + 14 + GH * ms + 18, f'{name}: {len(RUN[m]["order"])}칸', 12, 600, INK)
    D.para(rx, ty + 14 + GH * ms + 42, ['길의 길이는 같다. 목표 쪽이 아닌 칸을 뒤로 미룰 뿐이다.'], 11.5, SUB)


# ------------------------------------------------------------------ 2. 차이 한 가지
def patch(x, y, title, mode, col):
    """칸 5 × 4 조각. 조부모 G → 부모 P → 지금 칸 S."""
    n = 62
    S.text(x, y - 12, title, 13.5, 700, col)
    Gc, Pc, Sc = (1, 2), (2, 2), (3, 1)

    def c(p):
        return x + (p[0] + 0.5) * n, y + (p[1] + 0.5) * n
    for j in range(4):
        for i in range(5):
            wall = mode == 'blocked' and (i, j) == (2, 1)
            S.rect(x + i * n, y + j * n, n, n, fill='#3a3a3c' if wall else '#ffffff', stroke='#c7c7cc', rx=0)
    if mode != 'astar':                      # 시야 확인이 지나는 칸
        for p in ((1, 2), (2, 2), (2, 1), (3, 1)):
            if not (mode == 'blocked' and p == (2, 1)):
                S.rect(x + p[0] * n + 1, y + p[1] * n + 1, n - 2, n - 2, fill='#eaf3ff' if mode == 'theta' else '#fff1e8', stroke='none', sw=0, rx=0)
    via = [c(Gc), c(Pc), c(Sc)]
    if mode == 'theta':
        stroke(via, GRAY, 2.4, 0.7, '5 5')
        stroke([c(Gc), c(Sc)], BLUE, 4.5)
    else:
        stroke(via, PURPLE, 4.5)
        if mode == 'blocked':
            stroke([c(Gc), c(Sc)], RED, 2.4, 0.9, '5 5')
            S.text(c((2, 1))[0], c((2, 1))[1] + 6, '✕', 20, 700, RED, 'middle')
    for p, s in ((Gc, 'G'), (Pc, 'P'), (Sc, 'S')):
        dot(*c(p), 13, INK if p != Sc else ORANGE)
        S.text(c(p)[0], c(p)[1] + 4.5, s, 12, 700, '#ffffff', 'middle')
    return n


def difference(y):
    D.card(y, 520, '2', '다른 점은 하나 — 부모를 누구로 하나',
           '칸 S 를 꺼냈다. A* 에서 S 의 부모는 바로 옆 칸 P 다(P 를 거쳐 왔으므로). Theta* 는 한 번 더 묻는다: "P 의 부모 G 에서 S 가 바로 보이나?"', 'client')
    py = y + 110
    a = math.hypot(1, 1) + 1
    b = math.hypot(2, 1)
    n = patch(44, py, 'A*: 부모는 언제나 옆 칸', 'astar', PURPLE)
    patch(44 + 5 * n + 60, py, 'Theta*: 보이면 G 에 바로 잇는다', 'theta', BLUE)
    patch(44 + 2 * (5 * n + 60), py, 'Theta*: 안 보이면 그대로 둔다', 'blocked', RED)
    ty = py + 4 * n + 26
    D.para(44, ty, ['길 = G → P → S', f'길이 1 + 1.41 = {a:.2f}칸', '방향은 0° 다음 45° — 격자 방향뿐이다.'], 12, INK, 19)
    D.para(44 + 5 * n + 60, ty, ['G 와 S 를 이은 직선이 지나는 칸(파란 칸)이 모두', f'지날 수 있는 칸이면 부모를 G 로 바꾼다. 길 = G → S,', f'길이 {b:.2f}칸. 삼각형의 한 변은 두 변의 합보다 짧다.'], 12, INK, 19)
    D.para(44 + 2 * (5 * n + 60), ty, ['직선이 벽 칸을 지나면 "안 보인다"(시야 확인 실패).', 'A* 와 같이 P 를 거친 길을 그대로 둔다.', '→ 그래서 경로는 벽 모퉁이에서만 꺾인다.'], 12, INK, 19)
    # 오른쪽: 거듭하면
    rx = 44 + 3 * (5 * n + 60) - 14
    S.rect(rx, py - 30, 1596 - rx, 310, fill='#f7f7fa', stroke='#d1d1d6', rx=10)
    D.para(rx + 16, py - 4, ['거듭하면'], 13.5, INK, 20, 700)
    D.para(rx + 16, py + 22, [
        'S 의 부모가 G 가 되면, 다음에 S 의',
        '이웃을 꺼낼 때는 "S 의 부모"인 G 가',
        '다시 조부모 후보가 된다. 보이는 한',
        '부모는 계속 같은 점에 머문다.',
        '',
        '결과: 길 위의 점들이 한 칸씩',
        '이어지지 않고, 출발 → 모퉁이 →',
        '모퉁이 → 목표로 건너뛴다',
        '(3번 그림의 부챗살).',
        '',
        '값 비교는 A* 와 같다: 바꾼 쪽이',
        '더 쌀 때만 바꾼다(직선이 지나는',
        '칸의 벽 비용도 더해서 — 5번).',
    ], 12, INK, 19)
    D.para(44, y + 498, ['시야 확인(line of sight) = 두 칸의 중심을 이은 직선을 칸 단위로 따라가며 벽 · 충돌 구역 칸이 하나라도 있는지 보는 것. Nav2 구현은 칸을 꺼낼 때 한 번만 확인한다(Lazy Theta*).'], 11.5, SUB)


# ------------------------------------------------------------------ 3. 같은 격자에서 비교
def compare(y):
    D.card(y, 652, '3', '같은 지도 · 같은 출발과 목표',
           '가는 선은 "칸 → 그 칸의 부모"다. A* 는 모든 칸이 옆 칸을 가리키고, Theta* 는 멀리 있는 몇 개의 점(출발 · 벽 모퉁이)을 가리킨다. 굵은 선이 찾은 길이다.', 'client')
    cs = 27
    oy = y + 104
    la, ka, ta, na = toy_stats(RUN['astar'])
    lt, kt, tt, nt = toy_stats(RUN['theta'])
    for i, (m, name, col, st) in enumerate([('astar', 'A*  — 계단 모양', PURPLE, (la, ka, ta, na)), ('theta', 'Theta*  — 직선 + 모퉁이', BLUE, (lt, kt, tt, nt))]):
        ox = 44 + i * (GW * cs + 40)
        S.text(ox, oy - 12, name, 14.5, 700, col)
        grid(ox, oy, cs, RUN[m], shade=col, links=True, path_color=col, sw=4.5)
        stat_row(ox, oy + GH * cs + 26, [('길이', f'{st[0]:.1f}칸', col), ('꺾인 곳', f'{st[1]}곳', col), ('꺾인 각도의 합', f'{st[2]:.0f}°', col), ('꺼내 본 칸', f'{st[3]}칸', INK)])
    D.para(44, oy + GH * cs + 86, [
        f'· 길이: Theta* 가 {(1 - lt / la) * 100:.0f}% 짧다. 격자 길(A*)은 실제 최단보다 최대 약 8% 길어질 수 있다 — 방향이 45° 단위로 묶여 있어서다.',
        f'· 꺾임: {ka}곳 → {kt}곳. 로봇에게는 길이보다 이쪽이 크다. 꺾인 점마다 제어기가 방향을 고쳐 잡아야 하고, 계단은 좌우로 흔들리는 주행이 된다.',
        '· 찾는 수고(꺼내 본 칸)는 비슷하거나 조금 적다. Theta* 가 더하는 일은 칸을 꺼낼 때마다 직선 하나를 따라가 보는 것뿐이다.',
        '· Theta* 도 꺾이는 점은 칸의 중심이다. 그래서 수학적 최단(벽 모서리를 스치는 선)과 아주 조금 다를 수 있다 — "거의 최단"이다.',
    ], 12, INK, 20)


# ------------------------------------------------------------------ 4. 이 건물에서
def site_map(ox, oy, k, band=True):
    def px(x):
        return ox + (x - W.X0) * k

    def py(v):
        return oy + (W.Y1 - v) * k
    wd, ht = (W.X1 - W.X0) * k, (W.Y1 - W.Y0) * k
    S.raw(f'<clipPath id="sm{int(ox)}{int(oy)}"><rect x="{ox}" y="{oy}" width="{wd:.1f}" height="{ht:.1f}"/></clipPath><g clip-path="url(#sm{int(ox)}{int(oy)})">')
    S.rect(ox, oy, wd, ht, fill='#ffffff', stroke='none', sw=0, rx=0)
    if band:
        for x, v, sx, sy in W.rects():
            S.rect(px(x - sx / 2 - INFL), py(v + sy / 2 + INFL), (sx + 2 * INFL) * k, (sy + 2 * INFL) * k, fill='#cfe4ff', stroke='none', sw=0, rx=INFL * k)
        for x, v, sx, sy in W.rects():
            S.rect(px(x - sx / 2 - R), py(v + sy / 2 + R), (sx + 2 * R) * k, (sy + 2 * R) * k, fill='#c7c7cc', stroke='none', sw=0, rx=R * k)
    for i, (x, v, sx, sy) in enumerate(W.rects()):
        S.rect(px(x - sx / 2), py(v + sy / 2), sx * k, sy * k, fill='#3a3a3c' if i < len(W.WALLS) else '#77777d', stroke='none', sw=0, rx=0)
    return px, py


def spots(px, py, with_start=True):
    for name, (x, v) in SPOTS.items():
        if name == '충전':
            dot(px(x), py(v), 6, INK)
            D.label(px(x), py(v) + 22, '충전 위치', INK, 11, 'middle', 700)
        else:
            dot(px(x), py(v), 7, '#ffffff', TEAL, 3)
            D.label(px(x) + (14 if name != 'P2' else -14), py(v) - 10, name, TEAL, 12, 'start' if name != 'P2' else 'end', 700)


def building(y):
    D.card(y, 720, '4', '이 건물에서 — 지금 설정값으로',
           f'전역 비용 지도({num(RES)}m 칸, 건물 전체 {COST.shape[1]} × {COST.shape[0]}칸)에서 네 구간을 같은 비용으로 계산했다. 왼쪽이 A*, 오른쪽이 지금 쓰는 Theta* 다.', 'client')
    k = 62
    oy = y + 106
    wd, ht = (W.X1 - W.X0) * k, (W.Y1 - W.Y0) * k
    for i, (m, name, col) in enumerate([('astar', 'A* (같은 비용 지도 · 같은 가중치)', PURPLE), ('theta', 'Theta* (지금)', BLUE)]):
        ox = 44 + i * (wd + 30)
        S.text(ox, oy - 12, name, 14.5, 700, col)
        px, py = site_map(ox, oy, k)
        for a, b in ROUTES:
            pts = [(px(x), py(v)) for x, v in SITE[(a, b, m, WT)]['pts']]
            stroke(pts, '#ffffff', 5.5, 0.9)
            stroke(pts, col, 3)
        if m == 'theta':
            for key in ('P3>P1', 'P1>P2'):
                for x, v in D.PATHS[key]:
                    S.raw(f'<circle cx="{px(x):.1f}" cy="{py(v):.1f}" r="3.2" fill="{ORANGE}" stroke="#ffffff" stroke-width="1"/>')
        S.raw('</g>')
        S.rect(ox, oy, wd, ht, fill='none', stroke='#8e8e93', sw=1.2, rx=0)
        spots(px, py)
    # 범례
    ly = oy + ht + 24
    lx = 44
    for kind, col, s in [('box', '#3a3a3c', '벽 · 설비'), ('box', '#c7c7cc', f'충돌 구역: 벽에서 {num(R)}m 안(로봇 반지름) — 못 간다'), ('box', '#cfe4ff', f'비용 띠: 벽에서 {num(INFL)}m 안 — 갈 수 있지만 비싸다'),
                         ('dot', ORANGE, '실제 Nav2 가 낸 경로의 점(plan_probe)')]:
        if kind == 'box':
            S.rect(lx, ly - 11, 20, 14, fill=col, stroke='#8e8e93', sw=.6, rx=3)
        else:
            dot(lx + 10, ly - 4, 4, col, '#ffffff', 1)
        S.text(lx + 27, ly, s, 11.5, 400, INK)
        lx += 27 + sum(12.2 if ord(ch) > 0x1100 else 6.6 for ch in s) * 11.5 / 12 + 26
    # 표
    tx = 44 + 2 * (wd + 30)
    S.text(tx, oy - 12, '구간별 비교', 13.5, 700, INK)
    cols = (tx, tx + 100, tx + 204)
    S.text(cols[1], oy + 16, 'A*', 12, 700, PURPLE)
    S.text(cols[2], oy + 16, 'Theta*', 12, 700, BLUE)
    for i, (a, b) in enumerate(ROUTES):
        ry = oy + 48 + i * 86
        ra, rt = SITE[(a, b, 'astar', WT)], SITE[(a, b, 'theta', WT)]
        S.raw(f'<line x1="{tx}" y1="{ry - 18}" x2="{tx + 300}" y2="{ry - 18}" stroke="#e5e5ea"/>')
        S.text(cols[0], ry, f'{a} → {b}', 12.5, 700, INK)
        for j, r in enumerate((ra, rt)):
            col = (PURPLE, BLUE)[j]
            S.text(cols[j + 1], ry, f'{r["len"]:.2f} m', 12.5, 600, col)
            S.text(cols[j + 1], ry + 20, f'꺾임 {len(r["pts"]) - 2}곳', 12, 400, INK)
            S.text(cols[j + 1], ry + 40, f'합 {r["turn"]:.0f}°', 12, 400, INK)
        S.text(cols[0], ry + 20, '길이', 11, 400, SUB)
        S.text(cols[0], ry + 40, '꺾인 각도', 11, 400, SUB)
    sa = sum(SITE[(a, b, 'astar', WT)]['turn'] for a, b in ROUTES)
    st = sum(SITE[(a, b, 'theta', WT)]['turn'] for a, b in ROUTES)
    D.para(tx, oy + 48 + len(ROUTES) * 86 + 4, [
        f'네 구간의 꺾인 각도 합:',
        f'{sa:.0f}° → {st:.0f}° ({(1 - st / sa) * 100:.0f}% 줄었다).',
        '',
        '열린 곳(생산동 가운데)은 한 줄로',
        '가로지르고, 문 · 모퉁이 둘레에서만',
        '꺾인다. 주황 점(실제 경로)이 같은',
        '선 위에 놓인다.',
    ], 12, INK, 19)
    D.para(44, y + 700, ['설계도(world_spec.py)로 계산한 것이라 SLAM 지도(site.pgm)로 계획한 실제 경로와 몇 cm 다를 수 있다. 실제 경로의 길이 · 꺾임 · 벽 여유는 plan_probe.py 로 잰다.'], 11.5, SUB)


# ------------------------------------------------------------------ 5. 벽 비용
def cost_of(d, w):
    if d <= R:
        return None
    v = math.floor(252 * math.exp(-SCALE * (d - R))) if d <= INFL else 0
    return T.cell_cost(v, w)


def wallcost(y):
    D.card(y, 560, '5', '최단만 찾으면 벽을 스친다 — 벽 가까운 칸에 비용을 매긴다',
           f'Nav2 의 Theta* 는 거리에 "칸 비용"을 더한다. 벽에 가까운 칸일수록 비싸서, 조금 돌더라도 벽에서 떨어진 길이 싸진다. 그 세기가 w_traversal_cost {num(WT)} 다.', 'client')
    # 그림표: 벽에서 떨어진 거리 → 칸 하나의 비용
    gx, gy, gw, gh = 70, y + 118, 470, 250
    dmax, vmax = 0.8, 2.2
    S.text(gx - 26, gy - 16, '칸 하나를 지나는 값 (곧게 한 칸 가는 거리 = 1)', 13.5, 700, INK)

    def X(d):
        return gx + d / dmax * gw

    def Y(v):
        return gy + gh - v / vmax * gh
    S.rect(gx, gy, gw, gh, fill='#ffffff', stroke='#d1d1d6', rx=0)
    S.rect(gx, gy, X(R) - gx, gh, fill='#c7c7cc', stroke='none', sw=0, rx=0)
    S.rect(X(R), gy, X(INFL) - X(R), gh, fill='#cfe4ff', stroke='none', sw=0, rx=0)
    S.text((gx + X(R)) / 2, gy + 22, '충돌 구역', 11.5, 700, INK, 'middle')
    S.text((gx + X(R)) / 2, gy + 40, '못 간다', 11, 400, INK, 'middle')
    S.text((X(R) + X(INFL)) / 2, gy + 22, '비용 띠', 11.5, 700, BLUE, 'middle')
    S.text((X(INFL) + gx + gw) / 2, gy + 22, '열린 곳', 11.5, 700, GREEN, 'middle')
    S.text((X(INFL) + gx + gw) / 2, gy + 40, '거의 0 → 직선', 11, 400, INK, 'middle')
    S.raw(f'<line x1="{gx}" y1="{Y(1):.1f}" x2="{gx + gw}" y2="{Y(1):.1f}" stroke="#8e8e93" stroke-dasharray="4 3"/>')
    S.text(gx + gw + 6, Y(1) + 4, '거리 1칸', 10.5, 500, SUB)
    for w, col, sw_, dash in ((WT_LOW, RED, 2, '6 4'), (WT, BLUE, 3.4, None)):
        ds = [R + 0.0001 + (dmax - R) * i / 240 for i in range(241)]
        pts = [(X(d), Y(cost_of(d, w))) for d in ds]
        D.poly(pts, col, sw_, dash, late=False)
    D.label(X(0.33), Y(cost_of(0.33, WT)) - 12, f'w_traversal_cost {num(WT)} (지금)', BLUE, 11.5, 'start', 700)
    D.label(X(0.25), Y(cost_of(0.25, WT_LOW)) - 8, f'{num(WT_LOW)} (버린 값)', RED, 11.5, 'start', 700)
    for d in (0, R, INFL, 0.8):
        S.text(X(d), gy + gh + 16, f'{num(d)}', 11, 600, INK, 'middle')
    S.text(gx + gw / 2, gy + gh + 36, '벽에서 떨어진 거리 (m)', 11, 500, SUB, 'middle')
    for v in (0, 1, 2):
        S.text(gx - 6, Y(v) + 4, str(v), 10.5, 500, SUB, 'end')
    D.para(gx - 26, gy + gh + 64, [
        f'· 충돌 구역 바로 바깥 칸 하나 = 거리 {cost_of(R + 0.001, WT):.1f}칸어치. 띠의 끝({num(INFL)}m)에서도 {cost_of(INFL, WT):.1f}칸어치.',
        f'· 띠 밖은 {cost_of(0.6, WT):.2f} — 사실상 거리만 본다. 그래서 열린 곳의 길이 직선이 된다.',
        f'· 띠가 {num(INFL)}m 에서 끊기는 것은 전역 비용 지도의 팽창 반경(inflation_radius)이다.',
        '  1.0 처럼 넓으면 열린 곳까지 비용이 깔려 길이 통로 가운데로 휜다.',
    ], 12, INK, 19.5)
    # 가운데: 모퉁이 확대
    k = 150
    wx0, wx1, wy0, wy1 = 2.1, 4.5, 4.3, 6.5
    ox, oy = 600, y + 118
    S.text(ox, oy - 16, '전기실 문 둘레 (P3 → P1 구간 확대)', 13.5, 700, INK)
    S.raw(f'<clipPath id="zm"><rect x="{ox}" y="{oy}" width="{(wx1 - wx0) * k:.1f}" height="{(wy1 - wy0) * k:.1f}"/></clipPath><g clip-path="url(#zm)">')

    def px(x):
        return ox + (x - wx0) * k

    def py(v):
        return oy + (wy1 - v) * k
    S.rect(ox, oy, (wx1 - wx0) * k, (wy1 - wy0) * k, fill='#ffffff', stroke='none', sw=0, rx=0)
    for x, v, sx, sy in W.rects():
        S.rect(px(x - sx / 2 - INFL), py(v + sy / 2 + INFL), (sx + 2 * INFL) * k, (sy + 2 * INFL) * k, fill='#cfe4ff', stroke='none', sw=0, rx=INFL * k)
    for x, v, sx, sy in W.rects():
        S.rect(px(x - sx / 2 - R), py(v + sy / 2 + R), (sx + 2 * R) * k, (sy + 2 * R) * k, fill='#c7c7cc', stroke='none', sw=0, rx=R * k)
    for i, (x, v, sx, sy) in enumerate(W.rects()):
        S.rect(px(x - sx / 2), py(v + sy / 2), sx * k, sy * k, fill='#3a3a3c' if i < len(W.WALLS) else '#77777d', stroke='none', sw=0, rx=0)
    lo, hi = SITE[('P3', 'P1', 'theta', WT_LOW)], SITE[('P3', 'P1', 'theta', WT)]
    stroke([(px(a), py(b)) for a, b in lo['pts']], RED, 3, 1.0, '7 5')
    stroke([(px(a), py(b)) for a, b in hi['pts']], '#ffffff', 6.5, 0.9)
    stroke([(px(a), py(b)) for a, b in hi['pts']], BLUE, 3.6)
    S.raw('</g>')
    S.rect(ox, oy, (wx1 - wx0) * k, (wy1 - wy0) * k, fill='none', stroke='#8e8e93', sw=1.2, rx=0)
    D.para(ox, oy + (wy1 - wy0) * k + 24, [f'파랑 = {num(WT)}: 벽에 가장 가까이 간 곳 {hi["clear"]:.2f}m, 길이 {hi["len"]:.2f}m', f'빨강 점선 = {num(WT_LOW)}: {lo["clear"]:.2f}m, 길이 {lo["len"]:.2f}m — 회색(충돌 구역) 가장자리를 스친다'],
           12, INK, 19.5)
    # 오른쪽: 식 · 버린 이유
    rx = 1000
    S.rect(rx, y + 96, 596, 142, fill=C['client'][1], stroke=BLUE, sw=1.2, rx=10)
    D.para(rx + 18, y + 122, ['한 칸 넓힐 때의 값 (A* 의 g · h 그대로, 칸 비용만 더했다)'], 12.5, BLUE, 20, 700)
    S.text(rx + 18, y + 150, f'g(이웃) = g(지금) + {num(P["w_euc_cost"])} × 거리 + {num(WT)} × (c ÷ 252)²', 12.5, 600, INK, mono=True)
    S.text(rx + 18, y + 174, f'h(이웃) = {num(P["w_heuristic_cost"])} × 목표까지 직선 거리', 12.5, 600, INK, mono=True)
    S.text(rx + 18, y + 198, 'f = g + h', 12.5, 600, INK, mono=True)
    S.text(rx + 130, y + 198, 'c = 26 + 0.9 × 그 칸의 비용 지도 값(0 ~ 252)', 12.5, 600, INK, mono=True)
    S.text(rx + 18, y + 222, '부모를 조부모로 바꿀 때는 직선이 지나는 칸들의 비용을 모두 더해 비교한다.', 11.5, 400, SUB)
    D.para(rx, y + 268, [
        f'왜 {num(WT_LOW)} 을 버렸나',
    ], 13.5, INK, 20, 700)
    D.para(rx, y + 292, [
        f'· {num(WT_LOW)} 이면 띠 안의 칸이 싸서 최단에 가깝게 모퉁이를 돈다 — 길은 짧다.',
        f'· 그러나 벽에서 {num(R)}m, 곧 로봇이 벽에 닿기 직전의 선이다. 제어기(MPPI)가',
        '  그 선을 따라가다 조금만 안쪽으로 밀리면 로봇 중심이 충돌 구역에 든다.',
        '· 그 자리에서는 계획이 "start or goal pose are an obstacle" 로 거부된다.',
        '  실제 시험에서 세 구간이 이렇게 실패했다.',
        f'· {num(WT)} 으로 올리면 모퉁이를 넓게 돈다. 길이는 조금 늘고 실패가 없어졌다.',
        '',
        '정리: 팽창 반경(0.45)은 "어디까지 비싼가", w_traversal_cost 는 "얼마나',
        '비싼가"다. 둘이 함께 벽 여유를 정한다.',
    ], 12, INK, 19.5)


# ------------------------------------------------------------------ 6. 설정 · 한계
def settings(y):
    D.card(y, 470, '6', '지금 설정값 · 언제 도는가 · 한계',
           'ros/sim/src/config/nav2_params.yaml 의 planner_server → GridBased 와 global_costmap. 굵은 값은 이 프로젝트에서 정한 것이다(이유는 그 파일 머리 2 · 6).', 'client')
    gl = G
    rows = [
        ('계획기', 'nav2_theta_star_planner', 'NavFn → Smac 2D → Theta*. 열린 곳에서 출렁이지 않는 직선 경로', True),
        ('이웃', f'how_many_corners {num(P["how_many_corners"])}', '한 칸에서 8방향으로 넓힌다(4 도 된다)', False),
        ('거리', f'w_euc_cost {num(P["w_euc_cost"])}', '거리에 곱하는 값. 기준(1)', False),
        ('벽 비용', f'w_traversal_cost {num(WT)}', '벽 가까운 칸을 얼마나 꺼리나(5번). 0.2 는 모퉁이를 스쳐 버림', True),
        ('짐작', f'w_heuristic_cost {num(P["w_heuristic_cost"])}', '목표까지 직선 거리에 곱하는 값. 1 이하여야 길이 나빠지지 않는다', False),
        ('모르는 곳', f'allow_unknown {num(P["allow_unknown"])}', '지도에 없는(미탐색) 칸도 지날 수 있는 칸으로 본다', False),
        ('지도 칸', f'global_costmap {num(RES)}m', '건물 전체. 저장 지도 + 라이다 + 가상 장애물 층', False),
        ('로봇 크기', f'robot_radius {num(R)}', '반지름 원. 벽에서 이 안은 못 가는 칸(충돌 구역)', False),
        ('비용 띠', f'inflation_radius {num(INFL)}', '1.0/0.55 → 0.45: 띠 밖은 비용 0 → 열린 곳이 직선', True),
        ('띠의 기울기', f'cost_scaling_factor {num(SCALE)}', '벽에서 멀어질 때 비용이 줄어드는 빠르기', True),
    ]
    x, yy = 44, y + 92
    for i, (a, b, c, changed) in enumerate(rows):
        ry = yy + i * 27
        S.text(x, ry, a, 12, 600, INK)
        S.text(x + 96, ry, b, 11.5, 700 if changed else 500, BLUE if changed else INK, mono=True)
        S.text(x + 330, ry, c, 11.8, 400, INK)
        S.raw(f'<line x1="{x}" y1="{ry + 9}" x2="{x + 850}" y2="{ry + 9}" stroke="#e5e5ea"/>')
    D.para(x, yy + len(rows) * 27 + 12, ['경로는 꺾이는 점 사이를 지도 칸 크기(0.05m) 간격의 점으로 채워서 내보낸다 — 제어기는 촘촘한 점의 줄을 받는다.'], 11.5, SUB)
    # 언제 도는가
    rx = 940
    S.text(rx, y + 88, '언제 도는가 — 목표마다 한 번', 13.5, 700, INK)
    D.para(rx, y + 112, [
        '행동 트리 navigate_fixed_plan.xml 이 처음 낸 경로를 끝까지 쓴다.',
        '다시 계획하는 때는 셋뿐이다:',
        '  ① 목표가 바뀌었다   ② 경로가 막혔다(새 장애물이 경로 위에)',
        '  ③ 제어기가 실패해 복구 동작을 한 뒤',
        '기본 트리는 1초마다 다시 계획해 달리는 중에 경로가 흔들렸다.',
    ], 12, INK, 19.5)
    S.rect(rx, y + 226, 656, 226, fill='#f7f7fa', stroke='#d1d1d6', rx=10)
    S.text(rx + 16, y + 250, 'Theta* 가 못 하는 것 — 그때 누가 맡나', 13.5, 700, INK)
    D.para(rx + 16, y + 274, [
        '· 로봇이 어느 쪽을 보는지, 얼마나 빨리 도는지는 모른다. 경로는 꺾은선이고',
        '  모퉁이는 각이 져 있다 → 제어기(MPPI)가 그 둘레를 둥글게 돌아 준다.',
        '· 로봇을 원으로만 본다. 폭 0.5m 이하 틈은 막힌 것으로, 0.6m 틈은 지날 수',
        '  있는 것으로 본다(실제로 지나는지는 제어기 몫 — nav_04_mppi.svg 5번).',
        '· 라이다가 못 본 것은 모른다. 새 장애물의 뒤쪽은 목표 브리지가 가상',
        '  장애물로 채워 준다(nav_02_drive_controller.svg 3번).',
        '· 꺾이는 점이 칸 중심이라 수학적 최단과 몇 cm 다를 수 있다.',
        '이어서 볼 그림: nav_04_mppi.svg(경로를 따라가는 법) · nav_01_drive_layers.svg(계획이 보는 지도).',
    ], 12, INK, 19.5)


def build():
    S.text(24, 46, 'Theta* 계획기 설명서', 26, 700)
    S.text(24, 72, 'A* 를 처음 보는 사람을 위한 그림 설명. 0 ~ 3 은 원리(A* → Theta*), 4 ~ 6 은 이 건물 · 지금 설정값에서의 결과다. '
                   '숫자는 nav2_params.yaml 에서 읽어 온다.', 13, 400, SUB)
    y = 92
    for fn, h in ((idea, 268), (astar, 640), (difference, 520), (compare, 652), (building, 720), (wallcost, 560), (settings, 470)):
        fn(y)
        y += h + 14
    S.h = y + 10
    S.render(OUT)


if __name__ == '__main__':
    build()
