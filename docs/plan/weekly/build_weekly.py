"""주차별 진행 도면: 시스템 구성도와 같은 노드 그래프 위에 '이번 주에 하는 일'과 '다음 주에 할 일'을 표시한다.

읽는 법
- 노드 하나 = 구성 요소 하나(컨테이너 · 서비스 · 로봇 노드 · 장치). 배치는 architecture/system_architecture.svg 와 같다:
  가운데 세로 = 요청이 지나는 길(화면 → nginx → gateway → 서비스), 오른쪽 = 로봇 시스템(터틀봇 · 젯봇).
- 노드 색 = 맡은 파트(A 웹 · B 카메라 · C 터틀봇 · D 젯봇 · E 투척기 · 시험).
- 색을 채운 굵은 테두리 = 이번 주에 손대는 노드. 점선 테두리 = 이번 주는 쉬고 다음 주에 시작(재개)하는 노드.
  회색 = 끝났거나 아직 차례가 아닌 노드.
- 아래 표는 파트별 이번 주 · 다음 주 한 줄 요약이다. docs/plan/SCHEDULE.md 의 '주차별 한눈에 보기' 표를 그대로 읽어 온다.
노드별 할 일(NODES)은 SCHEDULE.md 4장을 구성 요소별로 나눠 적은 것이다. 계획서를 바꾸면 NODES 도 고친 뒤 다시 생성한다.
실행: python3 docs/plan/weekly/build_weekly.py  →  docs/plan/weekly/week_1.svg ~ week_9.svg
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / '_lib'))   # 공용 그리기 도구 docs/_lib/svg.py
from svg import C, Svg, text_width

HERE = Path(__file__).resolve().parent
SCHEDULE = HERE.parent / 'SCHEDULE.md'
W = 1820
NW, NH = 320, 92               # 노드 크기

PART = {   # 파트: (이름, 색 종류)
    'A': ('웹', 'client'), 'B': ('카메라', 'py'), 'C': ('터틀봇 · 시뮬', 'ros'),
    'D': ('젯봇', 'bridge'), 'E': ('투척기 · 시험', 'data'),
}
WEEKS = ['11-23 ~ 11-27', '11-30 ~ 12-04', '12-07 ~ 12-11', '12-14 ~ 12-18', '12-21 ~ 12-24',
         '12-28 ~ 12-31', '01-04 ~ 01-08', '01-11 ~ 01-15', '01-18 ~ 01-22']
GOALS = {2: '뼈대 · 계약 확정', 4: '기본 점검(시뮬)', 6: '두 시나리오(시뮬)', 8: '실물 연결', 9: '통합 테스트'}
GOAL_TEXT = {   # 단계 목표(SCHEDULE.md 3장)
    2: '스택이 한 번에 뜨고, 로그인이 되고, 시뮬레이션 로봇이 웹 명령으로 한 지점에 간다. 토픽 계약 · API 확정',
    4: '점검 요청 → 이동 → 촬영 → 품질 분석 → 판정이 시뮬레이션에서 끝까지 된다',
    6: '소방 관제 · 소화액 투척 두 시나리오가 시뮬레이션에서 된다. 대시보드와 팝업',
    8: '터틀봇 실기 주행 · 촬영, 투척기 발사, 젯봇 순찰 · 감지 보고가 같은 지도에서 된다',
    9: '두 시나리오가 실물로 처음부터 끝까지 연속 3회 끝난다',
}

# 노드: id → (이름, 파트, x, y, {주차: 할 일})
X1, X2, X3 = 40, 380, 720      # 웹 영역 세 열
R1, R2 = 1100, 1440            # 로봇 영역 두 열
Y0 = 300
TY = Y0 + 44                   # 터틀봇 묶음 첫 줄
JY = TY + 4 * 110 + 64         # 젯봇 묶음 첫 줄
NODES = {
    'test': ('전 구간 시험 · 시연 스크립트', 'E', X1, Y0, {
        1: '시험 틀(로그인 · API 차례로 부르기)', 3: '기본 흐름 시험(권한 · 지점 보내기)', 4: '기본 전 구간 시험',
        5: '장애물 · 금지구역 시험', 6: '시나리오 전 구간 시험 · 시연 스크립트', 8: '통합 시험 목록 정리',
        9: '통합 테스트 진행 · 기록'}),
    'ui': ('화면 (React SPA)', 'A', X2, Y0, {
        1: '화면 틀 · 로그인 · 공통 부품', 2: '관리자 화면(사용자 · 로봇 · 지점)', 3: '관제(카메라 · 조종) · 작업 화면',
        4: '지도 모드 · 점검 계획 · 판정 · 이력', 5: '규칙 편집 · 경고 · 관제 대시보드', 6: '사건 · 팝업 2종 · 시연 화면',
        7: '대시보드에 젯봇 · 순찰 표시', 8: '실물 화면 확인 · 문구 다듬기', 9: '화면 결함 수정 · 시연 배치 고정'}),
    'nginx': ('cdn · web (nginx)', 'A', X2, Y0 + 120, {
        1: '스택 뼈대 · 정적 화면 · API 프록시', 3: '영상 · WebSocket(조종) 프록시'}),
    'gateway': ('gateway', 'A', X2, Y0 + 240, {
        1: '서비스 뼈대', 2: '토큰 검증 · 역할 정책 · 감사 기록', 5: '대시보드 전용 역할(조회 전용)',
        9: '통합 테스트 · 결함 수정'}),
    'user': ('user-service', 'A', X1, Y0 + 370, {
        1: '로그인(쿠키 JWT) · 사용자 · 역할 5종', 2: '감사 로그 · 초기 계정'}),
    'insp': ('inspection-service', 'A', X2, Y0 + 370, {
        3: '점검 지점 · 작업 · 사건 기록', 4: '예약 점검 · 판정 · 재점검 · 이력', 5: '규칙 · 판독 결과 · 경고 · 설정',
        6: '사건 흐름 · 투척 두 모드 · 시연 실행기', 7: '두 로봇 조정(자리 · 우선순위)', 8: '실물 설정값 반영 · 오류 수정',
        9: '통합 테스트 · 결함 수정'}),
    'robot': ('robot-service', 'A', X3, Y0 + 370, {
        2: '로봇 등록 · rosbridge 어댑터 · 모의 로봇', 3: '미션 실행 · 결과 재전송 · 제어권', 4: '지도 · 위치 중계(지도 모드)',
        6: '출동 미션 · 투척 명령 · 투척 위치', 7: '젯봇 연결 · 감지 보고 받기', 8: '실기 로봇 등록 · 오류 수정',
        9: '통합 테스트 · 결함 수정'}),
    'db': ('db (PostgreSQL)', 'A', X1, Y0 + 500, {
        1: '서비스별 DB · 마이그레이션 틀', 3: '점검 · 미션 표', 5: '규칙 · 경고 · 설정 표', 6: '사건 표'}),
    'analysis': ('analysis-service · 판독기', 'B', X2, Y0 + 500, {
        1: '서비스 뼈대 · 작업 큐', 2: '사진 품질 분석 · 판독 인터페이스', 3: '판독기 틀 · 표시등 · 계기판',
        4: '열화상 판독기 · 소화기 데이터 수집', 5: '소화기 인식 모델 · 즉시 판독', 6: '도착 후 재판독(오탐 가르기)',
        8: '실제 대상 · 조명에서 기준 맞추기', 9: '오판 비율 측정 · 결함 수정'}),
    # 터틀봇 · 시뮬레이션 묶음
    'bridge': ('목표 브리지', 'C', R1, TY, {
        2: '목표 계약 ↔ Nav2 · 지도 · 위치 토픽', 3: '실패 사유 구분 · 조종 워치독', 5: '금지구역 · 가상 장애물 층',
        6: '출동 주행 · 조준 회전', 9: '주행 결함 수정'}),
    'nav': ('Nav2 · 지도', 'C', R1, TY + 110, {
        2: 'SLAM 지도 · AMCL · Nav2 주행', 3: '주행 품질 · 장애물 대응', 5: '주행 제어기 개선(좁은 통로)',
        7: '실기에 맞게 주행 설정 조정', 8: '시연 공간 지도 확정', 9: '도착 정확도 · 실패율 측정'}),
    'sim': ('시뮬레이션 · 월드 (Gazebo)', 'C', R1, TY + 220, {
        1: 'sim 컨테이너 · 시험 시설 월드', 3: '장애물 도구', 4: '점검 대상 · 화재 도구 · 안정화'}),
    'real': ('터틀봇 실기', 'C', R1, TY + 330, {
        6: '실기 조립 · 기본 구동', 7: '실제 공간 지도 · 주행 · 촬영', 8: '실기 출동 · 조준 · 좌표 등록',
        9: '반복 주행 시험'}),
    'tcam': ('터틀봇 카메라 · 영상', 'B', R2, TY, {
        1: '카메라 장비 점검 · 제원표', 2: '영상 중계 · 한 장 촬영 경로', 4: '지점별 촬영 구도 · 판독 영역',
        6: '조준용 대상 찾기 · 승인 팝업 영상', 7: '실기 카메라 맞추기(노출 · 초점)', 8: '실물 영상 지연 줄이기',
        9: '카메라 결함 수정'}),
    'lbridge': ('투척 브리지', 'E', R2, TY + 110, {
        2: '투척 계약 확정', 4: '시리얼 브리지(토픽 ↔ 시리얼)', 5: '모의 투척기', 7: '사거리 · 편차를 설정에 넣기'}),
    'launcher': ('투척기 (아두이노 + SG90)', 'E', R2, TY + 220, {
        1: '투척 방식 · 부품 정하기', 2: '기구 시제품', 3: '펌웨어(발사 · 상태 · 중복 무시)', 5: '탁상에서 사거리 재기',
        7: '터틀봇에 장착 · 사거리 · 편차', 8: '실기 발사 · 명중 확인', 9: '명중률 측정 · 결함 수정'}),
    # 젯봇 묶음
    'jbridge': ('젯봇 브리지 · 순찰', 'D', R1, JY, {
        3: '웹 원격 조종 · 워치독', 6: '목표 계약(자체 주행) · 순찰', 7: '화재 좌표 계산 · 감지 보고',
        8: '실기 공간 순찰 경로 확정', 9: '순찰 완주율 측정'}),
    'jloc': ('젯봇 위치 추정', 'D', R1, JY + 110, {
        4: '마커 인식 · 대기 구역 정렬', 5: '스테레오 오도메트리 · 지도 위 위치', 7: '대상 기준 위치 보정',
        8: '복귀 오차 측정', 9: '위치 오차 측정 · 결함 수정'}),
    'jdrive': ('젯봇 구동 · ROS 2 환경', 'D', R1, JY + 220, {
        1: '젯봇 점검 · ROS 2 환경 올리기', 2: '모터 구동 ROS 2 로 옮기기', 3: '속도 비율 재기'}),
    'jcam': ('젯봇 카메라 · 감지', 'B', R2, JY, {
        1: '카메라 2대 점검', 3: '카메라 2대 구동(영상 한 쌍)', 4: '스테레오 보정 · 고정대 보강',
        7: '실시간 열화상 감지', 8: 'Nano 처리 속도 조정', 9: '감지율 · 오탐 측정'}),
}
# 연결선: (노드, 노드, 이름표)
EDGES = [('ui', 'nginx', ''), ('nginx', 'gateway', ''), ('gateway', 'insp', ''), ('insp', 'analysis', '사진 판독'),
         ('bridge', 'nav', ''), ('nav', 'sim', ''), ('sim', 'real', '같은 코드'), ('lbridge', 'launcher', '시리얼'),
         ('jbridge', 'jloc', ''), ('jloc', 'jdrive', '')]


def overview():
    """SCHEDULE.md '주차별 한눈에 보기' 표 → {주차: [A, B, C, D, E 칸]}"""
    out = {}
    for ln in SCHEDULE.read_text(encoding='utf-8').splitlines():
        cells = [c.strip().replace('**', '') for c in ln.strip().strip('|').split('|')]
        if len(cells) == 7 and cells[0].isdigit():
            out[int(cells[0])] = cells[2:]
    assert sorted(out) == list(range(1, 10)), 'SCHEDULE.md 의 주차별 표를 읽지 못했다'
    return out


def fit(S, x, y, s, avail, size=11.5, weight=500, color='#1c1c1e'):
    """폭에 맞게 글자를 줄여 쓴다."""
    w = text_width(s, False, size)
    if w > avail:
        size = max(9.5, size * avail / w)
    S.text(x, y, s, size, weight, color)


def tag(S, x, y, label, color, solid):
    S.rect(x, y, 36, 18, fill=color if solid else '#ffffff', stroke=color, sw=1.2, rx=5)
    S.text(x + 18, y + 13, label, 10.5, 700, '#ffffff' if solid else color, 'middle')


def node(S, key, wk):
    name, part, x, y, plan = NODES[key]
    stroke, fill = C[PART[part][1]]
    now, nxt = plan.get(wk), plan.get(wk + 1)
    past = any(k < wk for k in plan)
    later = sorted(k for k in plan if k > wk)
    if now:
        S.rect(x, y, NW, NH, fill=fill, stroke=stroke, sw=3, rx=12)
    elif nxt:
        S.rect(x, y, NW, NH, fill='#ffffff', stroke=stroke, sw=1.8, rx=12, dash='6 4')
    else:
        S.rect(x, y, NW, NH, fill='#fafafc', stroke='#c7c7cc', sw=1.2, rx=12)
    active = bool(now or nxt)
    S.text(x + 14, y + 25, name, 14.5, 700, stroke if active else '#8e8e93')
    pw = text_width(part + ' ' + PART[part][0], False, 10.5) + 14
    S.rect(x + NW - pw - 10, y + 10, pw, 19, fill=stroke if active else '#c7c7cc', stroke='none', sw=0, rx=9)
    S.text(x + NW - pw / 2 - 10, y + 23.5, part + ' ' + PART[part][0], 10.5, 700, '#ffffff', 'middle')
    avail = NW - 14 - 44 - 12
    if now:
        tag(S, x + 14, y + 38, '금주', stroke, True)
        fit(S, x + 58, y + 51.5, now, avail, weight=600)
    else:
        if past and not later:
            msg = '✓ 끝남'
        elif past:
            msg = f'쉬어 감 · {later[0]}주차에 이어서'
        else:
            msg = f'아직 시작 전 · {later[0]}주차부터' if later else '—'
        tag(S, x + 14, y + 38, '금주', '#aeaeb2', False)
        S.text(x + 58, y + 51.5, msg, 11.5, 400, '#8e8e93')
    if nxt:
        tag(S, x + 14, y + 63, '차주', stroke, False)
        fit(S, x + 58, y + 76.5, nxt, avail, weight=500, color='#3a3a3c')
    else:
        tag(S, x + 14, y + 63, '차주', '#aeaeb2', False)
        S.text(x + 58, y + 76.5, '—' if wk < 9 else '일정 끝', 11.5, 400, '#8e8e93')


def edge(S, a, b, label=''):
    ax, ay = NODES[a][2] + NW / 2, NODES[a][3] + NH
    by = NODES[b][3]
    S.line([(ax, ay), (ax, by)], color='#8e8e93', sw=1.5, end=a in ('ui', 'nginx', 'gateway', 'insp'), late=False)
    if label:
        S.text(ax + 8, (ay + by) / 2 + 4, label, 10.5, 500, '#8e8e93')


def timeline(S, wk):
    x0, cw, y = 40, (W - 80 - 8 * 8) / 9, 96
    for i in range(1, 10):
        x = x0 + (i - 1) * (cw + 8)
        if i == wk:
            S.rect(x, y, cw, 50, fill='#1c1c1e', stroke='#1c1c1e', rx=10)
            col, sub = '#ffffff', '#d1d1d6'
        elif i == wk + 1:
            S.rect(x, y, cw, 50, fill='#ffffff', stroke='#1c1c1e', sw=1.6, rx=10, dash='6 4')
            col, sub = '#1c1c1e', '#636366'
        else:
            S.rect(x, y, cw, 50, fill='#e5e5ea' if i < wk else '#ffffff', stroke='#d1d1d6', rx=10)
            col, sub = '#8e8e93', '#aeaeb2'
        mark = ' · 금주' if i == wk else (' · 차주' if i == wk + 1 else (' ✓' if i < wk else ''))
        S.text(x + 12, y + 21, f'{i}주차{mark}', 13.5, 700, col)
        S.text(x + 12, y + 40, WEEKS[i - 1] + ('  (4일)' if i in (5, 6) else ''), 11.5, 500, sub, mono=True)
        if i in GOALS:
            S.text(x + cw / 2, y + 68, f'▲ {i}주차 끝: {GOALS[i]}', 11, 600, '#636366' if i >= wk else '#aeaeb2', 'middle')


def legend(S, y):
    x = 40
    S.text(x, y + 14, '표시', 12.5, 700, '#636366')
    x += 44
    S.rect(x, y, 30, 20, fill=C['client'][1], stroke=C['client'][0], sw=3, rx=6)
    S.text(x + 38, y + 14.5, '이번 주에 손대는 노드', 12, 500, '#3a3a3c')
    x += 190
    S.rect(x, y, 30, 20, fill='#ffffff', stroke=C['client'][0], sw=1.8, rx=6, dash='6 4')
    S.text(x + 38, y + 14.5, '다음 주에 시작(재개)', 12, 500, '#3a3a3c')
    x += 180
    S.rect(x, y, 30, 20, fill='#fafafc', stroke='#c7c7cc', sw=1.2, rx=6)
    S.text(x + 38, y + 14.5, '끝났거나 아직 차례가 아님', 12, 500, '#3a3a3c')
    x += 220
    S.text(x, y + 14, '파트', 12.5, 700, '#636366')
    x += 44
    for p, (nm, kind) in PART.items():
        lab = f'{p} {nm}'
        pw = text_width(lab, False, 11) + 16
        S.rect(x, y + 1, pw, 19, fill=C[kind][0], stroke='none', sw=0, rx=9)
        S.text(x + pw / 2, y + 14.5, lab, 11, 700, '#ffffff', 'middle')
        x += pw + 8


def goals(S, x, y, w, wk):
    """단계 목표 다섯 개. 다음에 닿을 목표를 강조한다."""
    S.rect(x, y, w, 250, fill='#ffffff', stroke='#c7c7cc', sw=1.2, rx=14)
    S.text(x + 16, y + 28, '단계 목표', 14.5, 700, '#3a3a3c')
    S.text(x + 92, y + 28, '금요일 통합 때 확인한다', 11.5, 400, '#8e8e93')
    nxt = min(k for k in GOAL_TEXT if k >= wk)
    for i, (k, t) in enumerate(GOAL_TEXT.items()):
        ry = y + 42 + i * 40
        if k == nxt:
            S.rect(x + 12, ry, w - 24, 34, fill='#1c1c1e', stroke='#1c1c1e', rx=8)
            c1, c2 = '#ffffff', '#ffffff'
            left = '이번 주 금요일' if k == wk else f'{k - wk}주 뒤'
        else:
            S.rect(x + 12, ry, w - 24, 34, fill='#f2f2f7' if k < wk else '#ffffff', stroke='#e5e5ea', rx=8)
            c1, c2 = ('#8e8e93', '#8e8e93') if k < wk else ('#3a3a3c', '#3a3a3c')
            left = '✓ 지남' if k < wk else f'{k - wk}주 뒤'
        S.text(x + 26, ry + 22, f'{k}주차 끝', 12.5, 700, c1)
        S.text(x + 104, ry + 22, left, 11.5, 600, c2)
        fit(S, x + 200, ry + 22, t, w - 230, 12, 500, c2)


def group(S, x, y, w, h, title, sub):
    S.rect(x, y, w, h, fill='#ffffff', stroke='#c7c7cc', sw=1.2, rx=14, dash='5 4', opacity=0.75)
    S.text(x + 16, y + 26, title, 14.5, 700, '#3a3a3c')
    S.text(x + 24 + text_width(title, False, 14.5), y + 26, sub, 11.5, 400, '#8e8e93')


def table(S, y, wk, ov):
    S.text(40, y, f'파트별 요약 — {wk}주차(금주)와 {wk + 1}주차(차주)' if wk < 9 else '파트별 요약 — 9주차(금주, 마지막 주)',
           17, 700)
    S.text(40, y + 22, 'docs/plan/SCHEDULE.md 의 "주차별 한눈에 보기" 표에서 읽어 온 한 줄 요약이다.', 12, 400, '#636366')
    y += 38
    lw, cw = 190, (W - 80 - 190) / 2
    S.rect(40, y, W - 80, 34, fill='#1c1c1e', stroke='#1c1c1e', rx=10)
    S.text(56, y + 22, '파트', 12.5, 700, '#ffffff')
    S.text(40 + lw + 16, y + 22, f'금주 · {wk}주차 ({WEEKS[wk - 1]})', 12.5, 700, '#ffffff')
    S.text(40 + lw + cw + 16, y + 22, f'차주 · {wk + 1}주차 ({WEEKS[wk]})' if wk < 9 else '차주 · 없음(일정 끝)',
           12.5, 700, '#ffffff')
    y += 40
    for i, (p, (nm, kind)) in enumerate(PART.items()):
        stroke, fill = C[kind]
        S.rect(40, y, W - 80, 42, fill='#ffffff', stroke='#e5e5ea', rx=9)
        S.rect(40, y, lw, 42, fill=fill, stroke=stroke, sw=1.4, rx=9)
        S.text(56, y + 26.5, f'{p}  {nm}', 13.5, 700, stroke)
        fit(S, 40 + lw + 16, y + 26.5, ov[wk][i], cw - 28, 12.5, 600)
        fit(S, 40 + lw + cw + 16, y + 26.5, ov[wk + 1][i] if wk < 9 else '—', cw - 28, 12.5, 400, '#3a3a3c')
        S.raw(f'<path d="M{40 + lw + cw:.1f} {y + 8} V{y + 34}" stroke="#e5e5ea" stroke-width="1"/>')
        y += 48
    return y


def build(wk, ov):
    S = Svg(W, 1500)
    S._markers = set()
    S.text(40, 46, f'주차별 진행 도면 — {wk}주차 ({WEEKS[wk - 1]})', 24, 700)
    S.text(40, 72, '시스템 구성도와 같은 노드 그래프 위에 이번 주에 하는 일(금주)과 다음 주에 할 일(차주)을 표시했다. '
                   '노드 하나 = 구성 요소 하나, 색 = 맡은 파트.', 13, 400, '#636366')
    timeline(S, wk)
    legend(S, 196)

    # 묶음 테두리
    group(S, 20, Y0 - 56, 1040, 500 + NH + 76, '웹 스택 (Docker Compose)',
          '요청이 지나는 길: 화면 → nginx → gateway → 서비스 · 서비스마다 자기 DB')
    tg_h = 44 + 4 * 110 + 2
    group(S, R1 - 20, Y0 - 8, 2 * NW + 60, tg_h + 8, '터틀봇 · 시뮬레이션', 'ROS 2 · rosbridge 로 robot-service 와 연결')
    group(S, R1 - 20, JY - 44, 2 * NW + 60, 44 + 3 * 110 + 2, '젯봇', '순찰 · 화재 감지 · 같은 토픽 계약')

    for a, b, lab in EDGES:
        edge(S, a, b, lab)
    g = NODES['gateway']
    gy = g[3] + NH + 19                                     # gateway 아래에서 세 서비스로 갈라지는 선
    for k in ('user', 'robot'):
        nx = NODES[k][2] + NW / 2
        S.line([(g[2] + NW / 2, gy), (nx, gy), (nx, NODES[k][3])], color='#8e8e93', sw=1.5, late=False)
    dy = NODES['db'][3]                                     # 서비스 → DB
    S.line([(X1 + NW / 2, NODES['user'][3] + NH), (X1 + NW / 2, dy)], color='#8e8e93', sw=1.5, late=False)
    S.line([(X2 + 30, NODES['insp'][3] + NH), (X2 + 30, dy - 19), (X1 + NW - 40, dy - 19), (X1 + NW - 40, dy)],
           color='#8e8e93', sw=1.5, late=False)
    r = NODES['robot']
    rx, ry = r[2] + NW, r[3] + NH / 2                       # robot-service → 로봇 묶음
    for k in ('bridge', 'jbridge'):
        ty = NODES[k][3] + NH / 2
        S.line([(rx, ry), (rx + 28, ry), (rx + 28, ty), (R1, ty)], color='#8944ab', sw=1.8, start=True, late=False)
    S.text(r[2] + 14, r[3] + NH + 18, 'rosbridge 로 로봇과 연결: 목표 · 상태 · 영상 · 감지 보고', 10.5, 600, '#8944ab')
    for a, b in (('bridge', 'tcam'), ('jbridge', 'jcam')):  # 같은 로봇 안 옆 노드
        y = NODES[a][3] + NH / 2
        S.line([(R1 + NW, y), (R2, y)], color='#8e8e93', sw=1.5, end=False, late=False)
    t = NODES['test']                                       # 시험 → 화면 · 게이트웨이
    S.line([(t[2] + NW, t[3] + NH / 2), (X2, t[3] + NH / 2)], color=C['data'][0], sw=1.5, dash='5 4', late=False)
    S.text(t[2] + 14, t[3] + NH + 18, '실제 스택에 대고 흐름 전체를 확인', 10.5, 500, '#8e8e93')
    for k in NODES:
        node(S, k, wk)

    goals(S, 20, Y0 + 500 + NH + 44, 1040, wk)
    bottom = JY + 3 * 110 + 30
    end = table(S, bottom + 36, wk, ov)
    n_now = sum(1 for v in NODES.values() if wk in v[4])
    n_next = sum(1 for v in NODES.values() if wk + 1 in v[4])
    S.text(40, end + 18, f'이번 주에 손대는 노드 {n_now}개 · 다음 주에 손대는 노드 {n_next}개 (전체 {len(NODES)}개)'
           + (f' · 단계 목표: {wk}주차 끝 — {GOALS[wk]}' if wk in GOALS else ''), 12.5, 600, '#636366')
    S.h = int(end + 44)
    S.render(HERE / f'week_{wk}.svg')


if __name__ == '__main__':
    ov = overview()
    for n, (_, _, _, _, plan) in NODES.items():
        assert all(1 <= k <= 9 for k in plan), n
    for wk in range(1, 10):
        build(wk, ov)
