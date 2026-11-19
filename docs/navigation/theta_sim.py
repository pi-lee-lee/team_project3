"""A* · Theta* 를 그림용으로 옮긴 계산(build_theta_star.py 가 쓴다). Nav2 실행 기록이 아니다.

Theta* 는 Nav2 Humble 의 nav2_theta_star_planner(theta_star.cpp · theta_star.hpp)를 보고 옮겼다:
  - 칸을 넓히는 방식은 A* 와 같다: g(이웃) = g(지금) + w_euc × 거리 + 칸 비용, f = g + w_heuristic × 목표까지 직선 거리.
  - 다른 점 하나: 칸을 꺼낼 때 "부모의 부모"가 보이면(시야 확인) 그쪽으로 부모를 바꾼다(resetParent).
  - 칸 비용 = w_traversal × c² / 252², c = 26 + 0.9 × 비용 지도 값. 비용 지도 값이 252 를 넘는 칸(충돌 구역 · 장애물)은 못 간다.
mode 'astar' 는 부모 바꾸기만 뺀 것, 'dijkstra' 는 거기서 h 까지 뺀 것이다 — 같은 조건에서 차이만 보려고.

시야 확인은 두 가지다. los() 는 Nav2 의 losCheck 그대로다(칸 모서리 기준이라 벽 칸의 가장자리 한 줄을 스칠 수 있다.
팽창된 비용 지도에서는 0.05m 차이라 문제가 없다). los_strict() 는 칸 중심을 이은 선이 닿는 칸을 모두 본다 —
벽이 한 칸 단위인 예시 격자 그림에서 선이 벽 칸을 지나지 않게 하려고 쓴다(strict=True. 이때는 목표 칸에도 부모 바꾸기를 한다).
"""
import heapq
import math

import numpy as np

MAX_OK = 252                                 # 이 값까지 지날 수 있다(253 = 충돌 구역, 254 = 장애물)
MOVES = [(0, 1), (0, -1), (-1, 0), (1, 0), (1, -1), (-1, 1), (1, 1), (-1, -1)]


def cell_cost(v, w_trav):
    c = 26 + 0.9 * v
    return w_trav * c * c / MAX_OK / MAX_OK


def los(cost, a, b, w_trav):
    """a → b 가 서로 보이는가(지나는 칸이 모두 통행 가능). (보임, 지나는 칸 비용 합)을 돌려준다. losCheck 를 옮긴 것."""
    (x0, y0), (x1, y1) = a, b
    dy, dx, f = abs(y1 - y0), abs(x1 - x0), 0
    sx, sy = (1 if x1 > x0 else -1), (1 if y1 > y0 else -1)
    ux, uy = (sx - 1) // 2, (sy - 1) // 2
    cx, cy, tot = x0, y0, 0.0

    def safe(x, y):
        nonlocal tot
        v = cost[y][x]
        if v > MAX_OK:
            return False
        tot += cell_cost(v, w_trav)
        return True
    if dx >= dy:
        while cx != x1:
            f += dy
            if f >= dx:
                if not safe(cx + ux, cy + uy):
                    return False, 0
                cy += sy
                f -= dx
            if f != 0 and not safe(cx + ux, cy + uy):
                return False, 0
            if dy == 0 and not safe(cx + ux, cy) and not safe(cx + ux, cy - 1):
                return False, 0
            cx += sx
    else:
        while cy != y1:
            f += dx
            if f >= dy:
                if not safe(cx + ux, cy + uy):
                    return False, 0
                cx += sx
                f -= dy
            if f != 0 and not safe(cx + ux, cy + uy):
                return False, 0
            if dx == 0 and not safe(cx, cy + uy) and not safe(cx - 1, cy + uy):
                return False, 0
            cy += sy
    return True, tot


def los_strict(cost, a, b, w_trav):
    """칸 중심 a → b 를 이은 선이 닿는 칸이 모두 통행 가능한가. (보임, 지나는 칸 비용 합)."""
    (x0, y0), (x1, y1) = a, b
    n = 8 * max(abs(x1 - x0), abs(y1 - y0), 1)
    seen, tot = set(), 0.0
    for i in range(n + 1):
        x, y = x0 + (x1 - x0) * i / n, y0 + (y1 - y0) * i / n
        for c in {(math.floor(x + 0.5 - 1e-6), math.floor(y + 0.5 - 1e-6)), (math.floor(x + 0.5 + 1e-6), math.floor(y + 0.5 + 1e-6))}:
            if c in seen:
                continue
            seen.add(c)
            v = cost[c[1]][c[0]]
            if v > MAX_OK:
                return False, 0
            tot += cell_cost(v, w_trav)
    return True, tot


def plan(cost, start, goal, mode='theta', w_euc=1.0, w_trav=0.0, w_h=1.0, strict=False):
    """cost[y][x] (0 ~ 254). 돌려주는 것: dict(path 꺾이는 점들, parent, order 꺼낸 순서, g) 또는 None."""
    h, w = len(cost), len(cost[0])
    g = {start: cell_cost(cost[start[1]][start[0]], w_trav)}
    parent = {start: start}
    order, closed = [], set()
    n = 0
    heap = [(0.0, 0, start)]
    while heap:
        _, _, cur = heapq.heappop(heap)
        if cur in closed:
            continue
        closed.add(cur)
        order.append(cur)
        if cur == goal and not strict:       # Nav2 는 목표 칸을 꺼내면 바로 끝낸다(마지막 한 칸이 꺾여 남을 수 있다)
            break
        if mode == 'theta':                  # 부모의 부모가 보이면 그쪽으로 잇는다
            gp = parent[parent[cur]]
            ok, lc = (los_strict if strict else los)(cost, cur, gp, w_trav)
            if ok:
                g2 = g[gp] + w_euc * math.hypot(cur[0] - gp[0], cur[1] - gp[1]) + lc
                if g2 < g[cur]:
                    g[cur], parent[cur] = g2, gp
        if cur == goal:                      # strict(예시 그림): 목표 칸도 부모를 바꿔 본 뒤 끝낸다
            break
        for mx, my in MOVES:
            nb = (cur[0] + mx, cur[1] + my)
            if not (0 <= nb[0] < w and 0 <= nb[1] < h) or cost[nb[1]][nb[0]] > MAX_OK or nb in closed:
                continue
            g2 = g[cur] + w_euc * math.hypot(mx, my) + cell_cost(cost[nb[1]][nb[0]], w_trav)
            if g2 < g.get(nb, 1e18):
                g[nb], parent[nb] = g2, cur
                hh = 0.0 if mode == 'dijkstra' else w_h * math.hypot(nb[0] - goal[0], nb[1] - goal[1])
                n += 1
                heapq.heappush(heap, (g2 + hh, n, nb))
    if goal not in closed:
        return None
    path = [goal]
    while parent[path[-1]] != path[-1]:
        path.append(parent[path[-1]])
    path.reverse()
    return dict(path=simplify(path), raw=path, parent=parent, order=order, g=g)


def simplify(path):
    """한 직선 위에 있는 가운데 점을 뺀다 → 꺾이는 점만 남는다."""
    out = [path[0]]
    for a, b in zip(path[1:], path[2:]):
        p = out[-1]
        if (a[0] - p[0]) * (b[1] - a[1]) != (a[1] - p[1]) * (b[0] - a[0]):
            out.append(a)
    return out + [path[-1]]


def length(path):
    return sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(path, path[1:]))


def turning(path):
    """꺾인 각도의 합(도)."""
    tot = 0.0
    for a, b, c in zip(path, path[1:], path[2:]):
        d = math.atan2(c[1] - b[1], c[0] - b[0]) - math.atan2(b[1] - a[1], b[0] - a[0])
        tot += abs(math.degrees((d + math.pi) % (2 * math.pi) - math.pi))
    return tot


def costmap(rects, x0, y0, x1, y1, res, radius, inflation, scaling):
    """직사각형 장애물 → 비용 지도(전역 비용 지도의 팽창 층과 같은 식). 행 0 이 y0 쪽이다. (비용, 장애물까지 거리)."""
    xs = x0 + (np.arange(round((x1 - x0) / res)) + 0.5) * res
    ys = y0 + (np.arange(round((y1 - y0) / res)) + 0.5) * res
    X, Y = np.meshgrid(xs, ys)
    d = np.full(X.shape, 9.0)
    for cx, cy, sx, sy in rects:
        d = np.minimum(d, np.hypot(np.maximum(np.abs(X - cx) - sx / 2, 0), np.maximum(np.abs(Y - cy) - sy / 2, 0)))
    c = np.where(d <= 0, 254, np.where(d <= radius, 253, np.where(d <= inflation, np.floor(252 * np.exp(-scaling * (d - radius))), 0)))
    return c.astype(int), d
