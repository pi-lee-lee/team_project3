"""기술 스택 도면 + 설명서: 시스템 구성도(arch_01_system_architecture.svg)의 계층마다 무슨 기술을 쓰는가.

읽는 법
- 어두운 머리 영역: 구성도의 요청 경로(브라우저 → cdn → web → gateway → 서비스 → db)와 로봇 쪽 연결을 기술 이름으로 다시 적은 것.
- 그 아래 흰 판 하나 = 구성도의 한 영역(색도 구성도와 같다). 왼쪽 = 영역 이름과 컨테이너, 오른쪽 카드 = 기술 하나(아이콘 · 이름 · 버전 · 하는 일).
- 붉은 둥근 상자 = 핵심 스택(CORE): 구성도의 구조를 이루는 상위 기술. 나머지는 그 아래의 라이브러리 · 기능.
- 아이콘: 공식 로고는 docs/_lib/icons/ 의 Simple Icons(CC0) SVG, 로고가 없는 것은 이 파일의 GLYPH(직접 그린 선 아이콘). 기술을 더하면 ICON 에도 한 줄 더한다.
이 파일의 STACK 하나가 SVG 와 Markdown 두 문서의 원본이다. 버전의 원본은 각 항목에 적힌 파일(package.json · pom.xml ·
requirements.txt · Dockerfile · compose.yaml)이므로, 그 파일을 바꾸면 STACK 도 고친 뒤 다시 생성한다.
실행: python3 docs/architecture/build_tech_stack.py  →  docs/architecture/arch_02_tech_stack.svg · arch_03_TECH_STACK.md
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / '_lib'))   # 공용 그리기 도구 docs/_lib/svg.py
from svg import C, MONO, Svg, text_width

HERE = Path(__file__).resolve().parent
OUT_SVG, OUT_MD = HERE / 'arch_02_tech_stack.svg', HERE / 'arch_03_TECH_STACK.md'
W = 1680
S = Svg(W, 2000)               # 높이는 마지막에 내용에 맞춘다

# 영역: (제목, 색, 컨테이너, 왼쪽 설명 줄, 버전 원본 파일, 한 줄 소개(MD), [(기술, 버전, 하는 일(SVG·MD), 왜 쓰는가(MD))])
STACK = [
    ('화면', 'client', 'frontend-build · web', ['브라우저에서 도는 React SPA', '빌드 결과 dist/ 를 web 이 서빙'],
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
    ('업무 서비스', 'spring', 'user-service · inspection-service · robot-service', ['컨테이너 하나 = MSA 서비스 하나', '자기 jar · 포트 · DB'],
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
        ('SKIP LOCKED', 'PostgreSQL 기능', '작업 큐: 한 작업은 한 워커만', '`FOR UPDATE SKIP LOCKED` 로 집으면 워커가 여럿이어도 같은 작업을 두 번 집지 않는다.'),
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
        ('compressed_image_transport', 'JPEG', '카메라 영상 압축 전송', '실제 로봇에서 Wi-Fi 로 원본 영상을 보내지 않기 위해서다.'),
        ('rclpy', 'Python 3.10', '브리지 노드(목표 · 감시 · 투척)', '`nav2_goal_bridge` · `cmd_vel_watchdog` · `mock_launcher` 를 Python 노드로 짠다.'),
     ]),
    ('실행 · 빌드 · 시험', 'dev', 'compose.yaml', ['명령 하나로 전체 실행', '코드는 이미지에 굽지 않고 마운트'],
     'compose.yaml · scripts/ · docs/',
     '전체를 한 번에 띄우고 확인하는 도구.', [
        ('Docker Compose', 'v2', '컨테이너 11개 · 네트워크 4개', '실행 9 + 빌드용 2. 네트워크(front · edge · backend · robot)로 서로 닿는 범위를 나눈다.'),
        ('빌드용 컨테이너', 'maven:3.9 · node:20', 'common-build · frontend-build', '호스트에 JDK · Node 를 설치하지 않아도 된다(`docs/guide/guide_03_BUILD_CONTAINERS.md`).'),
        ('E2E 시험', 'Python 3 표준 라이브러리', '실제 스택에 대고 전체 흐름 확인', '단위 테스트 대신 떠 있는 스택에 요청을 보내 본다(`scripts/e2e_test.py` · `e2e_scenarios.py`).'),
        ('문서 도면', 'Python → SVG', 'build_*.py 로 SVG 생성', '도면을 손으로 고치지 않고 스크립트에서 다시 만든다.'),
     ]),
    ('실제 로봇', 'gray', '보유 장비', ['아직 코드가 붙지 않은 하드웨어', '제원은 README 9절'],
     'README.md 9절',
     '보유한 하드웨어. 지금은 시뮬레이션으로만 돌고, 실물 연동은 `docs/plan/plan_02_SCHEDULE.md` 의 일정대로 한다.', [
        ('TurtleBot3 Waffle Pi', '실물', 'Raspberry Pi + OpenCR 보드', 'sim 컨테이너 자리를 대신한다(같은 노드 · 토픽, 목표 브리지도 같은 코드).'),
        ('LDS 라이다 · IMX219', 'TurtleBot3', '360° 거리 측정 · 점검 사진', '주행(Nav2)과 관측 사진의 입력.'),
        ('Jetson Nano 4GB', 'JetBot Mini', '순찰 · 화재 감지(예정)', '지금은 `fire.sh` 가 감지 보고(`/patrol/detection`)를 대신 보낸다.'),
        ('투척기 시리얼 브리지', 'rclpy', 'launcher_bridge.py (만들어만 둠)', '시뮬레이션에서는 `mock_launcher.py` 가 투척 계약에 답한다.'),
     ]),
]

# 핵심 스택: 시스템 구성도의 구조를 이루는 상위 기술(컨테이너 · 서비스의 뼈대). 도면에서 붉은 둥근 상자로 두른다.
# 라이브러리 · 기능 같은 하위 기술(Pillow · psycopg · Docker 볼륨 등)은 넣지 않는다.
CORE = {'React', 'TypeScript', 'Vite', 'nginx', 'Spring Cloud Gateway', 'Java', 'Spring Boot', 'Python', 'FastAPI',
        'PostgreSQL', 'ROS 2', 'Gazebo Classic', 'Nav2', 'rosbridge_server', 'Docker Compose'}
RED = '#ff3b30'

# 구성도의 요청 경로를 기술 이름으로: (컨테이너, 기술, 아이콘)
PATH_WEB = [('브라우저', 'React 18 · TypeScript', 'react'), ('cdn', 'nginx 캐시', 'nginx'), ('web', 'nginx 원본', 'nginx'),
            ('gateway', 'Spring Cloud Gateway', 'spring'), ('서비스 ×4', 'Spring Boot 3 · FastAPI', 'springboot'),
            ('db', 'PostgreSQL 17', 'postgresql')]
PATH_ROBOT = [('robot-service', 'RosbridgeRobotAdapter', 'springboot'), ('rosbridge', 'WebSocket(JSON) :9090', 'bridge'),
              ('nav2_goal_bridge', 'rclpy · 목표 단위 계약', 'python'), ('Nav2', 'Theta* · MPPI · AMCL', 'nav'),
              ('Gazebo', 'TurtleBot3 Waffle Pi', 'cube')]

# ---------------------------------------------------------------- 아이콘
# 공식 로고: docs/_lib/icons/<이름>.svg (Simple Icons, CC0 — 상표는 각 소유자의 것). 값 = 도면에 칠할 브랜드 색.
LOGO = {'react': '#149eca', 'typescript': '#3178c6', 'vite': '#646cff', 'reactrouter': '#ca4245', 'googlefonts': '#4285f4',
        'html5': '#e34f26', 'nginx': '#009639', 'spring': '#6db33f', 'springboot': '#6db33f', 'springsecurity': '#6db33f',
        'jsonwebtokens': '#d63aff', 'openjdk': '#e76f00', 'apachemaven': '#c71a36', 'flyway': '#cc0200',
        'postgresql': '#4169e1', 'python': '#3776ab', 'fastapi': '#009688', 'numpy': '#4d77cf', 'docker': '#2496ed',
        'ros': '#22314e', 'svg': '#e8a100', 'raspberrypi': '#a22846', 'nvidia': '#76b900'}
# 로고가 없는 기술 · 기능은 직접 그린 선 아이콘(24×24, 선 굵기 2). 색은 영역 색을 따른다.
GLYPH = {
    'swap': 'M4 8h13M14 5l3 3-3 3M20 16H7M10 13l-3 3 3 3',
    'layers': 'M12 3l9 5-9 5-9-5zM3 12.5l9 5 9-5M3 17l9 5 9-5',
    'file': 'M6 3h8l4 4v14H6zM14 3v4h4M9 12h6M9 16h6',
    'fork': 'M3 12h6M9 12c4 0 3-6 7-6h4M9 12c4 0 3 6 7 6h4M18 4l2 2-2 2M18 16l2 2-2 2',
    'shield': 'M12 3l8 3v6c0 4.5-3.2 8-8 9-4.8-1-8-4.5-8-9V6zM8.5 12l2.5 2.5 4.5-5',
    'server': 'M4 4h16v6H4zM4 14h16v6H4zM7.5 7h.01M7.5 17h.01',
    'database': 'M4 6c0-1.7 3.6-3 8-3s8 1.3 8 3-3.6 3-8 3-8-1.3-8-3zM4 6v12c0 1.7 3.6 3 8 3s8-1.3 8-3V6M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3',
    'image': 'M4 5h16v14H4zM4 16l5-5 4 4 3-3 4 4M15.5 9.5h.01',
    'send': 'M21 3L10 14M21 3l-7 18-4-7-7-4z',
    'upload': 'M12 16V4M7 9l5-5 5 5M4 20h16',
    'bell': 'M6 16v-5a6 6 0 0 1 12 0v5l2 2H4zM10 21h4',
    'lock': 'M6 11h12v9H6zM9 11V8a3 3 0 0 1 6 0v3',
    'cube': 'M12 3l8 4.5v9L12 21l-8-4.5v-9zM4 7.5l8 4.5 8-4.5M12 12v9',
    'robot': 'M5 9h14v10H5zM12 9V5M12 4h.01M9 13.5h.01M15 13.5h.01M9 16.5h6M2 13v3M22 13v3',
    'nav': 'M12 3l7 18-7-4-7 4z',
    'route': 'M5.6 17.2L9.3 9.6M11.6 7.5l5.6-1.9M5 17.5a1.6 1.6 0 1 0 0 3.2 1.6 1.6 0 0 0 0-3.2zM10 6.4a1.6 1.6 0 1 0 0 3.2 1.6 1.6 0 0 0 0-3.2zM19 3.4a1.6 1.6 0 1 0 0 3.2 1.6 1.6 0 0 0 0-3.2z',
    'fan': 'M4 20c2-8 6-13 16-16M4 20c4-6 8-9 16-10M4 20c5-3 9-4 16-4',
    'target': 'M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8zM12 2v4M12 18v4M2 12h4M18 12h4',
    'map': 'M3 6l6-2 6 2 6-2v14l-6 2-6-2-6 2zM9 4v14M15 6v14',
    'bridge': 'M2 17h20M4 17V9M20 17V9M4 9c4 5 12 5 16 0M9 12.2V17M15 12.2V17',
    'video': 'M3 7h12v10H3zM15 10.5l6-3.5v10l-6-3.5',
    'shrink': 'M4 4l6 6M10 5v5H5M20 20l-6-6M14 19v-5h5M20 4l-6 6M14 5v5h5M4 20l6-6M10 19v-5H5',
    'package': 'M12 3l8 4.5v9L12 21l-8-4.5v-9zM4 7.5l8 4.5 8-4.5M12 12v9M8 5.2l8 4.6',
    'check': 'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM8 12.5l3 3 5-6',
    'radar': 'M12 12l6-6M12 3a9 9 0 1 0 9 9M12 7a5 5 0 1 0 5 5',
    'usb': 'M12 2v14M9 5l3-3 3 3M12 16a2.5 2.5 0 1 0 0 5 2.5 2.5 0 0 0 0-5zM6 8v3l6 3M18 7v3l-6 3',
    'monitor': 'M3 4h18v12H3zM8 20h8M12 16v4',
    'cloud': 'M7 18a4 4 0 0 1-.5-8 6 6 0 0 1 11.5 1.5 3.3 3.3 0 0 1-.5 6.5z',
    'grid': 'M4 4h7v7H4zM13 4h7v7h-7zM4 13h7v7H4zM13 13h7v7h-7z',
    'chart': 'M4 20V4M4 20h16M8 16v-4M12 16V8M16 16v-6',
    'terminal': 'M4 5h16v14H4zM7 9l3 3-3 3M12 15h5',
    'chip': 'M7 7h10v10H7zM10 2v5M14 2v5M10 17v5M14 17v5M2 10h5M2 14h5M17 10h5M17 14h5',
}
# 기술 이름 → 아이콘(LOGO 또는 GLYPH 의 키, 'text:글자' 는 글자 그대로)
ICON = {
    'React': 'react', 'TypeScript': 'typescript', 'Vite': 'vite', 'React Router': 'reactrouter', 'Material Symbols': 'googlefonts',
    'Galmuri': 'text:가', 'Canvas 2D': 'html5', 'WebSocket · MJPEG': 'swap',
    'nginx': 'nginx', 'proxy_cache': 'layers', '정적 서빙 · gzip': 'file', '리버스 프록시': 'fork',
    'Spring Cloud Gateway': 'spring', 'Spring WebFlux': 'spring', 'JWT (jjwt)': 'jsonwebtokens', 'Spring Boot Actuator': 'springboot',
    'Java': 'openjdk', 'Spring Boot': 'springboot', 'Spring Web MVC': 'spring', 'Spring JDBC': 'spring', 'Flyway': 'flyway',
    'PostgreSQL JDBC': 'postgresql', 'RestClient': 'spring', 'Spring WebSocket': 'spring', 'java.net.http': 'openjdk',
    'Spring Security Crypto': 'springsecurity', 'Bean Validation': 'shield', 'Maven': 'apachemaven',
    'Python': 'python', 'FastAPI': 'fastapi', 'Uvicorn': 'server', 'psycopg': 'database', 'NumPy': 'numpy', 'Pillow': 'image',
    'httpx': 'send', 'python-multipart': 'upload',
    'PostgreSQL': 'postgresql', 'LISTEN / NOTIFY': 'bell', 'SKIP LOCKED': 'lock', 'Docker 볼륨': 'docker',
    'ROS 2': 'ros', 'Gazebo Classic': 'cube', 'TurtleBot3': 'robot', 'Nav2': 'nav', 'Theta* 계획기': 'route', 'MPPI 제어기': 'fan',
    'AMCL': 'target', 'slam_toolbox': 'map', 'rosbridge_server': 'bridge', 'web_video_server': 'video',
    'compressed_image_transport': 'shrink', 'rclpy': 'python',
    'Docker Compose': 'docker', '빌드용 컨테이너': 'package', 'E2E 시험': 'check', '문서 도면': 'svg',
    'TurtleBot3 Waffle Pi': 'raspberrypi', 'LDS 라이다 · IMX219': 'radar', 'Jetson Nano 4GB': 'nvidia', '투척기 시리얼 브리지': 'usb',
}
SECTION_ICON = {'화면': 'monitor', '엣지': 'cloud', '게이트웨이': 'shield', '업무 서비스': 'grid', '분석 서비스': 'chart',
                '저장소': 'database', '로봇': 'robot', '실행 · 빌드 · 시험': 'terminal', '실제 로봇': 'chip'}
ICON_DIR = Path(__file__).resolve().parents[1] / '_lib' / 'icons'
_used = set()


def icon(x, y, size, key, color, late=False):
    """아이콘을 (x, y) 에 size 크기로. 로고는 <defs> 에 한 번만 넣고 <use> 로 부른다."""
    k = size / 24
    if key.startswith('text:'):
        S.text(x + size / 2, y + size * 0.82, key[5:], size * 0.92, 800, color, 'middle', late=late)
    elif key in LOGO:
        _used.add(key)
        S.raw(f'<use href="#i-{key}" transform="translate({x:.1f} {y:.1f}) scale({k:.3f})" fill="{color}"/>', late)
    else:
        S.raw(f'<path d="{GLYPH[key]}" transform="translate({x:.1f} {y:.1f}) scale({k:.3f})" fill="none" stroke="{color}" '
              f'stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>', late)


def defs():
    logos = ''.join('<path id="i-%s" d="%s"/>' % (k, re.search(r'<path d="([^"]+)"', (ICON_DIR / f'{k}.svg').read_text()).group(1))
                    for k in sorted(_used))
    return ('<defs>' + logos +
            '<linearGradient id="hero" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#16161d"/>'
            '<stop offset="0.6" stop-color="#1f2233"/><stop offset="1" stop-color="#2b2350"/></linearGradient>'
            '<filter id="sh" x="-5%" y="-10%" width="110%" height="130%"><feDropShadow dx="0" dy="3" stdDeviation="7" '
            'flood-color="#1c1c1e" flood-opacity="0.09"/></filter></defs>')


# ---------------------------------------------------------------- 그리기
PAD = 40
LABEL_W, COLS, GAP, CARD_H = 236, 4, 12, 66
CARD_W = (W - 2 * PAD - LABEL_W - 20 - (COLS - 1) * GAP) / COLS
TEXT_W = CARD_W - 64 - 12            # 카드에서 아이콘 타일 오른쪽에 글자가 쓸 수 있는 폭


def flow(y, label, steps, both):
    """머리 영역의 요청 경로 한 줄(어두운 바탕). both = 양방향 화살표."""
    S.text(PAD + 32, y + 33, label, 12, 700, '#aeaeb2')
    x0, x1, gap = PAD + 150, W - PAD - 32, 38
    bw = (x1 - x0 - (len(steps) - 1) * gap) / len(steps)
    for i, (name, tech, ic) in enumerate(steps):
        x = x0 + i * (bw + gap)
        S.raw(f'<rect x="{x:.1f}" y="{y}" width="{bw:.1f}" height="56" rx="12" fill="#ffffff" fill-opacity="0.07" '
              f'stroke="#ffffff" stroke-opacity="0.2"/>')
        S.raw(f'<rect x="{x + 10:.1f}" y="{y + 10}" width="36" height="36" rx="9" fill="#ffffff"/>')
        icon(x + 17, y + 17, 22, ic, LOGO.get(ic, '#5856d6'))
        S.text(x + 58, y + 25, name, 13.5, 700, '#ffffff', mono=True)
        S.text(x + 58, y + 43, tech, 11.5, 400, '#c7c7cc')
        if i:
            S.line([(x - gap + 5, y + 28), (x - 5, y + 28)], color='#8e8e93', start=both)
    return y + 56


def hero(n):
    h = 318
    S.raw(f'<rect x="{PAD}" y="28" width="{W - 2 * PAD}" height="{h}" rx="24" fill="url(#hero)"/>')
    S.raw(f'<text x="{PAD + 32}" y="70" font-size="12" font-weight="700" fill="#a5a3ff" letter-spacing="2.4">TECH STACK</text>')
    S.text(PAD + 32, 108, '화재 점검 로봇 서비스 — 기술 스택', 30, 700, '#ffffff')
    S.text(PAD + 32, 136, '시스템 구성도의 영역마다 무슨 기술을 쓰는가 · 붉은 상자 = 구성도의 구조를 이루는 핵심 스택 · 나머지 = 그 아래의 라이브러리 · 기능', 13.5, 400, '#c7c7cc')
    x = W - PAD - 32
    for num, unit in reversed([(str(len(CORE)), '핵심 스택'), (str(n), '기술'), (str(len(STACK)), '영역'), ('11', '컨테이너'), ('4', '네트워크')]):
        w = 104
        if unit == '핵심 스택':
            S.raw(f'<rect x="{x - w}" y="54" width="{w}" height="78" rx="14" fill="{RED}" fill-opacity="0.16" stroke="{RED}" stroke-width="2.4"/>')
        else:
            S.raw(f'<rect x="{x - w}" y="54" width="{w}" height="78" rx="14" fill="#ffffff" fill-opacity="0.07" '
                  f'stroke="#ffffff" stroke-opacity="0.16"/>')
        S.text(x - w / 2, 98, num, 30, 700, '#ffffff', 'middle')
        S.text(x - w / 2, 120, unit, 11.5, 500, '#aeaeb2', 'middle')
        x -= w + 10
    y = flow(170, '요청이 지나는 길', PATH_WEB, False)
    flow(y + 16, '로봇 쪽 연결', PATH_ROBOT, True)
    return 28 + h


def band(y, no, title, kind, containers, notes, items):
    stroke, tint = C[kind]
    planned = kind == 'gray'
    ink = '#636366' if planned else stroke
    rows = -(-len(items) // COLS)
    # 왼쪽 이름표의 컨테이너 표시는 폭에 맞춰 줄을 바꾼다
    chips, cx, cyo = [], 0, 0
    for c in containers.split(' · '):
        cw = text_width(c, True, 11) + 16
        if cx and cx + cw > LABEL_W - 44:
            cx, cyo = 0, cyo + 26
        chips.append((cx, cyo, cw, c))
        cx += cw + 6
    label_h = 78 + cyo + 21 + 22 + len(notes) * 18 + 6
    cards_h = rows * (CARD_H + GAP) - GAP
    h = max(2 * 18 + cards_h, label_h)
    top = y + (h - cards_h) / 2          # 카드 묶음은 판 안에서 세로 가운데
    S.raw(f'<rect x="{PAD}" y="{y}" width="{W - 2 * PAD}" height="{h}" rx="20" fill="#ffffff" filter="url(#sh)"'
          + (' stroke="#aeaeb2" stroke-dasharray="6 5"' if planned else '') + '/>')
    S.raw(f'<rect x="{PAD}" y="{y + 22}" width="5" height="{h - 44}" rx="2.5" fill="{ink}"/>')
    lx = PAD + 26
    S.raw(f'<rect x="{lx}" y="{y + 20}" width="46" height="46" rx="13" fill="{ink}"/>')
    icon(lx + 11, y + 31, 24, SECTION_ICON[title], '#ffffff')
    S.raw(f'<text x="{lx + 60}" y="{y + 36}" font-size="11" font-weight="700" fill="{ink}" letter-spacing="1.5" '
          f'font-family="{MONO}">{no:02d}{"  예정" if planned else ""}</text>')
    S.text(lx + 60, y + 60, title, 19, 700, '#1c1c1e')
    for cx, cyo, cw, c in chips:
        S.rect(lx + cx, y + 78 + cyo, cw, 21, fill=tint if not planned else '#f2f2f7', stroke=tint if not planned else '#f2f2f7', rx=6)
        S.text(lx + cx + cw / 2, y + 92.5 + cyo, c, 11, 600, ink, 'middle', mono=True)
    ny = y + 78 + chips[-1][1] + 21 + 22
    for i, n in enumerate(notes):
        S.text(lx, ny + i * 18, n, 11.5, 400, '#636366')
    for i, (name, ver, role, _) in enumerate(items):
        x = PAD + LABEL_W + (i % COLS) * (CARD_W + GAP)
        cy = top + (i // COLS) * (CARD_H + GAP)
        vw = text_width(ver, True, 10.5) + 14
        for label, used, what in ((role, text_width(role, False, 11.5), '하는 일'), (name, text_width(name, False, 13.5) + vw + 8, '이름+버전')):
            if used > TEXT_W:
                print(f'  너무 김({what}): {label} — {used:.0f} > {TEXT_W:.0f}')
        key = ICON[name]
        col = LOGO.get(key, ink)
        if name in CORE:                 # 핵심 스택 = 붉은 둥근 상자
            S.rect(x, cy, CARD_W, CARD_H, fill='#fff7f6', stroke=RED, sw=2.8, rx=13)
        else:
            S.rect(x, cy, CARD_W, CARD_H, fill='#fbfbfd', stroke='#e5e5ea', sw=1, rx=13, dash='4 3' if planned else None)
        S.raw(f'<rect x="{x + 11:.1f}" y="{cy + 11}" width="44" height="44" rx="11" fill="{col}" fill-opacity="0.12"/>')
        icon(x + 21, cy + 21, 24, key, col)
        S.text(x + 66, cy + 28, name, 13.5, 700, '#1c1c1e')
        S.rect(x + CARD_W - vw - 11, cy + 13, vw, 20, fill='#f2f2f7', stroke='#f2f2f7', rx=10)
        S.text(x + CARD_W - 11 - vw / 2, cy + 27, ver, 10.5, 600, '#48484a', 'middle', mono=True)
        S.text(x + 66, cy + 49, role, 11.5, 400, '#636366')
    return y + h


def build_svg():
    n = sum(len(layer[6]) for layer in STACK)
    defs_idx = len(S.body)
    y = hero(n) + 20
    for no, (title, kind, containers, notes, _, _, items) in enumerate(STACK, 1):
        y = band(y, no, title, kind, containers, notes, items) + 16
    S.rect(PAD + 4, y, 30, 20, fill='#fff7f6', stroke=RED, sw=2.4, rx=6)
    S.text(PAD + 42, y + 14.5, '핵심 스택 — 구성도의 구조를 이루는 상위 기술', 12, 700, '#1c1c1e')
    S.rect(PAD + 330, y, 30, 20, fill='#fbfbfd', stroke='#d1d1d6', sw=1, rx=6)
    S.text(PAD + 368, y + 14.5, '하위 스택 — 라이브러리 · 기능', 12, 500, '#636366')
    y += 30
    S.text(PAD + 4, y + 14, '버전의 원본: package.json(화면) · pom.xml(Spring) · requirements.txt(Python) · Dockerfile · compose.yaml(이미지)   |   '
                            '글 설명과 "왜 쓰는가": arch_03_TECH_STACK.md   |   로고: Simple Icons(CC0), 상표는 각 소유자의 것 · 선 아이콘은 직접 그림', 11.5, 500, '#8e8e93')
    S.body.insert(defs_idx, defs())
    S.h = y + 36
    S.render(OUT_SVG)


def build_md():
    def cell(s):
        return s.replace('|', '\\|')

    out = ['# 기술 스택', '',
           '> **읽는 순서 — 시스템 구조:** [01 구성도](arch_01_system_architecture.svg) → [02 기술 스택 그림](arch_02_tech_stack.svg) → '
           '**03 기술 스택 설명** → [04 시스템 사이클](arch_04_system_cycle.svg) → [05 React SPA 사이클](arch_05_spa_cycle.svg)', '',
           '> 이 파일은 `build_tech_stack.py` 가 만든다. 직접 고치지 말고 스크립트의 `STACK` 을 고친 뒤 다시 생성한다',
           '> (`python3 docs/architecture/build_tech_stack.py`). 그림은 [arch_02_tech_stack.svg](arch_02_tech_stack.svg).', '',
           '[시스템 구성도](arch_01_system_architecture.svg)의 영역마다 **무슨 기술을, 어디에, 왜** 쓰는지 적는다.',
           '영역 순서는 구성도에서 요청이 지나는 순서와 같다.', '',
           f'**핵심 스택**(그림의 붉은 상자, 표의 🟥)은 구성도의 구조를 이루는 상위 기술 {len(CORE)}개다. 나머지는 그 아래에서 쓰는 라이브러리 · 기능이다.', '',
           '![기술 스택](arch_02_tech_stack.svg)', '',
           '## 한눈에', '',
           '요청이 지나는 길: ' + ' → '.join(f'`{n}`({t})' for n, t, _ in PATH_WEB), '',
           '로봇 쪽 연결: ' + ' ⇄ '.join(f'`{n}`({t})' for n, t, _ in PATH_ROBOT), '',
           '| 영역 | 컨테이너 | 핵심 스택 |', '| --- | --- | --- |']
    for title, _, containers, _, _, _, items in STACK:
        core = ' · '.join(f'**{name}** {ver}' if ver[0].isdigit() else f'**{name}**' for name, ver, _, _ in items if name in CORE) or '—'
        out.append(f'| [{title}](#{title.replace(" · ", "--").replace(" ", "-")}) | {containers} | {core} |')
    for title, _, containers, _, source, intro, items in STACK:
        out += ['', f'## {title}', '', intro, '',
                f'- 컨테이너: {containers}', f'- 버전의 원본: `{source}`', '',
                '| 기술 | 버전 | 하는 일 | 왜 쓰는가 |', '| --- | --- | --- | --- |']
        out += [f'| {"🟥 " if name in CORE else ""}**{name}** | {ver} | {cell(role)} | {cell(why)} |' for name, ver, role, why in items]
    out += ['', '## 일부러 쓰지 않는 것', '',
            '| 쓰지 않는 것 | 대신 | 이유 |', '| --- | --- | --- |',
            '| JPA · ORM | Spring JDBC(`JdbcClient`) + Flyway | 표가 단순하고 SQL 을 그대로 써야 하는 곳(작업 큐)이 있다 |',
            '| 메시지 브로커(Kafka · RabbitMQ) | PostgreSQL LISTEN/NOTIFY + SKIP LOCKED, outbox 재전송 | 컨테이너를 늘리지 않고도 "잃지 않고 한 번만 처리"가 된다 |',
            '| 서비스 등록소(Eureka 등) | compose 서비스 이름(DNS) | 서비스 수가 적고 주소가 고정이다 |',
            '| Spring Security 전체 | 게이트웨이 필터 + jjwt + BCrypt | 인증 · 권한을 게이트웨이 한 곳에서만 한다 |',
            '| 상태 관리 · UI 라이브러리(Redux · MUI 등) | React 훅 + 공통 부품 `src/ui.tsx` | 화면 수가 많지 않고 Apple HIG 모양을 직접 맞춘다 |',
            '| 지도 라이브러리 | Canvas 2D 직접 그리기 | 점유 격자 지도 한 장과 로봇 · 경로만 그리면 된다 |',
            '| OpenCV · 학습 모델 | numpy + Pillow | 지금 판독기는 색 · 밝기 계산으로 된다(소화기 AI 판독은 `docs/plan/plan_01_ROADMAP.md`) |',
            '', '## 버전을 바꿀 때', '',
            '1. 원본 파일을 고친다: `package.json`(화면) · `pom.xml`(Spring) · `requirements.txt`(Python) · `Dockerfile` · `compose.yaml`(이미지).',
            '2. `build_tech_stack.py` 의 `STACK` 에서 같은 항목의 버전을 고친다.',
            '3. `python3 docs/architecture/build_tech_stack.py` 로 SVG 와 이 문서를 다시 만든다.', '']
    OUT_MD.write_text('\n'.join(out), encoding='utf-8')
    print(f'wrote {OUT_MD}')


if __name__ == '__main__':
    build_svg()
    build_md()
