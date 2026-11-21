# 실행 안내 — 화재 점검 로봇 서비스 (시뮬레이션)

웹(로그인·관리자·사용자 화면) + MSA 백엔드 + ROS 2 TurtleBot3 시뮬레이션(SLAM·Nav2)을 Docker Compose 로 한 번에 띄운다.

> 설치부터 실행·초기화·문제 해결까지 단계별 안내(macOS·Linux·Windows PowerShell)는 [DOCKER_GUIDE.md](DOCKER_GUIDE.md) 를 본다.

## 실행

```bash
cp .env.example .env        # 비밀번호·JWT 키를 바꾼다 (DEMO_USERS_PASSWORD 를 넣으면 sup1·mgr1·user1 시험 계정 생성)
docker compose up -d --build
```

- 접속: http://localhost:8080 — 기본 계정 admin / `Admin1234!`, 시험 계정 sup1·mgr1·user1 / `User1234!` (`.env` 로 바꿀 수 있다).
- 시나리오(브랜치 `feat/scenarios-sim`): 소방 관제(지점별 점검 규칙 → 정상·경고·비상 → 경고)와 소화액 투척(화재 감지 → 터틀봇 출동 → 재판독 → 승인/자동 투척)이 시뮬레이션에서 돈다. 설계는 [plan/SCENARIOS.md](../design/SCENARIOS.md)·[plan/INTERFACES.md](../design/INTERFACES.md), 해 보는 방법은 아래 "시나리오 해 보기".
- 관제 대시보드: 전용 계정 dash1(역할 4 대시보드, 비밀번호는 시험 계정과 같음)로 로그인하면 바로 열린다(`/dashboard`). 조회만 할 수 있는 계정이고, 16:9 모니터 전체 화면용(1920×1080 고정, 반응형 아님)이다. 구성은 `web/nginx/frontend/src/pages/dashboard/` — `data.ts`(불러오기·경고) → `panels.tsx`(패널) + `layout.ts`(배치표) → `details.tsx`(누르면 뜨는 상세).
- 첫 실행은 각 Spring 서비스가 시작할 때 Maven 빌드를 하고, 시뮬레이터가 Nav2 를 올리므로 3~5분 걸린다.
- 종단 간 시험: `python3 scripts/e2e_test.py` (장애물 시나리오 제외: `--skip-obstacles`)

## 폴더 구조: 아키텍처 계층 > 기술 > 컨테이너

```
web/                       서버 쪽
  nginx/                   정문 cdn(cdn/default.conf) + 원본 서버 web(web/default.conf) + React 화면(frontend/)
  spring/                  Spring 서비스: gateway, user-service, inspection-service, robot-service, common(공유 라이브러리)
  python/                  Python 서비스: analysis-service
  postgres/                DB 초기화(init/)
ros/                       로봇 쪽
  sim/                     시뮬레이션(Gazebo·SLAM·Nav2·시험 도구)
  robot/                   로봇 측 노드(실제 로봇에도 같은 코드)
  maps/                    지도
docs/                      문서 (목록: docs/README.md)
  guide/                   실행 안내(이 파일) · Docker 구동 가이드
  architecture/            시스템 구조: 구성도 · 시스템 사이클 · SPA 사이클 SVG + 생성 스크립트
  navigation/              주행: 지도 3겹 · 주행 제어기 설명서 SVG + 생성 스크립트
  design/                  설계: 시나리오(SCENARIOS.md) · 인터페이스(INTERFACES.md)
  plan/                    계획: 향후 계획(ROADMAP.md) · 주간 일정(SCHEDULE.md)
  storyboard/              화면 스토리보드 SVG + 생성 스크립트
  _lib/                    SVG 생성 스크립트 공용 그리기 도구
scripts/                   E2E 시험
```

명령은 모두 저장소 루트에서 실행한다. 루트에는 `README.md`, `도커_실행.md`, `compose.yaml`, `.env.example` 만 둔다.

폴더 이름만 보고 무엇으로 만든 서비스인지 알 수 있게 기술별로 묶고, 그 안은 컨테이너(서비스)마다 폴더 하나다.


| 폴더 | 컨테이너 | 내용 |
| --- | --- | --- |
| `web/spring/gateway/` | gateway | Spring Cloud Gateway: JWT 쿠키 검증, 세션 유효성, 경로별 역할 정책, 감사 기록, 시스템 상태 |
| `web/spring/user-service/` | user-service | 로그인·사용자·역할(0 ADMIN, 1 관리자, 2 매니저, 3 사용자, 4 대시보드)·감사 로그 |
| `web/spring/inspection-service/` | inspection-service | 점검 지점, 작업, 사건 기록, 관측 사진, 사람 판정, 재점검, 지점 이력, 점검 계획(즉시·예약 실행) |
| `web/spring/robot-service/` | robot-service | 로봇 연결 계층: `RobotAdapter`(rosbridge·mock), 상태·제어권·조종·비상 정지·미션 실행·결과 재전송·영상 중계 |
| `web/python/analysis-service/` | analysis-service | Python: 사진 품질 배치 분석(ROI 밝기·선명도 → 재촬영 후보) |
| `web/nginx/` | cdn · web (nginx) · frontend-build | 정문 `cdn/default.conf`(CDN 엣지 역할: 화면 파일을 보관해 대신 제공, `/api`·`/ws` 는 통과) + 원본 서버 `web/default.conf`(화면 제공, 캐시 기간 지시, 게이트웨이 프록시) + React 화면 `frontend/`(frontend-build 가 빌드) |
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

`common-build` · `frontend-build` 는 빌드하고 끝나는 컨테이너다. 자세한 설명은 [BUILD_CONTAINERS.md](BUILD_CONTAINERS.md) 를 본다.

네트워크: `front`(cdn ↔ web, 외부 포트 8080 하나) · `edge`(web ↔ gateway) · `backend`(gateway ↔ 서비스 ↔ db) · `robot`(robot-service ↔ sim). rosbridge 는 robot-service 만 접근한다.

권한: `web/spring/gateway/src/main/resources/application.yml` 의 `gateway.rules` 표 한 곳에서 정한다. 지금은 `/api/admin/**` = ADMIN, 나머지 = 모든 역할. 규칙에 `methods` 를 적으면 그 메서드에만 맞는다 — 대시보드 역할(DASHBOARD)은 GET 만 허용되고 변경 요청·조종 WebSocket 은 거부된다. 역할 1·2·3 의 차이는 구현 단계에서 이 표에 줄을 추가한다.

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

주행 제어기는 MPPI 다. A\* 경로를 따르면서, 주행 중 지역 비용 지도에 새로 찍힌 장애물은 다시 계획되기를 기다리지 않고 바로 비켜 간다.
막혀서 길이 없으면 경로부터 다시 계획한다. 좁은 곳에서도 스스로 줄이지 않는다 — 기준은 "감속 없이 최대 속도로 달리는 것"이다.
로봇 모양은 경로 계획(전역 비용 지도)과 제어기(지역 비용 지도) 모두 반경 0.22m 원이다.

주행 품질은 `docker compose exec sim bash -c 'source /opt/ros/humble/setup.bash; python3 /sim/tools/drive_probe.py X Y 각도'` 로 잰다.
걸린 시간 · 평균 속도 · **최대속도 유지**(전진 속도 명령이 최대의 90% 이상이었던 시간 비율) · 벽까지 최소 거리 · 좌우 흔들림 · 전진 멈춤을 낸다.

```bash
docker compose exec sim /sim/tools/obstacle.sh place reroute      # C2 아래쪽을 막아 틈이 유일한 길이 되게
docker compose exec sim /sim/tools/obstacle.sh place gap 0.6      # C1 복도에 폭 0.6m 틈만 남김(좁은 통로)
docker compose exec sim bash -c 'source /opt/ros/humble/setup.bash; python3 /sim/tools/drive_probe.py 7.0 -0.1 0 --gap 0.6'
docker compose exec sim bash -c 'source /opt/ros/humble/setup.bash; python3 /sim/tools/drive_probe.py 7.0 -0.1 0 --drop detour 1.6'   # 1.6m 앞에 장애물을 갑자기 놓기
```

제어기를 바꾸며 잰 값(시뮬레이션, 최대 0.22m/s, 최대속도 유지 / 걸린 시간):

| 시험 | Regulated Pure Pursuit(이전) | MPPI |
| --- | --- | --- |
| 직선 3m | 60~77% / 16~20초 | 84~90% / 15~17초 |
| 굽은 길 8m (C1 ↔ P2) | 50~52% / 48~49초 | 89~93% / 38~39초 |
| 점검 지점 순회 (P1 → P3 → P2 → P1 → 충전 위치) | 재지 않음 | 69~95%, 모두 도착 (P3 가는 0.9m 문에서 69%) |
| 폭 0.7m 틈 | 36~41% / 20초 | 80~90% / 16~17초 |
| 폭 0.6m 틈 | 36~38% / 21초 | **멈칫(51초) 또는 실패** |
| 달리는 중 1.6m 앞에 놓인 팔레트(남는 폭 0.65m) | 28% / 23초 | 46% / 30초 |

- 3m 구간은 출발 가속 · 도착 감속 · 출발 전 제자리 회전이 10~15% 를 차지해 100% 가 되지 않는다.
- 위 표는 제어기용(지역) 비용 지도가 한 칸 0.05m 일 때의 값이다. 그때 MPPI 의 한계는 폭 0.7m 였다: 0.6m 틈에서는 로봇 중심이
  지날 수 있는 띠가 0.16m(세 칸)뿐이라 후보 궤적 대부분이 충돌로 버려졌다.
- **지역 비용 지도를 0.025m 로 바꾼 뒤에는 0.6m 틈도 속도를 유지하며 지난다**(아래 "계획 방식과 좁은 틈").
- 로봇 모양을 제어기 쪽만 실제 외곽 사각형으로 바꾸면 0.55m 틈도 85% 로 지나지만, 0.9m 문에서 벽에 끼어 채택하지 않았다
  (`nav2_params.yaml` 머리 5)).

#### 계획 방식과 좁은 틈

그림으로 보는 설명서: [주행 제어기](../navigation/drive_controller.svg)(목표 → 경로 → 속도 명령, 막혔을 때의 순서, 장애물별 결과) · [주행 지도 3겹](../navigation/drive_layers.svg)(기존 맵 · 계획 맵 · 2배 촘촘한 제어 맵, 새 장애물이 생기는 층).
계획기 · 제어기를 처음 본다면: [Theta\* 계획기](../navigation/theta_star.svg)(A\* 와 무엇이 다른가, 이 건물의 경로) · [MPPI 제어기](../navigation/mppi.svg)(한 주기에 하는 일, 평가 항목, 지금 설정값에서의 동작).

"처음에 출렁임 없는 최단 경로를 한 번 세우고, 그 경로를 제어기가 따라간다."

- **계획기**: Theta\*(any-angle A\*). 격자 칸을 따라가지 않고 서로 보이는 점끼리 직선으로 이어, 곧은 구간 + 모퉁이로만 된 경로를 낸다.
  벽에서 0.45m 띠만 비용을 두어 그 밖은 직선이다. Smac 2D A\* + 다듬기는 열린 곳에서도 S 자로 출렁였다.
- **한 번만 계획**: 행동 트리 `config/navigate_fixed_plan.xml`. 다시 계획하는 때는 목표가 바뀌었을 때, 경로가 막혔을 때,
  제어기 실패 · 복구 동작 뒤뿐이다(기본 트리는 1초마다 다시 계획해 주행 중 경로가 흔들렸다).
- **계획 경로 측정**: `docker compose exec sim bash -c 'source /opt/ros/humble/setup.bash; python3 /sim/tools/plan_probe.py'`
  — 로봇을 움직이지 않고 충전 위치 · P1~P3 사이 경로의 길이 · 꺾임 · 벽 여유를 낸다.
- **지역 비용 지도 0.025m**: 폭 0.6m 틈(문 바로 아래 골목을 반쯤 막은 `aisle60`)에서 0.05m 일 때는 15~31초 멈칫하거나 실패했고,
  0.025m 에서는 막지 않았을 때와 같은 시간에 지났다(P3 → P1 30~32초, P1 → P3 25~26초. 최근 12회 모두 틈으로 통과).
- **로봇 측 목표 브리지가 계획을 돕는 세 가지**(`ros/robot/src/nav2_goal_bridge.py`, 전역 비용 지도의 `virtual_layer`):
  - 장애물의 몸통 채우기 — 라이다는 새 장애물의 앞면만 선으로 본다. 보인 면 뒤 0.3m 를 막힌 것으로 찍는다(옆의 틈은 그대로).
  - 물러나 자세 잡기 — 같은 자리에서 제어기가 3번 실패하거나, 목표가 실패했는데 장애물이 0.4m 안에 있으면
    라이다로 본 가까운 장애물에서 멀어지는 쪽으로(전진 · 후진 중 덜 도는 쪽) 최대 0.45m 또는 사방 0.4m 가 트일 때까지
    움직인 뒤 다시 계획하게 한다. 실패한 목표는 이렇게 자세를 고쳐 3번까지 다시 보낸다.
    로봇 중심이 충돌 구역에 들면 Nav2 의 후진 · 회전 복구는 `Collision Ahead` 로 시작하지 못한다.
  - 두 번 막힌 자리 막기 — 물러났다가 같은 자리에서 또 막히면 그 자리를 막아 다른 길로 계획하게 한다.
- 한계: 로봇을 반지름 0.22m 원으로 본다. 틈이 0.5m 이하면 계획이 막힌 것으로 보고 돌아간다.
  두 번 막힌 자리 막기는 아직 작동한 적이 없다.
- **반복 시험**: `docker compose exec sim bash -c 'source /opt/ros/humble/setup.bash; python3 /sim/tools/nav_soak.py --rounds 3'`
  — 골목(P3 ↔ P1: 없음 · 폭 0.7 · 0.6 · 0.5m 틈 · 완전 막힘)과 생산동(P1 ↔ P2: 팔레트 · 문 막힘 · 진입 불가)을 장애물이
  서는 시점(출발 전 · 1.2m 앞 · 0.6m 앞)별로 달려, 맞는 결과(직행 · 우회 · 길 없음)인지와 정지 시간을 낸다(`--sets`, `--only`).
  한 회 42번 주행에 한 시간 남짓. 최근 연속 3회(126번)에서 틀린 결과 0, 물러나기는 뒤 2회(84번)에서 6번 작동했다.

Nav2·AMCL 설정은 `ros/sim/src/config/nav2_params.yaml`(TurtleBot3 기본값에서 고친 점을 파일 맨 위에 적어 둠).
시험하며 확인한 운영상 주의점 — 실제 현장에서도 그대로 적용된다:
- 복도·문 폭: TurtleBot3 Waffle + 기본 여유값에서는 **1.0~1.1m 이상**이어야 저장 지도 운영에서 통행 가능으로 판정된다(0.9m 복도는 막힘으로 판정됐다).
- 지도 잡음: 저장 지도의 점 하나가 로봇 반경만큼 팽창돼 좁은 복도를 막는다 → 저장 후 정리 필요.
- 긴 복도의 위치 추정: AMCL 이 복도 방향으로 미끄러지면 라이다가 엉뚱한 곳에 벽을 찍어 문이 막힌 것처럼 보인다 → 빔 수·갱신 간격·odom 오차 계수 조정.

### 금지구역

실제 장애물이 없어도 로봇이 가지 않게 막아 두는 구역이다(예: 공사 중인 구역).

- **설정**: ADMIN · 1 관리자(`sup1`)로 로그인 → 관제 → **지도** → **금지구역 설정** → 지도에서 누른 채 끌었다 놓으면 그 사각형이 금지구역이 된다
  (이름은 선택). 붉은 테두리 + 빗금 상자로 표시되고(고른 구역은 자홍), 다른 계정의 관제 지도 · 대시보드 지도에도 3초 안에 보인다.
- **삭제**: 금지구역 설정 모드에서 상자를 눌러 고른 뒤 **삭제**.
- **주행**: 구역은 계획 맵(전역 비용 지도)과 제어 맵(지역 비용 지도)에 막힌 칸으로 들어간다. 달리는 도중에 가던 길 위에 설정하면
  1 ~ 2초 안에 다시 계획해 돌아간다. 길이 그 구역뿐이면 그 지점은 "진입 불가"로 끝난다.
- **제한**: 한 변이 0.2m 이상이어야 하고, 로봇이 서 있는 자리(둘레 0.35m 포함)는 덮을 수 없다(덮으면 그 자리에서 계획이 거부돼 갇힌다).
- **시험**: `python3 scripts/e2e_test.py --only-zones` — 권한(2 매니저는 403) · 미리 설정(P3 → P1 이 랙 위로 돌아감) · 로봇 위 설정 거부 ·
  삭제 뒤 직행 · 달리는 도중 설정. 주행 내내 로봇 위치가 구역 안에 든 적이 없는지도 본다(34개 확인).

### 장애물 시험

```bash
docker compose exec sim /sim/tools/obstacle.sh place pallet    # 생산동 가운데 팔레트(P1 → P2 경로 위): 옆으로 비켜 지나감
docker compose exec sim /sim/tools/obstacle.sh place door      # 생산동 → C2 문 막힘: C1 · C2 로 돌아감
docker compose exec sim /sim/tools/obstacle.sh place block     # C2 위쪽 막힘: P2 진입 불가
docker compose exec sim /sim/tools/obstacle.sh place aisle     # 전기실 문 바로 아래 골목 막힘(P3 ↔ P1 경로 위): 랙 1 위로 돌아 나옴
docker compose exec sim /sim/tools/obstacle.sh place aisle60   # 같은 자리를 반쯤 막아 폭 0.6m 틈만 남김(aisle50 은 0.5m)
docker compose exec sim /sim/tools/obstacle.sh place detour    # C1 복도 팔레트 / reroute: C2 아래쪽 막힘 (C1 · C2 를 따라갈 때만 경로 위)
docker compose exec sim /sim/tools/obstacle.sh clear           # 모두 치우기
```

`python3 scripts/e2e_test.py --only-obstacles` 의 시나리오는 장애물을 **로봇이 달리는 도중에, 그때의 계획 경로를 막는 자리에** 놓는다
(놓기 직전에 경로와 겹치는지 검사한다. 계획기를 바꾸면 경로가 달라져, 고정된 자리의 장애물이 경로와 상관없어질 수 있다).

| | 구간 | 장애물 | 기대 |
| --- | --- | --- | --- |
| 9-1 | P1 → P2 | `pallet` | 제어기가 비켜 지나감 |
| 9-2 | P1 → P2 | `door` | 다시 계획해 C1 · C2 로 돌아감 |
| 9-3 | → P2, P3 | `block`(출발 전) | P2 진입 불가(`BLOCKED_NO_PATH`), P3 은 촬영 |
| 9-4 | P3 → P1 | `aisle` | 다시 계획해 랙 위로 돌아 나옴 |
| 9-5 | P3 → P1 | `aisle60` | 틈으로 지남 |
| 9-6 | P1 → P3 | 9-5 의 장애물을 그대로 둠 | 틈으로 지남 |


장애물 처리는 로봇 측 Nav2 가 한다(일시 장애물 대기, 우회 경로 재계획, 복구 동작). Nav2 가 실패하면 목표 브리지(`ros/robot/src/nav2_goal_bridge.py`)가 현재 위치에서 경로를 다시 계산해 원인을 나눈다.

| 사유 코드 | 뜻 | 화면 표시 |
| --- | --- | --- |
| BLOCKED_NO_PATH | 재계획해도 경로 없음 → 통로가 막혀 진입 불가 | 통로 막힘 · 진입 불가 |
| NAV_FAILED | 경로는 있으나 주행 실패(복구 동작 소진) | 주행 실패 |
| NO_PROGRESS | 90초 동안 목표에 가까워지지 못함 | 진행 불가 |
| NAV_UNAVAILABLE / PREFLIGHT_FAILED / CAPTURE_FAILED / TIMEOUT | 주행 시스템 미준비 / 출발 전 검사 실패 / 촬영 실패 / 서버 측 시간 초과 | — |

우회해서 도착한 경우는 성공으로 기록하고, 처음 계획보다 크게 돌아갔거나 복구 동작이 있었으면 "경로상 장애물 우회"를 참고로 남긴다(판단 기준은 근사치).

## 점검 (점검 계획: 즉시 실행 + 예약)

예전의 "점검 요청"과 "예약 점검"을 **점검** 하나로 합쳤다. 점검 계획 = 로봇 + 점검 구간(지점과 방문 순서) + 실행 방식이다.
계획마다 **실행** 버튼이 있어 누르면 바로 점검 작업을 요청하고(작업 요청자는 누른 사람), 실행 방식에 시각을 정해 두면 그때 자동으로 실행한다.
한 번만 점검하려면 새 점검에서 "저장하고 실행"을 누른다. 실행은 사용자 역할 누구나, 편집·삭제는 만든 사람 또는 3 사용자보다 높은 역할만 한다.
(재점검은 관측 화면에서 따로 요청한다 — `POST /api/inspections`, `…/recheck` 는 그대로 있다.)

| 실행 방식 | 설정 |
| --- | --- |
| 수동 | 없음 — 실행 버튼으로만 |
| 한 번 | 실행 일시 |
| 간격 반복 | 간격(5분 이상), 첫 실행 일시(선택), 요일·시간대 제한(선택, 예: 평일 09:00~18:00, 자정을 넘는 시간대 가능) |
| 매일 | 시각 |
| 요일 지정 | 요일 + 시각 |

- 시간대: 모든 컨테이너(Java·Python·PostgreSQL·nginx·ROS)를 `APP_TZ`(기본 `Asia/Seoul`)로 맞춘다 — 프로그램의 "지금", 로그, psql 조회가 화면과 같은 한국 시간이다.
  PostgreSQL 은 initdb 때 설정 파일에 UTC 가 굳어 있어 시작 옵션(`-c timezone`, `-c log_timezone`)으로 덮는다. 저장되는 시각(`timestamptz`)은 시간대와 무관한 절대 시각이라 바꿔도 기존 기록은 그대로다.
  예약 시각 기준 `SCHEDULE_ZONE` 은 따로 정하지 않으면 `APP_TZ` 를 따른다. 화면 왼쪽 아래 "서버 시간" 단추로 서버 시각과 기기 시계 차이를 볼 수 있다(`GET /api/time`).
- 실행기(inspection-service `ScheduleService`)가 5초마다 때가 된 회차를 로봇별 **실행 버퍼(대기열)** 에 담고, 로봇이 비면 예정 시각 순서대로 작업을 만든다.
  로봇이 작업 중·조종 중·연결 안 됨이면 회차를 건너뛰지 않고 기다렸다가 앞 작업이 끝나면 이어서 실행한다.
- 버퍼에 회차가 쌓이면 사용자 화면 위쪽에 밀린 예약 안내가 뜬다: 밀린 건수와 최대 지연, 로봇별로 지금 하는 작업(작업 번호·상태·지점 순서·현재 지점과 진행·요청자·경과 시간)과 그 뒤에 쌓인 회차 전부(실행 순서·예약 이름·지점·예정 시각·지연). 접어 둘 수 있다(`GET …/backlog`). 점검 상세 화면의 "대기 중"에서 회차별로 대기를 취소할 수 있다.
  늦게 실행된 회차는 실행 기록에 지연 시간(`delay_sec`)과 이유가 남고, 작업 메모에도 "(예정 HH:mm, N분 지연)"이 붙는다.
- 실행 버퍼는 서버 메모리에만 있다. inspection-service 가 재기동하면 버퍼는 빈 상태로 시작하고, 꺼져 있던 동안 지나간 회차(재기동 시각 이전 예정)는 실행하지 않고 "놓침"(MISSED)으로만 남긴다. 재기동 이후 예정 회차부터 다시 실행한다.
- 예약을 끄거나 지우면 그 예약의 대기 회차도 치운다(CANCELLED). 다시 켠 예약은 지금 기준으로 다음 시각을 다시 계산한다.
- 주의: 간격이 작업 시간보다 짧으면 대기열이 계속 늘어난다(건너뛰지 않으므로). 간격은 한 번 순회하는 시간보다 길게 잡는다.
- 예약이 만든 작업은 만든 사람 이름으로 요청되고, 작업 목록에 "예약" 표시가 붙는다. 3 사용자는 자기가 만든 예약만 고칠 수 있다.
- API: `GET/POST /api/inspections/schedules`, `PUT/DELETE …/{id}`, `POST …/{id}/enabled`, `POST …/{id}/run`(지금 한 번 실행, 로봇이 바쁘면 대기열로), `GET …/pending`(지연 목록), `DELETE …/pending/{key}`(대기 취소).

## 시뮬레이션 → 실제 로봇

서버 코드는 바꾸지 않는다. 경계는 "목표 지점 단위"다: 서버는 `/inspection/goal` 로 목표를 보내고 `/inspection/goal_status` 로 결과를 받는다.

1. 로봇(또는 Remote PC)에서 SLAM 으로 현장 지도를 만들고 Nav2 를 띄운 뒤, rosbridge(9090)·rosapi, web_video_server(8080), `ros/robot/src/nav2_goal_bridge.py`, `ros/robot/src/cmd_vel_watchdog.py` 를 실행한다. 팀 주행 코드를 쓰려면 같은 토픽 약속(`/inspection/goal`·`goal_status`·`bridge_status`)을 지키는 노드로 바꾼다.
2. 관리자 화면 → 로봇 → 연결 설정에서 `rosbridgeUrl`, `videoUrl`, 토픽 이름을 실제 값으로 바꾸고 저장한다(어댑터 재연결).
   카메라 영상은 **압축 토픽**(`/camera/image_raw/compressed`, JPEG)으로 받는다. 로봇에 `ros-humble-compressed-image-transport` 를 설치하면 카메라 노드가 압축 토픽을 함께 발행한다(`imageTransport: "raw"` 로 바꾸면 원본 토픽).
3. 시뮬레이터 없이 실행: `docker compose up -d --scale sim=0`

## 화면

- 디자인 컨셉: Apple Human Interface Guidelines — 시스템 글꼴, iOS 시스템 색(라이트·다크 모드), 큰 제목, 그룹형 목록(inset grouped),
  › 가 붙은 목록 칸, 스위치, 세그먼트 컨트롤, 캡슐형 상태 배지. 스타일은 `web/nginx/frontend/src/styles.css`, 공통 부품은 `src/ui.tsx`.
- 라이트 모드 색상표: 후보 8개(iOS 기본, 화이트, 회청, 슬레이트 50/200·100/300, 그레이, 쿨 뉴트럴·쿨 뉴트럴 진하게)를 WCAG 대비로 비교했고,
  모니터마다 밝기가 달라도 경계가 또렷하게 보이도록 **쿨 뉴트럴 진하게** 를 쓴다.
  | 항목 | 기준 | 결과 |
  | --- | --- | --- |
  | 카드/바탕 | 1.07~1.16 | 1.14 |
  | 카드 윤곽/카드 | 1.30~1.75 | 1.52 |
  | 칸 구분선/카드 | 1.12~1.35 | 1.25 |
  | 보조 글자 | 4.5 이상 | 7.6 |
  | 아이콘·흐린 글자 | 3.0 이상 | 3.9 |
  색: 바탕 `#eef0f4`, 카드 `#ffffff`, 사이드바 `#fbfbfd`, 윤곽 `#cdd2da`, 구분선 `#e3e6eb`, 글자 `#111827`/`#4b5563`/`#7a8291`.
  꼬리표·배지 글자는 시스템 색 대신 진한 잉크(`--ink-*`)를 쓰고 바탕은 10% 로 옅게 해 4.8:1 이상을 맞췄다. 다크 모드는 iOS 시스템 색 그대로다.
- 지원 화면: 스마트폰(<744px: 하단 탭 바, 한 열, 저장·실행 버튼은 탭 바 위에 고정), 태블릿(744~1179px: 좁은 사이드바),
  PC 모니터(≥1180px: 사이드바, 목록 900px·폼 680px 폭, 상세는 두 열).
- 화면은 일 단위로 나눈다: 목록 → 상세 → 편집(폼). 표 대신 목록 칸을 쓰고, 추가·편집은 대화상자 대신 별도 화면이다.
  사용자: 관제 / 점검(목록·상세·새 점검·편집) / 작업(목록·상세·관측) / 지점 이력(지점 목록·지점별 이력).
  관리자: 사용자·로봇·점검 지점(각각 목록·상세·폼) / 분석 기준 / 감사 로그 / 시스템.
- 목록 칸은 정보를 나눠 보여 준다: 앞 아이콘(상태·종류 색), 굵은 제목 + 색 꼬리표(상태·예약/수동·역할), 아이콘이 붙은 정보 줄,
  지점 코드는 청록 배지(지도의 점검 지점 색)로 나눠 › 로 방문 순서를 잇는다, 로봇은 연결 점이 붙은 칩. 부품은 `ui.tsx` 의 Tag·PointBadge·RouteChips·RobotChip·Meta·Avatar.
- 점검 지점 추가·수정은 지도에서 고른다: 누르면 위치, 누른 채 끌면 촬영 방향(오른쪽 0°, 반시계 +). "로봇 현재 위치로" 로 로봇이 서 있는 자리·방향을 그대로 넣을 수도 있다.
  지도 좌표 ↔ 화면 변환은 관제 지도와 같은 `src/mapGeo.ts` 하나를 쓴다. 지도 PNG 를 칸 수 × 축척 그대로 그려 칸 경계가 화면 픽셀 경계와 맞으므로,
  화면 → 좌표 → 화면 왕복 오차는 0 이다. 저장 값은 0.01m·1° 단위. (SLAM 지도 자체와 Gazebo 월드 사이에는 벽 안쪽 면 기준 0.04~0.07m 차이가 있다 — 로봇은 지도 좌표로 움직이므로 지도에서 고른 자리로 간다.)
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

## 시나리오 해 보기 (브랜치 `feat/scenarios-sim`)

터틀봇 한 대로 시뮬레이션에서 돈다. 젯봇은 아직 없어 감지 보고를 도구가 대신 보내고, 투척 기구는 모의 노드가 답한다.

### 가장 쉬운 방법: 시연 단추와 스크립트

시나리오를 손으로 따라 하지 않고 한 번에 돌린다. 둘은 같은 일을 한다(서버의 `DemoService` 가 단계를 차례로 실행).

- **화면:** admin 으로 로그인 → **"시연"** 메뉴 → 시나리오의 **실행** 단추. 아래에 진행 기록이 실시간으로 나온다. 실행 중에는 **중지**, 끝난 뒤 정리는 **초기화**. 맨 위 **통합 시연**은 초기화 → 소방 관제(이상 → 복구) → 화재(오탐 → 자동 투척)를 한 번에 이어서 돌린다(스크립트의 `all` 과 같음).
- **스크립트:** `python3 scripts/demo.py <시나리오>` (목록: `python3 scripts/demo.py`). `all` 은 소방 관제(이상 → 복구) → 화재(오탐 → 자동 투척)를 이어서 돌린다. `stop` 은 중지.

| 시나리오 | 하는 일 |
| --- | --- |
| `fire-approval` 화재 · 사람 승인 | 투척 모드를 사람 승인으로 두고 화재를 낸다. 터틀봇이 도착하면 **투척 승인 팝업에서 직접 승인**한다 |
| `fire-auto` 화재 · 자동 투척 | 자동 모드로 화재 → 도착 → 재판독 → 자동 투척 → 현장 감시 → 30초 뒤 열원을 없애 스스로 종료 |
| `fire-false` 화재 · 오탐 | 열원이 없는 곳에 비상 감지 보고 → 가서 보고 쏘지 않고 닫음 |
| `fire-preempt` 점검 중 화재 | 점검을 시작한 뒤 화재 → 점검을 멈추고 출동(승인은 화면에서) |
| `rules-abnormal` 소방 관제 · 이상 | 소화기 치움 · 표시등 빨강 · 계기판 0.6 → 세 지점 점검 → 비상 2 · 경고 1 |
| `rules-restore` 소방 관제 · 복구 | 대상 원위치 → 다시 점검 → 경고 자동 해제 |
| `reset` 초기화 | 인쇄물 치움 · 대상 원위치 · 열린 사건 닫기 · 투척 모드를 사람 승인으로 |

- 비상 팝업과 투척 승인 팝업은 **사용자 화면(user1)이나 대시보드(dash1)** 를 다른 창에 띄워 두고 본다(관리자 화면에는 뜨지 않는다).
- 지점에 규칙이 하나도 없으면 시연용 규칙("[시연] …")을 스스로 만든다. 이미 규칙이 있으면 그것을 쓴다.
- 한 번에 하나만 실행된다. 시뮬레이션 전용이다: 웹 서버는 sim 컨테이너의 도구를 직접 실행할 수 없어서, sim 의 `sim_control.py` 노드가 토픽(`/sim/command`)으로 명령을 받아 `fire.sh` · `target.sh` 를 대신 실행한다(실제 로봇에는 이 노드가 없다).

아래는 같은 일을 손으로 하는 방법이다.

### 소방 관제: 규칙 → 등급 → 경고

1. admin 으로 로그인 → "점검 지점" → 지점의 **규칙** → 규칙 추가. 판독기 종류를 고르면 설정 칸과 등급 기준 예시가 채워진다. "규칙 시험"에서 그 지점의 최근 사진으로 바로 판독해 볼 수 있다.

   | 지점 | 대상 | 판독기 | 기대 영역(사진 비율) | 등급 기준 예 |
   | --- | --- | --- | --- | --- |
   | P1 | 소화기(빨간 상자) | OBJECT | 0, 0, 1, 0.8 | IN_REGION 정상 · MISSING 비상 |
   | P2 | 표시등(초록 상자 위) | LAMP | 0, 0, 1, 0.33 | green 정상 · yellow 경고 · red 비상 |
   | P3 | 계기판(노랑 상자 위) | GAUGE | 0, 0, 1, 0.37 | 0.7~0.98 정상 · 0.5~0.7 경고 · 그 밖 비상 |

2. 대상을 바꾼다: `docker compose exec sim /sim/tools/target.sh gauge 0.6` · `lamp red` · `extinguisher remove` (되돌리기 `reset`).
3. user1 로 점검을 실행한다. 사진이 분석되면 관측 상세에 규칙별 등급이 나오고, 경고·비상이면 "경고" 메뉴와 대시보드에 뜬다.
4. 대상을 되돌리고 다시 점검하면 경고가 스스로 풀린다.

로봇의 도착 방향 허용 오차(0.15rad) 때문에 대상이 사진에서 좌우로 ±15% 쯤 움직인다. 그래서 영역을 가로 전체로 두고 세로로만 나눴고, 소화기는 "있다/없다"만 가린다("옆으로 옮겨짐"은 지금 영역으로는 가릴 수 없다).

### 소화액 투척: 감지 → 출동 → 재판독 → 투척

1. 투척 모드를 고른다: sup1 로 "사건" 화면 위의 세그먼트(사람 승인 / 자동 투척), 또는 admin "설정".
2. 화재를 낸다: `docker compose exec sim /sim/tools/fire.sh place office_south emergency --detect` (자리: `fire.sh list`). 열화상 인쇄물이 세워지고, 젯봇 대신 감지 보고가 간다.
3. 사건이 생기고 터틀봇이 투척 위치(사거리 1m, 판을 정면으로 보는 자리)로 간다. 도착하면 자기 카메라로 다시 판독한다.
   - 사람 승인 모드: 로봇이 도착하면 **투척 승인 팝업**이 뜬다(사용자 영역의 모든 화면과 대시보드, 비상 팝업보다 위). 로봇의 실시간 카메라와 재판독 결과를 보고 **투척 승인**을 누르면 쏜다. 대시보드 전용 계정(dash1)도 승인할 수 있다(조회 전용의 유일한 예외). "사건" 상세에서도 승인할 수 있다.
   - 자동 투척 모드: 재판독이 비상이고 조준 범위 안이면 바로 쏜다. 아니면 승인 대기로 넘어간다.
   - 가 보니 열원이 없으면(`place ... normal` 뒤 `detect ... emergency`) 쏘지 않고 오탐으로 닫는다.
4. 투척 뒤에도 열원이 보이면 터틀봇이 그 자리에 머물며 10초마다 다시 찍어 본다(**현장 감시**, 사건 상태 "투척함 · 현장 감시 중"). 열원이 사라지면(`fire.sh place <자리> normal` 로 열원 없는 인쇄물로 바꾸면 연속 2회 정상) 스스로 닫는다. 사람이 "조치 완료"(1 관리자·2 매니저)로 닫을 수도 있다. 닫히면 로봇이 풀려 밀린 예약 점검이 이어진다. 끝나면 `fire.sh clear`.

점검 중에 화재가 감지되면 그 점검 작업을 멈추고(취소) 출동한다.

**닫는 것과 실제 상황의 종료는 다르다.** 팝업의 "확인"은 봤다는 기록만 남기고, 사건의 "오탐으로 닫기"·"조치 완료"는 시스템의 사건을 닫고 로봇을 풀어 줄 뿐이다. 그래서 사건을 닫은 뒤에도 같은 감지가 계속 오면(유예 60초, 설정 `incident.reopen_grace_sec`) 새 사건으로 다시 열고 비상 경고도 다시 띄운다.

### 지금 구현에 없는 것

- 젯봇: 위치 추정(대기 구역 마커 정렬 · 대상 기준 보정), 순찰, 실시간 감지, 두 로봇의 조정(INTERFACES.md 7장 F3 · F4)
- 실물 투척 기구 연결(`ros/robot/src/launcher_bridge.py` 는 실물로 돌려 보지 않았다)
- 소화기 인식 모델(OBJECT 판독기는 색으로 찾는다), 마커(MARKER) 판독기와 기준 좌표 재기(A5)
- 도착 후 제자리에서 돌며 찾기(같은 자리에서 여러 번 다시 본다)
- 확인 불가 관측 · 실패한 작업의 경고는 경고 표에 넣지 않고 대시보드가 계산한다(확인 · 해제 대상이 아니다)
