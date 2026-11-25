# 화재 점검 로봇 (team_project3)

로봇이 시설을 돌며 소방 설비를 점검하고, 화재가 감지되면 출동해 소화액을 투척하는 서비스입니다.
웹(React) + Spring MSA 백엔드 + Python 분석 서비스 + ROS 2 Humble TurtleBot3 시뮬레이션을 Docker Compose 로 한 번에 띄웁니다.

> 지금 브랜치 `feat/scenarios-sim` 은 **터틀봇 한 대로 시뮬레이션에서** 동작합니다. 젯봇과 실물 투척 기구는 아직 연결되지 않았습니다([8. 지금 구현 범위](#8-지금-구현-범위)).

---

## 1. 접속과 계정

**접속 주소: http://localhost:8080**

| 계정 | 비밀번호 | 역할 | 로그인하면 열리는 화면 | 쓰는 곳 |
| --- | --- | --- | --- | --- |
| `admin` | `Admin1234!` | ADMIN (웹사이트 관리자) | 관리자 화면 | 사용자 · 로봇 · 점검 지점 · 규칙 · 설정 · **시연**. 사이드바 "화면 이동"으로 사용자 화면 · 관제 대시보드에도 들어간다(모든 화면 접근) |
| `sup1` | `User1234!` | 1 관리자 | 사용자 화면 | 아래 사용자 기능 전부 + 투척 모드 변경 · 수동 투척 · 사건/경고 해제 · **금지구역 설정**(관제 지도에서 끌어서 그림) |
| `mgr1` | `User1234!` | 2 매니저 | 사용자 화면 | 사용자 기능 + 수동 투척 · 사건/경고 해제 |
| `user1` | `User1234!` | 3 사용자 | 사용자 화면 | 관제 · 조종, 점검 요청, 판정, 경고 확인, 투척 승인 |
| `dash1` | `User1234!` | 대시보드 (조회 전용) | 관제 대시보드 | 상황실 모니터용. 조회만 하고, **투척 승인만 예외로** 할 수 있음 |

- 위 비밀번호는 기본값입니다. `.env` 의 `INITIAL_ADMIN_PASSWORD`(admin) 와 `DEMO_USERS_PASSWORD`(나머지 네 계정)를 바꿨다면 그 값을 씁니다.
- 관제 대시보드는 16:9 모니터 전체 화면용입니다(1920×1080 고정, 다크). 브라우저를 전체 화면(F11)으로 두고 봅니다.

## 2. 실행

```bash
cp .env.example .env
```

```bash
docker compose up -d --build
```

```bash
docker compose logs -f sim
```

- 처음 실행은 이미지 빌드 때문에 오래 걸립니다.
- 시뮬레이션은 준비까지 몇 분 걸립니다. 로그에 `lifecycle_manager_navigation ... Managed nodes are active` 가 보이면 로봇이 움직일 수 있습니다.
- 끄기: `docker compose down`
- 설치부터 문제 해결까지는 [docs/guide/guide_01_DOCKER_GUIDE.md](docs/guide/guide_01_DOCKER_GUIDE.md) 를 봅니다.

## 3. 시연 안내

시나리오를 단추 하나로 실행합니다. **창을 두 개** 띄워 두고 봅니다.

| 창 | 계정 | 보는 것 |
| --- | --- | --- |
| 창 1 | `admin` → **"시연"** 메뉴 | 시나리오 **실행** 단추와 진행 기록 |
| 창 2 | `dash1`(대시보드) 또는 `user1` | 지도 위 로봇, 경고, **비상 팝업**, **투척 승인 팝업** |

팝업은 관리자 화면에는 뜨지 않습니다. 같은 브라우저에서는 계정 하나만 로그인되므로, 창 2 는 다른 브라우저나 시크릿 창으로 엽니다.

### 시나리오

| 단추 | 일어나는 일 | 사람이 할 일 |
| --- | --- | --- |
| **화재 · 사람 승인** | 화재 감지 → 비상 팝업 → 터틀봇 출동 → 도착 → 투척 승인 팝업 | 팝업에서 로봇 카메라를 보고 **투척 승인** |
| **화재 · 자동 투척** | 출동 → 도착 → 재판독 → 자동 투척 → 현장 감시 → 30초 뒤 열원이 사라져 스스로 종료 | 없음 (비상 팝업은 확인을 눌러 닫음) |
| **화재 · 오탐** | 출동 → 가 보니 열원이 없음 → 쏘지 않고 닫음 | 없음 |
| **점검 중 화재** | 점검 시작 → 화재 감지 → 점검을 멈추고 출동 | 투척 승인 |
| **소방 관제 · 이상 발생** | 소화기 치움 · 표시등 빨강 · 계기판 0.6 → 세 지점 점검 → 비상 2건 · 경고 1건 | 비상 팝업 확인 |
| **소방 관제 · 복구** | 대상 원위치 → 다시 점검 → 경고가 스스로 풀림 | 없음 |
| **초기화** | 열화상 인쇄물 치움 · 대상 원위치 · 열린 사건 닫기 · 투척 모드를 사람 승인으로 | 없음 |

- 권장 순서: **초기화 → 소방 관제 · 이상 발생 → 소방 관제 · 복구 → 화재 · 오탐 → 화재 · 자동 투척 → 화재 · 사람 승인**
- 한 번에 하나만 실행됩니다. 로봇이 실제로 주행하므로 화재 시나리오는 1~3분, 소방 관제 시나리오는 5분 안팎 걸립니다.
- 중간에 멈추려면 **중지**, 뒷정리는 **초기화**를 누릅니다.

### 터미널에서 실행

단추와 같은 일을 스크립트로 합니다.

```bash
python3 scripts/demo.py
```

```bash
python3 scripts/demo.py fire-auto
```

```bash
python3 scripts/demo.py all
```

인자 없이 실행하면 시나리오 목록이 나옵니다. `all` 은 초기화 → 소방 관제(이상 → 복구) → 화재(오탐 → 자동 투척)를 이어서 돌리고, `stop` 은 중지합니다.
손으로 하나씩 해 보는 방법은 [docs/guide/guide_02_RUNNING.md](docs/guide/guide_02_RUNNING.md) 의 "시나리오 해 보기"에 있습니다.

---

## 4. 무엇을 하는 프로젝트인가

| | 소방 관제 (화재 예방) | 소화액 투척 (화재 대응) |
| --- | --- | --- |
| 흐름 | 로봇이 지점을 돌며 촬영 → 사진 판독 → 정상 · 경고 · 비상 등급 → 관제에 경고 | 화재 감지 → 터틀봇 출동 → 도착해 다시 판독 → 승인 또는 자동 투척 → 열원이 남으면 현장 감시 |
| 보는 것 | 소화기가 제자리에 있는가, 계기판 값, 표시등 색 | 열화상 이미지의 열원 크기 |
| 사람이 하는 일 | 규칙 정하기, 경고 확인, 판정 | 투척 승인(승인 모드), 사건 닫기 |

**기본 기능**

- 점검 계획: 지점과 순서를 정해 바로 실행하거나 예약(한 번 · 간격 · 매일 · 매주)합니다. 로봇이 바쁘면 건너뛰지 않고 기다렸다가 실행합니다.
- 관제 · 조종: 로봇 카메라(실시간), 지도 위 위치와 경로, 방향키 조종, 지도를 눌러 이동, 비상 정지.
- 점검 결과: 사진 품질 분석, 규칙별 판독 등급, 사람 판정(덮어쓰지 않고 쌓임), 재점검, 지점별 이력.
- 관리: 사용자 · 역할, 로봇, 점검 지점과 규칙, 설정, 감사 로그, 시스템 상태.

**비상 상황 알림**

- **비상 팝업:** 비상 등급 경고가 생기면 화면 전체를 붉게 덮는 큰 창이 뜹니다. "확인"을 눌러야 닫힙니다. 경고(주황)는 띄우지 않습니다.
- **투척 승인 팝업:** 로봇이 투척 위치에 도착하면 실시간 카메라, 재판독 결과와 함께 승인 단추가 뜹니다. 비상 팝업보다 위에 뜹니다.
- 닫는 것은 기록을 닫는 것이지 실제 상황의 종료가 아닙니다. 사건을 닫은 뒤에도 같은 감지가 계속 오면 새 사건으로 다시 엽니다.

## 5. 구성

```
브라우저 ─▶ cdn(nginx 캐시) ─▶ web(nginx) ─▶ gateway ─┬─▶ user-service        (로그인 · 사용자 · 역할 · 감사 로그)
                                                      ├─▶ inspection-service  (지점 · 규칙 · 작업 · 예약 · 경고 · 사건 · 설정)
                                                      ├─▶ robot-service ──────▶ sim (rosbridge)   로봇 연결 계층
                                                      └─▶ analysis-service    (사진 품질 · 판독기)
                                                                                    DB: PostgreSQL 17 (서비스별 DB)
```

| 컨테이너 | 기술 | 맡는 일 |
| --- | --- | --- |
| `cdn` · `web` | nginx | 화면 파일 캐시 · 제공, `/api` · `/ws` 전달. 밖으로 여는 포트는 `cdn` 의 8080 하나 |
| `gateway` | Spring Cloud Gateway | 쿠키 JWT 검증, 경로별 역할 정책, 감사 기록 |
| `user-service` | Spring Boot | 로그인, 사용자, 역할, 감사 로그 |
| `inspection-service` | Spring Boot | 점검 지점 · 규칙 · 작업 · 예약, 판독 결과, 경고, 사건(화재 대응) 흐름, 설정, 시연 실행 |
| `robot-service` | Spring Boot | 로봇 연결(rosbridge), 미션 실행, 조종 제어권, 투척 명령, 투척 위치 계산 |
| `analysis-service` | Python FastAPI | 사진 품질 분석, 판독기(물체 · 계기판 · 표시등 · 열화상) |
| `sim` | ROS 2 Humble · Gazebo · Nav2 | TurtleBot3 Waffle Pi 시뮬레이션, 목표 브리지, 모의 투척 기구 |
| `db` | PostgreSQL 17 | 서비스마다 DB 분리, 스키마는 Flyway |

- 서버는 로봇에 **목적지만** 보냅니다. 그곳까지의 길과 조종은 로봇(Nav2)이 합니다. 시뮬레이션과 실제 로봇이 같은 토픽 계약을 씁니다.
- 판단은 서버가 합니다: 사진의 등급, 누구를 보낼지, 투척할지. 로봇은 명령을 실행하고 결과를 알립니다.

## 6. 폴더

| 경로 | 내용 |
| --- | --- |
| `web/nginx/` | `cdn` · `web` 설정, React 화면(`frontend/`) |
| `web/spring/` | `gateway`, `user-service`, `inspection-service`, `robot-service`, `common` |
| `web/python/analysis-service/` | 분석 서비스와 판독기(`src/checkers/`) |
| `web/postgres/` | DB 초기화 |
| `ros/sim/` | 시뮬레이션: 월드, Nav2 설정, 도구(`tools/`: 장애물 · 점검 대상 · 화재 · 지도 작성) |
| `ros/robot/` | 로봇 쪽 노드: 목표 브리지, 조종 워치독, 투척 기구 브리지(모의 · 실물용) |
| `ros/maps/` | 지도 |
| `scripts/` | 전 구간 시험, 시연 스크립트 |
| `docs/` | 문서 |

## 7. 시험과 문서

로봇이 실제로 주행하므로 시험은 수 분에서 수십 분 걸립니다. 스택이 떠 있어야 합니다.

| 명령 | 확인하는 것 |
| --- | --- |
| `python3 scripts/e2e_test.py` | 기본 흐름: 로그인 · 점검 · 분석 · 판정 · 권한 · 조종 · 장애물(우회 · 다른 길 · 진입 불가) |
| `python3 scripts/e2e_scenarios.py --only rules` | 소방 관제: 규칙 → 등급 → 경고 → 자동 해제 |
| `python3 scripts/e2e_scenarios.py --only fire` | 소화액 투척: 승인 · 자동 · 오탐 · 가로채기 · 현장 감시 · 다시 열기 |

| 문서 | 내용 |
| --- | --- |
| [docs/guide/guide_02_RUNNING.md](docs/guide/guide_02_RUNNING.md) | 구성 · 시험 시설과 지도 · 주행 설정 · 화면 · 시나리오 해 보기 |
| [docs/guide/guide_01_DOCKER_GUIDE.md](docs/guide/guide_01_DOCKER_GUIDE.md) | 설치부터 실행 · 초기화 · 문제 해결 |
| [docs/navigation/nav_01_drive_layers.svg](docs/navigation/nav_01_drive_layers.svg) | 주행 지도 3겹(기존 맵 · 계획 맵 · 제어 맵)과 새 장애물이 생기는 층 |
| [docs/navigation/nav_02_drive_controller.svg](docs/navigation/nav_02_drive_controller.svg) | 주행 제어기: 목표 → 경로 → 속도 명령, 막혔을 때의 순서 |
| [docs/design/design_01_SCENARIOS.md](docs/design/design_01_SCENARIOS.md) | 두 시나리오의 설계(무엇을 왜) |
| [docs/design/design_02_INTERFACES.md](docs/design/design_02_INTERFACES.md) | 상세 설계: 토픽 계약 · API · DB 표 · 상태 흐름 · 설정 |
| [docs/plan/plan_01_ROADMAP.md](docs/plan/plan_01_ROADMAP.md) | 향후 계획: 소화기 인식 모델, 주행 제어기 개선 |
| [docs/README.md](docs/README.md) | 문서 전체 목록과 분류 기준(시스템 구조 도면 · 스토리보드 포함) |

## 8. 지금 구현 범위

**되는 것 (시뮬레이션, 터틀봇 한 대)**

- 기본 기능 전부, 관제 대시보드
- 소방 관제: 지점별 규칙, 판독기 4종, 등급, 경고와 자동 해제
- 소화액 투척: 감지 보고 → 출동 → 조준 보정 → 재판독 → 사람 승인 / 자동 투척 → 현장 감시 → 종료
- 시연 단추와 스크립트

**아직 없는 것**

| 항목 | 지금 |
| --- | --- |
| 젯봇(순찰 · 화재 감지 · 위치 추정 · 두 로봇의 조정) | 없음. 감지 보고는 시뮬레이션 도구가 대신 보냄. 젯봇의 ROS 2 구동은 다른 담당이 진행 중 |
| 실물 투척 기구 | 모의 노드가 투척 명령에 답함. 실로봇용 시리얼 브리지는 만들어만 두고 실물로 돌려 보지 않음 |
| 소화기 인식 모델 | 없음. 시뮬레이션의 빨간 상자를 색으로 찾음. "있다/없다"만 가리고 "옆으로 옮겨짐"은 가리지 못함 |
| 실제 로봇에서의 확인 | 하지 않음. 정확도 · 속도 수치는 장비로 재야 함 |
| 주행 제어기 개선(좁은 통로 통과, 실시간 회피) | 별도 작업으로 계획만 있음 |
| 시연 단추 | 시뮬레이션 전용 |

---

## 9. 보유 하드웨어 제원

| 플랫폼 | 연산 보드 | 구동부 | 센서 |
|---|---|---|---|
| TurtleBot3 Waffle Pi | Raspberry Pi + OpenCR | DYNAMIXEL XM430-W210 ×2 (엔코더 내장) | LiDAR, 카메라(IMX219), IMU |
| Yahboom JetBot Mini | NVIDIA Jetson Nano 4GB | TT DC 기어모터 ×2 (엔코더 없음) | 카메라(IMX219) |

---

### TurtleBot3 Waffle Pi

출처: [ROBOTIS e-Manual – TurtleBot3 Features](https://emanual.robotis.com/docs/en/platform/turtlebot3/features/)

| 항목 | 제원 |
|---|---|
| 최대 병진 속도 | 0.26 m/s |
| 최대 회전 속도 | 1.82 rad/s (104.27 deg/s) |
| 최대 적재 하중 | 30 kg |
| 크기 (L × W × H) | 281 × 306 × 141 mm |
| 무게 (SBC·배터리·센서 포함) | 1.8 kg |
| 등판 가능 턱 높이 | 10 mm 이하 |
| 예상 동작 시간 | 약 2시간 |
| 예상 충전 시간 | 약 2시간 30분 |
| SBC | Raspberry Pi 4 (현행 기준, 구형 키트는 Raspberry Pi 3B+) |
| MCU (OpenCR) | 32-bit ARM Cortex-M7 (FPU 포함), 216 MHz, 462 DMIPS |
| 액추에이터 | DYNAMIXEL XM430-W210 ×2 |
| LiDAR | 360° Laser Distance Sensor LDS-02 (현행 기준, 구형 키트는 LDS-01) |
| 카메라 | Raspberry Pi Camera Module v2.1 (Sony IMX219, 8MP) |
| IMU | 3축 자이로 + 3축 가속도 |
| 배터리 | Li-Po 11.1 V, 1800 mAh / 19.98 Wh, 5C |
| 전원 출력 | 3.3 V / 800 mA, 5 V / 4 A, 12 V / 1 A |
| 확장 핀 | GPIO 18핀, Arduino 32핀 헤더 |
| 주변장치 인터페이스 | UART ×3, CAN ×1, SPI ×1, I2C ×1, ADC ×5, 5핀 OLLO ×4 |
| DYNAMIXEL 포트 | RS485 ×3, TTL ×3 |
| PC 연결 | USB |
| 펌웨어 업데이트 | USB 또는 JTAG |
| 충전 어댑터 | 입력 100–240 V AC 50/60 Hz, 출력 12 V DC 5 A |

> SBC와 LiDAR는 출고 시기에 따라 다르다. 보유 장비의 실제 모델은 기판·센서 라벨로 확인할 것.

---

### Yahboom JetBot Mini

출처: [Yahboom 제품 페이지](https://category.yahboom.net/products/jetbot-mini), [RobotShop](https://www.robotshop.com/products/yahboom-yahboom-jetbot-mini-ai-vision-robot-car-ros-starter-kit-w-jetson-nano-4gb-2gb-sub-board), [GitHub – YahboomTechnology/jetbot-mini](https://github.com/YahboomTechnology/jetbot-mini)

| 항목 | 제원 |
|---|---|
| 조립 크기 | 170.5 × 126.5 × 146.5 mm |
| 조립 무게 | 708 g |
| 연산 보드 | NVIDIA Jetson Nano 4GB |
| ├ CPU | Quad-core ARM Cortex-A57 @ 1.43 GHz |
| ├ GPU | 128-core NVIDIA Maxwell (472 GFLOPS) |
| ├ 메모리 | 4 GB 64-bit LPDDR4, 25.6 GB/s |
| └ 전력 모드 | 5 W / 10 W |
| 확장 보드 | Yahboom 전용 확장 보드 (듀얼 모터 드라이버, PWM 서보, OLED, 온보드 MCU) |
| 구동 모터 | TT DC 기어모터 ×2, 감속비 1:48, **엔코더 없음** (개루프 제어) |
| 바퀴 | 구동 바퀴 ×2 + 캐스터(유니버설 휠) ×1 |
| 카메라 | IMX219 CSI 카메라, 8MP (3280 × 2464), 1/4" CMOS, 초점거리 2.96 mm, 화각 77° |
| 카메라 마운트 | 틸트(pitch) 각도 수동 조정 |
| 배터리 | 18650 배터리 팩, 12.6 V 2200 mAh |
| 무선 | 1300 Mbps 무선 랜카드 (드라이버 설치 불필요) |
| 소프트웨어 | ROS, OpenCV, Python 3 |

> 엔코더가 없으므로 휠 오도메트리를 쓸 수 없다. 위치 추정은 카메라 기반으로 해야 한다.
