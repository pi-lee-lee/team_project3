# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

화재 점검 로봇 서비스: 웹(React) + Spring MSA 백엔드 + Python 분석 워커 + ROS 2 Humble TurtleBot3(Waffle Pi) 시뮬레이션을 Docker Compose 로 한 번에 띄운다. 상세 안내는 `docs/guide/RUNNING.md`, 단계별 구동은 `docs/guide/DOCKER_GUIDE.md`, 최소 명령은 `도커_실행.md`.

## 명령 (모두 저장소 루트에서)

```bash
cp .env.example .env                         # 처음 한 번. .env 는 커밋하지 않는다
docker compose up -d --build                 # 전체 실행 → http://localhost:8080
docker compose up -d --force-recreate <svc>  # 서비스 하나 재시작(Spring 서비스는 시작할 때 다시 빌드됨)
docker compose run --rm frontend-build       # React 화면 다시 빌드(web 컨테이너가 dist 를 그대로 서빙)
docker compose logs -f sim                   # 시뮬레이션 로그 (Nav2 준비 완료: "lifecycle_manager_navigation ... Managed nodes are active")
```

시험 — 단위 테스트는 없고, 전체 흐름을 실제 스택에 대고 확인하는 E2E 하나다(스택이 떠 있어야 함, 수 분~20분):

```bash
python3 scripts/e2e_test.py                    # 전체
python3 scripts/e2e_test.py --skip-obstacles   # 장애물 시나리오 제외
python3 scripts/e2e_test.py --only-obstacles   # 장애물 시나리오(우회·다른 길·진입 불가)만
```
macOS 에는 `timeout` 명령이 없으니 붙이지 않는다.

시뮬레이션 도구(`ros/sim/src/tools/`, 컨테이너 안 `/sim/tools/`):

```bash
SIM_MODE=slam docker compose up -d --force-recreate sim   # 지도 작성 모드
docker compose exec sim /sim/tools/explore.sh             # 고정 경유점 순회로 SLAM
docker compose exec sim /sim/tools/save_map.sh            # ros/maps/site.* 저장 + 잡음 정리
docker compose up -d --force-recreate sim                 # nav 모드(저장 지도 + AMCL)로 복귀
python3 ros/sim/src/tools/explore.py --check              # 순회 계획 여유 거리 검사(호스트에서, ROS 불필요)
docker compose exec sim /sim/tools/obstacle.sh place detour|reroute|block   # 시험용 장애물, clear 로 치움
docker compose exec sim bash -c 'source /opt/ros/humble/setup.bash; python3 /sim/tools/drive_probe.py X Y 각도'  # 주행 품질 측정
python3 ros/sim/src/worlds/world_spec.py                  # 월드·설계도 지도 재생성(inspection.world 는 직접 고치지 않는다)
```

## 구조 (큰 그림)

폴더는 아키텍처 계층 > 기술 > 컨테이너: `web/{nginx,spring,python,postgres}`, `ros/{sim,robot,maps}`. 코드는 이미지에 굽지 않고 볼륨으로 마운트해 실행한다(Spring 은 시작 시 `mvn package`, `common` 은 `common-build` 가 m2 볼륨에 설치).

- **요청 경로**: 브라우저 → `cdn`(nginx 캐시 프록시: CDN 엣지 역할, 외부 포트 8080, `/assets/*` 만 보관하고 `index.html`·`/api`·`/ws` 는 통과. 설정 `web/nginx/cdn/default.conf`, 응답 헤더 `X-Cache-Status` 로 확인, 비우기는 `--force-recreate cdn`) → `web`(nginx 원본 서버: 정적 화면 + `Cache-Control` 지시, `/api`·`/ws` 프록시) → `gateway`(Spring Cloud Gateway: HttpOnly 쿠키 JWT 검증·세션 확인·경로별 역할 정책·감사 기록, 규칙은 `application.yml`) → 각 서비스.
- **서비스**: `user-service`(로그인·사용자·역할 0 ADMIN/1 관리자/2 매니저/3 사용자/4 대시보드(조회 전용, 게이트웨이가 GET 만 허용)·감사 로그), `inspection-service`(점검 지점·작업·사건 기록·관측·판정·이력·예약 점검: `ScheduleService` 가 때가 된 회차를 로봇별 메모리 실행 버퍼에 담아 로봇이 비면 이어서 실행(건너뛰지 않음, 지연은 화면 상단 안내). 재기동하면 버퍼가 비고 꺼진 동안 지난 회차는 MISSED 로만 기록. 시각은 `SCHEDULE_ZONE` 기준), `robot-service`(로봇 연결 계층), `analysis-service`(Python FastAPI: 관측 사진 품질 분석, PostgreSQL LISTEN/NOTIFY + SKIP LOCKED 작업 큐). DB 는 PostgreSQL 17 하나에 서비스별 DB, 스키마는 Flyway 마이그레이션.
- **로봇 추상화**: `robot-service` 의 `RobotAdapter` 인터페이스(구현: `RosbridgeRobotAdapter`, `MockRobotAdapter`)가 시뮬레이션/실로봇 교체 지점이다. 웹은 Nav2 를 직접 모르고 **목표 단위 토픽 계약**만 쓴다: `/inspection/goal` → `/inspection/goal_status`(사유 코드 `BLOCKED_NO_PATH`·`NAV_FAILED`·`NO_PROGRESS`·`NAV_UNAVAILABLE`), `bridge_status`, `map_pose`, `map`, `scan_map`. 이 계약을 Nav2 로 옮기는 쪽이 `ros/robot/src/nav2_goal_bridge.py`(실로봇에도 같은 코드)이고, rosbridge(9090)로 연결된다.
- **신뢰성**: 미션은 멱등, 결과는 outbox 에 보관 후 재전송, 조종은 제어권 임대 + `cmd_vel_watchdog.py`(0.5초 무명령 시 정지) + 비상 정지.
- **시뮬레이션**(`ros/sim`): Apple Silicon 에서 amd64 에뮬레이션으로 Gazebo Classic 헤드리스(Xvfb) 실행 → 실제보다 느리다. `sim.launch.py` 가 Gazebo·Nav2 bringup(nav: AMCL, slam: slam_toolbox)·rosbridge·web_video_server·브리지를 띄우고, 로봇 모델은 패키지 SDF 에서 라이다 거리만 `LIDAR_MAX_RANGE`(기본 8m) 로 바꾼 사본을 스폰한다.
- **Nav2 설정**: `ros/sim/src/config/nav2_params.yaml`. 기본값에서 바꾼 점과 이유가 파일 머리에 번호로 적혀 있다(Smac 2D A* + smoother, Regulated Pure Pursuit, 팽창 0.6/3.0, voxel 층 제거, AMCL 조정 등). 설정을 바꿀 때 그 목록도 함께 고친다. slam_toolbox 는 기본값 유지(조정했을 때 지도가 깨졌다).
- **월드·지도**: `ros/sim/src/worlds/world_spec.py` 하나가 월드(SDF), 설계도 지도(`ros/maps/reference.*`), 점검 지점 P1~P3, 장애물 정의의 원본이다. 운영 지도는 SLAM 으로 만든 `ros/maps/site.*`(없으면 reference). 월드를 바꾸면 SLAM 재스캔이 필요하다. 순회 계획(`explore.py`)은 직선 구간마다 로봇 중심이 벽·설비에서 0.27m 이상 떨어져야 출발한다.
- **웹 지도는 실제 지도와 별개**: `MapRenderer`(robot-service)가 `/inspection/map` 을 받아 표시용 PNG 를 새로 그린다(잡음 제거, 로봇이 못 지나는 틈 닫기, 섬은 직사각형, 직선 벽). 주행에 쓰는 지도에는 영향이 없다.
- **관제 대시보드**(`pages/dashboard`, 계정 dash1): 16:9 모니터용 1920×1080 고정 화면(반응형 아님, 창에 맞춰 통째로 확대·축소). `data.ts`(폴링·경고 합치기) → `panels.tsx`(패널 등록표 `PANELS`) + `layout.ts`(24×12 격자 배치표) → `details.tsx`(항목을 누르면 뜨는 상세 등록표 `DETAILS`). 요약 API 는 inspection-service `DashboardController`(`/api/dashboard/overview`).
- **화면**(`web/nginx/frontend`, React 18 + Vite): Apple HIG 스타일, 스마트폰·태블릿·PC 지원, 일 단위 화면(목록 → 상세 → 폼, 공통 부품 `src/ui.tsx`). 점검 요청·예약은 "점검 계획" 하나(`pages/user/plans`: 실행 버튼 = 즉시 요청, 실행 방식 MANUAL/ONCE/INTERVAL/DAILY/WEEKLY), 아이콘은 Material Symbols(`Icon.tsx` 에서 SF Symbols 식 이름을 매핑 — SF Symbols 는 라이선스상 웹에 넣지 않는다). 관제 화면(`pages/user/Monitor.tsx`)은 카메라 모드(MJPEG 스트림 + 방향키 조종 WebSocket)와 지도 모드(캔버스: 0.2초 폴링 + 로봇 위치 보간, URDF 치수 로봇, 점선 계획 경로, 클릭=목적지·드래그=도착 방향).

## 작업 규칙

- 커밋·푸시는 사용자가 요청할 때만. 작업 브랜치는 `feat/msa-sim-stack`이고, main 에는 아직 올리지 않는다(PR·병합 금지).
- `개선초안/` 은 사용자의 커밋하지 않은 폴더다. 커밋하거나 고치지 않는다.
- 루트에는 `README.md`(보유 하드웨어 제원), `도커_실행.md`, 실행에 필요한 파일(`compose.yaml`, `.env.example`, `.gitignore`, `.gitattributes`)만 둔다. 다른 문서는 `docs/` 아래 분류 폴더(`architecture/`, `guide/`, `plan/`, `storyboard/`)에 둔다. SVG 문서는 같은 폴더의 `build_*.py` 로 생성하므로 SVG 를 직접 고치지 말고 스크립트를 고친 뒤 다시 생성한다.
- 시간대: 모든 컨테이너는 `APP_TZ`(기본 Asia/Seoul) — compose 에서 `TZ` 와 PostgreSQL `-c timezone` 으로 맞춘다. 저장 시각은 timestamptz(절대 시각).
- nginx 설정(`web/nginx/web/`·`web/nginx/cdn/` 의 `default.conf`)은 폴더째 마운트한다(파일 하나만 마운트하면 편집기가 파일을 새로 쓸 때 컨테이너가 옛 파일을 본다). 고친 뒤 `docker compose exec web nginx -s reload`(cdn 도 같음)로 반영한다.
- 화면을 다시 빌드한 뒤 결과가 안 바뀐 것처럼 보이면 먼저 브라우저 새로고침 여부를 확인한다.
- 문서·주석·커밋 메시지는 한국어로 쓴다.
