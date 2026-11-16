# 실행 안내 — 화재 점검 로봇 서비스 (시뮬레이션)

웹(로그인·관리자·사용자 화면) + MSA 백엔드 + ROS 2 TurtleBot3 시뮬레이션(SLAM·Nav2)을 Docker Compose 로 한 번에 띄운다.

> 설치부터 실행·초기화·문제 해결까지 단계별 안내(macOS·Linux·Windows PowerShell)는 [DOCKER_GUIDE.md](DOCKER_GUIDE.md) 를 본다.

## 실행

```bash
cp .env.example .env        # 비밀번호·JWT 키를 바꾼다 (DEMO_USERS_PASSWORD 를 넣으면 sup1·mgr1·user1 시험 계정 생성)
docker compose up -d --build
```

- 접속: http://localhost:8080 — 기본 계정 admin / `Admin1234!`, 시험 계정 sup1·mgr1·user1 / `User1234!` (`.env` 로 바꿀 수 있다).
- 첫 실행은 각 Spring 서비스가 시작할 때 Maven 빌드를 하고, 시뮬레이터가 Nav2 를 올리므로 3~5분 걸린다.
- 종단 간 시험: `python3 scripts/e2e_test.py` (장애물 시나리오 제외: `--skip-obstacles`)

## 폴더 구조: 아키텍처 계층 > 기술 > 컨테이너

```
web/                       서버 쪽
  nginx/                   정문 cdn(cdn.conf) + 원본 서버 web(nginx.conf) + React 화면(frontend/)
  spring/                  Spring 서비스: gateway, user-service, inspection-service, robot-service, common(공유 라이브러리)
  python/                  Python 서비스: analysis-service
  postgres/                DB 초기화(init/)
ros/                       로봇 쪽
  sim/                     시뮬레이션(Gazebo·SLAM·Nav2·시험 도구)
  robot/                   로봇 측 노드(실제 로봇에도 같은 코드)
  maps/                    지도
docs/                      문서 (목록: docs/README.md)
  architecture/            시스템 아키텍처 구성도 · 시스템 사이클 SVG + 생성 스크립트
  guide/                   실행 안내(이 파일)·Docker 구동 가이드
  plan/                    향후 프로젝트 계획(ROADMAP.md)
  storyboard/              화면 스토리보드 SVG + 생성 스크립트
scripts/                   E2E 시험
```

명령은 모두 저장소 루트에서 실행한다. 루트에는 `README.md`, `도커_실행.md`, `compose.yaml`, `.env.example` 만 둔다.

폴더 이름만 보고 무엇으로 만든 서비스인지 알 수 있게 기술별로 묶고, 그 안은 컨테이너(서비스)마다 폴더 하나다.


| 폴더 | 컨테이너 | 내용 |
| --- | --- | --- |
| `web/spring/gateway/` | gateway | Spring Cloud Gateway: JWT 쿠키 검증, 세션 유효성, 경로별 역할 정책, 감사 기록, 시스템 상태 |
| `web/spring/user-service/` | user-service | 로그인·사용자·역할(0 ADMIN, 1 관리자, 2 매니저, 3 사용자)·감사 로그 |
| `web/spring/inspection-service/` | inspection-service | 점검 지점, 작업, 사건 기록, 관측 사진, 사람 판정, 재점검, 지점 이력 |
| `web/spring/robot-service/` | robot-service | 로봇 연결 계층: `RobotAdapter`(rosbridge·mock), 상태·제어권·조종·비상 정지·미션 실행·결과 재전송·영상 중계 |
| `web/python/analysis-service/` | analysis-service | Python: 사진 품질 배치 분석(ROI 밝기·선명도 → 재촬영 후보) |
| `web/nginx/` | cdn · web (nginx) · frontend-build | 정문 `cdn.conf`(CDN 엣지 역할: 화면 파일을 보관해 대신 제공, `/api`·`/ws` 는 통과) + 원본 서버 `nginx.conf`(화면 제공, 캐시 기간 지시, 게이트웨이 프록시) + React 화면 `frontend/`(frontend-build 가 빌드) |
| `web/postgres/init/` | db | PostgreSQL 17 초기화: 서비스마다 DB·계정 분리 |
| `web/spring/common/` | common-build | 서비스 간 계약(JWT·사용자 헤더) 공유 라이브러리 |
| `ros/sim/` | sim | Gazebo 월드·SLAM/Nav2 실행·시험 도구 |
| `ros/robot/` | (sim 안에서 실행) | 로봇 측 노드: Nav2 목표 브리지, cmd_vel 워치독 — 실제 로봇에도 같은 코드 |
| `ros/maps/` | — | 지도: `site.*`(SLAM), `reference.*`(설계도 기준) |

선택 이유: MSA 에서 빌드·배포·장애 격리의 단위는 컨테이너(서비스)다. 서비스마다 자기 `src`·빌드 파일·Dockerfile 을 가지면
한 서비스만 고쳐 다시 띄울 수 있고 담당도 폴더로 나뉜다. 최상위 `web/`(서버) · `ros/`(로봇)는 배치 위치가 다른 두 계층을 구분하는 묶음이다.
공유 코드는 `web/spring/common` 라이브러리 하나로 최소화했다(서비스들은 버전으로 의존).

이미지에는 실행 환경만 있고, 코드는 각 폴더를 볼륨으로 연결해 구동한다. 코드를 고친 뒤:

| 고친 곳 | 반영 |
| --- | --- |
| Spring 서비스 | `docker compose restart <서비스>` (시작할 때 다시 빌드) |
| `web/spring/common` | `docker compose run --rm common-build` 후 Spring 서비스 재시작 |
| 화면 | `docker compose run --rm frontend-build` |
| 분석 서비스 · ROS | `docker compose restart analysis-service` / `sim` |

네트워크: `front`(cdn ↔ web, 외부 포트 8080 하나) · `edge`(web ↔ gateway) · `backend`(gateway ↔ 서비스 ↔ db) · `robot`(robot-service ↔ sim). rosbridge 는 robot-service 만 접근한다.

권한: `web/spring/gateway/src/main/resources/application.yml` 의 `gateway.rules` 표 한 곳에서 정한다. 지금은 `/api/admin/**` = ADMIN, 나머지 = 모든 역할. 역할 1·2·3 의 차이는 구현 단계에서 이 표에 줄을 추가한다.

## 시험 시설(시뮬레이션 월드)과 지도

`ros/sim/src/worlds/world_spec.py` 하나에서 월드(`inspection.world`)와 설계도 기준 지도(`ros/maps/reference.*`)를 만든다.
소규모 공장 건물: 사무실(충전 위치 = 원점) · 전기실 · 생산동(설비·랙) · ㄱ자로 꺾인 복도 C1(폭 1.4m)·C2(폭 1.1m), 문 5개.

| 지점 | 위치 | 가는 길 |
| --- | --- | --- |
| P1 소화기 앞 | 생산동 서쪽 벽 | 사무실 → C1 → 생산동 문 |
| P2 비상구 앞 | C2 복도 끝 | C1 → 꺾임 → 좁은 C2 (또는 생산동 동쪽 문으로 C2 중간 진입) |
| P3 분전반 앞 | 전기실 서쪽 벽 | 사무실 북쪽 문(폭 1.0m) |

실제 현장과 같은 순서로 지도를 만든다 (SLAM → 저장 → AMCL 위치 추정 + Nav2):

```bash
SIM_MODE=slam docker compose up -d sim          # slam_toolbox + Nav2
docker compose exec sim /sim/tools/explore.sh    # 경유점을 돌며 지도 작성
docker compose exec sim /sim/tools/save_map.sh   # ros/maps/site.pgm · site.yaml 저장 + 고립 잡음 점 정리(원본은 site.raw.pgm)
docker compose up -d sim                         # 기본(nav) 모드로 재시작 → site.yaml 사용
```

`site.yaml` 이 없으면 `reference.yaml`(설계도 기준)을 쓴다.

순회 주행 계획(`ros/sim/src/tools/explore.py`)은 끼임을 막도록 다음 규칙으로 짠다.
- 경유점 사이는 직선이고, 구간 전체에서 로봇 중심이 벽·설비와 0.27m 이상(반경 0.22 + 지도 한 칸) 떨어진다.
  설비↔벽 0.65m 틈(양옆 여유 약 0.1m)처럼 좁은 곳도 틈 가운데 선을 따라 곧게 들어가고 나온다. 문은 가운데를 지난다.
- 출발 전에 `world_spec` 의 벽·설비로 이 규칙을 검사하고, 어긋나면 출발하지 않는다: `python3 ros/sim/src/tools/explore.py --check`
- 실패한 경유점은 코스트맵을 비우고 한 번 더 시도한 뒤 다음으로 넘어간다.
- 0.45m 틈(설비 2 ↔ 동쪽 벽)은 로봇 폭(반경 0.22)보다 좁아 지나갈 수 없으므로 계획에 넣지 않는다.

주행 제어기는 Regulated Pure Pursuit 이다. 굽은 곳에서 경로 방향과 26° 넘게 어긋나면 제자리에서 먼저 돌아 경로를 바라본 뒤 출발하고,
좁은 곳에서는 스스로 느려진다. 주행 품질은 `docker compose exec sim bash -c 'source /opt/ros/humble/setup.bash; python3 /sim/tools/drive_probe.py X Y 각도'` 로 잰다.

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
   카메라 영상은 **압축 토픽**(`/camera/image_raw/compressed`, JPEG)으로 받는다. 로봇에 `ros-humble-compressed-image-transport` 를 설치하면 카메라 노드가 압축 토픽을 함께 발행한다(`imageTransport: "raw"` 로 바꾸면 원본 토픽).
3. 시뮬레이터 없이 실행: `docker compose up -d --scale sim=0`

## 화면

- 디자인 컨셉: Apple Human Interface Guidelines — 시스템 글꼴, iOS 시스템 색(라이트·다크 모드), 사이드바(넓은 화면)·하단 탭 바(좁은 화면),
  큰 제목, 그룹형 목록, 세그먼트 컨트롤, 캡슐형 상태 배지. 스타일은 `web/nginx/frontend/src/styles.css` 맨 위에 정리했다.
- 아이콘: Google Material Symbols Rounded(Apache 2.0, 글꼴을 프로젝트에 포함 — 모든 OS 브라우저에서 같게 보임).
  화면 코드는 SF Symbols 식 이름으로 부르고 `Icon.tsx` 한 곳에서 연결한다. Apple SF Symbols 는 라이선스상 Apple 플랫폼 앱에서만 쓸 수 있어 웹에는 넣지 않았다.
- 관제(U1)는 두 모드다.
  - **카메라 모드**: 실시간 영상 + 방향키 조종(↑↓ 전진·후진, ←→ 제자리 회전, Space 정지). 누르는 동안만 움직이고, 제어권이 없으면 방향키를 누를 때 자동으로 요청한다.
  - **지도 모드**: 로봇의 지도 위에 로봇 위치·방향, 라이다 점, Nav2 계획 경로, 점검 지점을 표시한다. 지도를 클릭하고 "이 위치로 이동"을 누르면 Nav2 로 이동한다(제어권 필요, 방향키 조종을 시작하면 취소).
  - 지도는 로봇 측 브리지가 `/map` 을 `/inspection/map` 으로 5초마다 다시 내보내고, 지도 좌표 위치는 TF 로 계산해 `/inspection/map_pose` 로 낸다.
  - **실제 지도와 웹 지도는 따로다.** 실제 지도 `ros/maps/site.pgm` 은 로봇의 map_server·AMCL·Nav2 가 쓰고, 웹 지도는 robot-service 가
    그것을 받아 메모리에서 새로 그린 PNG(`/api/robots/{id}/map.png`, `MapRenderer`)다. 웹 지도 정리는 주행에 영향이 없다.
  - 웹 지도 정리: 미지 영역은 막힘으로 → 로봇이 다닐 수 있는 바닥만 계산(폭 0.4m 미만 틈은 닫힌 공간) → 떠 있는 장애물은 직사각형 →
    1칸 돌기·홈 제거 → SLAM 기울기로 생긴 1~2칸 벽 계단 펴기 → 바닥 경계를 정해진 굵기의 직선 벽으로. 라이다는 이웃한 점을 이어 선으로 그린다.

## 화면 문서

- `docs/storyboard/web_storyboard.svg` 화면 구조도·흐름도·화면 설계 / `docs/storyboard/web_screen_tree.svg` 화면 트리 / `docs/storyboard/web_service_scenario.svg` 가상 서비스 흐름
- 생성 스크립트: `docs/storyboard/*.py`

## 초안 기능 후보 반영

번호는 처음 받은 기획 초안(07 기능 후보)의 번호다. 초안 폴더는 저장소에서 지웠고, 이전 커밋(a320e10)에 남아 있다.

구현: 1·2·3·4·5·9·10·11·12·14·16·17(기준 설정)·18·23, 개선안 28~35(관제·조종, 게이트웨이 권한, 영상 중계, 워치독, 사용자·역할, 제어권 회수·비상 정지, 감사 로그, 시스템 상태).
제외: 6·7·8·15·19·25~27(PC 로컬 분석), 13(전환 정책 미정), 20~22(투척 미채택), 24(장애 시험 자동화, 후속).

## 알려진 한계

- 분석 서비스는 사진 품질(밝기·선명도)만 본다. 소화기 비치 여부 같은 내용 판독은 사람이 한다 — AI 판독 계획은 `docs/plan/ROADMAP.md`.

- 시뮬레이션은 Apple Silicon 에서 에뮬레이션으로 돌아 실제보다 느리다. 점검 작업 한 건에 수 분이 걸릴 수 있다.
- HTTPS 는 적용하지 않았다(로컬 시험용). 배포 시 nginx 에 인증서를 넣고 `COOKIE_SECURE=true` 로 바꾼다.
- 관리 기능을 웹 admin 화면에 두었다. 개선초안 04_PC앱(관리 기능은 PC 앱 전용)과 다르며, 권한을 정할 때 경계를 다시 정리한다.
- Spring 서비스는 시작할 때마다 빌드한다(개발 편의). 운영 배포에서는 jar 를 이미지에 넣는 방식으로 바꾼다.
