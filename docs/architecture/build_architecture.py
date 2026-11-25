"""시스템 아키텍처 구성도: 컨테이너 · MSA · Spring Boot 내부 계층 · 저장소 · 로봇 브리지.

읽는 법
- 가운데 세로: 브라우저 → cdn(엣지 캐시) → web(nginx 원본) → Spring Boot 층 → analysis-service(Python).
  굵은 실선 상자 = 컨테이너. 'Spring Boot 영역'은 컨테이너가 아니라 같은 기술의 서비스를 묶어 보인 옅은 점선이다.
  그 안의 상자 하나 = 컨테이너 하나 = MSA 서비스 하나(자기 jar · 포트 · DB).
- 왼쪽: db 컨테이너. 위아래 계층이 아니라, 각 서비스의 '저장 계층'에서 옆으로 붙는 저장소다(서비스마다 자기 DB).
- 오른쪽: sim 컨테이너(로봇 시스템). robot-service 의 RosbridgeRobotAdapter 가
  WebSocket 으로 rosbridge(:9090)에, HttpClient 로 web_video_server(:8080)에 옆으로 붙는다.
- 컨테이너 이름 옆 색 표시는 Docker 네트워크(front · edge · backend · robot)다.
실행: python3 docs/architecture/build_architecture.py  →  docs/architecture/arch_01_system_architecture.svg
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / '_lib'))   # 공용 그리기 도구 docs/_lib/svg.py
from svg import C, NET, Svg, text_width

OUT = Path(__file__).resolve().parent / 'arch_01_system_architecture.svg'
S = Svg(1820, 1600)            # 높이는 마지막에 내용에 맞춘다

CX0, CX1 = 400, 1220           # 가운데 컨테이너 상자 x 범위
BUS = 1262                     # 게이트웨이 → 서비스 라우팅 선
STRIP = 34                     # 컨테이너 안 계층 한 줄 높이
HEAD = 62                      # 컨테이너 머리(이름 + 컨테이너·서비스 설명) 높이
GREEN, PURPLE, BLUE = C['spring'][0], C['bridge'][0], C['ros'][0]
LAYER_NAME = {'cache': '화면 캐시', 'bypass': '캐시 우회', 'static': '정적 화면', 'proxy': 'API 프록시', 'stream': '영상 중계', 'ws': 'WebSocket',
              'web': '웹 계층', 'svc': '업무 계층', 'repo': '저장 계층', 'adapter': '연결 계층',
              'filter': '필터 체인', 'api': 'API', 'worker': '워커'}


def nets(x, y, names):
    for n in names:
        x += S.pill(x, y, n, NET[n]) + 6


def strip_row(x, w, sy, key, items, kind):
    S.rect(x + 10, sy, w - 20, STRIP - 6, fill='#ffffff', stroke='#e5e5ea', sw=1, rx=7)
    S.text(x + 22, sy + 19, LAYER_NAME[key], 12, 700, '#636366')
    cx = x + 106
    for it in items:
        if isinstance(it, tuple) and it[0] == 'text':
            S.text(cx, sy + 19, it[1], 12, 400, '#8e8e93')
            cx += text_width(it[1], False) + 12
        elif it in ('→', '←'):
            S.text(cx + 2, sy + 19, it, 13, 700, '#8e8e93')
            cx += 18
        else:
            cx += S.chip(cx, sy + 2, it, kind) + 6


def container(x, y, w, title, kind, networks, strips, sub=None, tag=None, extra=0, right=None):
    """컨테이너 상자. sub = 둘째 줄 설명, tag = 둘째 줄 앞 표시(예: 'MSA 서비스'), extra = 아래에 덧붙일 높이.
    반환: (높이, {줄 키: 가운데 y}, 줄이 끝난 y)"""
    stroke, fill = C[kind]
    head = HEAD if sub else 44
    h = head + len(strips) * STRIP + 8 + extra
    S.rect(x, y, w, h, fill=fill, stroke=stroke, sw=2.4, rx=12)   # 실선 굵은 테두리 = 컨테이너
    S.text(x + 16, y + 26, title, 15.5, 700, stroke)
    nets(x + 24 + text_width(title, False, 15.5), y + 12, networks)
    if right:
        S.text(x + w - 14, y + 26, right, 11.5, 600, '#5856d6', 'end')
    if sub:
        sx = x + 16
        if tag:
            tw = text_width(tag, False, 11) + 16
            S.rect(sx, y + 36, tw, 19, fill='#1c1c1e', stroke='#1c1c1e', rx=5)
            S.text(sx + tw / 2, y + 49.5, tag, 11, 700, '#ffffff', 'middle')
            sx += tw + 10
        S.text(sx, y + 50, sub, 12, 500, '#3a3a3c')
    ys = {}
    for i, (key, items) in enumerate(strips):
        sy = y + head + i * STRIP
        strip_row(x, w, sy, key, items, kind)
        ys[key] = sy + (STRIP - 6) / 2
    return h, ys, y + head + len(strips) * STRIP


def build():
    S.text(24, 44, '화재 점검 로봇 서비스 — 시스템 아키텍처 (컨테이너 · MSA · Spring Boot 계층)', 24, 700)
    S.text(24, 70, '굵은 실선 상자 = 컨테이너 · 가운데 = 요청이 지나는 길(브라우저 → cdn → web → 게이트웨이 → 서비스) · 왼쪽 = 서비스별 저장소(계층 아님) · '
                   '오른쪽 = 로봇 시스템(브리지로 수평 연결)', 13, 400, '#636366')

    # 브라우저(호스트 밖)
    S.rect(560, 92, 600, 52, fill=C['client'][1], stroke=C['client'][0], sw=1.6, rx=12)
    S.text(578, 115, '브라우저 — React SPA', 15, 700, C['client'][0])
    S.text(578, 134, '로그인 · 관리자 화면(ADMIN) · 사용자 화면(관제·조종 · 점검 요청 · 작업 · 이력)', 12, 400, '#3a3a3c')
    S.line([(860, 144), (860, 202)])
    S.text(870, 176, ':8080  외부에 열린 유일한 포트 — HTTP · WebSocket(조종) · MJPEG(영상)', 12, 600, '#636366', late=True)

    host_idx = len(S.body)       # Docker 호스트 테두리는 높이를 안 뒤 이 자리에 넣는다
    S.text(30, 182, 'Docker Compose 호스트', 13, 700, '#636366')
    S.text(30, 200, '실행 컨테이너 9 · 빌드 전용 2(common-build, frontend-build)', 11.5, 400, '#8e8e93')

    # ------------------------------------------------------------ cdn (엣지 캐시)
    ch, _, _ = container(CX0, 210, CX1 - CX0, 'cdn', 'edge', ['front'],
                         [('cache', ['location /', '→', 'web:80', 'proxy_cache', '/assets/* 1년 HIT',
                                     ('text', 'index.html 은 보관 안 함 · X-Cache-Status')]),
                          ('bypass', ['location /api/ · /ws/', '→', 'web:80', 'proxy_buffering off',
                                      ('text', '사용자별 응답은 보관하지 않고 통과')])],
                         sub='nginx:1.27 · listen 80 ← 호스트 :8080 · 실제 배포에서는 외부 CDN(CloudFront 등) 자리',
                         tag='컨테이너 · 정문(CDN 엣지)')
    WY = 210 + ch + 30
    S.line([(860, 210 + ch), (860, WY)])
    S.text(870, 210 + ch + 19, '원본 요청 — 보관본이 없거나 만료됐을 때만', 11.5, 600, '#636366', late=True)

    # ------------------------------------------------------------ web (nginx, 원본)
    wh, wys, _ = container(CX0, WY, CX1 - CX0, 'web', 'edge', ['front', 'edge'],
                           [('static', ['location /', '→', 'root /usr/share/nginx/html', 'try_files → /index.html',
                                        'Cache-Control', 'gzip']),
                            ('proxy', ['location /api/', '→', 'gateway:8080', 'Host · X-Forwarded-For',
                                       'client_max_body_size 12m']),
                            ('stream', ['location ~ /api/robots/{id}/stream', '→', 'gateway', 'proxy_buffering off',
                                        'read_timeout 1h']),
                            ('ws', ['location /ws/', '→', 'gateway', 'Upgrade · Connection 헤더', 'read_timeout 1h'])],
                           sub='nginx:1.27 · listen 80 · 업무 로직 없음(정적 화면 + 프록시) · 캐시 기간을 헤더로 지시',
                           tag='컨테이너 · 원본 서버')
    fx = 40
    S.rect(fx, WY + 12, 290, 96, fill='#ffffff', stroke=C['edge'][0], sw=1.2, rx=12, dash='5 4')
    S.text(fx + 14, WY + 36, 'frontend-build', 14, 700, C['edge'][0])
    S.text(fx + 14, WY + 55, '빌드 전용 컨테이너 (node)', 11.5, 600, '#636366')
    S.text(fx + 14, WY + 73, 'npm run build → frontend/dist', 11.5, 400, '#3a3a3c', mono=True)
    S.text(fx + 14, WY + 91, 'web 이 dist 를 읽기 전용으로 마운트', 11.5, 400, '#636366')
    S.line([(fx + 290, wys['static']), (CX0, wys['static'])], color=C['edge'][0], dash='5 4')
    web_bottom = WY + wh

    # ------------------------------------------------------------ Spring Boot 층
    top = web_bottom + 30
    spring_idx = len(S.body)     # 층 테두리는 높이를 안 뒤 이 자리에 넣는다
    S.text(CX0, top + 26, 'Spring Boot 영역', 16, 700, '#5b8a68')
    tw = text_width('묶음 표시 · 컨테이너 아님', False, 11) + 16
    S.rect(CX0 + 142, top + 12, tw, 20, fill='#ffffff', stroke='#8e8e93', sw=1, rx=5, dash='3 3')
    S.text(CX0 + 142 + tw / 2, top + 26, '묶음 표시 · 컨테이너 아님', 11, 700, '#636366', 'middle')
    S.text(CX0 + 152 + tw, top + 26, '안의 실선 상자 하나하나가 컨테이너 = MSA 서비스',
           12, 500, '#636366')
    S.rect(CX0, top + 40, CX1 - CX0, 34, fill='#ffffff', stroke=GREEN, sw=1, rx=8, dash='4 3')
    S.text(CX0 + 14, top + 62, 'tp3:common  공유 jar(컨테이너 아님)', 12, 700, GREEN)
    cx = CX0 + 250
    for c in ['JwtCodec  발급·검증', 'AuthHeaders  X-User-*', 'CurrentUser']:
        cx += S.chip(cx, top + 45, c, 'spring') + 8
    gy = top + 88
    S.line([(860, web_bottom), (860, web_bottom + 12), (1140, web_bottom + 12), (1140, gy)], color='#5856d6')
    S.text(1150, web_bottom + 26, '/api · /ws', 11.5, 600, '#5856d6', late=True)

    gh, _, _ = container(CX0, gy, CX1 - CX0, 'gateway', 'edge', ['edge', 'backend'],
                         [('filter', ['AuthWebFilter', '→', 'SessionChecker', '→', 'AccessPolicy', '→', 'ServiceUrls  라우팅']),
                          ('web', ['SystemController  상태 집계',
                                   ('text', '요청마다: X-User-* 지움 → JWT 검증 → 세션 확인 → 역할 → 헤더 붙여 전달 → 변경 감사')])],
                         sub='Spring Cloud Gateway(WebFlux) · :8080 · DB 없음 · 업무 기능 없이 인증·권한·라우팅만',
                         tag='컨테이너 · 게이트웨이', right='경로별로 각 서비스에 라우팅 ↘')
    g_bottom = gy + gh

    # 업무 서비스 컨테이너 (위에서 아래로: user · robot · inspection — 서로 부르는 robot↔inspection 을 이웃하게)
    uy = g_bottom + 26
    uh, uys, _ = container(CX0, uy, CX1 - CX0, 'user-service', 'spring', ['backend'],
                           [('web', ['AuthController  /api/auth', 'AdminController  /api/admin/users', 'InternalController  /internal']),
                            ('svc', ['Bootstrap  초기 계정', ('text', '(별도 서비스 클래스 없음 — 컨트롤러가 저장 계층을 바로 사용)')]),
                            ('repo', ['UserRepository  JdbcClient', ('text', '사용자 · 역할 · 세션 · 감사 로그')])],
                           sub='사용자 · 인증 서비스 · :8081 · 자기 DB userdb', tag='컨테이너 = MSA 서비스 ①',
                           right='/api/auth · /api/admin/users')

    # robot-service: 연결 계층은 구현물까지 펼친다
    ry = uy + uh + 26
    PANEL = 168
    rh, rys, r_strips_end = container(
        CX0, ry, CX1 - CX0, 'robot-service', 'spring', ['backend', 'robot'],
        [('web', ['RobotController  /api/robots', 'TeleopHandler  WS 조종', 'InternalController  /internal']),
         ('svc', ['MissionService  미션 실행', 'ControlService  제어권', 'OutboxSender  1초', 'RobotRegistry']),
         ('repo', ['RobotRepository  JdbcClient', ('text', '로봇 설정 · 미션 · report_outbox')])],
        sub='로봇 연결 · 미션 실행 서비스 · :8083 · 자기 DB robotdb', tag='컨테이너 = MSA 서비스 ②',
        extra=PANEL, right='/api/robots · /ws/robots')
    px0, px1, py0 = CX0 + 10, CX1 - 10, r_strips_end
    S.rect(px0, py0, px1 - px0, PANEL, fill='#ffffff', stroke=PURPLE, sw=1.3, rx=8)
    S.text(CX0 + 22, py0 + 20, '연결 계층', 12, 700, PURPLE)
    S.text(CX0 + 22, py0 + 36, 'adapter/', 11, 600, '#8e8e93', mono=True)
    # 인터페이스와 구현
    ix = CX0 + 106
    iw = S.chip(ix, py0 + 8, 'RobotAdapter «interface»', 'bridge')
    S.text(ix + iw + 10, py0 + 25, '← 업무 계층이 쓰는 경계', 11.5, 500, '#636366')
    mx = CX1 - 20
    S.chip(mx - 150, py0 + 8, 'MapRenderer 웹 지도', 'gray', mono=True, w=150)
    S.rect(mx - 150 - 8 - 196, py0 + 8, 196, 24, fill='#f2f2f7', stroke='#aeaeb2', sw=1.1, rx=6, dash='4 3')
    S.text(mx - 150 - 8 - 98, py0 + 24.5, 'MockRobotAdapter 대체용', 12, 600, '#636366', 'middle', mono=True)
    # RosbridgeRobotAdapter 상세 (연결 계층 폭 전체)
    rbx0, rbx1 = ix, px1 - 10
    S.rect(rbx0, py0 + 42, rbx1 - rbx0, PANEL - 52, fill=C['bridge'][1], stroke=PURPLE, sw=1.5, rx=8)
    S.text(rbx0 + 12, py0 + 62, 'RosbridgeRobotAdapter', 13, 700, PURPLE, mono=True)
    S.text(rbx0 + 200, py0 + 62, 'RobotAdapter 구현 · 시뮬레이션과 실제 로봇 공통 · 주소와 토픽 이름은 로봇 설정(config)', 11, 500, '#636366')
    ws_y = py0 + 86
    S.chip(rbx0 + 10, ws_y - 12, 'WebSocket 클라이언트', 'bridge')
    S.text(rbx0 + 174, ws_y + 4, 'ws://sim:9090  (java.net.http.WebSocket)', 12, 700, PURPLE, mono=True)
    S.text(rbx0 + 14, ws_y + 24, '구독  /odom /scan /inspection/goal_status · bridge_status · map_pose · scan_map · map  /plan',
           11, 400, '#3a3a3c')
    S.text(rbx0 + 14, ws_y + 40, '발행  /inspection/goal · goal_cancel  /cmd_vel_teleop      서비스  /rosapi/topics(제공 기능 확인)',
           11, 400, '#3a3a3c')
    http_y = py0 + 146
    S.chip(rbx0 + 10, http_y - 12, 'HttpClient', 'ros')
    S.text(rbx0 + 102, http_y + 4, 'http://sim:8080  /snapshot · /stream  (ros_compressed, 압축 JPEG)', 12, 700, BLUE, mono=True)

    iy = ry + rh + 46
    ih, iys, _ = container(CX0, iy, CX1 - CX0, 'inspection-service', 'spring', ['backend'],
                           [('web', ['ApiController  /api', 'InternalController  /internal']),
                            ('svc', ['TaskService  작업·사건', 'AnalysisTrigger  5초', 'RestClient  robot · analysis']),
                            ('repo', ['Store  JdbcClient', 'photos 볼륨  사진 파일', ('text', '지점 · 작업 · 사건 · 관측 · 판정')])],
                           sub='점검 업무 서비스 · :8082 · 자기 DB inspectiondb', tag='컨테이너 = MSA 서비스 ③',
                           right='/api/points · /api/inspections · /api/observations')
    spring_bottom = iy + ih + 14
    S.rect(CX0 - 20, top, CX1 - CX0 + 80, spring_bottom - top, fill='#e9f7ee', stroke=GREEN, sw=1.4, rx=16,
           dash='2 6', opacity=0.55)   # 컨테이너가 아니라 묶음이라 옅은 바탕 + 점선
    S.body.insert(spring_idx, S.body.pop())

    # analysis-service (Spring 밖)
    ay = spring_bottom + 36
    ah, ays, _ = container(CX0, ay, CX1 - CX0, 'analysis-service', 'py', ['backend'],
                           [('api', ['POST /jobs', '/api/admin/analysis/criteria  판정 기준']),
                            ('worker', ['LISTEN analysis_job', 'FOR UPDATE SKIP LOCKED', '밝기 · 선명도 → OK / RETAKE'])],
                           sub='사진 분석 서비스 · Python FastAPI(Spring 아님) · :8084 · 자기 DB analysisdb',
                           tag='컨테이너 = MSA 서비스 ④', right='/api/admin/analysis')
    bottom = ay + ah

    # 게이트웨이 라우팅 선
    S.line([(CX1, gy + 40), (BUS, gy + 40), (BUS, ay + 26)], color='#5856d6', end=False)
    for y0 in (uy, ry, iy, ay):
        S.line([(BUS, y0 + 26), (CX1 + 2, y0 + 26)], color='#5856d6')

    # 서비스 간 내부 호출(/internal)
    S.line([(560, g_bottom), (560, uy)], color=GREEN)
    S.text(570, g_bottom + 17, '세션 확인 /internal/users/{id}/session · 감사 /internal/audit', 11.5, 600, GREEN, late=True)
    S.line([(560, iy), (560, ry + rh)], color=GREEN)
    S.text(570, ry + rh + 28, '미션 요청 /internal/missions (취소 · 로봇 조회)', 11.5, 600, GREEN, late=True)
    S.line([(930, ry + rh), (930, iy)], color=GREEN)
    S.text(940, ry + rh + 28, '결과 보고 /internal/tasks/{id}/… (outbox 재전송)', 11.5, 600, GREEN, late=True)
    S.line([(560, iy + ih), (560, ay)], color=C['py'][0])
    S.text(570, iy + ih + 31, '분석 요청 POST /jobs', 11.5, 600, C['py'][0], late=True)
    S.line([(930, ay), (930, iy + ih)], color=C['py'][0])
    S.text(940, iy + ih + 31, '사진 받기 · 결과 보내기 /internal/observations/{id}/…', 11.5, 600, C['py'][0], late=True)

    # ------------------------------------------------------------ 왼쪽: 저장소 (내용만큼만, 아랫선 = analysis-service 아랫선)
    # 서비스의 저장 계층에서 아래로 내려와 자기 DB 로 들어간다. 선이 서로 겹치지 않도록
    # 위쪽 서비스일수록 바깥(왼쪽) 세로선을 쓰고, DB 칸은 위에서부터 user · robot · inspection · analysis 순서.
    dx0, dx1 = 40, 262
    rows = [('userdb', uys['repo'], 'user_svc', 'JDBC'), ('robotdb', rys['repo'], 'robot_svc', 'JDBC'),
            ('inspectiondb', iys['repo'], 'inspection_svc', 'JDBC'), ('analysisdb', ays['worker'], 'analysis_svc', 'psycopg')]
    d_bottom = bottom
    d_top = d_bottom - (112 + len(rows) * 52 + 4)
    e0 = d_top + 112
    S.rect(dx0, d_top, dx1 - dx0, d_bottom - d_top, fill='#fffaf6', stroke=C['data'][0], sw=2.4, rx=16)
    S.text(dx0 + 16, d_top + 26, 'db', 17, 700, C['data'][0])
    nets(dx0 + 48, d_top + 12, ['backend'])
    tw = text_width('컨테이너 · 저장소', False, 11) + 16
    S.rect(dx0 + 16, d_top + 36, tw, 19, fill='#1c1c1e', stroke='#1c1c1e', rx=5)
    S.text(dx0 + 16 + tw / 2, d_top + 49.5, '컨테이너 · 저장소', 11, 700, '#ffffff', 'middle')
    S.text(dx0 + 16, d_top + 74, 'PostgreSQL 17 · pgdata 볼륨', 12, 600, '#3a3a3c')
    S.text(dx0 + 16, d_top + 92, '계층 아님 · 서비스마다 자기 DB', 12, 700, C['data'][0])
    lanes = [306, 326, 346, 366]
    for i, (name, ry_, sub, proto) in enumerate(rows):
        ey = e0 + i * 52 + 22
        S.rect(dx0 + 14, ey - 22, dx1 - dx0 - 28, 44, fill=C['data'][1], stroke=C['data'][0], sw=1.3, rx=10)
        S.text(dx0 + 28, ey - 3, name, 13.5, 700, C['data'][0], mono=True)
        S.text(dx0 + 28, ey + 14, f'계정 {sub} · {proto}', 11, 400, '#636366')
        pts = [(CX0, ry_), (lanes[i], ry_), (lanes[i], ey), (dx1, ey)] if abs(ry_ - ey) > 2 else [(CX0, ey), (dx1, ey)]
        S.line(pts, color=C['data'][0], start=True)

    # ------------------------------------------------------------ 오른쪽: 로봇 시스템 (윗선 = robot-service 윗선)
    sx0, sx1 = 1316, 1790
    sim_idx = len(S.body)        # 테두리는 내용 높이를 안 뒤 이 자리에 넣는다

    def node(x, y, w, h, title, lines, kind):
        S.rect(x, y, w, h, fill=C[kind][1], stroke=C[kind][0], sw=1.4, rx=10)
        S.text(x + 12, y + 21, title, 13.5, 700, C[kind][0])
        for i, ln in enumerate(lines):
            S.text(x + 12, y + 40 + i * 17, ln, 11.5, 400, '#3a3a3c')

    s_top = ry
    lx, lw = sx0 + 16, 222
    rx_, rw = lx + lw + 26, sx1 - 18 - (lx + lw + 26)
    rb_y = ws_y - 30                         # rosbridge 상자 = WebSocket 줄 높이
    vid_y = http_y - 26                      # web_video_server 상자 = HttpClient 줄 높이
    wd_y = s_top + 104
    node(rx_, wd_y, rw, 70, 'cmd_vel_watchdog', ['조종 명령 중계', '0.5초 끊기면 정지'], 'ros')
    node(lx, rb_y, lw, 60, 'rosbridge_websocket :9090', ['WebSocket(JSON) ↔ ROS 토픽'], 'bridge')
    node(rx_, rb_y, rw, 84, 'nav2_goal_bridge', ['목표 계약 ↔ Nav2 액션', '실패 사유 판정 · 재시도 1회', '지도·위치·스캔 좌표 변환'], 'bridge')
    node(lx, vid_y, lw, 52, 'web_video_server :8080', ['카메라 토픽 → 압축 영상·스냅샷'], 'ros')
    nav_y = rb_y + 84 + 44
    node(rx_, nav_y, rw, 96, 'Nav2', ['경로: Theta* 직선(한 번 계획)', '추종: MPPI(실시간 회피)', '위치: AMCL / slam_toolbox'], 'ros')
    gz_y = nav_y + 96 + 44
    node(lx, gz_y, sx1 - sx0 - 34, 78, 'Gazebo — TurtleBot3 Waffle Pi',
         ['라이다 360° 0.16~8m (5Hz · 360점) · Pi 카메라 640×480', '바퀴 구동(diff drive) · 시험용 공장 월드'], 'dev')

    # sim 안쪽 흐름
    S.line([(lx + lw, ws_y), (rx_, ws_y)], color=PURPLE, start=True)                       # rosbridge ⇄ 브리지
    cx_ = rx_ + rw / 2
    S.line([(cx_, rb_y + 84), (cx_, nav_y)], color=BLUE, start=True)                       # 브리지 ⇄ Nav2
    S.text(cx_ + 8, rb_y + 84 + 27, 'NavigateToPose 액션', 11, 600, BLUE, late=True)
    S.line([(cx_, nav_y + 96), (cx_, gz_y)], color=BLUE, start=True)                       # Nav2 ⇄ Gazebo
    S.text(cx_ - 8, nav_y + 96 + 27, '/scan · /odom · /tf ↑  /cmd_vel ↓', 11, 600, BLUE, 'end', late=True)
    tx = lx + lw - 40                                                                     # rosbridge → watchdog
    S.line([(tx, rb_y), (tx, wd_y + 35), (rx_, wd_y + 35)], color=BLUE)
    S.text(tx - 6, wd_y + 30, '/cmd_vel_teleop', 11, 600, BLUE, 'end', late=True)
    S.line([(rx_ + rw, wd_y + 35), (sx1 - 7, wd_y + 35), (sx1 - 7, gz_y - 14), (sx1 - 40, gz_y - 14), (sx1 - 40, gz_y)],
           color=BLUE)                                                                    # watchdog → Gazebo
    S.text(sx1 - 46, gz_y - 20, '/cmd_vel', 11, 600, BLUE, 'end', late=True)

    # 수평 브리지 연결: RosbridgeRobotAdapter 의 두 클라이언트 → sim
    S.line([(rbx1, ws_y), (lx, ws_y)], color=PURPLE, sw=2.4, start=True)
    S.line([(rbx1, http_y), (lx, http_y)], color=BLUE, sw=2, start=True)
    ny = gz_y + 78 + 16
    S.rect(sx0 + 16, ny, sx1 - sx0 - 32, 76, fill='#ffffff', stroke=PURPLE, sw=1.2, rx=10)
    S.text(sx0 + 30, ny + 24, '브리지 연결 (수평)', 13, 700, PURPLE)
    S.text(sx0 + 30, ny + 44, 'RosbridgeRobotAdapter ⇄ rosbridge ⇄ nav2_goal_bridge', 11.5, 600, '#3a3a3c', mono=True)
    S.text(sx0 + 30, ny + 64, '웹은 목표 단위 계약(/inspection/*)만 알고 Nav2 를 모른다', 11.5, 400, '#636366')
    s_bottom = ny + 76 + 16
    S.body[sim_idx:sim_idx] = [f'<rect x="{sx0}" y="{s_top}" width="{sx1 - sx0}" height="{s_bottom - s_top}" rx="16" '
                               f'fill="#f5fbfe" stroke="{BLUE}" stroke-width="2.4"/>']
    S.text(sx0 + 16, s_top + 26, 'sim', 17, 700, BLUE)
    nets(sx0 + 56, s_top + 12, ['robot'])
    tw = text_width('컨테이너 · 로봇 시스템', False, 11) + 16
    S.rect(sx0 + 16, s_top + 36, tw, 19, fill='#1c1c1e', stroke='#1c1c1e', rx=5)
    S.text(sx0 + 16 + tw / 2, s_top + 49.5, '컨테이너 · 로봇 시스템', 11, 700, '#ffffff', 'middle')
    S.text(sx0 + 16, s_top + 76, 'ROS 2 Humble · Gazebo(헤드리스) · amd64', 12, 600, '#3a3a3c')
    S.text(sx0 + 16, s_top + 94, '실제 로봇은 이 상자 전체를 대체한다(같은 노드 · 토픽)', 12, 400, '#636366')

    # Docker 호스트 테두리
    S.body.insert(host_idx, f'<rect x="16" y="160" width="1790" height="{bottom - 160 + 30}" rx="18" fill="none" '
                            f'stroke="#aeaeb2" stroke-width="1.2" stroke-dasharray="8 6"/>')

    # 범례
    ly = bottom + 64
    x = 30
    S.text(x, ly + 4, '선:', 12, 700, '#3a3a3c')
    for col, label in [('#5856d6', '외부 요청 라우팅(/api · /ws)'), (GREEN, '서비스 간 내부 HTTP(/internal)'),
                       (C['py'][0], '분석 요청·결과'), (C['data'][0], 'DB 접속(자기 DB 만)'),
                       (PURPLE, '로봇 브리지(WebSocket)'), (BLUE, '영상 HTTP · ROS 2 토픽·액션')]:
        S.line([(x + 30, ly), (x + 64, ly)], color=col)
        S.text(x + 70, ly + 4, label, 12, 500, '#3a3a3c', late=True)
        x += 92 + text_width(label, False)
    x += 20
    S.text(x, ly + 4, '네트워크:', 12, 700, '#3a3a3c')
    x += 62
    for n in NET:
        x += S.pill(x, ly - 9, n, NET[n]) + 8
    S.h = ly + 30
    S.render(OUT)


if __name__ == '__main__':
    build()
