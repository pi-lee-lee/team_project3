# 실행 안내 — 화재 점검 로봇 서비스 (시뮬레이션)

웹(로그인·관리자·사용자 화면) + MSA 백엔드 + ROS 2 TurtleBot3 시뮬레이션(SLAM·Nav2)을 Docker Compose 로 한 번에 띄운다.

## 실행

```bash
cp .env.example .env        # 비밀번호·JWT 키를 바꾼다 (DEMO_USERS_PASSWORD 를 넣으면 sup1·mgr1·user1 시험 계정 생성)
docker compose up -d --build
```

- 접속: http://localhost:8080 — 계정과 비밀번호는 `.env` 에 있다(`INITIAL_ADMIN_LOGIN / INITIAL_ADMIN_PASSWORD`, 시험 계정은 `DEMO_USERS_PASSWORD`).
- 첫 실행은 각 Spring 서비스가 시작할 때 Maven 빌드를 하고, 시뮬레이터가 Nav2 를 올리므로 3~5분 걸린다.
- 종단 간 시험: `python3 scripts/e2e_test.py` (장애물 시나리오 제외: `--skip-obstacles`)

## 폴더 구조: 아키텍처 계층 > 컨테이너

| 폴더 | 컨테이너 | 내용 |
| --- | --- | --- |
| `web/gateway/` | gateway | Spring Cloud Gateway: JWT 쿠키 검증, 세션 유효성, 경로별 역할 정책, 감사 기록, 시스템 상태 |
| `web/user-service/` | user-service | 로그인·사용자·역할(0 ADMIN, 1 관리자, 2 매니저, 3 사용자)·감사 로그 |
| `web/inspection-service/` | inspection-service | 점검 지점, 작업, 사건 기록, 관측 사진, 사람 판정, 재점검, 지점 이력 |
| `web/robot-service/` | robot-service | 로봇 연결 계층: `RobotAdapter`(rosbridge·mock), 상태·제어권·조종·비상 정지·미션 실행·결과 재전송·영상 중계 |
| `web/analysis-service/` | analysis-service | Python: 사진 품질 배치 분석(ROI 밝기·선명도 → 재촬영 후보) |
| `web/frontend/` | frontend-build → web | React 화면(빌드 결과를 nginx 가 제공), `nginx.conf` |
| `web/db/` | db | PostgreSQL 17, 서비스마다 DB·계정 분리 |
| `web/common/` | common-build | 서비스 간 계약(JWT·사용자 헤더) 공유 라이브러리 |
| `ros/sim/` | sim | Gazebo 월드·SLAM/Nav2 실행·시험 도구 |
| `ros/robot/` | (sim 안에서 실행) | 로봇 측 노드: Nav2 목표 브리지, cmd_vel 워치독 — 실제 로봇에도 같은 코드 |
| `ros/maps/` | — | 지도: `site.*`(SLAM), `reference.*`(설계도 기준) |

선택 이유: MSA 에서 빌드·배포·장애 격리의 단위는 컨테이너(서비스)다. 서비스마다 자기 `src`·빌드 파일·Dockerfile 을 가지면
한 서비스만 고쳐 다시 띄울 수 있고 담당도 폴더로 나뉜다. 최상위 `web/`(서버) · `ros/`(로봇)는 배치 위치가 다른 두 계층을 구분하는 묶음이다.
공유 코드는 `web/common` 라이브러리 하나로 최소화했다(서비스들은 버전으로 의존).

이미지에는 실행 환경만 있고, 코드는 각 폴더를 볼륨으로 연결해 구동한다. 코드를 고친 뒤:

| 고친 곳 | 반영 |
| --- | --- |
| Spring 서비스 | `docker compose restart <서비스>` (시작할 때 다시 빌드) |
| `web/common` | `docker compose run --rm common-build` 후 Spring 서비스 재시작 |
| 화면 | `docker compose run --rm frontend-build` |
| 분석 서비스 · ROS | `docker compose restart analysis-service` / `sim` |

네트워크: `edge`(web ↔ gateway, 외부 포트 8080 하나) · `backend`(gateway ↔ 서비스 ↔ db) · `robot`(robot-service ↔ sim). rosbridge 는 robot-service 만 접근한다.

권한: `web/gateway/src/main/resources/application.yml` 의 `gateway.rules` 표 한 곳에서 정한다. 지금은 `/api/admin/**` = ADMIN, 나머지 = 모든 역할. 역할 1·2·3 의 차이는 구현 단계에서 이 표에 줄을 추가한다.

## 시험 시설(시뮬레이션 월드)과 지도

`ros/sim/src/worlds/world_spec.py` 하나에서 월드(`inspection.world`)와 설계도 기준 지도(`ros/maps/reference.*`)를 만든다.
소규모 공장 건물: 사무실(충전 위치 = 원점) · 전기실 · 생산동(설비·랙) · ㄱ자로 꺾인 복도 C1(폭 1.4m)·C2(폭 1.1m), 문 5개.

| 지점 | 위치 | 가는 길 |
| --- | --- | --- |
| P1 소화기 앞 | 생산동 서쪽 벽 | 사무실 → C1 → 생산동 문 |
| P2 비상구 앞 | C2 복도 끝 | C1 → 꺾임 → 좁은 C2 (또는 생산동 동쪽 문으로 C2 중간 진입) |
| P3 분전반 앞 | 전기실 서쪽 벽 | 사무실 북쪽 문(폭 0.9m) |

실제 현장과 같은 순서로 지도를 만든다 (SLAM → 저장 → AMCL 위치 추정 + Nav2):

```bash
SIM_MODE=slam docker compose up -d sim          # slam_toolbox + Nav2
docker compose exec sim /sim/tools/explore.sh    # 경유점을 돌며 지도 작성
docker compose exec sim /sim/tools/save_map.sh   # ros/maps/site.pgm · site.yaml 저장 + 고립 잡음 점 정리(원본은 site.raw.pgm)
docker compose up -d sim                         # 기본(nav) 모드로 재시작 → site.yaml 사용
```

`site.yaml` 이 없으면 `reference.yaml`(설계도 기준)을 쓴다.

Nav2·AMCL 설정은 `ros/sim/src/config/nav2_params.yaml`(TurtleBot3 기본값에서 고친 점을 파일 맨 위에 적어 둠).
시험하며 확인한 운영상 주의점 — 실제 현장에서도 그대로 적용된다:
- 복도·문 폭: TurtleBot3 Waffle + 기본 여유값에서는 **1.0~1.1m 이상**이어야 저장 지도 운영에서 통행 가능으로 판정된다(0.9m 복도는 막힘으로 판정됐다).
- 지도 잡음: 저장 지도의 점 하나가 로봇 반경만큼 팽창돼 좁은 복도를 막는다 → 저장 후 정리 필요.
- 긴 복도의 위치 추정: AMCL 이 복도 방향으로 미끄러지면 라이다가 엉뚱한 곳에 벽을 찍어 문이 막힌 것처럼 보인다 → 빔 수·갱신 간격·odom 오차 계수 조정.

### 장애물 시험

```bash
docker compose exec sim /sim/tools/obstacle.sh place detour    # C1 팔레트: 옆으로 비켜 지나감 (우회 가능)
docker compose exec sim /sim/tools/obstacle.sh place reroute   # C2 아래쪽 막힘: 생산동을 거쳐 다른 경로로
docker compose exec sim /sim/tools/obstacle.sh place block     # C2 위쪽 막힘: P2 진입 불가
docker compose exec sim /sim/tools/obstacle.sh clear           # 모두 치우기
```

장애물 처리는 로봇 측 Nav2 가 한다(일시 장애물 대기, 우회 경로 재계획, 복구 동작). Nav2 가 실패하면 목표 브리지(`ros/robot/src/nav2_goal_bridge.py`)가 현재 위치에서 경로를 다시 계산해 원인을 나눈다.

| 사유 코드 | 뜻 | 화면 표시 |
| --- | --- | --- |
| BLOCKED_NO_PATH | 재계획해도 경로 없음 → 통로가 막혀 진입 불가 | 통로 막힘 · 진입 불가 |
| NAV_FAILED | 경로는 있으나 주행 실패(복구 동작 소진) | 주행 실패 |
| NO_PROGRESS | 90초 동안 목표에 가까워지지 못함 | 진행 불가 |
| NAV_UNAVAILABLE / PREFLIGHT_FAILED / CAPTURE_FAILED / TIMEOUT | 주행 시스템 미준비 / 출발 전 검사 실패 / 촬영 실패 / 서버 측 시간 초과 | — |

우회해서 도착한 경우는 성공으로 기록하고, 처음 계획보다 크게 돌아갔거나 복구 동작이 있었으면 "경로상 장애물 우회"를 참고로 남긴다(판단 기준은 근사치).

## 시뮬레이션 → 실제 로봇

서버 코드는 바꾸지 않는다. 경계는 "목표 지점 단위"다: 서버는 `/inspection/goal` 로 목표를 보내고 `/inspection/goal_status` 로 결과를 받는다.

1. 로봇(또는 Remote PC)에서 SLAM 으로 현장 지도를 만들고 Nav2 를 띄운 뒤, rosbridge(9090)·rosapi, web_video_server(8080), `ros/robot/src/nav2_goal_bridge.py`, `ros/robot/src/cmd_vel_watchdog.py` 를 실행한다. 팀 주행 코드를 쓰려면 같은 토픽 약속(`/inspection/goal`·`goal_status`·`bridge_status`)을 지키는 노드로 바꾼다.
2. 관리자 화면 → 로봇 → 연결 설정에서 `rosbridgeUrl`, `videoUrl`, 토픽 이름을 실제 값으로 바꾸고 저장한다(어댑터 재연결).
3. 시뮬레이터 없이 실행: `docker compose up -d --scale sim=0`

## 화면 문서

- `docs/web_storyboard.svg` 화면 구조도·흐름도·화면 설계 / `docs/web_screen_tree.svg` 화면 트리 / `docs/web_service_scenario.svg` 가상 서비스 흐름
- 생성 스크립트: `docs/storyboard/*.py`

## 신희초안 기능 후보 반영

구현: 1·2·3·4·5·9·10·11·12·14·16·17(기준 설정)·18·23, 개선안 28~35(관제·조종, 게이트웨이 권한, 영상 중계, 워치독, 사용자·역할, 제어권 회수·비상 정지, 감사 로그, 시스템 상태).
제외: 6·7·8·15·19·25~27(PC 로컬 분석), 13(전환 정책 미정), 20~22(투척 미채택), 24(장애 시험 자동화, 후속).

## 알려진 한계

- 시뮬레이션은 Apple Silicon 에서 에뮬레이션으로 돌아 실제보다 느리다. 점검 작업 한 건에 수 분이 걸릴 수 있다.
- HTTPS 는 적용하지 않았다(로컬 시험용). 배포 시 nginx 에 인증서를 넣고 `COOKIE_SECURE=true` 로 바꾼다.
- 관리 기능을 웹 admin 화면에 두었다. 개선초안 04_PC앱(관리 기능은 PC 앱 전용)과 다르며, 권한을 정할 때 경계를 다시 정리한다.
- Spring 서비스는 시작할 때마다 빌드한다(개발 편의). 운영 배포에서는 jar 를 이미지에 넣는 방식으로 바꾼다.
