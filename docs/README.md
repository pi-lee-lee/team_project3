# 문서

문서는 **무엇을 알려 주는가**로 나눈다. 폴더 하나가 한 가지 질문에 답한다.

| 폴더 | 답하는 질문 | 형식 |
| --- | --- | --- |
| [`guide/`](guide/) | 어떻게 띄우고 쓰는가 | Markdown |
| [`architecture/`](architecture/) | 시스템이 어떻게 짜여 있는가 (컨테이너 · 서비스 · 요청 흐름) | SVG 도면 |
| [`navigation/`](navigation/) | 로봇이 어떻게 달리는가 (지도 · 계획 · 제어 · 장애물) | SVG 설명서 |
| [`design/`](design/) | 무엇을 만들고, 서로 무엇을 주고받는가 (시나리오 · 인터페이스) | Markdown |
| [`plan/`](plan/) | 앞으로 무엇을 언제 하는가 (향후 계획 · 일정) | Markdown |
| [`storyboard/`](storyboard/) | 화면이 어떻게 생겼고 어떻게 이어지는가 | SVG 도면 |
| `_lib/` | (문서 아님) SVG 생성 스크립트가 함께 쓰는 그리기 도구 | Python |

빠른 실행 명령만 보려면 저장소 루트의 [도커_실행.md](../도커_실행.md) 를 본다.

## guide — 실행 안내

| 파일 | 내용 |
| --- | --- |
| [RUNNING.md](guide/RUNNING.md) | 구성 · 폴더 구조 · 시험 시설과 지도 · 주행 설정 · 화면 · 시나리오 해 보기 · 알려진 한계 |
| [DOCKER_GUIDE.md](guide/DOCKER_GUIDE.md) | 설치부터 실행 · 초기화 · 문제 해결까지 단계별 안내(macOS · Linux · Windows PowerShell) |

## architecture — 시스템 구조

| 파일 | 내용 |
| --- | --- |
| [system_architecture.svg](architecture/system_architecture.svg) | 구성도: 컨테이너(cdn 엣지 캐시 → web 원본 → gateway) · Docker 네트워크 · MSA 서비스와 Spring Boot 내부 계층 · 서비스별 DB · 로봇 브리지 |
| [system_cycle.svg](architecture/system_cycle.svg) | 시스템 사이클: 화면 불러오기(CDN 캐시) · 인증 · 점검 미션 · 사진 분석 · 판정 · 재점검 · 관제 · 조종 · 예외 · 복구를 번호 순서로 |
| [spa_cycle.svg](architecture/spa_cycle.svg) | React SPA 사이클: 브라우저가 화면을 조립하는 과정(첫 접속 · 데이터 채우기 · 화면 이동 · 실시간 화면 · 새 빌드 반영) |

## navigation — 주행

| 파일 | 내용 |
| --- | --- |
| [drive_layers.svg](navigation/drive_layers.svg) | 주행 지도 3겹: 기존 맵(저장 지도) · 계획 맵(전역 비용 지도 0.05m) · 제어 맵(지역 비용 지도 0.025m, 2배 촘촘). 새 장애물이 생기고 사라지는 층, **금지구역이 동작하는 층**(계획 맵 가상 장애물 층 + 제어 맵 금지구역 층, 기존 맵에는 없음) |
| [drive_controller.svg](navigation/drive_controller.svg) | 주행 제어기: 목표 → 경로(Theta*) → 속도 명령(MPPI), 장애물별 맞는 결과와 측정 시간, 목표 브리지가 돕는 세 가지, 막혔을 때의 순서, 주요 설정값 |
| [theta_star.svg](navigation/theta_star.svg) | Theta* 계획기(처음 보는 사람용): A* 가 길을 찾는 법 → Theta* 가 바꾼 한 가지(보이는 점에 바로 잇기) → 같은 지도에서 비교 → 이 건물의 경로 → 벽 비용(w_traversal_cost) → 설정값 · 한계 |
| [mppi.svg](navigation/mppi.svg) | MPPI 제어기(처음 보는 사람용): 한 주기의 네 걸음(후보 1000개 → 굴리기 → 점수 → 가중 평균) → 속도 열 → 평가 항목 8가지 → temperature → 상황별 동작(직선 · 상자 · 좁은 틈) → 도착 구간 → 설정값 · 실측 |

먼저 `drive_layers.svg`(무엇을 보고 달리는가)를 보고, 이어서 `drive_controller.svg`(그것으로 어떻게 달리는가)를 본다.
계획기 · 제어기가 낯설면 `theta_star.svg`(길은 어떻게 찾나) → `mppi.svg`(그 길을 어떻게 따라가나) 순서로 본다.
측정값과 시험 방법의 글 설명은 [guide/RUNNING.md](guide/RUNNING.md) 의 "계획 방식과 좁은 틈", 남은 일은 [plan/ROADMAP.md](plan/ROADMAP.md) 에 있다.

## design — 설계

| 파일 | 내용 |
| --- | --- |
| [SCENARIOS.md](design/SCENARIOS.md) | 두 시나리오의 설계(무엇을 왜): 소화액 투척(감지 → 출동 → 승인/자동 투척) · 소방 관제(지점별 규칙 → 정상 · 경고 · 비상). 지금 있는 것/없는 것, 서비스별 변경 |
| [INTERFACES.md](design/INTERFACES.md) | 상세 설계(주고받는 모양): 디바이스 토픽 계약 · 카메라 판독 인터페이스 · 서비스 사이 API · 화면 API · DB 표 · 상태 흐름 · 설정 목록 |

## plan — 계획

| 파일 | 내용 |
| --- | --- |
| [ROADMAP.md](plan/ROADMAP.md) | 향후 계획: analysis-service 소화기 AI 판독(방식 · 데이터 · 단계 · 완료 기준) · 주행 제어기 개선 |
| [SCHEDULE.md](plan/SCHEDULE.md) | 주간 계획서(2026-11-23 ~ 2027-01-22, 9주): 파트별(웹 · 카메라 · 터틀봇 · 젯봇 · 투척기) 주차 계획 · 단계 목표 · 통합 테스트 주 · 위험과 대응 |

## storyboard — 화면

| 파일 | 내용 |
| --- | --- |
| [web_storyboard.svg](storyboard/web_storyboard.svg) | 화면 구조도 · 흐름도 · 화면 설계 |
| [web_screen_tree.svg](storyboard/web_screen_tree.svg) | 화면 트리 |
| [web_service_scenario.svg](storyboard/web_service_scenario.svg) | 가상 서비스 흐름 |

## SVG 는 스크립트로 만든다

SVG 를 직접 고치지 않는다. 같은 폴더의 `build_*.py` 를 고친 뒤 다시 생성한다(저장소 루트에서 실행).

| SVG | 생성 스크립트 |
| --- | --- |
| `architecture/system_architecture.svg` | `python3 docs/architecture/build_architecture.py` |
| `architecture/system_cycle.svg` | `python3 docs/architecture/build_cycle.py` |
| `architecture/spa_cycle.svg` | `python3 docs/architecture/build_spa_cycle.py` |
| `navigation/drive_controller.svg` | `python3 docs/navigation/build_drive_controller.py` |
| `navigation/drive_layers.svg` | `python3 docs/navigation/build_drive_layers.py` |
| `navigation/theta_star.svg` | `python3 docs/navigation/build_theta_star.py` (numpy 필요) |
| `navigation/mppi.svg` | `python3 docs/navigation/build_mppi.py` (numpy 필요) |
| `storyboard/web_storyboard.svg` | `python3 docs/storyboard/build_storyboard.py` |
| `storyboard/web_screen_tree.svg` | `python3 docs/storyboard/build_screen_tree.py` |
| `storyboard/web_service_scenario.svg` | `python3 docs/storyboard/build_service_scenario.py` |

- `architecture/` · `navigation/` 의 스크립트는 `_lib/svg.py`(색 · 글자 폭 · 도형)를 함께 쓴다.
- `navigation/` 의 `theta_star` · `mppi` 는 숫자를 `ros/sim/src/config/nav2_params.yaml` 에서 읽고(`_lib/nav2cfg.py`), 그림 속 경로 · 후보 궤적은
  Nav2 의 식을 옮긴 작은 계산(`theta_sim.py` · `mppi_sim.py`)으로 그린다. 설정을 바꾸면 다시 생성한다(실행 기록이 아니라 계산이다 — 실측은 `drive_probe.py` · `plan_probe.py`).
- `navigation/` 과 `storyboard/build_service_scenario.py` 는 평면도를 `ros/sim/src/worlds/world_spec.py` 에서 그대로 그린다. 월드를 바꾸면 다시 생성한다.

## 새 문서를 둘 곳

- 실행 · 사용법 → `guide/` · 시스템 구성 → `architecture/` · 주행(지도 · Nav2 · 브리지) → `navigation/`
- 기능의 설계 · 계약 → `design/` · 일정 · 앞으로 할 일 → `plan/` · 화면 → `storyboard/`
- 어디에도 맞지 않으면 폴더를 새로 만들고 이 표에 한 줄을 더한다. `docs/` 바로 아래에는 이 파일만 둔다.
