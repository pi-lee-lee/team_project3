"""웹 화면 스토리보드 SVG 생성기.

구성: 1) 화면 구조도(메뉴 트리)  2) 화면 흐름도  3) 화면별 설계(와이어프레임 + Description)
화면을 고치려면 아래 SCREENS 데이터를 수정하고 실행한다:  python3 build_storyboard.py
출력: docs/storyboard/web_storyboard.svg
"""
from html import escape
from pathlib import Path

OUT = Path(__file__).resolve().parent / 'web_storyboard.svg'
W = 1840
FONT = 'Apple SD Gothic Neo, Noto Sans KR, Malgun Gothic, sans-serif'

C = {
    'ink': '#0f172a', 'sub': '#475569', 'mute': '#94a3b8', 'line': '#64748b', 'grid': '#e2e8f0',
    'admin': '#7c3aed', 'admin_bg': '#f5f3ff', 'user': '#0d9488', 'user_bg': '#f0fdfa',
    'login': '#2563eb', 'leaf': '#f8fafc', 'blue': '#2563eb', 'red': '#dc2626', 'orange': '#ea580c',
    'green': '#16a34a', 'dark': '#1e293b',
}

out = []


def t(x, y, s, size=11, fill=C['ink'], anchor='start', weight='normal'):
    out.append(f'<text x="{x}" y="{y}" font-size="{size}" fill="{fill}" text-anchor="{anchor}" '
               f'font-weight="{weight}">{escape(s)}</text>')


def rect(x, y, w, h, fill='#fff', stroke=C['line'], rx=4, sw=1, dash=None):
    d = f' stroke-dasharray="{dash}"' if dash else ''
    out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" stroke="{stroke}" '
               f'stroke-width="{sw}"{d}/>')


def path(d, stroke=C['line'], sw=1.4, dash=None, arrow=False):
    a = ' marker-end="url(#arr)"' if arrow else ''
    ds = f' stroke-dasharray="{dash}"' if dash else ''
    out.append(f'<path d="{d}" fill="none" stroke="{stroke}" stroke-width="{sw}"{ds}{a}/>')


def node(cx, cy, w, h, label, kind, sub=None):
    fill, stroke, color = {
        'root': (C['dark'], C['dark'], '#fff'),
        'login': (C['login'], C['login'], '#fff'),
        'admin': (C['admin'], C['admin'], '#fff'),
        'user': (C['user'], C['user'], '#fff'),
        'ascreen': ('#fff', C['admin'], C['ink']),
        'uscreen': ('#fff', C['user'], C['ink']),
        'leaf': (C['leaf'], '#cbd5e1', C['sub']),
    }[kind]
    rect(cx - w / 2, cy - h / 2, w, h, fill, stroke, rx=6, sw=1.6 if kind != 'leaf' else 1)
    if sub:
        t(cx, cy - 3, label, 12, color, 'middle', 'bold')
        t(cx, cy + 12, sub, 9.5, color if kind in ('root', 'login', 'admin', 'user') else C['sub'], 'middle')
    else:
        t(cx, cy + 4, label, 10.5 if kind == 'leaf' else 12, color, 'middle',
          'normal' if kind == 'leaf' else 'bold')


# ---------------------------------------------------------------- 화면 데이터
ADMIN_NAV = ['사용자', '로봇', '점검 지점', '분석 기준', '감사 로그', '시스템']
USER_NAV = ['관제', '점검 요청', '작업 목록', '지점 이력']

SCREENS = [
    dict(id='L', name='로그인', path='/login', role='전체 (로그인 전)', feat='#29', parent='서비스',
         leaves=['아이디·비밀번호 로그인', '역할별 화면 이동', '로그아웃'], nav=None,
         wire=[('title', 270, 70, '화재 점검 로봇 서비스'),
               ('input', 170, 100, 200, 30, '아이디'), ('input', 170, 140, 200, 30, '비밀번호  ••••••'),
               ('btn', 170, 184, 200, 32, '로그인', 'blue'),
               ('note', 270, 240, '아이디 또는 비밀번호가 올바르지 않습니다', 'red'),
               ('m', 1, 158, 115), ('m', 2, 158, 155), ('m', 3, 158, 200), ('m', 4, 158, 236)],
         desc=['아이디 입력',
               '비밀번호 입력 (입력값 가림)',
               '로그인: 성공하면 역할에 따라 이동한다. ADMIN → A1 사용자 관리, 역할 1·2·3 → U1 관제',
               '실패 메시지: 아이디·비밀번호 오류 또는 정지된 계정. 성공·실패 모두 감사 로그에 기록',
               '※ 토큰은 HttpOnly 쿠키(JWT)로 발급하고 게이트웨이가 매 요청 검증한다']),

    dict(id='A1', name='사용자 관리', path='/admin/users', role='ADMIN', feat='#32', parent='관리자 영역',
         leaves=['사용자 목록', '사용자 추가', '역할 변경', '정지·해제', '세션 강제 종료', '비밀번호 재설정'], nav=0,
         wire=[('btn', 430, 40, 100, 24, '+ 사용자 추가', 'blue'),
               ('table', 10, 74, 520, ['아이디', '이름', '역할', '상태', '마지막 로그인', '작업'],
                [['admin', '관리자', 'ADMIN', '활성', '11/16 09:02', '-'],
                 ['sup1', '김관리', '1 관리자', '활성', '11/16 08:40', '정지 · 세션 · 비번'],
                 ['mgr1', '이매니저', '2 매니저', '정지', '11/15 17:11', '해제 · 세션 · 비번'],
                 ['user1', '박사용', '3 사용자', '활성', '11/16 10:20', '정지 · 세션 · 비번']]),
               ('modal', 290, 190, 240, 110, '사용자 추가', ['아이디', '이름', '비밀번호', '역할 ▾']),
               ('m', 1, 424, 52), ('m', 2, 4, 84), ('m', 3, 186, 120), ('m', 4, 440, 120), ('m', 5, 284, 200)],
         desc=['사용자 추가 모달을 연다',
               '사용자 목록: 아이디·이름·역할·상태·마지막 로그인',
               '역할 변경: 0 ADMIN / 1 관리자 / 2 매니저 / 3 사용자. 바꾸면 그 사용자의 기존 로그인이 끊긴다',
               '작업: 정지·해제, 세션 강제 종료, 비밀번호 재설정',
               '추가 모달: 아이디·이름·비밀번호(8자 이상)·역할. 이미 있는 아이디는 거부']),

    dict(id='A2', name='로봇 관리', path='/admin/robots', role='ADMIN', feat='#16 #33', parent='관리자 영역',
         leaves=['로봇 목록·연결 상태', '연결 설정(주소·토픽)', '제공 기능 확인', '제어권 회수', '비상 정지'], nav=1,
         wire=[('card', 10, 40, 520, 54, 'tb3-sim · TurtleBot3 (시뮬레이션)', '● 연결됨 · 제어: user1 · 작업: 없음'),
               ('btn', 340, 66, 90, 22, '제어권 회수', 'orange'), ('btn', 436, 66, 90, 22, '비상 정지', 'red'),
               ('field', 10, 108, '어댑터', 'ROSBRIDGE ▾'), ('field', 10, 134, 'rosbridge 주소', 'ws://sim:9090'),
               ('field', 10, 160, '영상 주소', 'http://sim:8080'),
               ('field', 10, 186, '토픽 매핑', 'odom /odom · scan /scan · image /camera/image_raw · nav /inspection/bridge_status'),
               ('btn', 430, 214, 100, 22, '저장·재연결', 'blue'),
               ('chips', 10, 254, [('odom ✓', 'green'), ('scan ✓', 'green'), ('camera ✓', 'green'),
                                    ('nav ✓', 'green'), ('battery ✕ 미지원', 'red')]),
               ('m', 1, 4, 48), ('m', 2, 384, 60), ('m', 3, 480, 60), ('m', 4, 4, 116), ('m', 5, 4, 262)],
         desc=['로봇 목록: 연결 상태, 현재 제어권을 가진 사용자, 진행 중인 작업',
               '제어권 회수: 조종 중인 사용자의 제어권을 강제로 거둔다',
               '비상 정지: 진행 중 작업을 취소하고 정지 명령을 보낸다',
               '연결 설정: 어댑터 종류(ROSBRIDGE·MOCK), rosbridge·영상 주소, 토픽 이름. 시뮬레이션 → 실제 로봇 교체는 이 값만 바꾼다',
               '제공 기능: 로봇이 실제로 내보내는 토픽을 확인해 지원·미지원을 표시']),

    dict(id='A3', name='점검 지점', path='/admin/points', role='ADMIN', feat='#1', parent='관리자 영역',
         leaves=['지점 목록', '지점 추가', '수정·비활성'], nav=2,
         wire=[('table', 10, 40, 520, ['코드', '이름', 'x', 'y', '방향', '상태', '작업'],
                [['P1', '소화기 앞', '4.3', '3.9', '180°', '사용', '수정 · 비활성'],
                 ['P2', '비상구 앞', '7.65', '6.1', '90°', '사용', '수정 · 비활성'],
                 ['P3', '분전반 앞', '0.3', '4.6', '180°', '사용', '수정 · 비활성']]),
               ('label', 10, 190, '지점 추가'),
               ('inputs', 10, 200, [('코드', 50), ('이름', 150), ('x', 56), ('y', 56), ('방향(도)', 70)]),
               ('btn', 420, 200, 110, 24, '추가', 'blue'),
               ('m', 1, 4, 50), ('m', 2, 4, 212), ('m', 3, 470, 68)],
         desc=['지점 목록: 로봇 지도 좌표(x, y)와 촬영 방향. 로봇이 서서 대상을 촬영할 위치',
               '지점 추가: 코드·이름·x·y·방향(도)',
               '수정·비활성: 비활성 지점은 새 요청에서 숨기고, 지난 관측 기록은 그대로 둔다']),

    dict(id='A4', name='분석 기준', path='/admin/analysis', role='ADMIN', feat='#17 #18', parent='관리자 영역',
         leaves=['밝기 기준', '선명도 기준', '관심 영역(ROI)', '저장'], nav=3,
         wire=[('field', 10, 44, '밝기 최소·최대', '60 ~ 200', 260), ('field', 10, 74, '선명도 최소', '80', 260),
               ('field', 10, 104, 'ROI (비율)', '0.2, 0.2 → 0.8, 0.8', 260),
               ('btn', 10, 140, 260, 26, '저장', 'blue'),
               ('roi', 300, 40, 230, 170),
               ('m', 1, 4, 52), ('m', 2, 4, 82), ('m', 3, 294, 48), ('m', 4, 4, 152)],
         desc=['밝기 기준(0~255): 범위 밖이면 너무 어둡거나 밝은 사진',
               '선명도 기준: 라플라시안 분산 최소값. 미달이면 흔들림·초점 불량',
               '관심 영역: 사진 중 평가할 영역(비율 좌표). 미리보기에 점선으로 표시',
               '저장: 이후 들어오는 관측부터 적용. 기준을 벗어난 사진은 "재촬영 후보"로 표시']),

    dict(id='A5', name='감사 로그', path='/admin/audit', role='ADMIN', feat='#34', parent='관리자 영역',
         leaves=['변경 요청 기록', '로그인 기록'], nav=4,
         wire=[('inputs', 10, 40, [('사용자', 120), ('동작 ▾', 100)]),
               ('btn', 440, 40, 90, 24, '새로고침', 'blue'),
               ('table', 10, 76, 520, ['시각', '사용자', '역할', '동작', '대상', '결과'],
                [['10:21:03', 'admin', 'ADMIN', 'PATCH', '/api/admin/users/3', '200'],
                 ['10:20:41', 'user1', 'USER', 'POST', '/api/inspections', '201'],
                 ['10:19:12', 'mgr1', '-', 'LOGIN_FAILED', '/api/auth/login', '401'],
                 ['10:18:55', 'sup1', 'SUPERVISOR', 'POST', '/api/robots/1/estop', '200'],
                 ['10:17:30', 'admin', 'ADMIN', 'POST', '/api/admin/robots/1/…', '200']]),
               ('m', 1, 4, 52), ('m', 2, 4, 86), ('m', 3, 520, 86)],
         desc=['필터: 사용자·동작으로 좁혀 본다',
               '기록: 변경 요청(POST·PUT·PATCH·DELETE)과 로그인 성공·실패. 게이트웨이가 남기며 수정·삭제하지 않는다',
               '결과: HTTP 응답 코드. 거부된 요청(403 등)도 기록된다']),

    dict(id='A6', name='시스템 상태', path='/admin/system', role='ADMIN', feat='#35 #5', parent='관리자 영역',
         leaves=['서비스 상태', '로봇 연결', '데이터 갱신 지연'], nav=5,
         wire=[('cards', 10, 40, [('gateway', 'UP', 'green'), ('user-service', 'UP', 'green'),
                                  ('inspection', 'UP', 'green'), ('robot-service', 'UP', 'green'),
                                  ('analysis', 'UP', 'green')]),
               ('table', 10, 120, 520, ['로봇', 'rosbridge', 'odom', 'scan', 'camera'],
                [['tb3-sim', '연결', '0.1s', '2.4s 지연', '0.2s']]),
               ('note', 10, 200, '5초마다 자동 새로고침', 'mute', 'start'),
               ('m', 1, 4, 48), ('m', 2, 100, 128), ('m', 3, 320, 156)],
         desc=['서비스 상태: 각 서비스 health를 게이트웨이가 모아 UP/DOWN 표시',
               '로봇 연결: 서버 ↔ rosbridge 구간의 연결 여부 (클라이언트 ↔ 서버 구간과 구분)',
               '데이터 갱신: 토픽별 마지막 수신 후 경과 시간. 2초를 넘으면 지연 표시']),

    dict(id='U1', name='관제·조종', path='/app/monitor', role='역할 1·2·3', feat='#5 #28 #30 #31',
         parent='사용자 영역', leaves=['카메라 모드(방향키 조종)', '지도 모드(클릭 이동)', '위치·갱신 상태', '제어권 획득·반납', '비상 정지'], nav=0,
         wire=[('input', 10, 40, 180, 22, '로봇: tb3-sim ▾'),
               ('video', 10, 70, 320, 182, '실시간 영상 (MJPEG)'),
               ('panel', 340, 70, 190, 104, ['● 연결 정상', '위치 x 0.52  y 0.10  θ 12°', 'odom 0.1s · scan 0.3s',
                                             'camera 0.2s', 'battery 미지원']),
               ('btn', 340, 182, 190, 24, '제어권 획득', 'blue'),
               ('pad', 395, 212),
               ('btn', 10, 262, 520, 26, '비상 정지', 'red'),
               ('m', 1, 4, 50), ('m', 2, 4, 80), ('m', 3, 334, 80), ('m', 4, 334, 194), ('m', 5, 380, 230),
               ('m', 6, 4, 274)],
         desc=['로봇 선택',
               '실시간 영상: 로봇 카메라 MJPEG을 서버가 중계',
               '상태: 연결, 위치(x, y, θ), 토픽별 갱신 경과. 오래된 값은 경고 색',
               '제어권 획득·반납: 한 시점에 1명만 조종. 점검 작업 중에는 획득할 수 없다',
               '카메라 모드: 방향키(↑↓ 전진·후진, ←→ 회전)로 조종. 누르는 동안만 움직이고, 제어권이 없으면 자동 요청. 지도 모드: 지도 위 위치·라이다·경로, 클릭한 곳으로 Nav2 이동',
               '비상 정지: 모든 사용자가 사용. 작업 취소 + 정지. 연결이 끊기면 로봇 측 워치독이 0.5초 안에 정지']),

    dict(id='U2', name='점검 요청', path='/app/request', role='역할 1·2·3', feat='#1 #14', parent='사용자 영역',
         leaves=['로봇 선택', '지점 선택(순서)', '메모', '요청 제출'], nav=1,
         wire=[('input', 10, 40, 220, 22, '로봇: tb3-sim (연결됨) ▾'),
               ('checklist', 10, 72, 520, ['① P1 소화기 앞  (4.3, 3.9)', '② P2 비상구 앞  (7.65, 6.1)',
                                           '☐ P3 분전반 앞  (0.3, 4.6)']),
               ('input', 10, 172, 520, 24, '메모'),
               ('btn', 10, 206, 520, 28, '점검 요청', 'blue'),
               ('m', 1, 4, 50), ('m', 2, 4, 82), ('m', 3, 4, 184), ('m', 4, 4, 220)],
         desc=['로봇 선택: 연결된 로봇만 선택할 수 있다',
               '점검 지점 선택: 고른 순서대로 방문한다 (번호 표시)',
               '메모 (선택)',
               '요청: 작업이 만들어지고 U4 작업 상세로 이동. 로봇이 출발 전 검사(연결·위치·카메라)를 하고, 실패하면 사유를 남긴다']),

    dict(id='U3', name='작업 목록', path='/app/tasks', role='역할 1·2·3', feat='#9', parent='사용자 영역',
         leaves=['작업 목록·상태', '작업 상세로 이동'], nav=2,
         wire=[('tabs', 10, 40, ['전체', '진행 중', '완료', '실패·취소']),
               ('table', 10, 74, 520, ['#', '로봇', '지점', '상태', '요청자', '요청 시각'],
                [['12', 'tb3-sim', 'P1, P2', '[진행 중]', 'user1', '10:20'],
                 ['11', 'tb3-sim', 'P3', '[완료]', 'mgr1', '09:55'],
                 ['10', 'tb3-sim', 'P1', '[취소됨]', 'user1', '09:40'],
                 ['9', 'tb3-sim', 'P2', '[실패]', 'sup1', '09:12']]),
               ('m', 1, 4, 50), ('m', 2, 260, 84), ('m', 3, 4, 114)],
         desc=['상태 필터',
               '상태: 대기 · 진행 중 · 완료 · 실패 · 취소 요청 · 취소됨. 로봇이 보고한 실행 단계 기준, 2초마다 갱신',
               '행 선택 → U4 작업 상세']),

    dict(id='U4', name='작업 상세', path='/app/tasks/:id', role='역할 1·2·3', feat='#2 #9 #10 #11 #12 #18',
         parent='사용자 영역', leaves=['진행 기록', '취소 요청', '관측 사진·품질', '사람 판정', '재점검 요청'], nav=2,
         wire=[('label', 10, 54, '작업 #12 · tb3-sim · 진행 중'),
               ('btn', 430, 38, 100, 24, '취소 요청', 'orange'),
               ('timeline', 10, 72, 180, ['요청됨 (사용자) 10:20', '접수됨 (로봇)', '출발 전 검사 통과', 'P1 이동 → 도착',
                                          'P1 촬영 저장', 'P2 이동 중…']),
               ('obs', 200, 72, 330, 216),
               ('m', 1, 424, 50), ('m', 2, 4, 80), ('m', 3, 204, 80), ('m', 4, 368, 92), ('m', 5, 368, 150),
               ('m', 6, 368, 250)],
         desc=['취소 요청: 사용자의 "취소 요청"과 로봇이 실제로 멈춘 결과를 따로 기록. 이미 끝난 작업이면 "취소 미적용"',
               '진행 기록: 요청·접수·출발 전 검사·이동·도착·촬영·완료를 사건별로 표시 (출처와 시각 포함)',
               '관측 사진: 지점·촬영 시각. 도착·촬영에 실패하면 "확인 불가"와 사유',
               '품질 분석: 밝기·선명도. 기준 밖이면 "재촬영 후보"',
               '사람 판정: 정상 / 이상 / 확인 불가(사유 필수). 판정은 덮어쓰지 않고 쌓인다',
               '재점검 요청: 같은 지점으로 새 작업을 만들고 원래 관측과 연결']),

    dict(id='U5', name='지점 이력', path='/app/history', role='역할 1·2·3', feat='#3 #4', parent='사용자 영역',
         leaves=['지점 선택', '관측 이력 비교', '마지막 관측 경과'], nav=3,
         wire=[('input', 10, 40, 200, 22, '지점: P1 소화기 앞 ▾'),
               ('note', 530, 56, '마지막 관측 3시간 전', 'orange', 'end'),
               ('thumbs', 10, 76, [('11/15 15:02', '정상', 'green', True), ('11/15 15:20', '확인 불가 (장애물)', 'orange', False),
                                   ('11/16 10:23', '정상 · 재점검', 'green', True), ('11/16 13:40', '재촬영 후보', 'orange', True)]),
               ('m', 1, 4, 50), ('m', 2, 400, 50), ('m', 3, 4, 84), ('m', 4, 270, 84)],
         desc=['지점 선택',
               '마지막 관측 후 경과 시간. 오래되면 경고 색',
               '관측 이력: 시간순 사진·판정·품질. 같은 지점의 과거와 현재를 비교',
               '재점검 연결: 확인 불가 → 재점검 → 결론 흐름을 표시. 사진을 누르면 해당 작업 상세(U4)로 이동']),
]


# ---------------------------------------------------------------- 와이어프레임 요소
def wire(el, ox, oy):
    k = el[0]
    if k == 'title':
        t(ox + el[1], oy + el[2], el[3], 15, C['ink'], 'middle', 'bold')
    elif k == 'input':
        _, x, y, w, h, label = el
        rect(ox + x, oy + y, w, h, '#fff', '#cbd5e1', 3)
        t(ox + x + 8, oy + y + h / 2 + 4, label, 10.5, C['sub'])
    elif k == 'btn':
        _, x, y, w, h, label, color = el
        rect(ox + x, oy + y, w, h, C[color], C[color], 3)
        t(ox + x + w / 2, oy + y + h / 2 + 4, label, 10.5, '#fff', 'middle', 'bold')
    elif k == 'note':
        x, y, s, color = el[1], el[2], el[3], el[4]
        anchor = el[5] if len(el) > 5 else 'middle'
        t(ox + x, oy + y, s, 10, C[color], anchor)
    elif k == 'label':
        t(ox + el[1], oy + el[2], el[3], 11, C['ink'], 'start', 'bold')
    elif k == 'table':
        _, x, y, w, heads, rows = el
        cw = w / len(heads)
        rect(ox + x, oy + y, w, 22 + 24 * len(rows), '#fff', '#cbd5e1', 2)
        rect(ox + x, oy + y, w, 22, '#e2e8f0', '#cbd5e1', 2)
        for i, h in enumerate(heads):
            t(ox + x + 6 + i * cw, oy + y + 15, h, 10, C['ink'], 'start', 'bold')
        for r, row in enumerate(rows):
            yy = oy + y + 22 + 24 * r
            if r:
                path(f'M{ox + x},{yy} H{ox + x + w}', '#e2e8f0', 1)
            for i, cell in enumerate(row):
                color = C['sub']
                if cell.startswith('['):
                    color = {'[진행 중]': C['blue'], '[완료]': C['green'], '[실패]': C['red']}.get(cell, C['mute'])
                    cell = cell.strip('[]')
                if '지연' in cell or cell in ('정지',):
                    color = C['orange']
                t(ox + x + 6 + i * cw, yy + 16, cell, 9.5, color)
    elif k == 'modal':
        _, x, y, w, h, title, fields = el
        rect(ox + x + 3, oy + y + 3, w, h, '#cbd5e1', '#cbd5e1', 6)
        rect(ox + x, oy + y, w, h, '#fff', C['line'], 6, 1.2)
        t(ox + x + 10, oy + y + 18, title + ' (모달)', 10.5, C['ink'], 'start', 'bold')
        for i, f in enumerate(fields):
            fx = ox + x + 10 + (i % 2) * 112
            fy = oy + y + 28 + (i // 2) * 26
            rect(fx, fy, 104, 20, '#fff', '#cbd5e1', 3)
            t(fx + 6, fy + 14, f, 9.5, C['mute'])
        rect(ox + x + w - 70, oy + y + h - 28, 60, 20, C['blue'], C['blue'], 3)
        t(ox + x + w - 40, oy + y + h - 14, '저장', 10, '#fff', 'middle', 'bold')
    elif k == 'card':
        _, x, y, w, h, title, sub = el
        rect(ox + x, oy + y, w, h, '#f8fafc', '#cbd5e1', 4)
        t(ox + x + 12, oy + y + 20, title, 11, C['ink'], 'start', 'bold')
        t(ox + x + 12, oy + y + 40, sub, 10, C['green'])
    elif k == 'field':
        x, y, label, value = el[1], el[2], el[3], el[4]
        w = el[5] if len(el) > 5 else 520
        t(ox + x, oy + y + 14, label, 10, C['sub'])
        rect(ox + x + 100, oy + y, w - 100, 20, '#fff', '#cbd5e1', 3)
        t(ox + x + 106, oy + y + 14, value, 10, C['ink'])
    elif k == 'chips':
        _, x, y, chips = el
        t(ox + x, oy + y + 4, '제공 기능', 10, C['ink'], 'start', 'bold')
        cx = ox + x + 64
        for label, color in chips:
            w = 14 + 7 * len(label)
            rect(cx, oy + y - 10, w, 20, '#fff', C[color], 10)
            t(cx + w / 2, oy + y + 4, label, 9.5, C[color], 'middle')
            cx += w + 8
    elif k == 'roi':
        _, x, y, w, h = el
        rect(ox + x, oy + y, w, h, C['dark'], C['dark'], 4)
        rect(ox + x + w * .2, oy + y + h * .2, w * .6, h * .6, 'none', '#fbbf24', 0, 1.4, '5 3')
        rect(ox + x + w * .45, oy + y + h * .35, w * .12, h * .4, '#b91c1c', '#b91c1c', 0)
        t(ox + x + w / 2, oy + y + h + 16, '미리보기 (최근 관측 사진)', 9.5, C['mute'], 'middle')
    elif k == 'inputs':
        _, x, y, fields = el
        cx = ox + x
        for label, w in fields:
            rect(cx, oy + y, w, 24, '#fff', '#cbd5e1', 3)
            t(cx + 6, oy + y + 16, label, 9.5, C['mute'])
            cx += w + 8
    elif k == 'cards':
        _, x, y, cards = el
        for i, (name, st, color) in enumerate(cards):
            cx = ox + x + i * 106
            rect(cx, oy + y, 98, 56, '#f8fafc', '#cbd5e1', 4)
            t(cx + 8, oy + y + 20, name, 9.5, C['sub'])
            t(cx + 8, oy + y + 42, st, 13, C[color], 'start', 'bold')
    elif k == 'video':
        _, x, y, w, h, label = el
        rect(ox + x, oy + y, w, h, C['dark'], C['dark'], 4)
        rect(ox + x + w * .55, oy + y + h * .4, w * .12, h * .4, '#b91c1c', '#b91c1c', 0)
        t(ox + x + w / 2, oy + y + 22, label, 10.5, '#e2e8f0', 'middle')
    elif k == 'panel':
        _, x, y, w, h, lines = el
        rect(ox + x, oy + y, w, h, '#f8fafc', '#cbd5e1', 4)
        for i, s in enumerate(lines):
            color = C['green'] if s.startswith('●') else (C['orange'] if '미지원' in s else C['sub'])
            t(ox + x + 10, oy + y + 20 + i * 19, s, 10, color)
    elif k == 'pad':
        _, x, y = el
        for dx, dy, s in [(20, 0, '↑'), (0, 22, '←'), (20, 22, '■'), (40, 22, '→')]:
            rect(ox + x + dx, oy + y + dy, 18, 18, '#e2e8f0', '#94a3b8', 3)
            t(ox + x + dx + 9, oy + y + dy + 13, s, 10, C['ink'], 'middle')
        t(ox + x + 70, oy + y + 30, 'W A S D', 9.5, C['mute'])
    elif k == 'checklist':
        _, x, y, w, items = el
        t(ox + x, oy + y + 4, '점검 지점 (고른 순서대로 방문)', 10, C['ink'], 'start', 'bold')
        for i, s in enumerate(items):
            on = not s.startswith('☐')
            rect(ox + x, oy + y + 12 + i * 28, w, 24, '#eff6ff' if on else '#fff', '#bfdbfe' if on else '#cbd5e1', 3)
            t(ox + x + 10, oy + y + 28 + i * 28, s, 10.5, C['blue'] if on else C['sub'])
    elif k == 'tabs':
        _, x, y, tabs = el
        cx = ox + x
        for i, s in enumerate(tabs):
            w = 20 + 11 * len(s)
            rect(cx, oy + y, w, 24, C['blue'] if i == 0 else '#fff', C['blue'] if i == 0 else '#cbd5e1', 12)
            t(cx + w / 2, oy + y + 16, s, 10, '#fff' if i == 0 else C['sub'], 'middle')
            cx += w + 6
    elif k == 'timeline':
        _, x, y, w, items = el
        rect(ox + x, oy + y, w, 216, '#f8fafc', '#cbd5e1', 4)
        t(ox + x + 10, oy + y + 18, '진행 기록', 10.5, C['ink'], 'start', 'bold')
        for i, s in enumerate(items):
            last = i == len(items) - 1
            yy = oy + y + 40 + i * 26
            out.append(f'<circle cx="{ox + x + 14}" cy="{yy - 4}" r="4" fill="{C["blue"] if last else C["green"]}"/>')
            t(ox + x + 24, yy, s, 9.5, C['blue'] if last else C['sub'])
    elif k == 'obs':
        _, x, y, w, h = el
        X, Y = ox + x, oy + y
        rect(X, Y, w, h, '#fff', '#cbd5e1', 4)
        rect(X + 10, Y + 10, 150, 110, C['dark'], C['dark'], 3)
        rect(X + 80, Y + 40, 20, 50, '#b91c1c', '#b91c1c', 0)
        t(X + 16, Y + 26, 'P1 · 10:23 촬영', 9.5, '#e2e8f0')
        t(X + 172, Y + 24, '품질 분석', 10, C['ink'], 'start', 'bold')
        t(X + 172, Y + 42, '밝기 132 · 선명도 210', 9.5, C['sub'])
        t(X + 172, Y + 58, '→ 양호', 9.5, C['green'])
        t(X + 172, Y + 82, '사람 판정', 10, C['ink'], 'start', 'bold')
        for i, (s, col, bg) in enumerate([('정상', C['green'], '#dcfce7'), ('이상', C['red'], '#fee2e2'),
                                          ('확인 불가', C['orange'], '#ffedd5')]):
            bx = X + 172 + i * 52
            rect(bx, Y + 90, 48, 20, bg, bg, 3)
            t(bx + 24, Y + 104, s, 9.5, col, 'middle', 'bold')
        rect(X + 172, Y + 118, 148, 20, '#fff', '#cbd5e1', 3)
        t(X + 178, Y + 132, '의견 / 확인 불가 사유', 9.5, C['mute'])
        t(X + 10, Y + 140, '판정 이력: user1 정상 (10:30)', 9.5, C['sub'])
        t(X + 172, Y + 182, '↺ 재점검 요청', 10.5, C['blue'], 'start', 'bold')
        t(X + 10, Y + 168, 'P2 · 도착 전 (진행 중)', 9.5, C['mute'])
    elif k == 'thumbs':
        _, x, y, items = el
        for i, (time, verdict, color, photo) in enumerate(items):
            X = ox + x + i * 132
            rect(X, oy + y, 122, 92, C['dark'], C['dark'], 3)
            if photo:
                rect(X + 52, oy + y + 24, 18, 46, '#b91c1c', '#b91c1c', 0)
            else:
                t(X + 61, oy + y + 50, '(촬영 없음)', 9.5, C['mute'], 'middle')
            t(X, oy + y + 108, time, 9.5, C['sub'])
            t(X, oy + y + 124, verdict, 9.5, C[color])
        path(f'M{ox + x + 122 + 2},{oy + y + 46} H{ox + x + 264 - 4}', C['orange'], 1.2, '4 3', True)
        t(ox + x + 193, oy + y + 40, '재점검', 9, C['orange'], 'middle')
    elif k == 'm':
        _, n, x, y = el
        out.append(f'<circle cx="{ox + x}" cy="{oy + y}" r="8" fill="{C["red"]}"/>')
        t(ox + x, oy + y + 4, str(n), 10, '#fff', 'middle', 'bold')


def wrap(s, n=27):
    lines, cur = [], ''
    for word in s.split(' '):
        cand = (cur + ' ' + word).strip()
        if len(cand) > n and cur:
            lines.append(cur)
            cur = word
        else:
            cur = cand
    if cur:
        lines.append(cur)
    return lines


# ---------------------------------------------------------------- 1. 화면 구조도 (트리)
def section_title(y, s, note):
    t(30, y, s, 18, C['ink'], 'start', 'bold')
    t(30 + 16 * len(s) + 20, y, note, 11, C['sub'])
    path(f'M30,{y + 10} H{W - 30}', C['grid'], 1)


def tree(y0):
    section_title(y0, '1. 화면 구조도', '서비스 → 로그인 → 영역 → 화면 → 화면 기능 (Depth 0 ~ 4)')
    for i, (label, yy) in enumerate([('Depth 0', 50), ('Depth 1', 120), ('Depth 2', 190), ('Depth 3', 280),
                                     ('Depth 4', 360)]):
        t(30, y0 + yy + 4, label, 10, C['mute'])
    cx = W / 2
    node(cx, y0 + 50, 260, 40, '화재 점검 로봇 웹 서비스', 'root')
    login = SCREENS[0]
    node(cx, y0 + 120, 200, 40, 'L · 로그인', 'login', login['path'])
    path(f'M{cx},{y0 + 70} V{y0 + 100}')
    # 로그인 기능 노드 (오른쪽)
    lx = cx + 140
    path(f'M{cx + 100},{y0 + 120} H{lx + 450}', C['line'], 1)
    for i, leaf in enumerate(login['leaves']):
        node(lx + 70 + i * 160, y0 + 120, 148, 28, leaf, 'leaf')
    admin = SCREENS[1:7]
    user = SCREENS[7:]
    col_w, gap = 150, 8
    ax = [40 + i * (col_w + gap) for i in range(len(admin))]
    ux0 = ax[-1] + col_w + 60
    ux = [ux0 + i * (col_w + gap) for i in range(len(user))]
    acx = (ax[0] + ax[-1] + col_w) / 2
    ucx = (ux[0] + ux[-1] + col_w) / 2
    path(f'M{cx},{y0 + 140} V{y0 + 160} H{acx} V{y0 + 170}')
    path(f'M{cx},{y0 + 160} H{ucx} V{y0 + 170}')
    node(acx, y0 + 190, 220, 40, '관리자 영역', 'admin', 'ADMIN · /admin')
    node(ucx, y0 + 190, 220, 40, '사용자 영역', 'user', '역할 1·2·3 · /app')
    for cols, scr, pcx, kind in [(ax, admin, acx, 'ascreen'), (ux, user, ucx, 'uscreen')]:
        centers = [c + col_w / 2 for c in cols]
        path(f'M{pcx},{y0 + 210} V{y0 + 236}')
        path(f'M{centers[0]},{y0 + 236} H{centers[-1]}')
        for c, s in zip(cols, scr):
            mid = c + col_w / 2
            path(f'M{mid},{y0 + 236} V{y0 + 255}')
            node(mid, y0 + 280, col_w, 50, f'{s["id"]} · {s["name"]}', kind, s['path'])
            spine_x = c + 10
            last = y0 + 336 + (len(s['leaves']) - 1) * 32 + 13
            path(f'M{spine_x},{y0 + 305} V{last}', C['mute'], 1)
            for i, leaf in enumerate(s['leaves']):
                ly = y0 + 336 + i * 32
                path(f'M{spine_x},{ly + 13} H{c + 20}', C['mute'], 1)
                node(c + 20 + 65, ly + 13, 130, 26, leaf, 'leaf')
    return y0 + 336 + 6 * 32 + 30


# ---------------------------------------------------------------- 2. 화면 흐름도
def flow(y0):
    section_title(y0, '2. 화면 흐름도', '실선 = 사용자 조작에 따른 이동, 점선 = 자동 이동(세션 만료·로그아웃)')
    Y = y0 + 40
    # 시작 → 로그인 → 역할 판단
    out.append(f'<circle cx="60" cy="{Y + 200}" r="10" fill="{C["ink"]}"/>')
    t(60, Y + 228, '접속', 10, C['sub'], 'middle')
    node(170, Y + 200, 140, 44, 'L · 로그인', 'login')
    path(f'M70,{Y + 200} H98', arrow=True)
    dx, dy = 330, Y + 200
    out.append(f'<polygon points="{dx},{dy - 30} {dx + 46},{dy} {dx},{dy + 30} {dx - 46},{dy}" fill="#fff" '
               f'stroke="{C["ink"]}" stroke-width="1.4"/>')
    t(dx, dy + 4, '역할 확인', 10.5, C['ink'], 'middle', 'bold')
    path(f'M240,{dy} H282', arrow=True)
    # 관리자 그룹
    gx, gy, gw, gh = 450, Y, 820, 130
    rect(gx, gy, gw, gh, C['admin_bg'], C['admin'], 10, 1.2)
    t(gx + 16, gy + 24, '관리자 영역 — 상단 메뉴로 A1~A6 사이를 자유롭게 이동', 11, C['admin'], 'start', 'bold')
    for i, s in enumerate(SCREENS[1:7]):
        node(gx + 76 + i * 133, gy + 78, 118, 44, f'{s["id"]} · {s["name"]}', 'ascreen')
    t(gx + 76, gy + 116, '기본 화면', 9.5, C['admin'], 'middle')
    path(f'M{dx},{dy - 30} V{gy + 78} H{gx + 15}', arrow=True)
    t(dx + 8, gy + 70, 'ADMIN', 10.5, C['admin'], 'start', 'bold')
    # 사용자 그룹
    ux, uy, uw, uh = 450, Y + 170, 1060, 230
    rect(ux, uy, uw, uh, C['user_bg'], C['user'], 10, 1.2)
    t(ux + 16, uy + 24, '사용자 영역 — 상단 메뉴로 U1·U2·U3·U5 이동, U4는 작업을 골라 들어간다', 11, C['user'], 'start', 'bold')
    pos = {'U1': (ux + 90, uy + 120), 'U2': (ux + 290, uy + 75), 'U3': (ux + 290, uy + 170),
           'U4': (ux + 560, uy + 120), 'U5': (ux + 860, uy + 120)}
    for s in SCREENS[7:]:
        node(*pos[s['id']], 140, 44, f'{s["id"]} · {s["name"]}', 'uscreen')
    t(pos['U1'][0], pos['U1'][1] + 36, '기본 화면', 9.5, C['user'], 'middle')
    path(f'M{dx},{dy + 30} V{pos["U1"][1]} H{pos["U1"][0] - 72}', arrow=True)
    t(dx + 8, pos['U1'][1] - 8, '역할 1·2·3', 10.5, C['user'], 'start', 'bold')

    def edge(a, b, label, bend=0, lx=0, ly=-8):
        (x1, y1), (x2, y2) = pos[a], pos[b]
        sx, ex = x1 + 70, x2 - 72
        if bend:
            path(f'M{x1},{y1 + 22} C{x1},{y1 + bend} {x2},{y2 + bend} {x2},{y2 + 24}', arrow=True)
            t((x1 + x2) / 2 + lx, y1 + bend * .75 + ly, label, 10, C['ink'], 'middle')
        else:
            path(f'M{sx},{y1} C{(sx + ex) / 2},{y1} {(sx + ex) / 2},{y2} {ex},{y2}', arrow=True)
            t((sx + ex) / 2 + lx, (y1 + y2) / 2 + ly, label, 10, C['ink'], 'middle')

    edge('U2', 'U4', '요청 제출 → 생성된 작업', lx=10, ly=-14)
    edge('U3', 'U4', '행 선택', lx=10, ly=20)
    edge('U4', 'U5', '지점 이력 보기')
    edge('U5', 'U4', '사진 선택 → 해당 작업', bend=90, ly=8)
    x4, y4 = pos['U4']
    path(f'M{x4 - 30},{y4 - 22} C{x4 - 40},{y4 - 80} {x4 + 40},{y4 - 80} {x4 + 30},{y4 - 22}', arrow=True)
    t(x4, y4 - 70, '재점검 요청 → 새 작업 상세', 10, C['ink'], 'middle')
    t(pos['U1'][0], pos['U1'][1] - 34, '점검 작업 중에는 조종 불가', 9.5, C['sub'], 'middle')
    # 로그아웃·세션 만료
    path(f'M{ux + uw},{uy + 60} H{ux + uw + 40} V{Y - 20} H170 V{Y + 176}', C['mute'], 1.3, '6 4', True)
    path(f'M{gx + gw},{gy + 40} H{ux + uw + 40}', C['mute'], 1.3, '6 4')
    t(ux + uw + 48, Y + 90, '로그아웃', 10, C['sub'])
    t(ux + uw + 48, Y + 106, '세션 만료 (401)', 10, C['sub'])
    t(ux + uw + 48, Y + 122, '계정 정지·역할 변경', 10, C['sub'])
    t(ux + uw + 48, Y + 138, '→ 로그인으로', 10, C['sub'])
    t(ux + uw + 48, Y + 168, '권한 없는 화면 (403)', 10, C['sub'])
    t(ux + uw + 48, Y + 184, '→ 역할 기본 화면으로', 10, C['sub'])
    return Y + 430


# ---------------------------------------------------------------- 3. 화면 설계
def page(s, px, py):
    PW, PH = 880, 440
    rect(px, py, PW, PH, '#fff', '#94a3b8', 6, 1.2)
    # 헤더 표
    cells = [[('화면 ID', 70), (s['id'], 80), ('화면명', 70), (s['name'], 190), ('권한', 60), (s['role'], 410)],
             [('경로', 70), (s['path'], 80 + 70 + 190 - 0), ('관련 기능', 60 + 0), (s['feat'], 200),
              ('상위', 60), (s['parent'], 140)]]
    cells[1] = [('경로', 70), (s['path'], 150), ('관련 기능', 70), (s['feat'], 270), ('상위', 60), (s['parent'], 260)]
    for r, row in enumerate(cells):
        x = px
        for i, (txt, w) in enumerate(row):
            head = i % 2 == 0
            rect(x, py + r * 26, w, 26, '#e2e8f0' if head else '#fff', '#cbd5e1', 0)
            t(x + 8, py + r * 26 + 17, txt, 10.5, C['ink'], 'start', 'bold' if head else 'normal')
            x += w
    # 브라우저 틀
    bx, by, bw, bh = px + 10, py + 62, 560, 366
    rect(bx, by, bw, bh, '#fff', '#94a3b8', 4)
    rect(bx, by, bw, 20, '#f1f5f9', '#94a3b8', 4)
    for i, col in enumerate(['#f87171', '#fbbf24', '#4ade80']):
        out.append(f'<circle cx="{bx + 10 + i * 12}" cy="{by + 10}" r="3.5" fill="{col}"/>')
    t(bx + 50, by + 14, 'http://localhost:8080' + s['path'], 9.5, C['sub'])
    ox, oy = bx + 10, by + 28
    if s['nav'] is not None:
        nav = ADMIN_NAV if s['id'].startswith('A') else USER_NAV
        color = C['admin'] if s['id'].startswith('A') else C['user']
        rect(bx, by + 20, bw, 26, color, color, 0)
        x = bx + 12
        for i, n in enumerate(nav):
            on = i == s['nav']
            t(x, by + 37, n, 10.5, '#fff' if on else '#e9d5ff' if s['id'].startswith('A') else '#ccfbf1', 'start',
              'bold' if on else 'normal')
            if on:
                path(f'M{x},{by + 42} H{x + 11 * len(n)}', '#fff', 2)
            x += 14 + 11 * len(n)
        who = 'admin (ADMIN)' if s['id'].startswith('A') else 'user1 (3 사용자)'
        t(bx + bw - 12, by + 37, f'{who} | 로그아웃', 9.5, '#fff', 'end')
        oy = by + 50 - 30
    for el in s['wire']:
        wire(el, ox, oy + 6)
    # Description
    dx, dy, dw, dh = px + 580, py + 62, 290, 366
    rect(dx, dy, dw, dh, '#f8fafc', '#cbd5e1', 4)
    t(dx + 12, dy + 22, 'Description', 12, C['ink'], 'start', 'bold')
    path(f'M{dx + 12},{dy + 30} H{dx + dw - 12}', '#cbd5e1', 1)
    yy = dy + 50
    n = 0
    for d in s['desc']:
        note = d.startswith('※')
        if not note:
            n += 1
            out.append(f'<circle cx="{dx + 20}" cy="{yy - 4}" r="8" fill="{C["red"]}"/>')
            t(dx + 20, yy, str(n), 10, '#fff', 'middle', 'bold')
        for j, line in enumerate(wrap(d, 25)):
            t(dx + 34, yy + j * 15, line, 10.5, C['sub'] if note else C['ink'])
        yy += len(wrap(d, 25)) * 15 + 12


def pages(y0):
    section_title(y0, '3. 화면 설계', '화면별 와이어프레임과 설명 (빨간 번호 = Description 항목)')
    y = y0 + 30
    for i, s in enumerate(SCREENS):
        page(s, 30 + (i % 2) * 900, y + (i // 2) * 460)
    return y + ((len(SCREENS) + 1) // 2) * 460


def build():
    body_start = len(out)
    t(30, 44, '웹 화면 스토리보드', 24, C['ink'], 'start', 'bold')
    t(290, 44, '화재 점검 로봇 서비스 · 로그인 / 관리자(ADMIN) / 사용자(역할 1·2·3) · #번호 = 기능 후보 번호(개선초안 02)', 11.5, C['sub'])
    y = tree(90)
    y = flow(y + 20)
    y = pages(y + 20)
    t(30, y + 10, '제외한 기능 후보: 6·7·8·15·19·25~27 (PC 로컬 분석) · 13 (전환 정책 미정) · 20~22 (투척 미채택) · 24 (장애 시험, 후속)',
      10.5, C['sub'])
    H = int(y + 40)
    body = '\n'.join(out[body_start:])
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" font-family="{FONT}">
<defs><marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse">
<path d="M0,0 L10,5 L0,10 z" fill="{C['line']}"/></marker></defs>
<rect width="{W}" height="{H}" fill="#ffffff"/>
{body}
</svg>
'''
    OUT.write_text(svg, encoding='utf-8')
    print(f'wrote {OUT} ({W}x{H})')


if __name__ == '__main__':
    build()
