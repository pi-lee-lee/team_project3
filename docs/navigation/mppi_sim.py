"""MPPI 한 주기를 그림용으로 옮긴 작은 계산(build_mppi.py 가 쓴다). Nav2 실행 기록이 아니다.

nav2_mppi_controller 의 순서 — 잡음 섞기 → 굴리기 → 평가 항목 점수 → 가중 평균 → 첫 명령 실행 → 한 칸 밀기 — 와
설정값(nav2_params.yaml 의 FollowPath)을 그대로 쓰되, 다음은 간단히 했다:
  - 비용 지도(격자) 대신 직사각형 장애물까지의 거리를 바로 잰다(로봇은 반지름 robot_radius 원).
  - 속도 열 다듬기(Savitzky-Golay)는 없고, 첫 칸에 지금 속도를 넣는 한 칸 밀림도 없다.
  - PathAlign 은 같은 거리만큼 간 경로 점이 아니라 가장 가까운 경로 점까지의 거리로 잰다.
식은 Nav2 Humble 의 nav2_mppi_controller(optimizer.cpp · critics/*.cpp)를 보고 옮겼다. 후보는 잡음을 더한 그대로 굴리고
(한계로 자르지 않는다 → ConstraintCritic · PreferForwardCritic 이 감점), 가중 평균한 답만 한계로 자른다.
"""
import math

import numpy as np

import build_drive_controller  # noqa: F401  (docs/_lib 를 경로에 넣는다)
import nav2cfg

CFG = nav2cfg.load()
CS = CFG['controller_server']['ros__parameters']
F = CS['FollowPath']
LOCAL = CFG['local_costmap']['local_costmap']['ros__parameters']
R = LOCAL['robot_radius']
N, DT, B = int(F['time_steps']), F['model_dt'], int(F['batch_size'])
STEP = 0.05                                  # 경로 점 간격(m) = 계획 맵 한 칸


def wrap(a):
    return (a + np.pi) % (2 * np.pi) - np.pi


def line_path(pts, step=STEP):
    """꺾은선을 step 간격 점으로."""
    out = []
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        n = max(1, round(math.hypot(x1 - x0, y1 - y0) / step))
        out += [(x0 + (x1 - x0) * i / n, y0 + (y1 - y0) * i / n) for i in range(n)]
    return np.array(out + [pts[-1]])


class Mppi:
    def __init__(self, path, rects, yaw=0.0, goal_yaw=0.0, seed=3):
        self.path, self.rects, self.goal_yaw = line_path(path), rects, goal_yaw
        self.state = np.array([path[0][0], path[0][1], yaw])
        self.U = np.zeros((N, 2))            # 기준 속도 열(지난 주기의 답): [vx, wz] × time_steps
        self.rng = np.random.default_rng(seed)
        self.trace = [self.state.copy()]

    def dist(self, p):
        """점(…, 2)에서 가장 가까운 장애물 면까지 거리."""
        d = np.full(p.shape[:-1], 9.0)
        for cx, cy, sx, sy in self.rects:
            dx = np.maximum(np.abs(p[..., 0] - cx) - sx / 2, 0)
            dy = np.maximum(np.abs(p[..., 1] - cy) - sy / 2, 0)
            d = np.minimum(d, np.hypot(dx, dy))
        return d

    def rollout(self, V):
        """속도 열(…, N, 2) → 궤적(…, N, 2), 방향(…, N). 두 바퀴(DiffDrive) 모델."""
        th = self.state[2] + np.cumsum(V[..., 1] * DT, axis=-1)
        prev = np.concatenate([np.full(th.shape[:-1] + (1,), self.state[2]), th[..., :-1]], axis=-1)
        x = self.state[0] + np.cumsum(V[..., 0] * np.cos(prev) * DT, axis=-1)
        y = self.state[1] + np.cumsum(V[..., 0] * np.sin(prev) * DT, axis=-1)
        return np.stack([x, y], axis=-1), th

    def score(self, T, th, V, noise):
        o = F['ObstaclesCritic']
        me = self.state[:2]
        i0 = int(np.argmin(np.linalg.norm(self.path - me, axis=1)))
        local = self.path[i0:i0 + int(F['prune_distance'] / STEP) + 1]      # 로봇 앞 prune_distance 까지만 본다
        goal = local[-1]
        gd = float(np.linalg.norm(goal - me))
        ends = T[:, -1]
        near = np.argmin(np.linalg.norm(ends[:, None] - local[None], axis=2), axis=1)
        far = int(near.max())                                               # 후보들이 가장 멀리 닿은 경로 점
        parts = {}

        d = self.dist(T)
        hit = (d < R).any(axis=1)
        edge = d - R                                                        # 로봇 가장자리에서 장애물까지
        crit = np.maximum(0, o['collision_margin_distance'] - edge).sum(axis=1)
        rep = np.where((d < o['inflation_radius']) & (edge >= o['collision_margin_distance']), o['inflation_radius'] - edge, 0).mean(axis=1)
        obs = o['critical_weight'] * crit + (o['repulsion_weight'] * rep if gd > o['near_goal_distance'] else 0)
        obs = np.where(hit, o['critical_weight'] * o['collision_cost'], obs)
        parts['ObstaclesCritic'] = obs

        a = F['PathAlignCritic']
        seg = local[:far + 1]
        bad = self.dist(local) < R                                          # 충돌 구역에 든 경로 점
        blocked = float(bad[:far + 1].mean())                               # 앞 경로가 덮인 비율
        on = gd > a['threshold_to_consider'] and far >= a['offset_from_furthest'] and not (
            blocked > a['max_path_occupancy_ratio'] and bad[:far + 1].sum() > 2)
        pts = T[:, ::int(a['trajectory_point_step'])]
        dd = np.linalg.norm(pts[:, :, None] - seg[None, None], axis=3).min(axis=2).mean(axis=1)
        parts['PathAlignCritic'] = a['cost_weight'] * dd if on else np.zeros(B)

        f = F['PathFollowCritic']
        ti = min(far + int(f['offset_from_furthest']), len(local) - 1)
        while bad[ti] and ti < len(local) - 2:                              # 덮인 점이면 그 너머 첫 빈 점을 겨눈다
            ti += 1
        tgt = local[ti]
        parts['PathFollowCritic'] = f['cost_weight'] * np.linalg.norm(ends - tgt, axis=1) if gd > f['threshold_to_consider'] else np.zeros(B)

        g = F['PathAngleCritic']
        tg = local[min(far + int(g['offset_from_furthest']), len(local) - 1)]
        off = abs(wrap(math.atan2(tg[1] - me[1], tg[0] - me[0]) - self.state[2]))
        if gd > g['threshold_to_consider'] and off > g['max_angle_to_furthest']:
            parts['PathAngleCritic'] = g['cost_weight'] * np.abs(wrap(np.arctan2(tg[1] - T[..., 1], tg[0] - T[..., 0]) - th)).mean(axis=1)
        else:
            parts['PathAngleCritic'] = np.zeros(B)

        c = F['GoalCritic']
        parts['GoalCritic'] = c['cost_weight'] * np.linalg.norm(T - goal, axis=2).mean(axis=1) if gd < c['threshold_to_consider'] else np.zeros(B)
        c = F['GoalAngleCritic']
        parts['GoalAngleCritic'] = c['cost_weight'] * np.abs(wrap(th - self.goal_yaw)).mean(axis=1) if gd < c['threshold_to_consider'] else np.zeros(B)

        v = V[..., 0]                                                       # 한계를 벗어난 만큼 · 뒤로 간 만큼(시간 합)
        parts['ConstraintCritic'] = F['ConstraintCritic']['cost_weight'] * (np.maximum(v - F['vx_max'], 0) + np.maximum(F['vx_min'] - v, 0)).sum(axis=1) * DT
        c = F['PreferForwardCritic']
        parts['PreferForwardCritic'] = c['cost_weight'] * np.maximum(-v, 0).sum(axis=1) * DT if gd > c['threshold_to_consider'] else np.zeros(B)

        ctrl = F['gamma'] * ((self.U[:, 0] * noise[..., 0]).sum(axis=1) / F['vx_std'] ** 2
                             + (self.U[:, 1] * noise[..., 1]).sum(axis=1) / F['wz_std'] ** 2)
        info = dict(hit=hit, far=far, align_on=on, blocked=blocked, goal_dist=gd, target=tgt, local=local)
        return sum(parts.values()) + ctrl, parts, info

    def step(self):
        """한 주기. 그림에 쓸 중간 값을 모두 돌려준다."""
        noise = self.rng.normal(0, [F['vx_std'], F['wz_std']], (B, N, 2))
        V = self.U + noise                                                  # 후보는 한계로 자르지 않는다
        T, th = self.rollout(V)
        costs, parts, info = self.score(T, th, V, noise)
        w = np.exp(-(costs - costs.min()) / F['temperature'])
        w /= w.sum()
        Unew = (w[:, None, None] * V).sum(axis=0)
        Unew[:, 0] = np.clip(Unew[:, 0], F['vx_min'], F['vx_max'])          # 답만 한계로 자른다
        Unew[:, 1] = np.clip(Unew[:, 1], -F['wz_max'], F['wz_max'])
        snap = dict(state=self.state.copy(), U=self.U.copy(), V=V, T=T, costs=costs, parts=parts, w=w, Unew=Unew,
                    nominal=self.rollout(self.U)[0], best=self.rollout(Unew)[0], **info)
        v, wz = Unew[0]
        x, y, yaw = self.state
        self.state = np.array([x + v * math.cos(yaw) * DT, y + v * math.sin(yaw) * DT, yaw + wz * DT])
        self.U = np.vstack([Unew[1:], Unew[-1:]])                          # 한 칸 밀어 다음 주기의 출발점으로
        self.trace.append(self.state.copy())
        snap['cmd'] = (float(v), float(wz))
        return snap

    def run(self, cycles, stop_x=None):
        snaps = []
        for _ in range(cycles):
            snaps.append(self.step())
            if stop_x is not None and self.state[0] >= stop_x:
                break
        return snaps


def box_gap(x, width, depth=0.3, span=1.4):
    """경로(y=0) 위에 폭 width 틈만 남기는 상자 둘."""
    h = (span - width) / 2
    return [(x, width / 2 + h / 2, depth, h), (x, -width / 2 - h / 2, depth, h)]


if __name__ == '__main__':                   # 모의 실험만 돌려 숫자로 본다
    scenes = {
        '직선': [],
        '상자': [(1.5, 0.17, 0.3, 0.3)],
        '틈0.7': box_gap(1.5, 0.7),
        '틈0.6': box_gap(1.5, 0.6),
    }
    for name, rects in scenes.items():
        m = Mppi([(0, 0), (3.2, 0)], rects)
        snaps = m.run(400, stop_x=2.6)
        tr = np.array(m.trace)
        vs = np.array([s['cmd'][0] for s in snaps])
        hits = [int(s['hit'].sum()) for s in snaps]
        print(f'{name}: {len(snaps) * DT:.1f}초, 끝 x={tr[-1, 0]:.2f}, 옆으로 최대 {np.abs(tr[:, 1]).max():.2f}m, '
              f'최대속도 유지 {(vs > 0.9 * F["vx_max"]).mean() * 100:.0f}%, 충돌 후보 최대 {max(hits)}/{B}, '
              f'장애물까지 최소 {m.dist(tr[:, :2]).min():.2f}m')
