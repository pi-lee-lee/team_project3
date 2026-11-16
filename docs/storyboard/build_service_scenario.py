"""가상 서비스 흐름 스토리보드 SVG 생성기.

신희초안 00 회의 요약의 시나리오를 장면(Scene) 단위로 그린다:
  관리자가 확인할 지점을 요청 → 로봇이 방문해 사진과 기록을 가져옴 → 담당자가 확인 결과·추가 점검 필요를 남김
  → 모의 이상 신고가 들어오면 해당 지점을 다시 확인.
배경(장소)은 아직 정하지 않았으므로 '가상 시설'의 예시이고, 지점·좌표는 시뮬레이션 월드와 같다.
실행: python3 build_service_scenario.py  →  docs/web_service_scenario.svg
"""
from pathlib import Path

import sys

import build_screen_tree as tree
import build_storyboard as sb

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'ros' / 'sim' / 'src' / 'worlds'))
import world_spec as W_  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / 'web_service_scenario.svg'
W = 1840
CARD_W, CARD_H = 580, 372
VIS_SCALE = 0.5
VIS_W, VIS_H = 560 * VIS_SCALE, 366 * VIS_SCALE

ACTOR = {  # 이름, 색
    'user': ('사용자 (역할 1·2·3)', sb.C['user']),
    'admin': ('웹 admin', sb.C['admin']),
    'server': ('웹·서버', sb.C['blue']),
    'robot': ('로봇', sb.C['orange']),
}
LANES = ['user', 'admin', 'server', 'robot']


def scr(base, name=None, wire=None, nav=None):
    """기존 화면 정의를 바탕으로 장면에 맞는 내용을 넣은 화면."""
    s = dict(tree.BY_ID.get(base) or tree.EXTRA[base])
    if name:
        s['name'] = name
    if wire is not None:
        s['wire'] = wire
    if nav is not None:
        s['nav'] = nav
    return s


TL = lambda items: ('timeline', 10, 40, 250, items)  # noqa: E731

SCENES = [
    dict(no='S0', title='준비: 지점·로봇 확인', actors=['admin'],
         v1=scr('A3'), v2=('screen', scr('A2')),
         situation='웹 admin 이 점검할 지점 3곳(소화기 앞·비상구 앞·분전반 앞)의 위치와 촬영 방향을 등록하고, 로봇 연결과 제공 기능(odom·scan·camera)을 확인한다.',
         actions=['지점 좌표·방향 저장 (inspection-service)', '로봇 연결 상태·제공 기능 확인 (robot-service)'],
         records='지점 등록 · 감사 로그(POST /api/admin/points)'),
    dict(no='S1', title='점검 요청', actors=['user', 'server'],
         v1=scr('U2'), v2=('map', dict(robot=(0, 0, 0), order=True)),
         situation='퇴근 전 정기 점검. 사용자가 로봇과 지점 순서(P1 → P2 → P3)를 골라 점검을 요청한다.',
         actions=['작업 #21 생성 → 로봇 서비스에 미션 전달', '같은 작업 ID 는 다시 와도 한 번만 실행 (중복 명령 처리)'],
         records='REQUESTED (사용자) · ACCEPTED (로봇)'),
    dict(no='S2', title='출발 전 검사 → 출발', actors=['robot', 'server'],
         v1=scr('U4', '작업 상세', [('label', 10, 30, '작업 #21 · tb3-sim · 진행 중'),
                                   TL(['요청됨 (사용자)', '로봇 접수', '출발 전 검사 통과', 'P1 이동 시작']),
                                   ('obs', 270, 40, 260, 200)]),
         v2=('map', dict(robot=(2.2, -0.1, 0), path=[(0, 0), (2.2, -0.1), (4.7, -0.1), (4.7, 1.2), (4.3, 3.6)])),
         situation='로봇이 위치(odom)·카메라 수신을 확인한 뒤 출발한다. 검사에 실패하면 지점마다 "확인 불가: 출발 전 검사 실패"가 남는다.',
         actions=['로봇 쪽 목표 실행 노드가 주행 (서버는 목표 지점만 보냄)', '진행 단계가 작업 상세에 실시간 표시'],
         records='PREFLIGHT_OK · STARTED · MOVING(P1)'),
    dict(no='S3', title='P1 도착·촬영', actors=['robot'],
         v1=scr('U1'), v2=('map', dict(robot=(4.3, 3.9, 3.14), done=['P1'], path=[(0, 0), (2.2, -0.1), (4.7, -0.1), (4.7, 1.2), (4.3, 3.6)])),
         situation='P1 에 도착해 소화기 쪽을 촬영한다. 사용자는 관제 화면에서 실시간 영상을 볼 수 있다(점검 중에는 조종 불가).',
         actions=['도착 후 1.5초 정지 → 스냅샷 촬영', '사진은 먼저 로봇 서비스에 보관한 뒤 전송'],
         records='ARRIVED · OBSERVATION_SAVED + 사진 · 품질 분석 "양호"'),
    dict(no='S4', title='P2: 우회 시도 후 진입 불가', actors=['robot', 'server'],
         v1=scr('U4', '작업 상세', [('label', 10, 30, '작업 #21 · 진행 중'),
                                   TL(['P1 촬영 저장', 'P2 이동 시작 (C1 팔레트 우회)', 'C2 적재물 → 생산동 쪽 재계획',
                                       '진입 불가: 경로 없음', 'P2 확인 불가 저장', 'P3 이동 시작'])]),
         v2=('map', dict(robot=(7.55, 4.4, 1.57), done=['P1'], failed=['P2'], obstacles=['detour', 'block'],
                         path=[(4.3, 3.9), (4.7, 1.2), (4.7, 0.1), (5.6, 0.25), (6.8, -0.1), (7.55, 0.3), (7.55, 4.6)],
                         path2=[(7.55, 4.6), (6.6, 4.1), (6.6, 6.0)])),
         situation='C1 복도의 팔레트는 옆으로 비켜 지나간다(우회). C2 복도 위쪽이 적재물로 막혀 생산동 쪽 경로도 다시 계산하지만, 비상구 앞으로 가는 길이 모두 막혀 있다.',
         actions=['일시 장애물은 기다리고, 돌아갈 수 있으면 우회 (로봇 측 Nav2)',
                  '재계획·복구 동작을 다 써도 경로가 없을 때만 "진입 불가: 경로 없음"'],
         records='ARRIVAL_BLOCKED · 확인 불가(사유 코드 BLOCKED_NO_PATH = 통로 막힘)'),
    dict(no='S5', title='P3 촬영 → 재촬영 후보', actors=['robot', 'server'],
         v1=scr('U4', '작업 상세', [('label', 10, 30, 'P3 분전반 앞 · 18:12 촬영'),
                                   ('video', 10, 40, 300, 200, '어두운 사진'),
                                   ('label', 322, 70, '품질 분석'),
                                   ('note', 322, 92, '밝기 48 · 선명도 61', 'sub', 'start'),
                                   ('note', 322, 112, '→ 재촬영 후보', 'orange', 'start'),
                                   ('note', 322, 132, '(너무 어두움, 흐림)', 'orange', 'start')]),
         v2=('log', ['analysis-service 작업 큐', '1. inspection 이 분석 요청', '2. 워커가 사진을 받아', '   ROI 밝기·선명도 계산',
                     '3. 기준(A4) 밖 → RETAKE', '4. 결과를 작업 상세에 표시']),
         situation='분전반 앞 조명이 꺼져 사진이 어둡다. 분석 서비스가 관리자가 정한 기준(A4) 밖으로 판단해 "재촬영 후보"로 표시한다.',
         actions=['미션 완료: 촬영 2 · 확인 불가 1', '분석은 배치로 처리, 결과는 원래 관측에 연결'],
         records='COMPLETED · 분석 결과(밝기·선명도·판정·적용 기준)'),
    dict(no='S6', title='담당자 판정', actors=['user'],
         v1=scr('U4-1', '관측 판정 입력'),
         v2=('log', ['판정 결과', 'P1  정상', 'P2  확인 불가', '    "C2 복도 적재물, 통로 막힘"', 'P3  확인 불가',
                     '    "조명 꺼짐, 재촬영 필요"']),
         situation='사용자가 사진과 품질 결과를 보고 지점별로 판정한다. 확인 불가는 사유를 반드시 적는다.',
         actions=['판정은 덮어쓰지 않고 이력으로 쌓인다', '누가 언제 판정했는지 함께 남는다'],
         records='REVIEWED × 3 · 판정 이력'),
    dict(no='S7', title='모의 이상 신고 → 재점검 요청', actors=['user', 'server'],
         v1=scr('U4', '작업 상세', [('label', 10, 30, '작업 #21 · 완료'),
                                   ('card', 10, 44, 520, 54, '모의 이상 신고 (야간 경비)', '분전반 부근에서 탄 냄새가 난다'),
                                   ('label', 10, 124, 'P3 분전반 앞 · 확인 불가 (조명 꺼짐)'),
                                   ('btn', 10, 134, 160, 28, '↺ 재점검 요청', 'blue'),
                                   ('label', 10, 192, 'P2 비상구 앞 · 진입 불가 (통로 막힘)'),
                                   ('btn', 10, 202, 160, 28, '↺ 재점검 요청', 'blue')]),
         v2=('map', dict(robot=(0.3, 4.6, 3.14), done=['P1'], failed=['P2', 'P3'], recheck=['P3', 'P2'], obstacles=['block'])),
         situation='모의 이상 신고가 들어온다. 사용자가 조명을 켜게 한 뒤 P3 재점검을, 적재물을 치운 뒤 P2 재점검을 요청한다.',
         actions=['재점검 작업 #22·#23 생성', '새 작업은 원래 관측(#57·#58)과 연결'],
         records='REQUESTED (recheckOf = 원래 관측 ID)'),
    dict(no='S8', title='재점검 결과·이상 판정', actors=['user', 'robot'],
         v1=scr('U5', '지점 이력', [('input', 10, 40, 200, 22, '지점: P3 분전반 앞 ▾'),
                                   ('note', 530, 56, '마지막 관측 2분 전', 'mute', 'end'),
                                   ('thumbs', 10, 76, [('11/14 18:03', '정상', 'green', True),
                                                       ('11/16 18:12', '확인 불가 (조명)', 'orange', False),
                                                       ('11/16 18:31', '이상 · 재점검', 'red', True),
                                                       ('-', '', 'mute', False)])], nav=3),
         v2=('log', ['P3 판정: 이상', '"분전반 경고등 점등.', ' 전기 담당 확인 요청"', '', 'P2 판정: 정상',
                     '"적재물 치운 뒤 통로 확보"']),
         situation='재촬영 사진은 품질 양호. 분전반 경고등 점등을 확인해 "이상"으로 판정하고 조치 의견을 남긴다. 지점 이력에서 확인 불가 → 재점검 → 결론 흐름이 이어진다.',
         actions=['같은 지점의 과거·현재 사진을 나란히 비교', '재점검 관측은 원래 관측과 연결 표시'],
         records='OBSERVATION_SAVED · REVIEWED (이상 + 의견)'),
    dict(no='S9', title='admin 사후 확인', actors=['admin'],
         v1=scr('A5'), v2=('screen', scr('A6')),
         situation='웹 admin 이 감사 로그로 누가 무엇을 요청·판정했는지 보고, 시스템 상태로 로봇 연결과 미전송 보고가 없는지 확인한다.',
         actions=['변경 요청과 로그인 기록 조회', '서비스 UP/DOWN, 토픽 갱신 지연 확인'],
         records='(조회만) 감사 로그는 수정·삭제하지 않는다'),
    dict(no='S10', title='예외: 서버 일시 중단', actors=['server', 'robot'],
         v1=scr('A6', '시스템 상태', [('cards', 10, 40, [('gateway', 'UP', 'green'), ('user-service', 'UP', 'green'),
                                                       ('inspection', 'DOWN', 'red'), ('robot-service', 'UP', 'green'),
                                                       ('analysis', 'UP', 'green')]),
                                     ('table', 10, 120, 520, ['로봇', 'rosbridge', 'odom', 'scan', '미전송 보고'],
                                      [['tb3-sim', '연결', '0.1s', '0.3s', '3']])]),
         v2=('log', ['robot-service 보관함', '① ARRIVED       보관', '② 관측 + 사진    보관', '③ COMPLETED     보관',
                     '→ 복구 후 순서대로 전송', '→ 같은 보고는 한 번만 반영']),
         situation='점검 중 inspection-service 가 재시작된다. 로봇의 보고는 robot-service 보관함에 쌓였다가 복구 후 순서대로 전송된다.',
         actions=['원격 조종 중 연결이 끊기면 로봇 측 워치독이 0.5초 안에 정지', 'robot-service 가 재시작되면 진행 중 작업을 "중단(상태 불명)"으로 기록'],
         records='보고 ID 로 중복 제거 · MISSION_INTERRUPTED (해당 시)'),
    dict(no='S11', title='후속 후보 (이번 범위 밖)', actors=[], dim=True,
         v1=None, v2=None,
         situation='모형 대응 장치(서보 투석기)는 필요성과 시험 결과에 따라 연결한다. PC 앱의 로컬 분석은 개선안에서 서버 배치 분석으로 옮겼다.',
         actions=['20~22 투척 시험·결과 검토·방향 보정: 미채택', '13 신고에 따른 작업 자동 전환: 정책 미정 → 지금은 담당자가 재점검 요청'],
         records='채택 시 장면을 추가한다'),
]


# ------------------------------------------------------------------ 그림 요소
def world_map(x, y, st):
    """위에서 본 시설 지도. 벽·설비·대상·지점은 sim/worlds/world_spec.py 에서 읽는다."""
    import math
    w, h = VIS_W, VIS_H
    sb.rect(x, y, w, h, '#f8fafc', '#cbd5e1', 4)
    k = min((w - 16) / (W_.X1 - W_.X0), (h - 16) / (W_.Y1 - W_.Y0))
    ox = x + (w - (W_.X1 - W_.X0) * k) / 2
    oy = y + h - (h - (W_.Y1 - W_.Y0) * k) / 2
    sx = lambda X: ox + (X - W_.X0) * k  # noqa: E731
    sy = lambda Y: oy - (Y - W_.Y0) * k  # noqa: E731

    def box(cx, cy, bw, bh, fill, stroke=None):
        sb.rect(sx(cx - bw / 2), sy(cy + bh / 2), bw * k, bh * k, fill, stroke or fill, 0)
    sb.rect(sx(W_.X0), sy(W_.Y1), (W_.X1 - W_.X0) * k, (W_.Y1 - W_.Y0) * k, '#fff', '#fff', 0)
    for _, cx, cy, bw, bh in W_.WALLS:
        box(cx, cy, bw, bh, '#475569')
    for _, cx, cy, bw, bh, _, _ in W_.FIXTURES:
        box(cx, cy, bw, bh, '#cbd5e1')
    for _, cx, cy, bw, bh, rgb in W_.TARGETS:
        box(cx, cy, bw, bh, '#%02x%02x%02x' % tuple(int(c * 255) for c in rgb))
    for name in st.get('obstacles', []):
        cx, cy, bw, bh = W_.OBSTACLES[name]
        box(cx, cy, bw, bh, '#92400e')
        sb.t(sx(cx) + (8 if name != 'block' else -8), sy(cy) + 3, '적재물', 8.5, '#92400e',
             'start' if name != 'block' else 'end', 'bold')
    for key, dash, color in [('path', None, sb.C['blue']), ('path2', '4 3', sb.C['red'])]:
        p = st.get(key)
        if p:
            sb.path('M' + ' L'.join(f'{sx(a):.1f},{sy(b):.1f}' for a, b in p), color, 1.6, dash, True)
    for i, (pk, (px, py, _)) in enumerate(W_.POINTS.items()):
        color = sb.C['green'] if pk in st.get('done', []) else sb.C['red'] if pk in st.get('failed', []) else sb.C['sub']
        sb.out.append(f'<circle cx="{sx(px):.1f}" cy="{sy(py):.1f}" r="6" fill="#fff" stroke="{color}" stroke-width="2"/>')
        mark = '✓' if pk in st.get('done', []) else '✕' if pk in st.get('failed', []) else (str(i + 1) if st.get('order') else '')
        sb.t(sx(px), sy(py) + 3.5, mark, 8.5, color, 'middle', 'bold')
        sb.t(sx(px), sy(py) - 9, pk, 9, color, 'middle', 'bold')
        if pk in st.get('recheck', []):
            sb.out.append(f'<circle cx="{sx(px):.1f}" cy="{sy(py):.1f}" r="10" fill="none" stroke="{sb.C["blue"]}" '
                          f'stroke-width="1.4" stroke-dasharray="3 2"/>')
    sb.out.append(f'<circle cx="{sx(0):.1f}" cy="{sy(0):.1f}" r="4" fill="none" stroke="{sb.C["mute"]}"/>')
    if st.get('robot'):
        rx, ry, yaw = st['robot']
        cx, cy = sx(rx), sy(ry)
        pts_ = [(cx + 9 * math.cos(-yaw), cy + 9 * math.sin(-yaw)),
                (cx + 6 * math.cos(-yaw + 2.5), cy + 6 * math.sin(-yaw + 2.5)),
                (cx + 6 * math.cos(-yaw - 2.5), cy + 6 * math.sin(-yaw - 2.5))]
        sb.out.append('<polygon points="' + ' '.join(f'{a:.1f},{b:.1f}' for a, b in pts_) +
                      f'" fill="{sb.C["blue"]}" stroke="#1e3a8a" stroke-width="1"/>')
    sb.t(x, y + h + 13, '시설 지도 (왼쪽 아래 사무실·충전 위치, 위 전기실, 가운데 생산동, 아래 C1·오른쪽 C2 복도)', 9.5, sb.C['mute'])


def log_box(x, y, lines):
    sb.rect(x, y, VIS_W, VIS_H, '#0f172a', '#0f172a', 4)
    for i, s in enumerate(lines):
        sb.t(x + 12, y + 22 + i * 19, s, 10.5, '#e2e8f0' if i else '#93c5fd', 'start', 'bold' if i == 0 else 'normal')


def actor_chips(x, y, actors):
    cx = x
    for a in reversed(actors):
        name, color = ACTOR[a]
        w = 14 + 11 * len(name)
        cx -= w + 6
        sb.rect(cx, y, w, 18, '#fff', '#fff', 9)
        sb.t(cx + w / 2, y + 13, name, 10, color, 'middle', 'bold')


def scene_card(sc, x, y):
    dim = sc.get('dim')
    sb.rect(x + 3, y + 3, CARD_W, CARD_H, '#e2e8f0', '#e2e8f0', 10)
    sb.rect(x, y, CARD_W, CARD_H, '#fff' if not dim else '#f8fafc', '#94a3b8', 10, 1.2, '6 4' if dim else None)
    head = sb.C['dark'] if not dim else '#94a3b8'
    sb.rect(x, y, CARD_W, 34, head, head, 10)
    sb.rect(x, y + 24, CARD_W, 10, head, head, 0)
    sb.t(x + 14, y + 22, f'{sc["no"]}  {sc["title"]}', 14, '#fff', 'start', 'bold')
    actor_chips(x + CARD_W - 8, y + 8, sc['actors'])
    vy = y + 44
    if sc['v1']:
        tree.SCALE = VIS_SCALE
        sb.rect(x + 10, vy, VIS_W, VIS_H, '#fff', '#fff', 0)
        tree.thumb(sc['v1'], x + 10, vy)
        sb.t(x + 10, vy + VIS_H + 13, f'화면 {sc["v1"]["id"]} {sc["v1"]["name"]}', 9.5, sb.C['mute'])
    if sc['v2']:
        kind, val = sc['v2']
        vx = x + 20 + VIS_W
        if kind == 'map':
            world_map(vx, vy, val)
        elif kind == 'log':
            log_box(vx, vy, val)
        else:
            tree.SCALE = VIS_SCALE
            tree.thumb(val, vx, vy)
            sb.t(vx, vy + VIS_H + 13, f'화면 {val["id"]} {val["name"]}', 9.5, sb.C['mute'])
    ty = vy + VIS_H + 34 if sc['v1'] else y + 60
    sb.t(x + 14, ty, '상황', 11, sb.C['ink'], 'start', 'bold')
    for i, line in enumerate(sb.wrap(sc['situation'], 46)):
        sb.t(x + 52, ty + i * 16, line, 11, sb.C['ink'])
    ty += max(1, len(sb.wrap(sc['situation'], 46))) * 16 + 8
    sb.t(x + 14, ty, '동작', 11, sb.C['ink'], 'start', 'bold')
    for a in sc['actions']:
        sb.t(x + 52, ty, '· ' + a, 10.5, sb.C['sub'])
        ty += 16
    ty += 6
    sb.rect(x + 10, ty - 13, CARD_W - 20, 22, '#f1f5f9', '#e2e8f0', 4)
    sb.t(x + 16, ty + 2, '남는 기록', 10, sb.C['blue'], 'start', 'bold')
    sb.t(x + 76, ty + 2, sc['records'], 10, sb.C['sub'])


def overview(y0):
    """맨 위: 행위자 레인 위에 장면 순서를 놓은 흐름 요약."""
    sb.t(30, y0, '서비스 흐름 요약', 18, sb.C['ink'], 'start', 'bold')
    sb.t(200, y0, '가로 = 시간 순서, 세로 = 장면의 주 행위자. 원 안의 번호는 아래 장면 카드와 같다.', 11, sb.C['sub'])
    top = y0 + 20
    lane_h = 62
    x0 = 170
    for i, a in enumerate(LANES):
        name, color = ACTOR[a]
        ly = top + i * lane_h
        sb.rect(30, ly, W - 60, lane_h - 6, '#f8fafc' if i % 2 else '#fff', '#e2e8f0', 6)
        sb.rect(30, ly, 130, lane_h - 6, color, color, 6)
        sb.t(95, ly + lane_h / 2 + 1, name, 12, '#fff', 'middle', 'bold')
    flow = [s for s in SCENES if not s.get('dim')]
    step = (W - 60 - x0 - 40) / (len(flow) - 1)
    prev = None
    for i, s in enumerate(flow):
        lane = LANES.index(s['actors'][0])
        cx = x0 + 30 + i * step
        cy = top + lane * lane_h + (lane_h - 6) / 2
        if prev:
            px, py = prev
            sb.path(f'M{px + 16},{py} C{(px + cx) / 2},{py} {(px + cx) / 2},{cy} {cx - 18},{cy}', sb.C['line'], 1.4,
                    arrow=True)
        for other in s['actors'][1:]:
            oy = top + LANES.index(other) * lane_h + (lane_h - 6) / 2
            sb.path(f'M{cx},{cy} V{oy}', ACTOR[other][1], 1, '3 3')
            sb.out.append(f'<circle cx="{cx}" cy="{oy}" r="5" fill="{ACTOR[other][1]}"/>')
        color = ACTOR[s['actors'][0]][1]
        sb.out.append(f'<circle cx="{cx}" cy="{cy}" r="16" fill="{color}"/>')
        sb.t(cx, cy + 4, s['no'], 10.5, '#fff', 'middle', 'bold')
        short = s['title'].split(':')[0].split('→')[0].strip()
        sb.t(cx, cy + 30, short[:9], 9.5, sb.C['sub'], 'middle')
        prev = (cx, cy)
    return top + len(LANES) * lane_h + 20


def build():
    sb.out.clear()
    sb.t(30, 44, '가상 서비스 흐름 스토리보드', 24, sb.C['ink'], 'start', 'bold')
    sb.t(372, 44, '초안 시나리오: 지점 점검 요청 → 로봇 방문·촬영 → 담당자 확인 → 모의 이상 신고 → 해당 지점 재확인', 12, sb.C['sub'])
    sb.t(30, 66, '역할 1·2·3 중 누가 요청·판정하는지는 권한 결정 때 정한다. 배경은 미정이므로 "가상 시설"의 예시다. 지점·좌표·화면은 현재 구현(시뮬레이션 월드, 웹 화면)과 같고, 작업 번호·시각·판정 내용은 예시 값이다.',
         11, sb.C['mute'])
    y = overview(110)
    cols = [30, 630, 1230]
    for i, sc in enumerate(SCENES):
        scene_card(sc, cols[i % 3], y + 10 + (i // 3) * (CARD_H + 24))
    H = int(y + 10 + ((len(SCENES) + 2) // 3) * (CARD_H + 24) + 30)
    body = '\n'.join(sb.out)
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" font-family="{sb.FONT}">
<defs><marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse">
<path d="M0,0 L10,5 L0,10 z" fill="{sb.C['line']}"/></marker></defs>
<rect width="{W}" height="{H}" fill="#ffffff"/>
{body}
</svg>
'''
    OUT.write_text(svg, encoding='utf-8')
    print(f'wrote {OUT} ({W}x{H})')


if __name__ == '__main__':
    build()
