"""기술 스택 도면 + 설명서: 시스템 구성도(system_architecture.svg)의 계층마다 무슨 기술을 쓰는가.

읽는 법
- 맨 위 두 줄: 구성도의 요청 경로(브라우저 → cdn → web → gateway → 서비스 → db)와 로봇 쪽 연결을 기술 이름으로 다시 적은 것.
- 그 아래 띠 하나 = 구성도의 한 영역(색도 구성도와 같다). 왼쪽 = 영역 이름과 컨테이너, 오른쪽 카드 = 기술 하나(이름 · 버전 · 하는 일).
이 파일의 STACK 하나가 SVG 와 Markdown 두 문서의 원본이다. 버전의 원본은 각 항목에 적힌 파일(package.json · pom.xml ·
requirements.txt · Dockerfile · compose.yaml)이므로, 그 파일을 바꾸면 STACK 도 고친 뒤 다시 생성한다.
실행: python3 docs/architecture/build_tech_stack.py  →  docs/architecture/tech_stack.svg · TECH_STACK.md
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / '_lib'))   # 공용 그리기 도구 docs/_lib/svg.py
from svg import C, Svg, text_width

HERE = Path(__file__).resolve().parent
OUT_SVG, OUT_MD = HERE / 'tech_stack.svg', HERE / 'TECH_STACK.md'
W = 1640
S = Svg(W, 2000)               # 높이는 마지막에 내용에 맞춘다
GRAY = '#636366'

# 영역: (제목, 색, 컨테이너, 왼쪽 설명 줄, 버전 원본 파일, 한 줄 소개(MD), [(기술, 버전, 하는 일(SVG·MD), 왜 쓰는가(MD))])
STACK = [
    ('화면', 'client', 'frontend-build → web', ['브라우저에서 도는 React SPA', '빌드 결과 dist/ 를 web 이 서빙'],
     'web/nginx/frontend/package.json',
     '브라우저가 받아 실행하는 React SPA. `frontend-build` 컨테이너가 `dist/` 로 빌드하고 `web`(nginx)이 그대로 내보낸다.', [
        ('React', '18.3.1', '화면 조립(SPA) · 함수형 컴포넌트', '화면을 부품(컴포넌트)으로 나누고, 상태가 바뀐 부분만 다시 그린다.'),
        ('TypeScript', '5.6.3', '타입 검사(tsc -b) 후 빌드', 'API 응답 모양을 타입으로 적어 두어, 틀린 사용을 빌드 때 잡는다.'),
        ('Vite', '5.4.11', '개발 서버 · 번들 빌드(dist/)', '빌드가 빠르고, 결과 파일 이름에 해시를 붙여 `/assets/*` 를 오래 캐시할 수 있게 한다.'),
        ('React Router', '6.28.0', '주소 ↔ 화면 연결(화면 이동)', '새로 고침 없이 화면을 바꾼다. 어느 주소로 들어와도 `web` 이 `index.html` 을 돌려준다.'),
        ('Material Symbols', '0.27.2', '아이콘 글꼴', 'SF Symbols 는 라이선스상 웹에 넣을 수 없어 대신 쓴다(`Icon.tsx` 가 이름을 매핑).'),
        ('Galmuri', '2.40', '픽셀 표시 모드 글꼴(OFL)', '픽셀 모드 스킨(`pixel.css`)에서만 쓰는 한글 픽셀 글꼴.'),
        ('Canvas 2D', '브라우저 표준', '관제 지도 · 로봇 · 경로 그리기', '지도 라이브러리 없이 직접 그린다(`mapGeo.ts`). 0.2초 폴링 + 위치 보간.'),
        ('WebSocket · MJPEG', '브라우저 표준', '방향키 조종 · 실시간 카메라', '조종은 양방향 연결이 필요하고, 영상은 `<img>` 하나로 받는 MJPEG 로 충분하다.'),
     ]),
    ('엣지', 'edge', 'cdn · web', ['외부에 열린 유일한 포트 :8080', 'cdn = 캐시, web = 원본 서버'],
     'compose.yaml · web/nginx/{cdn,web}/default.conf',
     '브라우저가 처음 만나는 두 컨테이너. 둘 다 nginx 이고 업무 로직은 없다.', [
        ('nginx', '1.27-alpine', 'cdn · web 두 컨테이너의 서버', '설정 파일만으로 캐시 · 정적 서빙 · 프록시를 모두 한다.'),
        ('proxy_cache', 'nginx 기능', 'cdn: /assets/* 만 보관(1년)', 'CDN 엣지 역할. `index.html` · `/api` · `/ws` 는 보관하지 않고 통과시킨다. 실제 배포에서는 외부 CDN 자리.'),
        ('정적 서빙 · gzip', 'nginx 기능', 'web: dist/ 서빙 · Cache-Control', '캐시 기간은 원본 서버(`web`)가 헤더로 지시하고 `cdn` 이 따른다.'),
        ('리버스 프록시', 'nginx 기능', 'web: /api · /ws → gateway', 'WebSocket 은 Upgrade 헤더를 넘기고, 영상 스트림은 버퍼링을 끈다.'),
     ]),
    ('게이트웨이', 'edge', 'gateway', ['인증 · 권한 · 라우팅만', 'DB 없음 · 업무 기능 없음'],
     'web/spring/gateway/pom.xml · web/spring/common/pom.xml',
     '모든 `/api` · `/ws` 요청이 지나는 한 곳. 여기서 인증 · 역할 확인 · 감사 기록을 하고 서비스로 넘긴다.', [
        ('Spring Cloud Gateway', '2025.0.0', '경로별 라우팅 · 필터 체인', '인증 · 권한을 서비스마다 다시 만들지 않고 한 곳에 둔다(규칙은 `application.yml`).'),
        ('Spring WebFlux', 'Boot 3.5.6', '논블로킹 서버', '게이트웨이는 받아서 넘기는 일만 하므로 연결을 붙잡지 않는 방식이 맞다(영상 · WebSocket 도 지난다).'),
        ('JWT (jjwt)', '0.12.6', 'HttpOnly 쿠키 토큰 발급 · 검증', '토큰을 스크립트가 읽지 못하는 쿠키에 둔다. 발급 · 검증 코드는 공유 jar `tp3:common` 의 `JwtCodec`.'),
        ('Spring Boot Actuator', '3.5.6', '상태 검사(/actuator/health)', 'compose 가 컨테이너 상태를 확인하는 데 쓴다(Spring 서비스 공통).'),
     ]),
    ('업무 서비스', 'spring', 'user · inspection · robot-service', ['컨테이너 하나 = MSA 서비스 하나', '자기 jar · 포트 · DB'],
     'web/spring/*/pom.xml · web/spring/*/Dockerfile',
     'Spring Boot 서비스 셋(`user-service` · `inspection-service` · `robot-service`). 같은 뼈대를 쓰고 서비스마다 자기 DB 를 가진다.', [
        ('Java', '21 (Temurin)', '언어 · 실행 환경(JDK)', '장기 지원(LTS) 판. 레코드 · 패턴 매칭으로 코드가 짧아진다.'),
        ('Spring Boot', '3.5.6', '서비스 뼈대 · 내장 서버', '설정 없이 jar 하나로 실행된다.'),
        ('Spring Web MVC', 'starter-web', 'REST API(@RestController)', '요청 하나에 스레드 하나인 단순한 방식. 업무 서비스에는 이것으로 충분하다.'),
        ('Spring JDBC', 'JdbcClient', 'SQL 직접 작성(JPA 안 씀)', '표가 단순하고 `SKIP LOCKED` 같은 SQL 을 그대로 써야 해서 ORM 을 두지 않았다.'),
        ('Flyway', 'Boot 관리 버전', '스키마 마이그레이션(V…sql)', '서비스가 시작할 때 자기 DB 스키마를 스스로 맞춘다.'),
        ('PostgreSQL JDBC', 'Boot 관리 버전', 'DB 드라이버', 'PostgreSQL 접속.'),
        ('RestClient', 'Spring 6', '서비스 간 /internal 호출', '서비스끼리는 내부 HTTP 로만 부른다(상대 주소는 compose 서비스 이름).'),
        ('Spring WebSocket', 'starter-websocket', '조종 채널(robot-service)', '방향키 조종 명령을 끊김 없이 받는다(`TeleopHandler`).'),
        ('java.net.http', 'JDK 내장', 'rosbridge WebSocket · 영상 HTTP', '로봇 연결(`RosbridgeRobotAdapter`)에 외부 라이브러리를 더하지 않는다.'),
        ('Spring Security Crypto', 'BCrypt', '비밀번호 해시(user-service)', 'Spring Security 전체가 아니라 해시 기능만 쓴다(인증은 게이트웨이가 한다).'),
        ('Bean Validation', 'starter-validation', '요청 값 검증', '잘못된 입력을 컨트롤러에 들어오기 전에 막는다.'),
        ('Maven', '3.9', '빌드 · 공유 jar tp3:common', '서비스는 시작할 때 `mvn package` 로 빌드한다. 공유 코드는 `common-build` 가 m2 볼륨에 설치.'),
     ]),
    ('분석 서비스', 'py', 'analysis-service', ['Spring 이 아닌 Python 서비스', '사진 품질 분석 · 판독기'],
     'web/python/analysis-service/requirements.txt · Dockerfile',
     '관측 사진을 분석하고 규칙대로 판독하는 Python 서비스. 영상 계산 때문에 Spring 이 아닌 Python 으로 따로 두었다.', [
        ('Python', '3.12-slim', '언어 · 실행 환경', '영상 계산 라이브러리(numpy · Pillow)를 바로 쓴다.'),
        ('FastAPI', '0.115.6', 'API(/jobs · /check · /checkers)', '요청 · 응답 모양을 타입으로 적으면 검증까지 해 준다.'),
        ('Uvicorn', '0.32.1', 'ASGI 서버 :8084', 'FastAPI 를 실행하는 서버.'),
        ('psycopg', '3.2.3', 'DB 접속 · LISTEN 작업 큐', 'PostgreSQL 의 LISTEN/NOTIFY 를 그대로 쓸 수 있다.'),
        ('NumPy', '2.1.3', '영상 계산(밝기 · 선명도 · 색)', '판독기(OBJECT · GAUGE · LAMP · THERMAL)의 계산. 학습 모델은 아직 없다.'),
        ('Pillow', '11.0.0', '사진 열기 · 영역 자르기', 'OpenCV 없이도 필요한 처리는 된다(이미지가 가볍다).'),
        ('httpx', '0.28.1', '사진 받기 · 결과 보내기', 'inspection-service 의 `/internal` 을 부른다.'),
        ('python-multipart', '0.0.20', '사진 업로드 받기(POST /check)', 'FastAPI 가 파일 업로드를 받을 때 필요하다.'),
     ]),
    ('저장소', 'data', 'db', ['계층이 아니라 서비스 옆에 붙는 저장소', '서비스마다 자기 DB · 자기 계정'],
     'compose.yaml · web/postgres/',
     'PostgreSQL 컨테이너 하나에 서비스별 DB(`userdb` · `inspectiondb` · `robotdb` · `analysisdb`)를 둔다. 서비스는 자기 DB 만 본다.', [
        ('PostgreSQL', '17', '서비스마다 자기 DB(4개)', '컨테이너는 하나지만 DB 와 계정을 나눠 MSA 의 "서비스별 저장소"를 지킨다.'),
        ('LISTEN / NOTIFY', 'PostgreSQL 기능', '분석 작업 알림(폴링 없이)', '메시지 브로커(Kafka · RabbitMQ)를 따로 띄우지 않고 DB 로 작업을 알린다.'),
        ('FOR UPDATE SKIP LOCKED', 'PostgreSQL 기능', '작업 큐: 한 작업은 한 워커만', '워커가 여럿이어도 같은 작업을 두 번 집지 않는다.'),
        ('Docker 볼륨', 'pgdata · photos', 'DB 파일 · 관측 사진 보관', '컨테이너를 다시 만들어도 데이터가 남는다.'),
     ]),
    ('로봇', 'ros', 'sim', ['시뮬레이션 컨테이너(amd64)', '실제 로봇은 이 상자 전체를 대체'],
     'ros/sim/Dockerfile · ros/sim/src/config/nav2_params.yaml',
     'ROS 2 로봇 시스템. 지금은 Gazebo 시뮬레이션이고, 실제 로봇도 같은 노드 · 토픽을 쓴다. 웹과는 rosbridge 로만 만난다.', [
        ('ROS 2', 'Humble', '로봇 미들웨어(토픽 · 액션)', 'TurtleBot3 와 Nav2 가 공식 지원하는 장기 지원 판.'),
        ('Gazebo Classic', 'amd64 · Xvfb', '물리 시뮬레이션(헤드리스)', '실물 없이 주행 · 센서를 시험한다. amd64 패키지만 있어 Apple Silicon 에서는 에뮬레이션으로 돈다.'),
        ('TurtleBot3', 'Waffle Pi', '로봇 모델(라이다 · 카메라)', '보유한 실물과 같은 모델.'),
        ('Nav2', 'Humble', '자율 주행 묶음(계획 · 제어)', '목표 좌표를 주면 경로를 짜고 따라간다(NavigateToPose 액션).'),
        ('Theta* 계획기', 'nav2_theta_star', '직선 위주 전역 경로', '격자를 따라 꺾이는 경로 대신 보이는 점끼리 곧게 잇는다.'),
        ('MPPI 제어기', 'nav2_mppi', '경로 추종 · 실시간 회피', '후보 궤적을 많이 굴려 보고 가장 나은 속도를 고른다.'),
        ('AMCL', 'nav2_amcl', '저장 지도에서 위치 추정', '라이다 스캔을 저장 지도에 맞춰 로봇 위치를 잡는다(nav 모드).'),
        ('slam_toolbox', 'Humble', '지도 작성(SLAM 모드)', '운영 지도 `ros/maps/site.*` 를 만든다.'),
        ('rosbridge_server', ':9090', 'ROS 토픽 ↔ WebSocket(JSON)', 'Java 서비스가 ROS 를 설치하지 않고도 토픽을 주고받는다.'),
        ('web_video_server', ':8080', '카메라 → MJPEG · 스냅샷', '카메라 토픽을 HTTP 영상으로 바꿔 브라우저까지 중계할 수 있게 한다.'),
        ('compressed_image_transport', 'Humble', '카메라 JPEG 압축 전송', '실제 로봇에서 Wi-Fi 로 원본 영상을 보내지 않기 위해서다.'),
        ('rclpy', 'Python 3.10', '브리지 노드(목표 · 감시 · 투척)', '`nav2_goal_bridge` · `cmd_vel_watchdog` · `mock_launcher` 를 Python 노드로 짠다.'),
     ]),
    ('실행 · 빌드 · 시험', 'dev', 'compose.yaml', ['명령 하나로 전체 실행', '코드는 이미지에 굽지 않고 마운트'],
     'compose.yaml · scripts/ · docs/',
     '전체를 한 번에 띄우고 확인하는 도구.', [
        ('Docker Compose', 'v2', '컨테이너 11개 · 네트워크 4개', '실행 9 + 빌드용 2. 네트워크(front · edge · backend · robot)로 서로 닿는 범위를 나눈다.'),
        ('빌드용 컨테이너', 'maven:3.9 · node:20', 'common-build · frontend-build', '호스트에 JDK · Node 를 설치하지 않아도 된다(`docs/guide/BUILD_CONTAINERS.md`).'),
        ('E2E 시험', 'Python 3 표준 라이브러리', '실제 스택에 대고 전체 흐름 확인', '단위 테스트 대신 떠 있는 스택에 요청을 보내 본다(`scripts/e2e_test.py` · `e2e_scenarios.py`).'),
        ('문서 도면', 'Python → SVG', 'build_*.py 로 SVG 생성', '도면을 손으로 고치지 않고 스크립트에서 다시 만든다.'),
     ]),
    ('실제 로봇', 'gray', '보유 장비 · 연동 예정', ['아직 코드가 붙지 않은 하드웨어', '제원은 README 9절'],
     'README.md 9절',
     '보유한 하드웨어. 지금은 시뮬레이션으로만 돌고, 실물 연동은 `docs/plan/SCHEDULE.md` 의 일정대로 한다.', [
        ('TurtleBot3 Waffle Pi', '실물', 'Raspberry Pi + OpenCR 보드', 'sim 컨테이너 자리를 대신한다(같은 노드 · 토픽, 목표 브리지도 같은 코드).'),
        ('LDS 라이다 · IMX219', 'TurtleBot3', '360° 거리 측정 · 점검 사진', '주행(Nav2)과 관측 사진의 입력.'),
        ('Jetson Nano 4GB', 'JetBot Mini', '순찰 · 화재 감지(예정)', '지금은 `fire.sh` 가 감지 보고(`/patrol/detection`)를 대신 보낸다.'),
        ('투척기 시리얼 브리지', 'launcher_bridge.py', '투척 기구 연결(만들어만 둠)', '시뮬레이션에서는 `mock_launcher.py` 가 투척 계약에 답한다.'),
     ]),
]

# 구성도의 요청 경로를 기술 이름으로: (컨테이너, 기술, 색)
PATH_WEB = [('브라우저', 'React 18 · TypeScript', 'client'), ('cdn', 'nginx 캐시', 'edge'), ('web', 'nginx 원본', 'edge'),
            ('gateway', 'Spring Cloud Gateway', 'edge'), ('서비스 ×4', 'Spring Boot 3 · FastAPI', 'spring'),
            ('db', 'PostgreSQL 17', 'data')]
PATH_ROBOT = [('robot-service', 'RosbridgeRobotAdapter', 'spring'), ('rosbridge', 'WebSocket(JSON) :9090', 'bridge'),
              ('nav2_goal_bridge', 'rclpy · 목표 단위 계약', 'bridge'), ('Nav2', 'Theta* · MPPI · AMCL', 'ros'),
              ('Gazebo', 'TurtleBot3 Waffle Pi', 'dev')]

LABEL_W, COLS, GAP, CARD_H = 270, 4, 12, 62
CARD_W = (W - 80 - LABEL_W - 16 - (COLS - 1) * GAP) / COLS


def flow(y, label, steps, both):
    """요청 경로 한 줄. both = 양방향 화살표."""
    S.text(40, y + 31, label, 12.5, 700, GRAY)
    x0 = 150
    bw = (W - 40 - x0 - (len(steps) - 1) * 44) / len(steps)
    for i, (name, tech, kind) in enumerate(steps):
        x = x0 + i * (bw + 44)
        S.rect(x, y, bw, 52, fill=C[kind][1], stroke=C[kind][0], sw=1.6, rx=10)
        S.text(x + bw / 2, y + 22, name, 13.5, 700, C[kind][0], 'middle', mono=True)
        S.text(x + bw / 2, y + 41, tech, 11.5, 500, '#3a3a3c', 'middle')
        if i:
            S.line([(x - 40, y + 26), (x - 4, y + 26)], start=both)
    return y + 52


def band(y, title, kind, containers, notes, items):
    stroke, fill = C[kind]
    planned = kind == 'gray'
    if planned:
        fill = '#f7f7fa'
    rows = -(-len(items) // COLS)
    h = max(16 + rows * (CARD_H + GAP) + 4, 112)
    S.rect(40, y, W - 80, h, fill=fill, stroke=stroke, sw=2 if not planned else 1.4, rx=14, dash='6 5' if planned else None)
    S.text(58, y + 32, title, 18, 700, stroke)
    S.text(58, y + 54, containers, 12, 600, '#1c1c1e', mono=not planned)
    for i, n in enumerate(notes):
        S.text(58, y + 76 + i * 18, n, 11.5, 400, GRAY)
    for i, (name, ver, role, _) in enumerate(items):
        x = 40 + LABEL_W + (i % COLS) * (CARD_W + GAP)
        cy = y + 16 + (i // COLS) * (CARD_H + GAP)
        vw = text_width(ver, True, 10.5) + 14
        for label, used, size in ((role, text_width(role, False, 11.5), 'role'), (name, text_width(name, False, 13.5) + vw + 10, 'name')):
            if used > CARD_W - 24:
                print(f'  너무 김({size}): {label} — {used:.0f} > {CARD_W - 24:.0f}')
        S.rect(x, cy, CARD_W, CARD_H, fill='#ffffff', stroke=stroke, sw=1.1, rx=9, dash='4 3' if planned else None)
        S.text(x + 12, cy + 25, name, 13.5, 700, '#1c1c1e')
        S.rect(x + CARD_W - vw - 10, cy + 10, vw, 20, fill=fill, stroke=stroke, sw=0.8, rx=10)
        S.text(x + CARD_W - 10 - vw / 2, cy + 24, ver, 10.5, 600, stroke if not planned else GRAY, 'middle', mono=True)
        S.text(x + 12, cy + 47, role, 11.5, 400, '#3a3a3c')
    return y + h


def build_svg():
    n = sum(len(layer[6]) for layer in STACK)
    S.text(40, 46, '화재 점검 로봇 서비스 — 기술 스택', 24, 700)
    S.text(40, 72, f'시스템 구성도(system_architecture.svg)의 영역마다 쓰는 기술 · 띠 하나 = 구성도의 한 영역(같은 색) · 카드 하나 = 기술 하나(이름 · 버전 · 하는 일) · 모두 {n}개',
           13, 400, GRAY)
    y = flow(98, '요청이 지나는 길', PATH_WEB, False)
    y = flow(y + 14, '로봇 쪽 연결', PATH_ROBOT, True)
    y += 26
    for title, kind, containers, notes, _, _, items in STACK:
        y = band(y, title, kind, containers, notes, items) + 14
    S.text(40, y + 16, '버전의 원본: package.json(화면) · pom.xml(Spring) · requirements.txt(Python) · Dockerfile · compose.yaml(이미지). '
                       '글 설명과 "왜 쓰는가"는 같은 폴더의 TECH_STACK.md.', 12, 500, GRAY)
    S.h = y + 40
    S.render(OUT_SVG)


def build_md():
    def cell(s):
        return s.replace('|', '\\|')

    out = ['# 기술 스택', '',
           '> 이 파일은 `build_tech_stack.py` 가 만든다. 직접 고치지 말고 스크립트의 `STACK` 을 고친 뒤 다시 생성한다',
           '> (`python3 docs/architecture/build_tech_stack.py`). 그림은 [tech_stack.svg](tech_stack.svg).', '',
           '[시스템 구성도](system_architecture.svg)의 영역마다 **무슨 기술을, 어디에, 왜** 쓰는지 적는다.',
           '영역 순서는 구성도에서 요청이 지나는 순서와 같다.', '',
           '![기술 스택](tech_stack.svg)', '',
           '## 한눈에', '',
           '요청이 지나는 길: ' + ' → '.join(f'`{n}`({t})' for n, t, _ in PATH_WEB), '',
           '로봇 쪽 연결: ' + ' ⇄ '.join(f'`{n}`({t})' for n, t, _ in PATH_ROBOT), '',
           '| 영역 | 컨테이너 | 핵심 기술 |', '| --- | --- | --- |']
    for title, _, containers, _, _, _, items in STACK:
        core = ' · '.join(f'{name} {ver}' if ver[0].isdigit() else name for name, ver, _, _ in items[:4])
        out.append(f'| [{title}](#{title.replace(" · ", "--").replace(" ", "-")}) | {containers} | {core} |')
    for title, _, containers, _, source, intro, items in STACK:
        out += ['', f'## {title}', '', intro, '',
                f'- 컨테이너: {containers}', f'- 버전의 원본: `{source}`', '',
                '| 기술 | 버전 | 하는 일 | 왜 쓰는가 |', '| --- | --- | --- | --- |']
        out += [f'| **{name}** | {ver} | {cell(role)} | {cell(why)} |' for name, ver, role, why in items]
    out += ['', '## 일부러 쓰지 않는 것', '',
            '| 쓰지 않는 것 | 대신 | 이유 |', '| --- | --- | --- |',
            '| JPA · ORM | Spring JDBC(`JdbcClient`) + Flyway | 표가 단순하고 SQL 을 그대로 써야 하는 곳(작업 큐)이 있다 |',
            '| 메시지 브로커(Kafka · RabbitMQ) | PostgreSQL LISTEN/NOTIFY + SKIP LOCKED, outbox 재전송 | 컨테이너를 늘리지 않고도 "잃지 않고 한 번만 처리"가 된다 |',
            '| 서비스 등록소(Eureka 등) | compose 서비스 이름(DNS) | 서비스 수가 적고 주소가 고정이다 |',
            '| Spring Security 전체 | 게이트웨이 필터 + jjwt + BCrypt | 인증 · 권한을 게이트웨이 한 곳에서만 한다 |',
            '| 상태 관리 · UI 라이브러리(Redux · MUI 등) | React 훅 + 공통 부품 `src/ui.tsx` | 화면 수가 많지 않고 Apple HIG 모양을 직접 맞춘다 |',
            '| 지도 라이브러리 | Canvas 2D 직접 그리기 | 점유 격자 지도 한 장과 로봇 · 경로만 그리면 된다 |',
            '| OpenCV · 학습 모델 | numpy + Pillow | 지금 판독기는 색 · 밝기 계산으로 된다(소화기 AI 판독은 `docs/plan/ROADMAP.md`) |',
            '', '## 버전을 바꿀 때', '',
            '1. 원본 파일을 고친다: `package.json`(화면) · `pom.xml`(Spring) · `requirements.txt`(Python) · `Dockerfile` · `compose.yaml`(이미지).',
            '2. `build_tech_stack.py` 의 `STACK` 에서 같은 항목의 버전을 고친다.',
            '3. `python3 docs/architecture/build_tech_stack.py` 로 SVG 와 이 문서를 다시 만든다.', '']
    OUT_MD.write_text('\n'.join(out), encoding='utf-8')
    print(f'wrote {OUT_MD}')


if __name__ == '__main__':
    build_svg()
    build_md()
