"""시스템 사이클 도면: 요청·미션·분석·조종이 컨테이너 사이를 어떻게 도는지 번호 순서로 보여 준다(스윔레인).

값(주기·시간·코드)은 코드에서 확인한 것이다:
  SessionChecker 10초 캐시 · OutboxSender 1초 · AnalysisTrigger 5초(60초 재요청) · TeleopHandler 100ms/0.5초 ·
  cmd_vel_watchdog 0.5초 · 제어권 2분 · 출발 전 검사(odom 2초 · 카메라 5초 · Nav2 · 위치 추정) · 도착 후 1.5초 촬영(3회) ·
  bridge map 5초 · map_pose 5Hz · 지도 화면 0.2초 · cdn 보관 기간(web/nginx/web/default.conf 의 Cache-Control, cdn/default.conf).
실행: python3 docs/architecture/build_cycle.py  →  docs/architecture/system_cycle.svg
"""
from pathlib import Path

from svg import C, Svg, text_width

OUT = Path(__file__).resolve().parent / 'system_cycle.svg'

LANES = [  # 키, 이름, 설명, 색
    ('b', '브라우저', 'React SPA', 'client'),
    ('c', 'cdn · web', '엣지 캐시 · 원본 서버(nginx)', 'edge'),
    ('g', 'gateway', '인증 · 권한 · 라우팅', 'edge'),
    ('u', 'user-service', '계정 · 세션 · 감사', 'spring'),
    ('i', 'inspection-service', '작업 · 사건 · 관측', 'spring'),
    ('a', 'analysis-service', 'Python 작업 큐', 'py'),
    ('r', 'robot-service', '미션 · 제어권 · 브리지', 'spring'),
    ('s', 'sim (로봇)', 'rosbridge · 브리지 · Nav2', 'ros'),
]
X0, DX = 300, 212
LX = {k: X0 + i * DX for i, (k, *_) in enumerate(LANES)}
ROW = 38

SECTIONS = [
    ('A', '화면 불러오기 (CDN)', '화면 파일은 cdn 이 보관해 두고 대신 내준다. 무엇을 얼마나 보관할지는 원본(web)이 Cache-Control 로 정한다', 'client', [
        ('b', 'c', 'GET / → index.html — cdn 은 보관하지 않고 매번 web 에서 받아 전달(no-cache): 새 빌드가 바로 보인다'),
        ('b', 'c', 'GET /assets/index-<해시>.js · css — 첫 요청은 MISS: cdn 이 web 에서 받아(gzip) 보관(max-age 1년 · immutable)'),
        ('c', 'c', '다음 요청부터 HIT: 원본에 가지 않고 보관본으로 응답(X-Cache-Status) · web 이 응답하지 않아도 보관본으로 버틴다'),
        ('b', 'b', '브라우저 캐시: 같은 파일 이름이면 요청을 보내지 않는다 · 다시 빌드하면 해시(파일 이름)가 바뀌어 새 파일을 받는다'),
        ('b', 'g', '/api · /ws 는 사용자마다 응답이 다르므로 cdn · web 이 보관 없이 gateway 로 넘긴다 → B 사이클'),
    ]),
    ('B', '인증 · 요청 처리', '모든 /api · /ws 요청. 브라우저 → 서비스 화살표는 모두 cdn·web(보관 없이 통과)·gateway 를 거친다', 'edge', [
        ('b', 'u', '로그인 POST /api/auth/login → 비밀번호(BCrypt) 확인 → JWT 발급(JwtCodec) → HttpOnly 쿠키'),
        ('b', 'g', '이후 요청마다 쿠키 전송'),
        ('g', 'g', 'X-User-* 지움(위조 방지) → JWT 검증 → /internal · /actuator 는 막음'),
        ('g', 'u', '세션 확인 /internal/users/{id}/session — 10초 캐시, 응답 없으면 거부(정지·역할 변경 즉시 반영)'),
        ('g', 'g', '역할 규칙(AccessPolicy) 확인 → X-User-* 헤더 붙여 경로별 서비스로 → 서비스는 CurrentUser 로 읽음'),
        ('g', 'u', '변경 요청(POST·PUT·DELETE)은 끝난 뒤 감사 기록 /internal/audit'),
    ]),
    ('C', '점검 미션', '작업 하나 = 미션 하나(번호 같음). 지점마다 이동 → 도착 → 촬영을 반복한다', 'spring', [
        ('b', 'i', '점검 실행 POST /api/inspections/schedules/{id}/run (점검 계획)'),
        ('i', 'r', '로봇 확인 GET /internal/robots/{id} → 작업 저장 · 사건 REQUESTED'),
        ('i', 'r', '미션 전달 POST /internal/missions — missionId = 작업 번호(같은 번호는 다시 실행하지 않음)'),
        ('r', 'r', '미션이 제어권을 가짐 → ACCEPTED → 출발 전 검사(연결 · odom 2초 · 카메라 5초 · Nav2 준비 · 위치 추정)'),
        ('r', 's', '지점마다 목표 /inspection/goal (rosbridge) — 사건 MOVING'),
        ('s', 's', 'nav2_goal_bridge → Nav2 NavigateToPose: Theta* 직선 경로(한 번 계획) + MPPI 추종 · 실패하면 코스트맵 비우고 경로 확인 후 1회 재시도'),
        ('s', 'r', '결과 /inspection/goal_status: SUCCEEDED(우회 여부) · BLOCKED_NO_PATH · NAV_FAILED · NO_PROGRESS · NAV_UNAVAILABLE'),
        ('r', 's', '도착 1.5초 뒤 스냅샷 HTTP(최대 3회) → ARRIVED · 진입 불가·실패면 촬영 불가로 남기고 다음 지점'),
        ('r', 'r', '사건 · 관측(사진)을 report_outbox 에 먼저 저장 — 모든 지점이 끝나면 COMPLETED, 제어권 반납'),
        ('r', 'i', 'OutboxSender 1초마다 순서대로 전송 /internal/tasks/{id}/events · observations — X-Report-Id 로 중복 제거'),
        ('i', 'b', '작업 상태 · 사건 기록 · 관측 사진을 화면에서 조회'),
    ]),
    ('D', '사진 분석', '사진마다 한 번. 분석 서비스가 멈춰도 결과가 빠지지 않는다', 'py', [
        ('i', 'a', 'AnalysisTrigger 5초마다: 분석 없는 사진 POST /jobs (60초 안에 결과 없으면 다시 요청)'),
        ('a', 'a', 'analysis_job 저장 + NOTIFY → 워커가 LISTEN 으로 깨어나 FOR UPDATE SKIP LOCKED 로 하나씩'),
        ('a', 'i', '사진 받기 GET /internal/observations/{id}/image'),
        ('a', 'i', '결과 보내기 POST /internal/observations/{id}/analysis — 밝기 · 선명도 → OK / RETAKE'),
    ]),
    ('E', '사람 판정 · 재점검', '최종 판단은 사람. 재점검은 새 작업으로 C 사이클을 다시 돈다', 'client', [
        ('b', 'i', '판정 POST /api/observations/{id}/reviews — 확인 불가는 사유 필수, 덮어쓰지 않고 이력으로 쌓음'),
        ('b', 'i', '재점검 POST /api/observations/{id}/recheck → 원래 관측과 연결된 새 작업 → C1 부터 다시'),
    ]),
    ('F', '관제 · 조종 (실시간)', '사람이 직접 움직이는 경로. 미션과 같은 제어권 규칙을 쓴다', 'bridge', [
        ('b', 'r', '제어권 요청 /api/robots/{id}/control/acquire — 한 명만, 2분 조종 없으면 자동 반납'),
        ('b', 'r', 'WebSocket /ws/robots/{id}/teleop — 누르는 동안 100ms 마다 속도(서버가 속도 제한)'),
        ('r', 's', '/cmd_vel_teleop → cmd_vel_watchdog → /cmd_vel — 명령이 0.5초 끊기면 서버와 로봇 양쪽에서 정지'),
        ('s', 'b', '영상: web_video_server 압축 MJPEG → robot-service 중계 → /api/robots/{id}/stream'),
        ('s', 'r', '지도 · 위치: /inspection/map 5초마다 · map_pose 5Hz · scan_map(스캔 시각 TF 로 지도 좌표)'),
        ('b', 'r', '지도 화면: /mapview 0.2초마다(위치는 화면에서 보간) · map.png 는 지도 버전이 바뀔 때(MapRenderer)'),
        ('b', 's', '지도 클릭 이동 POST /goto → /inspection/goal(manual-…) — 방향키 조종을 시작하면 취소'),
    ]),
    ('G', '예외 · 복구', '실패해도 기록이 남고, 같은 요청을 다시 보내도 안전하다', 'data', [
        ('b', 's', '취소: CANCEL_REQUESTED → /internal/missions/{id}/cancel → 목표 취소 → CANCELLED (요청과 실제 취소를 따로 기록)'),
        ('b', 's', '비상 정지: 진행 중 미션 취소 + 정지 명령 + 사용자 제어권 회수'),
        ('r', 'r', 'robot-service 재시작: 실행 중이던 미션을 INTERRUPTED 로 기록하고 정지 명령'),
        ('r', 'i', '보고 전송 실패: outbox 에 남아 다음 주기에 순서대로 재전송'),
        ('i', 'r', '미션 전달 응답 없음(DISPATCH_UNKNOWN): 같은 번호로 다시 보내도 중복 실행 없이 현재 상태를 돌려줌'),
    ]),
]

HEAD_Y = 96
TOP = HEAD_Y + 74
H = TOP + sum(58 + len(st) * ROW + 14 for *_, st in SECTIONS) + 40
S = Svg(LX['s'] + 210, H)


def halo(x, y, s, size=12, weight=500, color='#1c1c1e', anchor='start'):
    from xml.sax.saxutils import escape
    S.raw(f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" font-weight="{weight}" fill="{color}" '
          f'text-anchor="{anchor}" paint-order="stroke" stroke="#ffffff" stroke-width="5" '
          f'stroke-linejoin="round">{escape(s)}</text>', late=True)


def build():
    S.text(24, 44, '화재 점검 로봇 서비스 — 시스템 사이클', 24, 700)
    S.text(24, 70, '세로 줄 = 컨테이너, 화살표 = 호출 · 메시지(번호 순서), 동그라미 = 그 컨테이너 안에서 하는 일. '
                   '주기 · 시간 값은 코드 기준이다.', 13, 400, '#636366')
    # 레인 머리와 세로 줄
    for k, name, sub, kind in LANES:
        x = LX[k]
        S.rect(x - 100, HEAD_Y, 200, 54, fill=C[kind][1], stroke=C[kind][0], sw=1.6, rx=12)
        S.text(x, HEAD_Y + 23, name, 14, 700, C[kind][0], 'middle')
        S.text(x, HEAD_Y + 42, sub, 11.5, 400, '#636366', 'middle')
        S.raw(f'<line x1="{x}" y1="{HEAD_Y + 54}" x2="{x}" y2="{H - 30}" stroke="#c7c7cc" stroke-width="1.2" '
              f'stroke-dasharray="4 5"/>')

    y = TOP
    for sid, title, desc, kind, steps in SECTIONS:
        col = C[kind][0]
        hh = 58 + len(steps) * ROW
        S.rect(16, y, S.w - 32, hh, fill='#ffffff', stroke='#d1d1d6', sw=1, rx=14, opacity=0.55)
        S.rect(16, y, 8, hh, fill=col, stroke=col, rx=4)
        S.text(40, y + 28, f'{sid}  {title}', 16, 700, col)
        S.text(40, y + 47, desc, 12, 400, '#636366')
        sy = y + 58 + ROW / 2
        for n, (f, t, label) in enumerate(steps, 1):
            num = f'{sid}{n}'
            S.raw(f'<circle cx="{40 + 14}" cy="{sy}" r="13" fill="{col}"/>')
            S.text(54, sy + 4.5, num, 11, 700, '#ffffff', 'middle')
            if f == t:      # 컨테이너 안에서 하는 일
                x = LX[f]
                S.raw(f'<circle cx="{x}" cy="{sy}" r="7" fill="#ffffff" stroke="{col}" stroke-width="2.4"/>', late=True)
                if x + 14 + text_width(label, False) > S.w - 20:      # 오른쪽 끝을 넘으면 원의 왼쪽에
                    halo(x - 14, sy + 4.5, label, 12, 500, '#1c1c1e', 'end')
                else:
                    halo(x + 14, sy + 4.5, label, 12, 500, '#1c1c1e')
            else:
                x1, x2 = LX[f], LX[t]
                d = 1 if x2 > x1 else -1
                S.raw(f'<circle cx="{x1}" cy="{sy}" r="4" fill="{col}"/>', late=True)
                S.line([(x1, sy), (x2 - d * 2, sy)], color=col, sw=2)
                # 라벨: 화살표 위, 시작점 쪽에서 화살표 방향으로
                lx = min(x1, x2) + 10
                if lx + text_width(label, False) > S.w - 20:          # 넘치면 화살표 오른쪽 끝에 맞춘다
                    halo(max(x1, x2) - 10, sy - 6, label, 12, 500, '#1c1c1e', 'end')
                else:
                    halo(lx, sy - 6, label, 12, 500, '#1c1c1e')
            sy += ROW
        y += hh + 14
    S.render(OUT)


if __name__ == '__main__':
    build()
