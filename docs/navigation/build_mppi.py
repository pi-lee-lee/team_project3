"""MPPI 제어기 설명서(그림): MPPI 를 처음 보는 사람이 그림만 따라가도 "무엇을 하는 물건이고, 지금 설정으로 어떻게 도는지" 알게 한다.

값은 ros/sim/src/config/nav2_params.yaml 에서 읽어 쓴다(설정을 바꾸고 다시 생성하면 그림 · 숫자가 따라 바뀐다).
후보 궤적 그림은 mppi_sim.py 가 같은 순서 · 같은 설정값으로 계산한 것이다(Nav2 실행 기록이 아니다 — 간단히 한 점은 그 파일 머리).
실측값(최대속도 유지 등)은 drive_probe.py 로 잰 것으로 docs/guide/RUNNING.md 와 nav2_params.yaml 머리 5) · 9) 에서 가져왔다.
실행: python3 docs/navigation/build_mppi.py  →  docs/navigation/mppi.svg
"""
import math
from pathlib import Path

import numpy as np

import build_drive_controller as D        # docs/_lib 를 경로에 넣는다
import mppi_sim as M
from build_drive_controller import BLUE, GRAY, INK, ORANGE, PURPLE, RED, SUB
from nav2cfg import num
from svg import C, Svg

OUT = Path(__file__).resolve().parent / 'mppi.svg'
S = Svg(1640, 4000)
D.S = S                                   # 공용 그리기 함수(card · para · poly · robot · label)가 이 도면에 그리게 한다

GREEN, TEAL, PY = '#248a3d', '#30b0c7', C['py'][0]
F, R, N, DT, B = M.F, M.R, M.N, M.DT, M.B
HORIZON = N * DT                          # 3.0초
REACH = F['vx_max'] * HORIZON             # 0.66m
GLOBAL = M.CFG['global_costmap']['global_costmap']['ros__parameters']
SAMPLE = ['#248a3d', '#007aff', '#8944ab', '#e5352b']   # 후보 예시 4개(점수 좋은 순, 마지막은 충돌)
_clip = [0]


# ------------------------------------------------------------------ 모의 실험(그림에 쓸 장면)
def simulate(rects, cycles=300, seed=3):
    m = M.Mppi([(0, 0), (3.4, 0)], rects, seed=seed)
    snaps = m.run(cycles, stop_x=2.4)
    return m, snaps


BOX = [(1.5, 0.17, 0.3, 0.3)]             # 경로(y = 0)에 걸친 상자
SCENES = {
    'open': simulate([]),
    'box': simulate(BOX),
    'gap55': simulate(M.box_gap(1.5, 0.55)),
    'gap50': simulate(M.box_gap(1.5, 0.50)),
}


def snap_at(key, x):
    return next(s for s in SCENES[key][1] if s['state'][0] >= x)


SNAP = snap_at('box', 0.50)               # 1 · 2 · 4 번 그림이 함께 쓰는 한 주기


# ------------------------------------------------------------------ 그리기 도우미
def stage(x, y, w, h, x0, k, rects, path=(0, 3.4)):
    """장면 틀: 바닥 · 경로(파란 점선) · 장애물과 충돌 구역. 좌표 변환을 돌려준다. 다 그린 뒤 end_stage()."""
    _clip[0] += 1
    cid = f'st{_clip[0]}'
    S.rect(x, y, w, h, fill='#fbfbfd', stroke='#d1d1d6', rx=8)
    S.raw(f'<clipPath id="{cid}"><rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8"/></clipPath><g clip-path="url(#{cid})">')

    def fx(v):
        return x + (v - x0) * k

    def fy(v):
        return y + h / 2 - v * k
    for cx, cy, sx, sy in rects:          # 충돌 구역: 로봇 중심이 들어가면 닿는다(반지름만큼 부풀림)
        S.rect(fx(cx - sx / 2 - R), fy(cy + sy / 2 + R), (sx + 2 * R) * k, (sy + 2 * R) * k, fill='#fde8e6', stroke=RED, sw=1, rx=R * k, dash='4 3')
    for cx, cy, sx, sy in rects:
        S.rect(fx(cx - sx / 2), fy(cy + sy / 2), sx * k, sy * k, fill='#3a3a3c', stroke='none', sw=0, rx=2)
    D.poly([(fx(path[0]), fy(0)), (fx(path[1]), fy(0))], BLUE, 2.6, '0.1 7', late=False)
    return fx, fy


def end_stage():
    S.raw('</g>')


def traj_d(fx, fy, start, T, step=2):
    pts = [(fx(start[0]), fy(start[1]))] + [(fx(a), fy(b)) for a, b in T[step - 1::step]]
    return 'M' + ' L'.join(f'{a:.1f} {b:.1f}' for a, b in pts)


def stroke(d, color, sw=1.0, op=1.0):
    S.raw(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{sw}" stroke-linecap="round" stroke-linejoin="round" opacity="{op:.2f}"/>')


def pick(snap, n):
    """그릴 후보 n 개(1000개를 다 그리면 뭉개진다). 고르게 뽑는다."""
    return np.linspace(0, B - 1, n).astype(int)


def mix(c0, c1, t):
    a, b = [int(c0[i:i + 2], 16) for i in (1, 3, 5)], [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    return '#' + ''.join(f'{round(p + (q - p) * t):02x}' for p, q in zip(a, b))


def fan(fx, fy, snap, mode, n=70):
    """후보 궤적 다발. mode: plain(한 색) · cost(점수 색) · weight(가중치만큼 진하게) · hit(충돌만 구분)."""
    idx = pick(snap, n)
    ok = ~snap['hit']
    rank = np.argsort(np.argsort(snap['costs'])) / max(1, ok.sum() - 1)
    for i in idx:
        d = traj_d(fx, fy, snap['state'], snap['T'][i])
        if mode == 'plain':
            stroke(d, '#7d8fb3', 1.0, 0.55)
        elif snap['hit'][i]:
            stroke(d, RED, 1.0, 0.5 if mode != 'weight' else 0.12)
        elif mode == 'cost':
            stroke(d, mix('#1faa4b', '#c7c7cc', min(1.0, rank[i] * 1.6)), 1.2, 0.85)
        elif mode == 'hit':
            stroke(d, '#4aa56a', 1.0, 0.55)
        else:
            stroke(d, '#9a9aa2', 0.9, 0.3)
    if mode == 'weight':                  # 가중치가 큰 후보는 따로 진하게
        for i in np.argsort(snap['w'])[-25:]:
            stroke(traj_d(fx, fy, snap['state'], snap['T'][i]), GREEN, 1.4, min(0.95, 0.25 + snap['w'][i] * 12))


def ghost(fx, fy, snap, k):
    """로봇(속이 비치게): 후보 궤적은 로봇 중심에서 나오므로 몸에 가리지 않게 다발보다 먼저 그린다."""
    x, y, _ = snap['state']
    S.raw(f'<circle cx="{fx(x):.1f}" cy="{fy(y):.1f}" r="{R * k:.1f}" fill="#1c1c1e" fill-opacity=".10" stroke="#1c1c1e" stroke-width="1.6"/>')


def center(fx, fy, snap):
    x, y, _ = snap['state']
    S.raw(f'<circle cx="{fx(x):.1f}" cy="{fy(y):.1f}" r="4.5" fill="#1c1c1e" stroke="#ffffff" stroke-width="1.5"/>')


def arrow_right(x, y, color=GRAY):
    S.raw(f'<path d="M{x - 7} {y - 9} L{x + 7} {y} L{x - 7} {y + 9} z" fill="{color}"/>')


def legend(x, y, items):
    """items: (종류, 색, 글). 종류 line · dot · box · zone."""
    for kind, col, s in items:
        if kind == 'line':
            S.raw(f'<line x1="{x}" y1="{y - 4}" x2="{x + 22}" y2="{y - 4}" stroke="{col}" stroke-width="3" stroke-linecap="round"/>')
        elif kind == 'dots':
            S.raw(f'<line x1="{x}" y1="{y - 4}" x2="{x + 22}" y2="{y - 4}" stroke="{col}" stroke-width="2.6" stroke-linecap="round" stroke-dasharray="0.1 7"/>')
        elif kind == 'zone':
            S.rect(x, y - 11, 22, 14, fill='#fde8e6', stroke=col, sw=1, rx=4, dash='4 3')
        else:
            S.rect(x, y - 11, 22, 14, fill=col, stroke='none', sw=0, rx=3)
        S.text(x + 28, y, s, 11.5, 400, INK)
        x += 28 + sum(12.2 if ord(ch) > 0x1100 else 6.6 for ch in s) * 11.5 / 12 + 22


# ------------------------------------------------------------------ 0. 한 문장
def idea(y):
    D.card(y, 232, '0', 'MPPI 는 무엇인가', '경로(선)를 받아 바퀴에 줄 속도(전진 v, 회전 ω)를 0.1초마다 정하는 "제어기"다. 길을 찾는 것은 계획기(Theta*)의 일이다.', 'py')
    S.rect(40, y + 72, 900, 142, fill=C['py'][1], stroke=PY, sw=1.4, rx=12)
    D.para(60, y + 100, ['조금씩 다르게 모는 방법 1000가지를 머릿속에서 3초 앞까지 몰아 본다.'], 17, PY, 26, 700)
    D.para(60, y + 128, ['잘 간 것일수록 크게 쳐서 섞은 것이 이번 0.1초의 속도다. 0.1초 뒤 처음부터 다시 한다.'], 17, PY, 26, 700)
    D.para(60, y + 160, [
        '이름 그대로다 — Model Predictive(바퀴 모델로 앞날을 굴려 본다) + Path Integral(굴려 본 결과를 점수로 가중 평균한다).',
        '식을 풀어 "가장 좋은 하나"를 구하지 않는다. 많이 던져 보고 좋은 쪽으로 기운다. 그래서 장애물 같은 꺾인 조건도 점수로만 넣으면 된다.',
    ], 12.5, INK, 20)
    # 어디에 있나
    bx, by = 980, y + 86
    cols = [('계획기 Theta*', '목표마다 한 번', '경로 = 점을 이은 선', 'client'), ('제어기 MPPI', f'1초에 {num(M.CS["controller_frequency"])}번', '속도 명령 (v, ω)', 'py'),
            ('바퀴', 'TurtleBot3', f'최대 {num(F["vx_max"])} m/s', 'dev')]
    for i, (t, m, s, kind) in enumerate(cols):
        x = bx + i * 212
        D.box(x, by, 176, 74, t, [s], kind, mono=m)
        if i:
            S.line([(x - 34, by + 37), (x - 3, by + 37)], color=INK, sw=1.8)
    D.label(bx + 194, by + 28, '/plan', INK, 10, 'middle', 500)
    D.label(bx + 406, by + 28, '/cmd_vel', INK, 10, 'middle', 500)
    D.para(bx, by + 100, ['MPPI 가 보는 것: 경로 + 지역 비용 지도(로봇 둘레 3×3m, 라이다가 지금 본 장애물).',
                          '경로에 없는 새 장애물은 여기서만 보인다 → 다시 계획하지 않고도 비켜 간다.'], 12, SUB, 19)


# ------------------------------------------------------------------ 1. 한 주기
def cycle(y):
    D.card(y, 566, '1', f'한 주기({num(DT)}초)에 하는 일 — 네 걸음',
           '같은 순간을 네 번 그렸다. 로봇(회색 원, 가운데 점이 중심)은 파란 점선(경로)을 따라 오른쪽으로 가는 중이고, 경로에 걸친 상자를 비켜 가기 시작했다.', 'py')
    s = SNAP
    w, h, gap, k = 376, 264, 16, 262
    x0 = s['state'][0] - 0.28
    hits = int(s['hit'].sum())
    v, wz = s['cmd']
    steps = [
        ('①', '지난 주기의 답에서 시작', ['기준 = 지난번에 정한 속도 열(30칸)을 한 칸 당긴 것.', '검은 선은 기준대로만 몰면 3초 동안 갈 길이다.', '앞선 주기들에서 이미 아래로 휘기 시작한 답이다.']),
        ('②', f'잡음을 섞어 후보 {B}개', [f'기준의 칸마다 무작위 값을 더한다(표준편차:', f'전진 {num(F["vx_std"])} m/s · 회전 {num(F["wz_std"])} rad/s).', f'→ 조금씩 다른 속도 열 {B}개. 그림은 그중 70개.']),
        ('③', '3초 앞까지 굴려 보고 점수', ['후보마다 바퀴 모델로 갈 길을 그리고 점수를 낸다.', f'빨강 = 충돌 구역에 든 후보({hits}개) → 사실상 탈락.', '초록이 진할수록 점수가 좋다(낮다). 기준은 3번 그림.']),
        ('④', '좋은 쪽으로 가중 평균', ['점수가 좋을수록 큰 가중치로 속도 열을 평균한다.', f'주황 = 그 결과. 맨 앞 한 칸만 낸다: v {v:.2f} m/s,', f'ω {wz:+.2f} rad/s. 나머지는 다음 주기의 ① 이 된다.']),
    ]
    py = y + 104
    for i, (no, title, lines) in enumerate(steps):
        px = 44 + i * (w + gap)
        S.text(px, py - 12, f'{no} {title}', 14.5, 700, PY)
        fx, fy = stage(px, py, w, h, x0, k, BOX)
        ghost(fx, fy, s, k)
        if i == 0:
            stroke(traj_d(fx, fy, s['state'], s['nominal'], 1), INK, 3.2)
        elif i == 1:
            fan(fx, fy, s, 'plain')
            stroke(traj_d(fx, fy, s['state'], s['nominal'], 1), INK, 2.2, 0.9)
        elif i == 2:
            fan(fx, fy, s, 'cost')
        else:
            fan(fx, fy, s, 'weight')
            stroke(traj_d(fx, fy, s['state'], s['best'], 1), '#ffffff', 6.5, 0.9)
            stroke(traj_d(fx, fy, s['state'], s['best'], 1), ORANGE, 4)
        center(fx, fy, s)
        end_stage()
        D.para(px + 2, py + h + 22, lines, 12, INK, 18.5)
        if i < 3:
            arrow_right(px + w + gap / 2, py + h / 2, PY)
    # 치수 표시(① 에만): 3초 앞 = 0.66m, 로봇 반지름
    fx = lambda v_: 44 + (v_ - x0) * k   # noqa: E731
    yy = py + h - 20
    S.line([(fx(s['state'][0]), yy), (fx(s['state'][0] + REACH), yy)], color=SUB, sw=1.2, start=True)
    D.label(fx(s['state'][0] + REACH / 2), yy - 6, f'3초 동안 최대 {REACH:.2f}m', SUB, 10.5, 'middle', 600)
    D.label(44 + 3 * (w + gap) + w - 10, py + 20, f'충돌 후보의 가중치 = 0', RED, 10.5, 'end', 600)
    legend(44, py + h + 92, [('dots', BLUE, '경로(Theta*)'), ('box', '#3a3a3c', '상자(라이다가 본 것)'), ('zone', RED, f'충돌 구역: 상자에서 로봇 반지름 {num(R)}m 안 — 로봇 "중심"이 들어가면 닿는다'),
                             ('line', ORANGE, '이번 주기의 답')])
    S.rect(44, py + h + 112, 1552, 34, fill='#f7f7fa', stroke='#d1d1d6', rx=8)
    S.text(60, py + h + 134, f'↻  {num(DT)}초 뒤 로봇이 조금 움직인 자리에서 ① 부터 다시 한다(1초에 {num(M.CS["controller_frequency"])}번). 한 번에 완벽한 답을 내지 않아도, 주기마다 조금씩 고쳐 가며 상자를 비켜 간다 — 5번 그림.',
           12.5, 600, INK)


# ------------------------------------------------------------------ 2. 후보 = 속도 열
def chart(x, y, w, h, lo, hi, title, limits, nominal, samples, std):
    """속도 열 그림표: 가로 0 ~ 3초(30칸), 세로 속도."""
    def cx(i):
        return x + (i + 0.5) * w / N

    def cy(v):
        return y + h - (v - lo) / (hi - lo) * h
    S.text(x, y - 10, title, 12.5, 700, INK)
    S.rect(x, y, w, h, fill='#fbfbfd', stroke='#d1d1d6', rx=0)
    for i in range(1, N):
        S.raw(f'<line x1="{x + i * w / N:.1f}" y1="{y}" x2="{x + i * w / N:.1f}" y2="{y + h}" stroke="#ececf1"/>')
    band = [(cx(i), cy(min(hi, nominal[i] + std))) for i in range(N)] + [(cx(i), cy(max(lo, nominal[i] - std))) for i in reversed(range(N))]
    S.raw('<path d="M' + ' L'.join(f'{a:.1f} {b:.1f}' for a, b in band) + f' z" fill="{PY}" opacity=".13"/>')
    for v, s in zip(limits, ('최소', '최대')):
        S.raw(f'<line x1="{x}" y1="{cy(v):.1f}" x2="{x + w}" y2="{cy(v):.1f}" stroke="{RED}" stroke-width="1.2" stroke-dasharray="5 4"/>')
        S.text(x + w + 6, cy(v) + 4, f'{s} {num(v)}', 10.5, 500, RED)
    if lo < 0 < hi and 0 not in limits:
        S.raw(f'<line x1="{x}" y1="{cy(0):.1f}" x2="{x + w}" y2="{cy(0):.1f}" stroke="#8e8e93" stroke-width=".8"/>')
        S.text(x - 6, cy(0) + 4, '0', 10.5, 500, SUB, 'end')
    for col, ser in samples:
        stroke('M' + ' L'.join(f'{cx(i):.1f} {cy(min(hi, max(lo, v))):.1f}' for i, v in enumerate(ser)), col, 1.3, 0.85)
    stroke('M' + ' L'.join(f'{cx(i):.1f} {cy(v):.1f}' for i, v in enumerate(nominal)), INK, 2.8)
    for t in (0, 1, 2, 3):
        S.text(x + t * w / 3, y + h + 15, f'{t}초', 10.5, 500, SUB, 'middle')


def sequence(y):
    D.card(y, 492, '2', '후보 하나는 "속도 열"이다',
           f'후보는 길(좌표)이 아니라 앞으로 {num(HORIZON)}초 동안 {num(DT)}초마다 낼 속도 {N}칸이다(time_steps {N} × model_dt {num(DT)}). 길은 그 속도대로 몰았을 때 나오는 결과다.', 'py')
    s = SNAP
    order = np.argsort(s['costs'])
    ids = [int(order[0]), int(order[B // 3]), int(order[int((~s['hit']).sum()) - 5]), int(np.flatnonzero(s['hit'])[3])]
    cw, ch, cx0 = 500, 128, 60
    chart(cx0, y + 104, cw, ch, -0.3, 0.7, '전진 속도 v (m/s)', (F['vx_min'], F['vx_max']), s['U'][:, 0], [(c, s['V'][i][:, 0]) for c, i in zip(SAMPLE, ids)], F['vx_std'])
    chart(cx0, y + 288, cw, ch, -1.4, 1.4, '회전 속도 ω (rad/s, + 가 왼쪽)', (-F['wz_max'], F['wz_max']), s['U'][:, 1], [(c, s['V'][i][:, 1]) for c, i in zip(SAMPLE, ids)], F['wz_std'])
    D.para(cx0, y + 450, ['검은 굵은 선 = 기준 · 옅은 띠 = 잡음의 표준편차 · 가는 색 선 = 후보 4개', '빨간 점선 = 한계. 후보는 넘을 수 있고(넘은 만큼 감점) 마지막 답만 잘라 낸다.'], 11.5, SUB, 18)
    # 가운데: 같은 후보 5개를 길로
    arrow_right(652, y + 250, PY)
    mx, my, mw, mh, k = 680, y + 104, 372, 312, 300
    S.text(mx, my - 10, '같은 후보 4개를 바퀴 모델로 굴린 길', 12.5, 700, INK)
    fx, fy = stage(mx, my, mw, mh, s['state'][0] - 0.3, k, BOX)
    ghost(fx, fy, s, k)
    for c, i in zip(SAMPLE, ids):
        stroke(traj_d(fx, fy, s['state'], s['T'][i], 1), c, 2.2, 0.95)
    center(fx, fy, s)
    end_stage()
    D.label(mx + mw - 8, my + mh - 10, '초록 = 점수 1등 · 빨강 = 충돌 구역에 든다', RED, 10.5, 'end', 600)
    D.para(mx, y + 450, [f'바퀴 모델(DiffDrive): 0.1초마다 "v 만큼 앞으로,', f'ω 만큼 돌기"를 {N}번 잇는다. 옆걸음(vy)은 없다.'], 11.5, SUB, 18)
    # 오른쪽: 얼마나 멀리 보나
    rx, ry, k = 1100, y + 104, 262
    S.text(rx, ry - 10, '얼마나 멀리 보나 (같은 축척)', 12.5, 700, INK)
    S.rect(rx, ry, 496, 312, fill='#fbfbfd', stroke='#d1d1d6', rx=8)
    ox, oy = rx + 80, ry + 150
    half = LOCAL_W / 2
    for dist, col, lab, dy in [(half, PY, f'지역 비용 지도 끝 {num(half)}m', 126), (F['prune_distance'], BLUE, f'경로를 보는 거리 {num(F["prune_distance"])}m', 100),
                               (REACH, ORANGE, f'3초 동안 닿는 곳 {REACH:.2f}m', 74)]:
        S.raw(f'<line x1="{ox + dist * k:.1f}" y1="{oy - dy}" x2="{ox + dist * k:.1f}" y2="{oy + 40}" stroke="{col}" stroke-width="1.6" stroke-dasharray="5 4"/>')
        S.text(ox + dist * k - 6, oy - dy + 10, lab, 11, 600, col, 'end')
    D.poly([(ox, oy), (ox + half * k, oy)], BLUE, 2.6, '0.1 7', late=False)
    S.raw(f'<path d="M{ox} {oy} L{ox + REACH * k * math.cos(0.5):.1f} {oy - REACH * k * math.sin(0.5):.1f} A{REACH * k:.1f} {REACH * k:.1f} 0 0 1 '
          f'{ox + REACH * k * math.cos(0.5):.1f} {oy + REACH * k * math.sin(0.5):.1f} z" fill="{ORANGE}" opacity=".16"/>')
    D.robot(ox, oy, R * k, 0, late=False)
    S.line([(ox, oy + 84), (ox + R * k, oy + 84)], color=SUB, sw=1.2, start=True)
    S.text(ox + R * k / 2, oy + 100, f'반지름 {num(R)}m', 10.5, 500, SUB, 'middle')
    D.para(rx + 14, ry + 270, [f'{num(F["vx_max"])} m/s × {num(HORIZON)}초 = {REACH:.2f}m. 로봇 몸 지름의 1.5배만큼만 내다본다.',
                               '멀리 있는 일은 경로(계획기)가, 코앞의 일은 MPPI 가 맡는다.'], 11.5, INK, 18)


LOCAL_W = M.LOCAL['width']


# ------------------------------------------------------------------ 3. 평가 항목
def pic_align(x, y):
    D.poly([(x + 8, y + 70), (x + 122, y + 70)], BLUE, 2.4, '0.1 6', late=False)
    pts = [(x + 14, y + 70), (x + 40, y + 60), (x + 68, y + 46), (x + 96, y + 38), (x + 118, y + 34)]
    D.poly(pts, GREEN, 2.4, late=False)
    for px_, py_ in pts[1:]:
        S.raw(f'<line x1="{px_}" y1="{py_}" x2="{px_}" y2="{y + 70}" stroke="{RED}" stroke-width="1.3"/>')


def pic_follow(x, y):
    D.poly([(x + 8, y + 70), (x + 122, y + 70)], BLUE, 2.4, '0.1 6', late=False)
    D.poly([(x + 14, y + 70), (x + 40, y + 66), (x + 62, y + 56)], '#9a9aa2', 2.2, late=False)
    D.poly([(x + 14, y + 70), (x + 50, y + 68), (x + 92, y + 64)], GREEN, 2.4, late=False)
    S.raw(f'<circle cx="{x + 112}" cy="{y + 70}" r="6" fill="#ffffff" stroke="{BLUE}" stroke-width="2.4"/>')
    S.raw(f'<line x1="{x + 62}" y1="{y + 56}" x2="{x + 108}" y2="{y + 67}" stroke="{RED}" stroke-width="1.3" stroke-dasharray="3 3"/>')
    S.raw(f'<line x1="{x + 92}" y1="{y + 64}" x2="{x + 106}" y2="{y + 68}" stroke="{RED}" stroke-width="1.6"/>')


def pic_angle(x, y):
    D.poly([(x + 8, y + 78), (x + 122, y + 78)], BLUE, 2.4, '0.1 6', late=False)
    S.raw(f'<circle cx="{x + 104}" cy="{y + 78}" r="6" fill="#ffffff" stroke="{BLUE}" stroke-width="2.4"/>')
    S.raw(f'<line x1="{x + 36}" y1="{y + 56}" x2="{x + 98}" y2="{y + 76}" stroke="{SUB}" stroke-width="1.1" stroke-dasharray="3 3"/>')
    S.raw(f'<path d="M{x + 62} {y + 64} A28 28 0 0 0 {x + 46} {y + 30}" fill="none" stroke="{RED}" stroke-width="2"/>')
    D.robot(x + 36, y + 56, 15, -110, late=False)


def pic_obst(x, y):
    S.rect(x + 46, y + 10, 76, 56, fill='#fff1e8', stroke='none', sw=0, rx=22)
    S.rect(x + 56, y + 18, 56, 40, fill='#fde8e6', stroke=RED, sw=1, rx=14, dash='4 3')
    S.rect(x + 70, y + 28, 28, 20, fill='#3a3a3c', stroke='none', sw=0, rx=2)
    D.poly([(x + 10, y + 86), (x + 44, y + 70), (x + 74, y + 52)], RED, 2.2, late=False)
    D.poly([(x + 10, y + 86), (x + 44, y + 76), (x + 84, y + 68), (x + 120, y + 62)], ORANGE, 2.2, late=False)
    D.poly([(x + 10, y + 86), (x + 50, y + 84), (x + 90, y + 82), (x + 124, y + 80)], GREEN, 2.2, late=False)
    S.text(x + 74, y + 49, '✕', 13, 700, RED, 'middle')


def pic_goal(x, y):
    S.raw(f'<circle cx="{x + 100}" cy="{y + 50}" r="34" fill="#e9f7ee" stroke="{GREEN}" stroke-width="1" stroke-dasharray="4 3"/>')
    S.raw(f'<circle cx="{x + 100}" cy="{y + 50}" r="6" fill="#ffffff" stroke="{TEAL}" stroke-width="3"/>')
    pts = [(x + 12, y + 78), (x + 38, y + 70), (x + 62, y + 60), (x + 82, y + 54)]
    D.poly(pts, GREEN, 2.4, late=False)
    for px_, py_ in pts[1:]:
        S.raw(f'<line x1="{px_}" y1="{py_}" x2="{x + 100}" y2="{y + 50}" stroke="{RED}" stroke-width="1" stroke-dasharray="3 3"/>')


def pic_goal_angle(x, y):
    S.raw(f'<circle cx="{x + 64}" cy="{y + 52}" r="30" fill="#e9f7ee" stroke="{GREEN}" stroke-width="1" stroke-dasharray="4 3"/>')
    D.robot(x + 64, y + 52, 15, 0, late=False)
    S.line([(x + 64, y + 52), (x + 64, y + 6)], color=TEAL, sw=2.2, late=False)
    S.raw(f'<path d="M{x + 92} {y + 52} A28 28 0 0 0 {x + 72} {y + 25}" fill="none" stroke="{RED}" stroke-width="2"/>')
    S.text(x + 70, y + 16, '도착 방향', 10, 600, TEAL)


def pic_forward(x, y):
    D.robot(x + 66, y + 50, 15, 0, late=False)
    S.line([(x + 86, y + 50), (x + 122, y + 50)], color=GREEN, sw=2.4, late=False)
    S.line([(x + 46, y + 50), (x + 12, y + 50)], color=GRAY, sw=2.4, late=False)
    S.text(x + 28, y + 43, '✕', 13, 700, RED, 'middle')


def pic_limit(x, y):
    S.rect(x + 10, y + 42, 110, 14, fill='#e9f7ee', stroke=GREEN, sw=1, rx=3)
    S.rect(x + 96, y + 42, 24, 14, fill='#fde8e6', stroke=RED, sw=1, rx=3)
    S.raw(f'<line x1="{x + 96}" y1="{y + 34}" x2="{x + 96}" y2="{y + 64}" stroke="{RED}" stroke-width="2"/>')
    S.text(x + 10, y + 76, '0', 10, 500, SUB)
    S.text(x + 96, y + 76, f'{num(F["vx_max"])} m/s', 10, 600, RED, 'middle')
    S.text(x + 10, y + 32, '속도', 10, 500, SUB)


def critics(y):
    D.card(y, 596, '3', '점수는 여덟 가지 "평가 항목(critic)"의 합이다',
           '항목마다 후보 궤적을 보고 감점을 낸다(낮을수록 좋다). 감점 × 가중치를 모두 더한 것이 그 후보의 점수다. 가중치가 곧 "무엇을 더 중히 여기나"다.', 'py')
    o = F['ObstaclesCritic']

    def th(n):
        return num(F[n]['threshold_to_consider'])
    items = [
        ('PathAlignCritic', '경로에 붙어 가기', BLUE, pic_align, F['PathAlignCritic']['cost_weight'],
         ['궤적의 점들이 경로에서 떨어진 거리(빨간 선)의 평균.', f'켜짐: 목표까지 {th("PathAlignCritic")}m 넘게 남았을 때.',
          f'앞 경로가 장애물에 {num(F["PathAlignCritic"]["max_path_occupancy_ratio"] * 100)}% 넘게 덮이면 꺼진다', '→ 그때는 경로를 벗어나 비켜 갈 수 있다.']),
        ('PathFollowCritic', '앞으로 나아가기', BLUE, pic_follow, F['PathFollowCritic']['cost_weight'],
         ['궤적의 끝이 "경로 위 앞쪽 점"에서 먼 거리.', '멀리 간 후보(초록)가 덜 간 후보(회색)보다 유리', '→ 속도를 내게 하는 항목이다.', f'켜짐: 목표까지 {th("PathFollowCritic")}m 넘게 남았을 때.']),
        ('PathAngleCritic', '경로 쪽을 보기', BLUE, pic_angle, F['PathAngleCritic']['cost_weight'],
         [f'경로 앞쪽 점이 정면에서 {num(F["PathAngleCritic"]["max_angle_to_furthest"])}rad(57°) 넘게', '틀어져 있을 때만 켜진다. 그쪽으로 도는 후보가', '유리 → 출발할 때 제자리에서 먼저 돈다.',
          f'켜짐: 목표까지 {th("PathAngleCritic")}m 넘게 남았을 때.']),
        ('ObstaclesCritic', '부딪히지 않기', RED, pic_obst, o['critical_weight'],
         [f'빨강: 충돌 구역에 닿음 → {num(o["collision_cost"])}점 × {num(o["critical_weight"])}(탈락).', f'주황: {num(o["collision_margin_distance"])}m 안으로 스침 → ×{num(o["critical_weight"])}.',
          f'초록: 팽창 띠({num(o["inflation_radius"])}m) 안 → 가까울수록 ×{num(o["repulsion_weight"])}', f'(밀어내기. 목표 {num(o["near_goal_distance"])}m 안에서는 끈다).']),
        ('GoalCritic', '목표로 모이기', GREEN, pic_goal, F['GoalCritic']['cost_weight'],
         ['궤적의 점들이 목표에서 떨어진 거리의 평균.', f'켜짐: 목표 {th("GoalCritic")}m 안(점선 원)에 들어왔을 때.', '이때부터 "경로 따라가기" 대신 이 항목이', '로봇을 목표 점으로 끌어당긴다.']),
        ('GoalAngleCritic', '도착 방향 맞추기', GREEN, pic_goal_angle, F['GoalAngleCritic']['cost_weight'],
         ['로봇 방향과 도착 방향의 차이.', f'켜짐: 목표 {th("GoalAngleCritic")}m 안 — 자리를 다 잡은 뒤에만.', '(0.4 였을 때는 옆으로 0.2m 남기고 돌아서 버려', '도착하지 못했다. 그래서 줄였다.)']),
        ('PreferForwardCritic', '후진보다 전진', GRAY, pic_forward, F['PreferForwardCritic']['cost_weight'],
         ['후보 안에서 뒤로 가는 구간(v < 0)만큼 감점.', '잡음 때문에 후보에는 후진 구간이 섞인다.', f'마지막 답은 vx_min {num(F["vx_min"])} 으로 잘리므로 후진 명령은', '나가지 않는다(카메라가 앞을 본다).']),
        ('ConstraintCritic', '속도 한계 지키기', GRAY, pic_limit, F['ConstraintCritic']['cost_weight'],
         [f'전진 속도가 한계({num(F["vx_min"])} ~ {num(F["vx_max"])} m/s)를 벗어난 만큼 감점.', '후보는 잡음을 더한 그대로라 한계를 넘는다', '→ 넘는 후보를 불리하게 해 답이 한계 안에 머문다.', f'마지막 답은 한계로 자른다(회전 ±{num(F["wz_max"])} rad/s 도).']),
    ]
    w, h, gap = 376, 222, 16
    for i, (name, ko, col, pic, wt, lines) in enumerate(items):
        x, yy = 44 + (i % 4) * (w + gap), y + 78 + (i // 4) * (h + 14)
        S.rect(x, yy, w, h, fill='#ffffff', stroke='#d1d1d6', rx=10)
        S.rect(x, yy, w, 5, fill=col, stroke='none', sw=0, rx=2)
        S.rect(x + 12, yy + 18, 132, 96, fill='#fbfbfd', stroke='#e5e5ea', rx=8)
        pic(x + 12, yy + 18)
        S.text(x + 158, yy + 36, ko, 14.5, 700, col if col != GRAY else SUB)
        S.text(x + 158, yy + 54, name, 11, 500, SUB, mono=True)
        S.text(x + 158, yy + 80, '가중치', 11, 500, SUB)
        S.rect(x + 200, yy + 70, 120, 12, fill='#f2f2f7', stroke='none', sw=0, rx=6)
        S.rect(x + 200, yy + 70, max(6, 120 * wt / 20), 12, fill=col, stroke='none', sw=0, rx=6)
        S.text(x + 328, yy + 81, num(wt), 13, 700, INK)
        if name == 'ObstaclesCritic':
            S.text(x + 158, yy + 102, f'스침 {num(wt)} · 밀어내기 {num(o["repulsion_weight"])}', 11, 500, SUB)
        D.para(x + 14, yy + 138, lines, 11.8, INK, 18.5)
    D.para(44, y + 558, ['읽는 법: 경로에 붙기(14) > 나아가기(10) > 목표 · 전진(5) > 방향(2~3). 충돌은 가중치가 아니라 "탈락"이다.',
                         '밀어내기(0.5)는 일부러 약하게 두었다 — 세면 좁은 틈에 들어가느니 서 있는 쪽이 점수가 좋아진다.'], 12, SUB, 19)


# ------------------------------------------------------------------ 4. 가중 평균
def weights(y):
    T = F['temperature']
    D.card(y, 420, '4', '점수를 가중치로 바꾸기 — temperature',
           '1등 하나만 고르지 않는다. 점수가 가장 좋은 후보와의 차이가 작을수록 큰 가중치를 주어 모두 평균한다. 얼마나 1등에 쏠리게 할지가 temperature 다.', 'py')
    s = SNAP
    order = np.argsort(s['costs'])
    ok = int((~s['hit']).sum())
    cum = np.cumsum(s['w'][order])
    n90 = int(np.searchsorted(cum, 0.9)) + 1
    show = min(ok, 450)
    x0, y0, bw = 60, y + 108, 1.9
    S.text(x0, y0 - 12, f'1번 그림의 후보 {B}개를 점수 순으로 세운 것(앞 {show}개)', 12.5, 700, INK)
    dc = s['costs'][order[:show]] - s['costs'][order[0]]
    hmax = 96
    for i in range(show):
        S.rect(x0 + i * bw, y0 + hmax - dc[i] / dc[-1] * hmax, bw - 0.4, max(0.5, dc[i] / dc[-1] * hmax), fill='#c7c7cc', stroke='none', sw=0, rx=0)
        wv = s['w'][order[i]] / s['w'][order[0]]
        S.rect(x0 + i * bw, y0 + 136 + hmax - wv * hmax, bw - 0.4, max(0.5, wv * hmax), fill=GREEN, stroke='none', sw=0, rx=0, opacity=0.35 + 0.65 * wv)
    S.text(x0 + show * bw, y0 - 12, f'회색 = 1등과의 점수 차이 ({show}등: {dc[-1]:.2f}점)', 11.5, 600, SUB, 'end')
    S.text(x0 + show * bw, y0 + 124, '초록 = 가중치 (1등 = 1)', 11.5, 600, GREEN, 'end')
    S.raw(f'<line x1="{x0}" y1="{y0 + hmax + 0.5}" x2="{x0 + show * bw}" y2="{y0 + hmax + 0.5}" stroke="#8e8e93"/>')
    S.raw(f'<line x1="{x0}" y1="{y0 + 136 + hmax + 0.5}" x2="{x0 + show * bw}" y2="{y0 + 136 + hmax + 0.5}" stroke="#8e8e93"/>')
    S.text(x0, y0 + 136 + hmax + 16, '1등', 10.5, 500, SUB)
    S.text(x0 + show * bw, y0 + 136 + hmax + 16, f'{show}등', 10.5, 500, SUB, 'end')
    if n90 <= show:
        bx = x0 + n90 * bw
        S.raw(f'<line x1="{bx:.1f}" y1="{y0 + 128}" x2="{bx:.1f}" y2="{y0 + 136 + hmax + 6}" stroke="{INK}" stroke-width="1.2" stroke-dasharray="4 3"/>')
        D.label(bx - 6, y0 + 150, f'앞 {n90}개가 가중치의 90% →', INK, 11, 'end', 600)
    D.para(x0, y0 + 136 + hmax + 44, [f'{B}개 중 충돌 {B - ok}개는 가중치 0. 남은 {ok}개 가운데 앞 {n90}개가 답의 90% 를 정한다. 나머지는 거의 반영되지 않는다.'], 12, INK)
    # 오른쪽: 곡선
    gx, gy, gw, gh = 980, y + 108, 330, 200
    S.text(gx, gy - 12, '가중치 = exp( −(점수 − 1등 점수) ÷ temperature )', 12.5, 700, INK)
    S.rect(gx, gy, gw, gh, fill='#fbfbfd', stroke='#d1d1d6', rx=0)
    dmax = 1.5
    for tt, col, sw_, lab in [(0.1, GRAY, 1.6, '0.1'), (1.0, GRAY, 1.6, '1.0'), (T, PY, 3.2, f'{num(T)} (지금)')]:
        pts = [(gx + d / dmax * gw, gy + gh - math.exp(-d / tt) * gh) for d in np.linspace(0, dmax, 60)]
        stroke('M' + ' L'.join(f'{a:.1f} {b:.1f}' for a, b in pts), col, sw_)
        d = {0.1: 0.12, 1.0: 0.9}.get(tt, 0.42)
        D.label(gx + d / dmax * gw + 8, gy + gh - math.exp(-d / tt) * gh - 6, lab, col if col != GRAY else SUB, 11.5, 'start', 700)
    for d in (0, 0.5, 1.0, 1.5):
        S.text(gx + d / dmax * gw, gy + gh + 15, f'{d:g}', 10.5, 500, SUB, 'middle')
    S.text(gx + gw / 2, gy + gh + 32, '1등과의 점수 차이', 11, 500, SUB, 'middle')
    S.text(gx - 6, gy + 8, '1', 10.5, 500, SUB, 'end')
    S.text(gx - 6, gy + gh, '0', 10.5, 500, SUB, 'end')
    ex = F['PathAlignCritic']['cost_weight']
    D.para(gx + gw + 24, gy + 16, [
        '점수 차이가 temperature 만큼이면',
        '가중치는 0.37배(= 1/e)가 된다.',
        '',
        f'{num(T)}점은 얼마인가:',
        f'경로에서 평균 {T / ex * 100:.0f}cm 더 벗어난 후보',
        f'(붙어 가기 {num(ex)} × {T / ex:.3f}m ≈ {num(T)}점).',
        '',
        '작게(0.1): 1등만 따른다 — 날카롭지만',
        '주기마다 답이 튀어 덜컹거린다.',
        '크게(1.0): 고루 섞는다 — 부드럽지만',
        '나쁜 후보까지 섞여 둔해진다.',
    ], 11.8, INK, 18)
    D.para(gx, gy + gh + 58, [f'gamma {num(F["gamma"])}: 기준에서 멀리 벗어난 속도 열에 아주 작은 감점(답이 급히 바뀌지 않게).  iteration_count {num(F["iteration_count"])}: 한 주기에 이 과정을 한 번만 한다.'],
           11.5, SUB)


# ------------------------------------------------------------------ 5. 상황별
def spark(x, y, w, snaps, total):
    """전진 속도 명령의 시간 변화(모의)."""
    h = 34
    S.rect(x, y, w, h, fill='#ffffff', stroke='#e5e5ea', rx=0)
    vs = [s['cmd'][0] for s in snaps]
    pts = [(x + i / total * w, y + h - v / F['vx_max'] * (h - 4) - 1) for i, v in enumerate(vs)]
    S.raw('<path d="M' + f'{x} {y + h} L' + ' L'.join(f'{a:.1f} {b:.1f}' for a, b in pts) + f' L{pts[-1][0]:.1f} {y + h} z" fill="{PY}" opacity=".18"/>')
    stroke('M' + ' L'.join(f'{a:.1f} {b:.1f}' for a, b in pts), PY, 1.6)
    S.raw(f'<line x1="{pts[-1][0]:.1f}" y1="{y}" x2="{pts[-1][0]:.1f}" y2="{y + h}" stroke="{INK}" stroke-width="1.2"/>')
    S.text(pts[-1][0] + 5, y + 13, f'{len(vs) * DT:.0f}초', 11, 700, INK)


def scenes(y):
    D.card(y, 880, '5', '상황별로 실제로 어떻게 움직이나',
           '같은 설정값으로 네 상황을 처음부터 끝까지 돌린 것이다(모의 계산). 주황 굵은 선 = 로봇 중심이 지나간 자리, 점선 원 = 그때의 로봇, 가는 다발 = 그 순간의 후보(초록: 살아남음 · 빨강: 탈락), 회색 원 = 끝난 자리.', 'py')
    w, h, k = 760, 250, 262
    total = max(len(v[1]) for v in SCENES.values())
    defs = [
        ('open', 'A  막힌 것이 없는 직선', [], (0.5, 1.6),
         ['후보가 경로 좌우로 고르게 퍼지고, 평균은 경로 위에 놓인다.', '붙어 가기(14)와 나아가기(10)만 일한다 → 곧게, 멈춤 없이 간다.']),
        ('box', 'B  달리는 길에 상자가 놓였다 (다시 계획하지 않음)', BOX, (0.45, 1.1),
         ['상자 쪽 후보는 충돌로 탈락 → 살아남은 아래쪽 후보들의 평균으로 방향이 기운다. 속도는 줄지 않는다.', '경로가 충돌 구역에 덮여 "붙어 가기"가 꺼지고, "나아가기"는 상자 너머의 경로 점을 겨눈다. 지나면 경로로 돌아온다.']),
        ('gap55', 'C  폭 0.6m 틈 — 지역 비용 지도 0.025m (지금)', M.box_gap(1.5, 0.55), (0.6, 1.2),
         ['로봇 중심이 지날 띠는 0.16m. 칸 어긋남으로 양쪽 한 칸씩 잃어도 0.11m 가 남는다.', '(그 최악의 경우를 그렸다.) 탈락이 많아도 띠 안의 후보가 충분해 멈추지 않는다.']),
        ('gap50', 'D  같은 틈 — 지역 비용 지도 0.05m (전)', M.box_gap(1.5, 0.50), (0.6, 1.15),
         ['칸이 커서 같은 어긋남에 띠가 0.06m(한 칸)로 준다. 후보 대부분이 탈락하고', '살아남는 것은 틈에 못 미쳐 멈추는 후보뿐 → 틈 앞에서 선다. 실제로도 15~31초 멈칫하거나 실패했다.']),
    ]
    for i, (key, title, rects, moments, lines) in enumerate(defs):
        m, snaps = SCENES[key]
        x, yy = 44 + (i % 2) * (w + 32), y + 104 + (i // 2) * 394
        S.text(x, yy - 12, title, 14, 700, PY)
        fx, fy = stage(x, yy, w, h, -0.25, k, rects)
        tr = np.array(m.trace)                # 끝난 자리의 로봇(다발에 가리지 않게 먼저, 속이 비치게)
        S.raw(f'<circle cx="{fx(tr[-1, 0]):.1f}" cy="{fy(tr[-1, 1]):.1f}" r="{R * k:.1f}" fill="#1c1c1e" fill-opacity=".14" stroke="#1c1c1e" stroke-width="1.8"/>')
        peak = 0
        for mx in moments:
            s = snap_at(key, mx)
            peak = max(peak, int(s['hit'].sum()))
            fan(fx, fy, s, 'hit', 46)
            S.raw(f'<circle cx="{fx(s["state"][0]):.1f}" cy="{fy(s["state"][1]):.1f}" r="{R * k:.1f}" fill="none" stroke="{INK}" stroke-width="1.2" stroke-dasharray="4 3"/>')
        d = 'M' + ' L'.join(f'{fx(a):.1f} {fy(b):.1f}' for a, b in tr[::3, :2])
        stroke(d, '#ffffff', 6.5, 0.9)
        stroke(d, ORANGE, 3.6)
        S.raw(f'<circle cx="{fx(tr[-1, 0]):.1f}" cy="{fy(tr[-1, 1]):.1f}" r="5" fill="#1c1c1e" stroke="#ffffff" stroke-width="1.5"/>')
        end_stage()
        worst = max(int(s['hit'].sum()) for s in snaps)
        stop = sum(1 for s in snaps if s['cmd'][0] < 0.03) * DT
        S.rect(x + w - 232, yy + 8, 224, 44, fill='#ffffff', stroke='#d1d1d6', rx=8, opacity=0.94)
        S.text(x + w - 220, yy + 26, f'충돌로 탈락한 후보: 최대 {worst} / {B}', 11.5, 600, INK)
        S.text(x + w - 220, yy + 44, f'멈춰 선 시간: {stop:.1f}초' if stop >= 0.5 else '멈춰 선 시간: 없음', 11.5, 600, RED if stop >= 0.5 else GREEN)
        S.text(x, yy + h + 20, '전진 속도 명령', 10.5, 600, SUB)
        spark(x + 86, yy + h + 6, w - 130, snaps, total)
        D.para(x, yy + h + 62, lines, 12, INK, 19)
    D.para(44, y + 866, ['모의 계산은 격자 없이 거리로 충돌을 보므로, 칸 어긋남은 틈을 그만큼 좁혀 흉내 냈다(C 0.55m · D 0.50m). D 는 30초에서 끊었다. 가속 한계 · 위치 추정 오차가 없어 실제보다 매끄럽다 — 실측은 7번 표.'], 11.5, SUB)


# ------------------------------------------------------------------ 6. 도착 구간
def arrival(y):
    D.card(y, 372, '6', '목표에 가까워지면 평가 항목이 바뀐다',
           '항목마다 "목표까지 남은 거리"로 켜지고 꺼진다(threshold_to_consider). 달릴 때는 경로를, 다 와서는 목표 점을, 마지막에 방향을 본다.', 'py')
    x0, x1, yy = 300, 1180, y + 96
    dmax = 1.2

    def px(d):
        return x1 - d / dmax * (x1 - x0)
    o = F['ObstaclesCritic']
    gc = M.CS['general_goal_checker']
    rows = [
        ('나아가기 PathFollow', BLUE, F['PathFollowCritic']['threshold_to_consider'], dmax),
        ('경로에 붙기 PathAlign', BLUE, F['PathAlignCritic']['threshold_to_consider'], dmax),
        ('경로 쪽 보기 PathAngle', BLUE, F['PathAngleCritic']['threshold_to_consider'], dmax),
        ('장애물 밀어내기', RED, o['near_goal_distance'], dmax),
        ('충돌 탈락 (항상)', RED, 0, dmax),
        ('목표로 모이기 Goal', GREEN, 0, F['GoalCritic']['threshold_to_consider']),
        ('도착 방향 GoalAngle', GREEN, 0, F['GoalAngleCritic']['threshold_to_consider']),
    ]
    marks = sorted({F['PathFollowCritic']['threshold_to_consider'], F['PathAlignCritic']['threshold_to_consider'], F['GoalAngleCritic']['threshold_to_consider']})
    for d in marks:
        S.raw(f'<line x1="{px(d):.1f}" y1="{yy - 8}" x2="{px(d):.1f}" y2="{yy + len(rows) * 28 + 4}" stroke="#8e8e93" stroke-dasharray="4 3"/>')
        S.text(px(d), yy + len(rows) * 28 + 20, f'{num(d)}m', 11.5, 700, INK, 'middle')
    for i, (name, col, a, b) in enumerate(rows):
        ry = yy + i * 28
        S.text(x0 - 14, ry + 15, name, 12, 600, col, 'end')
        S.rect(x0, ry + 2, x1 - x0, 18, fill='#f2f2f7', stroke='none', sw=0, rx=9)
        S.rect(px(b), ry + 2, px(a) - px(b), 18, fill=col, stroke='none', sw=0, rx=9, opacity=0.85)
    by = yy + len(rows) * 28 + 20
    S.text(x0, by, '← 멀다', 11, 500, SUB)
    S.text(px(0), by, '목표', 11.5, 700, TEAL, 'middle')
    S.raw(f'<circle cx="{px(0):.1f}" cy="{yy - 14}" r="7" fill="#ffffff" stroke="{TEAL}" stroke-width="3"/>')
    D.robot(px(1.0), yy - 16, 10, 0, late=False)
    S.line([(px(1.0) + 16, yy - 16), (px(0.86), yy - 16)], color=INK, sw=1.6, late=False)
    S.text(x0 + (x1 - x0) / 2, by + 24, '목표까지 남은 거리', 11, 500, SUB, 'middle')
    D.para(1220, yy + 6, [
        f'① {num(F["PathFollowCritic"]["threshold_to_consider"])}m 밖: 경로를 따라 달린다.',
        f'② {num(F["GoalCritic"]["threshold_to_consider"])}m 안: 목표 점이 끌어당긴다.',
        f'③ {num(F["PathAlignCritic"]["threshold_to_consider"])}m 안: 경로 항목이 모두 꺼지고,',
        '    벽이 밀어내는 점수도 꺼진다(벽 앞',
        '    촬영 자리까지 들어가야 하므로).',
        f'④ {num(F["GoalAngleCritic"]["threshold_to_consider"])}m 안: 제자리에서 방향을 맞춘다.',
        f'⑤ 위치 {num(gc["xy_goal_tolerance"])}m · 방향 {num(gc["yaw_goal_tolerance"])}rad 안이면',
        '    도착(goal checker). 한 번 위치가',
        '    맞으면 방향만 더 본다(stateful).',
    ], 12, INK, 19.5)
    D.para(44, y + 354, [f'이 거리들은 기본값(최대 0.5 m/s, 1.4m 앞을 보는 로봇 기준)을 이 로봇의 예측 거리 {REACH:.2f}m 에 맞춰 줄인 것이다. "목표"는 로봇 앞 {num(F["prune_distance"])}m 까지 자른 경로의 끝이므로, 진짜 목표가 그 안에 들어와야 ② 가 시작된다.'],
           11.5, SUB)


# ------------------------------------------------------------------ 7. 설정값 · 실측
def settings(y):
    D.card(y, 600, '7', '지금 설정값과 실제로 잰 결과',
           'ros/sim/src/config/nav2_params.yaml 의 controller_server → FollowPath. 굵은 값은 Nav2 기본값에서 바꾼 것이다(이유는 그 파일 머리 5 · 9).', 'py')
    lc = M.LOCAL
    rows = [
        ('주기', f'controller_frequency {num(M.CS["controller_frequency"])} · model_dt {num(DT)}', '1초에 10번 다시 정한다. 둘은 같은 값이어야 한다', False),
        ('내다보기', f'time_steps {N}', f'{num(HORIZON)}초 = 최대 {REACH:.2f}m 앞', False),
        ('후보 수', f'batch_size {B}', '많을수록 좁은 곳에서 살아남는 후보가 늘지만 계산도 는다', False),
        ('잡음', f'vx_std {num(F["vx_std"])} · wz_std {num(F["wz_std"])}', '후보가 퍼지는 폭. 전진 0.1 → 0.15 (속도 쪽을 더 찾게). 회전 0.3 은 굽은 길에서 멈칫해 버림', True),
        ('속도 한계', f'vx {num(F["vx_min"])} ~ {num(F["vx_max"])} · wz ±{num(F["wz_max"])}', '로봇 최대 속도. 후진 없음(카메라가 앞을 본다). 마지막 답을 이 범위로 자른다', True),
        ('섞는 정도', f'temperature {num(F["temperature"])} · gamma {num(F["gamma"])}', '4번 그림', False),
        ('경로 보는 거리', f'prune_distance {num(F["prune_distance"])}', '로봇 앞 이만큼의 경로만 평가에 쓴다', True),
        ('나아가기', f'PathFollowCritic {num(F["PathFollowCritic"]["cost_weight"])}', '5 → 10: 전진을 우선한다', True),
        ('붙어 가기', f'PathAlignCritic {num(F["PathAlignCritic"]["cost_weight"])}', '유지. 10 으로 낮추면 굽은 곳 안쪽을 깎아 벽에 붙었다', False),
        ('밀어내기', f'repulsion_weight {num(F["ObstaclesCritic"]["repulsion_weight"])}', '1.5 → 0.5: 세면 틈에 들어가느니 서 있는 쪽이 점수가 좋았다', True),
        ('도착 방향', f'GoalAngle threshold {num(F["GoalAngleCritic"]["threshold_to_consider"])}', '0.4 → 0.15: 자리를 다 잡은 뒤에 돈다', True),
        ('보는 지도', f'local_costmap {num(lc["resolution"])}m · {num(lc["width"])}×{num(lc["height"])}m', f'0.05 → 0.025: 좁은 틈(5번 C · D). 팽창 {num(lc["inflation_layer"]["inflation_radius"])}m, 로봇 = 반지름 {num(R)}m 원', True),
    ]
    x, yy = 44, y + 92
    for i, (a, b, c, changed) in enumerate(rows):
        ry = yy + i * 27
        S.text(x, ry, a, 12, 600, INK)
        S.text(x + 104, ry, b, 11.5, 700 if changed else 500, PY if changed else INK, mono=True)
        S.text(x + 400, ry, c, 11.8, 400, INK)
        S.raw(f'<line x1="{x}" y1="{ry + 9}" x2="{x + 950}" y2="{ry + 9}" stroke="#e5e5ea"/>')
    # 실측
    tx, ty = 1040, y + 84
    S.text(tx, ty, '실제로 잰 값 (시뮬레이션, drive_probe.py)', 13.5, 700, INK)
    S.text(tx, ty + 20, '최대속도 유지 = 전진 명령이 최대의 90% 이상이던 시간 비율 / 걸린 시간', 11, 400, SUB)
    head = ('시험', '이전 제어기(RPP)', 'MPPI')
    meas = [
        ('직선 3m', '60~77% / 16~20초', '84~90% / 15~17초'),
        ('굽은 길 8m', '50~52% / 48~49초', '89~93% / 38~39초'),
        ('폭 0.7m 틈', '36~41% / 20초', '80~90% / 16~17초'),
        ('폭 0.6m 틈 (칸 0.05m)', '36~38% / 21초', '멈칫(51초) 또는 실패'),
        ('폭 0.6m 틈 (칸 0.025m)', '—', '92% / 25초 (P1→P3)'),
        ('1.6m 앞에 놓인 팔레트', '28% / 23초', '46% / 30초'),
    ]
    cx = (tx, tx + 190, tx + 360)
    for j, s in enumerate(head):
        S.text(cx[j], ty + 50, s, 11.5, 700, SUB)
    for i, row in enumerate(meas):
        ry = ty + 76 + i * 26
        S.raw(f'<line x1="{tx}" y1="{ry - 17}" x2="{tx + 556}" y2="{ry - 17}" stroke="#e5e5ea"/>')
        for j, s in enumerate(row):
            bad = '멈칫' in s
            S.text(cx[j], ry, s, 11.8, 600 if j == 2 else 400, RED if bad else (PY if j == 2 else INK))
    ny = ty + 76 + len(meas) * 26 + 10
    D.para(tx, ny, [
        '· 3m 구간은 출발 가속 · 도착 감속 · 제자리 회전이 10~15% 를 차지한다.',
        '· 팔레트는 남는 폭 0.65m. 비켜 가느라 느려진 것이고 다시 계획을 기다리지는 않았다.',
    ], 11.5, SUB, 18)
    # 한계
    S.rect(44, y + 432, 1552, 150, fill='#f7f7fa', stroke='#d1d1d6', rx=10)
    S.text(60, y + 456, 'MPPI 가 못 하는 것 — 그때 누가 맡나', 13.5, 700, INK)
    D.para(60, y + 480, [
        f'· 3초({REACH:.2f}m) 앞까지만 본다. 막다른 길 · 먼 우회는 알 수 없다 → 후보가 모두 탈락하면 제어기가 실패를 내고, 행동 트리가 복구 뒤 Theta* 로 다시 계획한다.',
        '· 후보가 무작위라 띠가 아주 좁으면 살아남는 후보가 없다. 같은 자리에서 3번 실패하면 목표 브리지가 물러나 자세를 다시 잡는다(폭 0.5m 이하 틈은 계획이 막힌 것으로 본다).',
        f'· {num(M.CS["progress_checker"]["movement_time_allowance"])}초 동안 {num(M.CS["progress_checker"]["required_movement_radius"])}m 를 못 가면 "전진 없음"으로 실패 처리된다(progress checker) — 서서 버티는 것을 끊는 장치다.',
        '· 로봇을 원(반지름 0.22m)으로 본다. 실제 외곽 사각형으로 바꾸면 0.55m 틈도 지났지만 0.9m 문에서 벽에 끼어 버렸다(계획과 제어는 같은 모양을 써야 한다).',
        '이어서 볼 그림: theta_star.svg(경로는 어떻게 만드나) · drive_controller.svg(막혔을 때의 순서) · drive_layers.svg(MPPI 가 보는 지도).',
    ], 12, INK, 20)


def build():
    S.text(24, 46, 'MPPI 제어기 설명서', 26, 700)
    S.text(24, 72, 'MPPI 를 처음 보는 사람을 위한 그림 설명. 0 ~ 4 는 원리, 5 ~ 7 은 이 로봇(TurtleBot3 Waffle Pi, Nav2 Humble)의 지금 설정값으로 어떻게 도는지다. '
                   '숫자는 nav2_params.yaml 에서 읽어 온다.', 13, 400, SUB)
    y = 92
    for fn, h in ((idea, 232), (cycle, 566), (sequence, 492), (critics, 596), (weights, 420), (scenes, 880), (arrival, 372), (settings, 600)):
        fn(y)
        y += h + 14
    S.h = y + 10
    S.render(OUT)


if __name__ == '__main__':
    build()
