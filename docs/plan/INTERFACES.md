# 상세 설계: 인터페이스

[SCENARIOS.md](SCENARIOS.md)(무엇을 왜 하는가)의 다음 단계다. 구현에 들어가기 전에 **서로 주고받는 모양**을 모두 정한다.
이 문서가 정한 인터페이스가 구현 범위이고, 이 문서가 채워진 것이 계획 단계의 완료다.

## 0. 범위와 원칙

### 구현 범위

**실물 디바이스 두 대를 뺀 전부를 구현한다.**

| 구분 | 내용 | 맡는 쪽 |
| --- | --- | --- |
| 실물 디바이스 | 터틀봇(주행 · 센서 · **투척 기구** 포함), 젯봇(ROS 2 구동 · 스테레오 카메라 · 모터) | 디바이스 담당 |
| 그 밖의 전부 | 서버(Spring · Python) · 화면 · DB · 시뮬레이션 · 로봇 쪽 브리지 노드(`ros/robot`, `ros/patrol`) · 모의 장치 · 시험 | 이 계획 |

- 디바이스와의 경계는 **2장의 토픽 계약**이다. 디바이스는 "넘겨받는 것"(2.5)만 내면 되고, 그것을 계약 토픽으로 바꾸는 브리지 노드는 이 저장소에서 만든다(지금 `nav2_goal_bridge.py` 가 그렇게 되어 있다).
- **판단은 서버가 한다.** 투척할지 말지, 어느 등급인지, 누구를 보낼지는 서버가 정하고 디바이스는 명령을 실행하고 결과를 알린다.

### 설계 원칙

1. **정해지지 않은 것은 설정으로 둔다.** 값 · 대상 · 규격이 미정인 항목은 코드에 넣지 않고 설정 자리를 만들어 둔다(8장에 목록).
2. **카메라로 하는 판독은 인터페이스 하나로 받는다.** 계기판 · 표시등 · 소화기 · 열화상 · 마커 모두 analysis-service 의 판독 인터페이스(3장)를 거친다. 판독 종류를 더해도 다른 서비스는 바뀌지 않는다.
3. **로봇이 달라도 계약은 같다.** 터틀봇과 젯봇은 같은 목표 계약을 지킨다. 로봇마다 다른 것(토픽 이름 · 허용 오차 · 제공 기능)은 로봇 설정(`robot.config`)에 둔다.
4. **ROS 2 는 Humble 로 한다.** Jazzy 로 바뀌어도 노드 · 토픽 구성은 같고, 서비스(Spring · Python · 화면 · DB)에는 변경이 없다. 계약 메시지는 표준 메시지(`std_msgs/String` 의 JSON, `geometry_msgs`, `nav_msgs`)만 쓴다.
5. **지금 있는 규칙을 그대로 따른다.** 명령에는 ID 를 붙여 한 번만 실행(멱등), 로봇 보고는 outbox 에 담아 재전송, 사건 기록은 추가만, 시각은 timestamptz.

---

## 1. 인터페이스 목록

| 번호 | 인터페이스 | 사이 | 상태 | 절 |
| --- | --- | --- | --- | --- |
| R1 | 목표 이동 `/inspection/goal` · `goal_cancel` · `goal_status` | 서버 ↔ 로봇 | 있음 + 확장 | 2.1 |
| R2 | 로봇 상태 `/inspection/bridge_status` · `map_pose` · `map` · `scan_map` · 영상 | 로봇 → 서버 | 있음 + 확장 | 2.1 |
| R3 | 투척 `/inspection/actuator` · `actuator_status` · `actuator_state` | 서버 ↔ 터틀봇 | 새로 | 2.2 |
| R4 | 정렬 `/patrol/align` · `align_status` | 서버 ↔ 젯봇 | 새로 | 2.3 |
| R5 | 실시간 감지 `/patrol/detection`, 설정 `/patrol/config` | 젯봇 ↔ 서버 | 새로 | 2.3 |
| R6 | 로봇 설정 `robot.config` | robot-service | 있음 + 확장 | 2.4 |
| J1 | 디바이스에서 넘겨받는 것 | 디바이스 → 브리지 | 새로 | 2.5 |
| C1 | 판독 작업(비동기) `POST /jobs` | inspection → analysis | 있음 + 확장 | 3.2 |
| C2 | 즉시 판독 `POST /check` | inspection → analysis | 새로 | 3.2 |
| C3 | 판독기 목록 `GET /checkers` | inspection → analysis | 새로 | 3.2 |
| C4 | 규칙 · 결과 모양 | 공통 | 새로 | 3.3 · 3.4 |
| C5 | 판독기 코드 인터페이스 | analysis · 젯봇 | 새로 | 3.5 |
| S1 | 미션 `POST /internal/missions` | inspection → robot | 있음 + 확장 | 4.1 |
| S2 | 투척 명령 · 사진 · 투척 위치 후보 | inspection → robot | 새로 | 4.1 |
| S3 | 로봇 보고(사건 기록 · 관측 · 감지) | robot → inspection | 있음 + 확장 | 4.2 |
| S4 | 판독 결과 `POST /internal/observations/{id}/analysis` | analysis → inspection | 있음 + 확장 | 4.3 |
| A1~A6 | 화면이 부르는 API(경고 · 규칙 · 사건 · 설정 · 기준 좌표 · 대시보드) | 화면 ↔ gateway | 새로 | 5 |
| D1~D7 | DB 표 | 서비스별 DB | 새로 | 6 |
| F1~F4 | 상태 흐름(사건 · 경고 · 젯봇 작업) · 두 로봇의 조정 | 서버 | 새로 | 7 |

---

## 2. 디바이스 계약 (ROS 2 토픽)

서버(robot-service)는 rosbridge(9090)로 연결한다. 특별히 적지 않으면 `std_msgs/String` 에 JSON 을 담는다. 토픽 이름은 기본값이고 로봇 설정에서 바꿀 수 있다(2.4).

### 2.1 공통: 목표 이동과 상태 (터틀봇 · 젯봇)

| 토픽 | 방향 | 내용 |
| --- | --- | --- |
| `/inspection/goal` | 서버 → 로봇 | `{"goalId", "x", "y", "yaw", "refs"?}` — 지도 좌표(m, rad) |
| `/inspection/goal_cancel` | 서버 → 로봇 | `{"goalId"}` (`"*"` = 전부) |
| `/inspection/goal_status` | 로봇 → 서버 | `{"goalId", "state", "code", "reason", "detoured", "recoveries", "plannedLength", "traveled", "arrivalError"?}` |
| `/inspection/bridge_status` | 로봇 → 서버, 1Hz | `{"navReady", "localized", "poseQuality"?, "docked"?}` |
| `/inspection/map_pose` | 로봇 → 서버, 5Hz | `geometry_msgs/PoseStamped` (frame `map`) |
| `/inspection/map` | 터틀봇 → 서버, 5초 | `nav_msgs/OccupancyGrid` — 공용 지도는 터틀봇만 낸다 |
| `/inspection/scan_map` | 터틀봇 → 서버 | `{"pts": [[x, y], ...]}` |
| `/inspection/drive_plan` | 터틀봇 → 서버 | `{"v": 0.22, "w": 0.1, "traj": [[x, y], ...]}` — 제어기가 지금 내는 속도 명령과 그 명령으로 3초간 갈 호(지도 좌표). 주행 명령이 있을 때만 5Hz. 관제 지도의 "제어기 방향"(브랜치 `feat/drive-controller` 에서만) |
| `/inspection/virtual_map` | 로봇 안(브리지 → Nav2 전역 비용 지도) | `nav_msgs/OccupancyGrid`, 지도와 같은 크기. 계획에만 쓰는 가상 장애물: 새 장애물의 몸통, 두 번 막힌 자리. 서버는 쓰지 않는다 |
| 영상 | 로봇 → 서버 | web_video_server(MJPEG) · 스냅샷 — 지금과 같음 |
| `cmd_vel` | 서버 → 로봇 | `geometry_msgs/Twist`, 워치독 경유 — 지금과 같음 |

- `state`: `ACTIVE` · `SUCCEEDED` · `ABORTED` · `CANCELED` (지금과 같음)
- `code`: `BLOCKED_NO_PATH` · `NAV_FAILED` · `NO_PROGRESS` · `NAV_UNAVAILABLE` (지금과 같음) + **`POSE_UNCERTAIN`**(위치를 믿을 수 없어 중단 — 젯봇)

**확장 항목** (없으면 지금 동작 그대로)

| 항목 | 뜻 | 쓰는 로봇 |
| --- | --- | --- |
| `goal.refs` | 이 목표 근처의 위치 기준 대상 목록 `[{"ruleId", "kind", "x", "y", "yaw", "params"}]`. 로봇이 대상을 보면 위치를 바로잡는다 | 젯봇 |
| `goal_status.arrivalError` | 도착 시 로봇이 추정한 오차 `{"xy": m, "yaw": rad}` | 젯봇 |
| `bridge_status.poseQuality` | 위치 신뢰도 0~1. 정렬 직후 1, 이동할수록 내려간다 | 젯봇 |
| `bridge_status.docked` | 대기 구역에 정렬되어 서 있는지 | 젯봇 |

터틀봇은 이 계약을 Nav2 로 옮기고(`ros/robot/src/nav2_goal_bridge.py`, 있음), 젯봇은 자체 주행으로 옮긴다(`ros/patrol/src/goal_bridge.py`, 새로).

### 2.2 투척 (터틀봇)

판단은 서버가 하고, 터틀봇은 명령을 실행하고 결과를 알린다.

| 토픽 | 방향 | 내용 |
| --- | --- | --- |
| `/inspection/actuator` | 서버 → 로봇 | `{"commandId", "kind": "LAUNCH", "count": 1, "params": {}}` |
| `/inspection/actuator_status` | 로봇 → 서버 | `{"commandId", "state": "ACCEPTED" \| "DONE" \| "FAILED", "code", "reason", "launched": 1}` |
| `/inspection/actuator_state` | 로봇 → 서버, 1Hz | `{"ready": true, "remaining": 5 \| null, "fault": "" }` |

- `commandId`: 서버가 만든다(`inc-{사건ID}-{순번}`). **같은 ID 가 다시 오면 실행하지 않고 지난 결과를 다시 보낸다.**
- `params`: 기구가 받는 추가 값의 자리(세기 · 각도 등). 지금은 비워 보낸다. 기구가 정해지면 설정 `launch.params` 값이 그대로 실려 간다.
- `code`(실패): `NOT_READY` · `EMPTY`(탄 없음) · `JAMMED` · `TIMEOUT` · `ESTOP` · `UNSUPPORTED`
- `actuator_state` 가 없으면 서버는 "투척 기구 없음"으로 보고 투척 단계를 `UNSUPPORTED` 로 끝낸다(제공 기능 `launcher`).
- 비상 정지 중에는 명령을 받지 않고 `ESTOP` 으로 답한다.

**브리지와 기구 사이(시리얼)** — `ros/robot/src/launcher_bridge.py` 가 위 토픽을 기구의 시리얼로 바꾼다. 기본 형식은 한 줄 명령이다.

| 방향 | 줄 | 뜻 |
| --- | --- | --- |
| 브리지 → 기구 | `L <id> <count>` | 발사 |
| 기구 → 브리지 | `OK <id> <launched>` / `ERR <id> <code>` | 결과 |
| 브리지 → 기구 | `S` | 상태 묻기(1초마다) |
| 기구 → 브리지 | `ST <ready 0\|1> <remaining\|-1>` | 상태 |

포트 · 속도 · 줄 형식은 브리지 파라미터로 둔다. 기구 쪽 형식이 다르게 정해지면 **이 파일만** 바꾼다(토픽 계약과 서버는 그대로). 시뮬레이션에는 같은 토픽에 답하는 `mock_launcher.py` 를 둔다.

### 2.3 젯봇 전용: 정렬과 실시간 감지

| 토픽 | 방향 | 내용 |
| --- | --- | --- |
| `/patrol/align` | 서버 → 젯봇 | `{"cmdId", "kind": "START" \| "END" \| "ZONE", "markerId"}` |
| `/patrol/align_status` | 젯봇 → 서버 | `{"cmdId", "state": "ACTIVE" \| "SUCCEEDED" \| "ABORTED", "code", "reason", "error": {"xy", "yaw"}}` |
| `/patrol/correction` | 젯봇 → 서버 | `{"ruleId", "applied": true, "delta": {"xy", "yaw"}, "confidence"}` — 대상 기준 보정을 했거나 버렸을 때 |
| `/patrol/detection` | 젯봇 → 서버 | `{"detId", "kind": "THERMAL", "grade", "value", "confidence", "x", "y", "poseQuality", "stamp", "image": "<jpeg base64>"}` |
| `/patrol/config` | 서버 → 젯봇 (연결 시 · 바뀔 때) | `{"markers": [...], "detectors": [{"kind": "THERMAL", "params", "grading"}], "reportFrames": 5, "maxCorrectionM": 0.5}` |

- `align`
  - `START`: 마커를 보고 지도 위 위치를 맞춘다. `error` = 맞추기 전 추정과의 차이(첫 정렬이면 없음).
  - `END`: 대기 구역으로 돌아와 마커를 찾고 정해진 자리에 선다. `error` = **복귀 오차**(이번 작업에서 쌓인 오차).
  - `ZONE`: 작업 중간 정렬 구역에서의 정렬(정렬 구역을 둘 때만).
  - `code`: `MARKER_NOT_FOUND` · `DOCK_FAILED` · `POSE_UNCERTAIN`
- `detection`
  - `x` · `y`: 화재의 지도 좌표(젯봇 위치 + 스테레오로 잰 방향 · 거리).
  - `detId`: 젯봇이 만든다. 같은 것을 계속 보는 동안 같은 ID 로 다시 보낸다(서버가 하나로 합친다).
  - 연속 `reportFrames` 프레임에서 같은 등급일 때만 보낸다. `NORMAL` 은 보내지 않는다.
- `config`: 젯봇은 판독 기준을 스스로 갖지 않고 서버가 준 것을 쓴다. 마커 좌표 · 열화상 기준을 화면에서 바꾸면 여기로 내려간다.

### 2.4 로봇 설정 (`robot.config`, robot-service)

로봇마다 다른 것은 여기에 둔다. 지금 있는 항목(`rosbridgeUrl`, `videoUrl`, `imageTransport`, `topics`)에 더한다.

```json
{
  "kind": "INSPECTOR",
  "topics": { "goal": "/inspection/goal", "actuator": "/inspection/actuator", "align": "/patrol/align" },
  "arrival": { "xyTolerance": 0.12, "yawTolerance": 0.15 },
  "camera": { "frame": "RGB", "hfovDeg": 62.2, "heightM": 0.11 },
  "dockMarkerId": null
}
```

| 항목 | 값 | 뜻 |
| --- | --- | --- |
| `kind` | `INSPECTOR`(터틀봇) · `PATROL`(젯봇) | 미션 앞뒤에 정렬을 넣을지(F3), 규칙 영역을 어느 것으로 쓸지(3.3) |
| `topics` | 토픽 이름 | 디바이스 쪽 이름이 달라지면 여기만 고친다 |
| `arrival` | 허용 오차 | 젯봇은 실측 뒤 정한다 |
| `camera.frame` | `RGB` · `THERMAL` | 현업용 열화상 카메라가 달리면 `THERMAL` — 판독기가 인쇄물 찾기 단계를 건너뛴다(3.5) |
| `dockMarkerId` | 마커 번호 | 젯봇의 대기 구역 마커 |

제공 기능(`capabilities`)에 `launcher` · `align` · `detection` 을 더한다. 토픽이 없으면 "미지원"으로 나오고, 서버는 그 기능이 필요한 단계를 건너뛰거나 실패로 기록한다.

### 2.5 디바이스에서 넘겨받는 것 (J1)

브리지 노드가 계약 토픽을 만들려면 디바이스가 아래를 내야 한다. 이름은 디바이스 쪽에서 정하고, 브리지 파라미터로 맞춘다.

| 디바이스 | 넘겨받는 것 | 쓰는 곳 |
| --- | --- | --- |
| 터틀봇 | 지금과 같음: `/odom`, `/scan`, 카메라, `cmd_vel`, Nav2 | `nav2_goal_bridge.py` |
| 터틀봇 투척 기구 | 시리얼 포트(2.2 의 줄 형식 또는 정해지는 형식) | `launcher_bridge.py` |
| 젯봇 | 좌 · 우 영상(시각이 맞춰진 한 쌍) + `camera_info`, 스테레오 보정값 | 정렬 · 오도메트리 · 감지 |
| 젯봇 | `cmd_vel` 받기(m/s · rad/s) | 자체 주행 · 웹 조종 |
| 젯봇 | TF `base_link` → 카메라 | 카메라 위치 → 로봇 위치 |

---

## 3. 카메라 판독 인터페이스 (analysis-service)

카메라 사진을 보고 내리는 판단은 모두 여기를 거친다: 점검 사진의 등급, 도착 후 화재 재판독, 규칙 시험, 마커 · 대상의 위치 재기.

### 3.1 구성

```
사진 + 규칙 목록 ──▶ [품질 검사] ──▶ 규칙마다: [대상 찾기 locate] ─▶ [읽기 read] ─▶ [등급 매기기 grade] ──▶ 결과 목록
                      (지금 있음)      └───────── 판독기(종류별 코드) ─────────┘   └─ 공통 코드(설정) ─┘
```

- **판독기**는 "찾기"와 "읽기"만 한다. 읽은 값(숫자 또는 이름)을 **등급으로 바꾸는 것은 공통 코드**이고 기준은 설정이다. 그래서 등급 기준이 미정이어도 판독기는 만들 수 있다.
- 사진이 너무 어둡거나 밝으면 판독하지 않고 모든 규칙을 `UNKNOWN` 으로 낸다. "흐림"만으로는 건너뛰지 않는다 — 대상이 사라져 빈 벽만 찍힌 사진도 선명도가 낮게 나오는데, 그것이 "없음"으로 판독해야 하는 경우다(시뮬레이션 시험에서 확인).

### 3.2 API

| | 요청 | 응답 | 쓰는 곳 |
| --- | --- | --- | --- |
| C1 `POST /jobs` (있음) | `{"observationId"}` | 202. 워커가 사진과 규칙을 inspection-service 에서 받아 판독하고 결과를 보낸다(S4) | 점검 사진 |
| C2 `POST /check` (새로) | multipart: `image`(JPEG), `request` = `{"rules": [규칙…], "robotKind", "cameraFrame", "camera": {…}}` | `{"quality": {…}, "results": [결과…]}` (즉시) | 도착 후 재판독, 규칙 시험, 마커 · 대상 위치 재기 |
| C3 `GET /checkers` (새로) | — | `[{"kind", "version", "valueType": "number" \| "label", "paramsSchema": {JSON Schema}, "labels": […]}]` | 관리자 화면이 규칙 입력 폼을 이것으로 만든다 |

- C1 의 워커는 `GET {inspection}/internal/observations/{id}/rules` 로 그 관측의 지점 · 로봇 종류에 맞는 규칙 목록을 받는다(4.3).
- C3 덕분에 판독 종류를 더해도 화면 코드를 고치지 않는다(폼이 `paramsSchema` 로 그려진다).

### 3.3 규칙 모양 (C4)

```json
{
  "ruleId": 12,
  "pointId": 1,
  "name": "소화기 비치",
  "kind": "OBJECT",
  "enabled": true,
  "params": { "label": "fire_extinguisher", "expect": "PRESENT", "minConfidence": 0.5 },
  "regions": { "INSPECTOR": [0.30, 0.35, 0.70, 0.95], "PATROL": [0.20, 0.30, 0.80, 0.95] },
  "grading": { "type": "map", "map": { "IN_REGION": "NORMAL", "OUT_OF_REGION": "WARNING", "MISSING": "EMERGENCY" }, "default": "UNKNOWN" },
  "target": { "x": 2.2, "y": 0.0, "yaw": 3.14, "sizeM": 0.5, "useAsReference": false }
}
```

| 항목 | 뜻 |
| --- | --- |
| `kind` | 판독기 종류. `GET /checkers` 에 있는 값 |
| `params` | 판독기별 설정(아래 표). 모양은 `paramsSchema` 가 정한다 |
| `regions` | 로봇 종류별 기대 영역 `[x0, y0, x1, y1]`(사진 크기에 대한 비율). 없으면 사진 전체 |
| `grading` | 읽은 값 → 등급. `map`(이름 → 등급) 또는 `ranges`(숫자 구간 → 등급), `default`(어디에도 안 맞을 때) |
| `target` | 대상의 지도 좌표 · 실제 크기. `useAsReference` 가 켜져 있으면 젯봇의 위치 기준으로 쓴다(`goal.refs`) |

**판독기 종류와 읽는 값**

| `kind` | `params` | 읽는 값(`value`) | `grading` 예 |
| --- | --- | --- | --- |
| `OBJECT` | `label`, `expect`(`PRESENT`/`ABSENT`), `minConfidence`, `model` | `IN_REGION` · `OUT_OF_REGION` · `MISSING` (ABSENT 규칙: `ABSENT` · `PRESENT`) | 위 예 |
| `GAUGE` | `minAngle`, `maxAngle`, `minValue`, `maxValue`, `unit`, `needle`(색 · 굵기 힌트) | 숫자(눈금 값) | `{"type": "ranges", "ranges": [{"min": 0.7, "max": 0.98, "grade": "NORMAL"}, {"min": 0.5, "max": 0.7, "grade": "WARNING"}], "default": "EMERGENCY"}` |
| `LAMP` | `colors`: 이름 → 색 범위(HSV), `offBelow`(밝기) | `green` · `yellow` · `red` · `off` 등 이름 | `{"type": "map", "map": {"green": "NORMAL", "yellow": "WARNING", "red": "EMERGENCY", "off": "WARNING"}}` |
| `THERMAL` | `palette`(`iron` 등), `hotThreshold`(상대 온도 0~1), `minAreaRatio` | 숫자(뜨거운 영역이 프레임에서 차지하는 비율 0~1) | `{"type": "ranges", "ranges": [{"max": 0.01, "grade": "NORMAL"}, {"min": 0.01, "max": 0.08, "grade": "WARNING"}], "default": "EMERGENCY"}` |
| `MARKER` | `dictionary`, `markerId`, `sizeM` | 숫자(마커까지 거리 m) — 등급 없이 위치 재기에 쓴다 | — |

값은 예시다. 실제 대상과 기준이 정해지면 **설정만 바꾼다**. 새 종류(예: 문 열림, 누수)는 판독기 파일 하나를 더하면 `GET /checkers` 에 나타난다.

### 3.4 결과 모양 (C4)

```json
{
  "ruleId": 12,
  "kind": "OBJECT",
  "grade": "WARNING",
  "value": "OUT_OF_REGION",
  "unit": null,
  "confidence": 0.83,
  "located": { "bbox": [0.72, 0.40, 0.90, 0.92], "relative": { "bearing": 0.21, "distance": 1.4 } },
  "evidence": { "expectedRegion": [0.30, 0.35, 0.70, 0.95] },
  "reason": "기대 영역 밖에서 발견",
  "checkerVersion": "object-1"
}
```

| 항목 | 뜻 |
| --- | --- |
| `grade` | `NORMAL` · `WARNING` · `EMERGENCY` · `UNKNOWN`(못 찾음 · 사진 불량 · 판독기 오류) |
| `value` · `unit` | 읽은 값. 숫자 또는 이름 |
| `located.bbox` | 대상을 찾은 사각형(비율). 못 찾으면 `located` 가 없다 |
| `located.relative` | 카메라 기준 방향(rad) · 거리(m). 대상의 실제 크기(`target.sizeM`)와 카메라 정보가 있을 때만 — 위치 재기(5장 A5)와 젯봇 보정에 쓴다 |
| `evidence` | 화면에 겹쳐 그릴 근거(판독기별: 기대 영역, 바늘 각도, 열원 윤곽 등) |

### 3.5 판독기 코드 인터페이스 (C5)

`web/python/analysis-service/src/checkers/` 에 종류마다 파일 하나. 서비스에 의존하지 않는 순수 함수라서(입력: 사진 배열과 설정) **젯봇 안에서도 같은 파일을 쓴다**(`ros/patrol` 이 같은 폴더를 가져다 쓴다).

```python
class Checker(Protocol):
    kind: str                 # 'GAUGE'
    version: str              # 'gauge-1'
    value_type: str           # 'number' | 'label'
    params_schema: dict       # JSON Schema — 화면의 입력 폼과 저장 전 검사에 쓴다

    def locate(self, frame: Frame, params: dict, region: Region | None) -> Located | None:
        """대상을 찾는다. 못 찾으면 None → UNKNOWN."""

    def read(self, frame: Frame, located: Located, params: dict) -> Reading:
        """찾은 대상에서 값을 읽는다: Reading(value, unit, confidence, evidence, reason)."""
```

- `Frame`: 사진 배열 + `camera_frame`(`RGB`/`THERMAL`) + 카메라 정보. `THERMAL` 판독기는 `RGB` 면 인쇄물을 찾아 펴고(`locate`), `THERMAL` 이면 프레임 전체를 그대로 쓴다. **`read` 는 두 경우가 같다** — 시연(인쇄물)과 현업(열화상 카메라)이 갈리는 곳은 `locate` 하나다.
- 등급 매기기는 판독기 밖의 공통 함수 `grade(reading, grading) -> grade` 다.
- 젯봇에 올리는 것: `THERMAL` 전체(실시간 감지), `GAUGE` · `LAMP` · `MARKER` 의 `locate`(위치 보정 · 정렬).

---

## 4. 서비스 사이 내부 API

모두 내부망 전용(`/internal/**`, 게이트웨이가 막는다 — 지금과 같음).

### 4.1 inspection-service → robot-service

**S1 미션 (확장)** `POST /internal/missions`

```json
{
  "missionId": 68, "robotId": 1, "kind": "INSPECTION",
  "waypoints": [
    { "pointId": 1, "code": "P1", "x": 1.0, "y": 0.0, "yaw": 0.0, "action": "CAPTURE",
      "refs": [ { "ruleId": 14, "kind": "GAUGE", "x": 2.2, "y": 0.1, "yaw": 3.14, "params": {} } ] }
  ]
}
```

| 항목 | 값 | 뜻 |
| --- | --- | --- |
| `kind` | `INSPECTION`(기본) · `RESPONSE` | `RESPONSE` 는 화재 출동. 도착하면 미션을 끝내지 않고 `HOLDING` 으로 기다린다 |
| `waypoints[].action` | `CAPTURE`(기본) · `HOLD` | `HOLD`: 촬영하지 않고 도착만 보고 |
| `waypoints[].refs` | 위치 기준 대상 | 젯봇에만 전달(`goal.refs`) |

- 로봇 종류가 `PATROL` 이면 robot-service 가 미션 앞에 `align START`, 뒤에 `align END` 를 넣는다(F3). inspection-service 는 로봇 종류를 몰라도 된다.
- 응답 · 멱등 · 취소(`POST /internal/missions/{id}/cancel`)는 지금과 같다.

**S2 새 호출**

| 호출 | 요청 → 응답 | 뜻 |
| --- | --- | --- |
| `POST /internal/robots/{id}/actuate` | `{"commandId", "kind": "LAUNCH", "count", "params"}` → `{"accepted": true}` 또는 409(`NOT_READY` 등) | 투척 명령. 결과는 사건 기록으로 온다(S3) |
| `GET /internal/robots/{id}/snapshot` | → JPEG + 헤더 `X-Pose`(x, y, yaw), `X-Camera`(카메라 정보 JSON) | 지금 사진과 그 순간의 위치 |
| `POST /internal/robots/{id}/standoff` | `{"targetX", "targetY", "rangeM", "toleranceM", "max": 8}` → `{"candidates": [{"x", "y", "yaw", "distanceFromRobot"}]}` | 투척 위치 후보. 지도를 가진 robot-service 가 계산한다: 대상에서 사거리만큼 떨어지고, 빈 칸이며, 대상과의 사이에 벽이 없는 자세들. 가까운 순 |
| `POST /internal/missions/{id}/finish` | `{"result": "COMPLETED" \| "FAILED", "reason"}` | `HOLDING` 중인 출동 미션을 끝낸다(제어권 반납) |
| `GET /internal/robots?kind=INSPECTOR&idle=true` | → 로봇 목록(위치 포함) | 출동시킬 로봇 고르기 |

### 4.2 robot-service → inspection-service (S3)

지금처럼 outbox 에 담아 `X-Report-Id` 로 중복 없이 보낸다.

**사건 기록** `POST /internal/tasks/{id}/events` — 종류 추가

| `type` | `detail` | 언제 |
| --- | --- | --- |
| `ALIGNED` / `ALIGN_FAILED` | `{"kind": "START"\|"END"\|"ZONE", "errorXy", "errorYaw", "code"}` | 젯봇 정렬 결과. `END` 의 오차가 복귀 오차 |
| `POSE_CORRECTED` / `POSE_CORRECTION_REJECTED` | `{"ruleId", "deltaXy", "deltaYaw"}` | 대상 기준 보정 |
| `HOLDING` | `{"x", "y", "yaw"}` | 출동 미션이 투척 위치에 도착해 대기 |
| `ACTUATED` / `ACTUATE_FAILED` | `{"commandId", "launched", "code", "reason"}` | 투척 결과 |

**관측** `POST /internal/tasks/{id}/observations` — `meta` 에 `robotKind`, `cameraFrame`, `arrivalErrorXy` 추가(규칙 영역 선택과 근거 기록에 쓴다).

**실시간 감지 (새로)** `POST /internal/detections` — multipart: `meta` + `image`

```json
{ "robotId": 2, "detId": "jb-0192", "kind": "THERMAL", "grade": "EMERGENCY", "value": 0.14, "confidence": 0.9,
  "x": 3.1, "y": 1.8, "poseQuality": 0.7, "missionId": 71, "capturedAt": "2026-11-18T09:12:26Z" }
```

응답 `{"alertId", "incidentId" | null, "duplicate": bool}`. 같은 `detId` 는 하나로 합친다.

### 4.3 analysis-service ↔ inspection-service (S4)

| 호출 | 내용 |
| --- | --- |
| `GET /internal/observations/{id}/image` (있음) | 사진 |
| `GET /internal/observations/{id}/rules` (새로) | `{"robotKind", "cameraFrame", "camera", "rules": [규칙…]}` — 그 관측의 지점에 걸린, 켜져 있는 규칙 |
| `POST /internal/observations/{id}/analysis` (확장) | 지금 내용(`brightness`, `sharpness`, `verdict`, `reasons`, `criteria`)에 `"results": [결과…]` 추가. 없으면 지금과 같게 동작 |

inspection-service 는 결과를 저장하고(D2), 등급에 따라 경고를 만들거나 푼다(F2).

---

## 5. 화면이 부르는 API (gateway)

역할: `A` = ADMIN, `S` = 1 관리자, `M` = 2 매니저, `U` = 3 사용자, `D` = 대시보드(조회만). `GET` 은 지금 규칙대로 모든 역할이 본다(관리자 경로 제외).

### A1 경고

| 메서드 · 경로 | 역할 | 내용 |
| --- | --- | --- |
| `GET /api/alerts?state=OPEN,ACKED&limit=` | 모두 | 경고 목록(등급 · 최근 순) |
| `GET /api/alerts/{id}` | 모두 | 한 건 + 근거 |
| `POST /api/alerts/{id}/ack` | S·M·U | 확인함 `{"comment"}` |
| `POST /api/alerts/{id}/resolve` | S·M | 해제 `{"comment"}` |

### A2 점검 규칙

| 메서드 · 경로 | 역할 | 내용 |
| --- | --- | --- |
| `GET /api/points/{id}/rules` | 모두 | 지점의 규칙과 최근 등급 |
| `GET /api/admin/checkers` | A | 판독기 목록(C3 그대로) |
| `POST /api/admin/points/{id}/rules` · `PUT /api/admin/rules/{id}` · `DELETE /api/admin/rules/{id}` | A | 규칙 만들기 · 고치기 · 지우기. `params` 는 `paramsSchema` 로 검사 |
| `POST /api/admin/rules/test` | A | multipart `image` + `rule` → 결과 한 건(C2). 저장 전에 기준 사진으로 시험한다 |
| `GET /api/observations/{id}/results` | 모두 | 관측의 규칙별 결과(근거 포함) |

### A3 사건 (화재 대응)

| 메서드 · 경로 | 역할 | 내용 |
| --- | --- | --- |
| `GET /api/incidents?state=open` · `GET /api/incidents/{id}` | 모두 | 목록 · 상세(사건 기록, 사진, 대응 로봇, 재판독 결과) |
| `GET /api/incidents/{id}/image?kind=detection\|recheck\|after` | 모두 | 근거 사진 |
| `POST /api/incidents/{id}/approve` | S·M·U·D | 투척 승인(`AWAITING_APPROVAL` 일 때만). 대시보드 계정도 할 수 있다 — 조회 전용의 유일한 예외(상황실 화면의 투척 승인 팝업) |
| `POST /api/incidents/{id}/launch` | S·M | 수동 투척(도착해 있을 때, 모드와 무관) |
| `POST /api/incidents/{id}/dismiss` | S·M·U | 오탐으로 닫기 `{"comment"}` |
| `POST /api/incidents/{id}/resolve` | S·M | 조치 완료로 닫기 |

### A4 설정

| 메서드 · 경로 | 역할 | 내용 |
| --- | --- | --- |
| `GET /api/settings` | 모두 | `{"launch.mode": "APPROVAL", …}` |
| `PUT /api/settings/{key}` | A·S | 값 바꾸기 `{"value"}`. 감사 로그에 남는다 |

설정 목록은 8장.

### A5 기준 좌표 (마커 · 대상)

| 메서드 · 경로 | 역할 | 내용 |
| --- | --- | --- |
| `GET /api/markers` | 모두 | 마커 목록(번호 · 좌표 · 용도) |
| `POST /api/admin/markers` · `PUT` · `DELETE /api/admin/markers/{id}` | A | 마커 등록. 좌표는 지도에서 찍거나 아래 "재기"로 채운다 |
| `POST /api/admin/references/measure` | A | `{"robotId", "kind": "MARKER" \| "RULE", "id"}` → `{"x", "y", "yaw", "samples", "spread"}` — 터틀봇의 지금 사진과 위치로 대상의 지도 좌표를 잰다(S2 snapshot + C2). 여러 번 불러 평균한다 |

### A6 대시보드 · 로봇

| 메서드 · 경로 | 변경 |
| --- | --- |
| `GET /api/dashboard/overview` | `alerts` 를 경고 표에서 읽는다(모양은 지금 그대로). `incidents`(열린 사건), `launchMode`, 지점별 `grade` 추가 |
| `GET /api/robots` · `/status` | `kind`, `poseQuality`, `docked`, `launcher`(`ready` · `remaining`), `lastClosureError` 추가 |
| `POST · PUT /api/admin/robots` | `config` 에 2.4 의 항목 |

**게이트웨이 규칙에 더할 줄** (`application.yml`, 위에서부터 맞는 규칙)

```yaml
- pattern: /api/settings/**
  methods: [PUT]
  roles: [ADMIN, SUPERVISOR]
- pattern: /api/incidents/*/launch
  roles: [SUPERVISOR, MANAGER]
- pattern: /api/incidents/*/resolve
  roles: [SUPERVISOR, MANAGER]
- pattern: /api/alerts/*/resolve
  roles: [SUPERVISOR, MANAGER]
```

나머지는 지금 규칙으로 맞는다(`/api/admin/**` = ADMIN, `GET` = 모두, 변경 = 사용자 역할, 대시보드 계정은 `GET` 만).
라우팅: `/api/alerts/**` · `/api/incidents/**` · `/api/settings/**` · `/api/markers/**` · `/api/admin/rules/**` · `/api/admin/markers/**` · `/api/admin/references/**` · `/api/admin/checkers` → inspection-service.

---

## 6. DB 표

### inspection-service (Flyway V7~)

```sql
-- D1 점검 규칙
CREATE TABLE inspection_rule (
    rule_id     bigint       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    point_id    bigint       NOT NULL REFERENCES inspection_point (point_id),
    name        varchar(100) NOT NULL,
    kind        varchar(30)  NOT NULL,              -- 판독기 종류. 값의 검사는 GET /checkers 로 한다(표에 CHECK 를 두지 않는다)
    params      jsonb        NOT NULL DEFAULT '{}',
    regions     jsonb        NOT NULL DEFAULT '{}', -- {"INSPECTOR":[x0,y0,x1,y1], "PATROL":[...]}
    grading     jsonb        NOT NULL,
    target_x    double precision,                   -- 대상의 지도 좌표(없어도 된다)
    target_y    double precision,
    target_yaw  double precision,
    target_size_m double precision,
    use_as_reference boolean NOT NULL DEFAULT false,
    enabled     boolean      NOT NULL DEFAULT true,
    created_at  timestamptz  NOT NULL DEFAULT now(),
    updated_at  timestamptz  NOT NULL DEFAULT now(),
    deleted_at  timestamptz
);
CREATE INDEX idx_rule_point ON inspection_rule (point_id) WHERE deleted_at IS NULL;

-- D2 규칙별 판독 결과. 다시 판독하면 행이 추가된다(가장 최근 행이 현재 값)
CREATE TABLE rule_result (
    result_id       bigint       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    observation_id  bigint       NOT NULL REFERENCES observation (observation_id),
    rule_id         bigint       NOT NULL REFERENCES inspection_rule (rule_id),
    grade           varchar(10)  NOT NULL CHECK (grade IN ('NORMAL', 'WARNING', 'EMERGENCY', 'UNKNOWN')),
    value_num       double precision,
    value_label     varchar(50),
    unit            varchar(20),
    confidence      double precision,
    located         jsonb,
    evidence        jsonb,
    reason          text,
    checker_version varchar(40),
    rule_snapshot   jsonb        NOT NULL,          -- 판독 당시의 규칙(나중에 규칙을 고쳐도 근거가 남는다)
    analyzed_at     timestamptz  NOT NULL DEFAULT now()
);
CREATE INDEX idx_result_obs ON rule_result (observation_id, result_id DESC);
CREATE INDEX idx_result_rule ON rule_result (rule_id, result_id DESC);

ALTER TABLE observation ADD COLUMN robot_kind varchar(20), ADD COLUMN camera_frame varchar(10), ADD COLUMN arrival_error_xy double precision;

-- D3 경고
CREATE TABLE alert (
    alert_id    bigint       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    type        varchar(40)  NOT NULL,              -- RULE_VIOLATION, FIRE_DETECTED, OBS_UNABLE, TASK_FAILED, ...
    grade       varchar(10)  NOT NULL CHECK (grade IN ('WARNING', 'EMERGENCY')),
    state       varchar(10)  NOT NULL DEFAULT 'OPEN' CHECK (state IN ('OPEN', 'ACKED', 'RESOLVED')),
    dedup_key   varchar(100) NOT NULL,              -- 같은 대상 · 같은 종류를 하나로: 'rule:12', 'incident:5', 'task:68'
    title       varchar(200) NOT NULL,
    detail      text,
    point_id    bigint       REFERENCES inspection_point (point_id),
    x           double precision,
    y           double precision,
    ref_kind    varchar(20)  NOT NULL,              -- observation | task | incident | rule
    ref_id      bigint       NOT NULL,
    task_id     bigint,
    evidence    jsonb        NOT NULL DEFAULT '{}',
    opened_at   timestamptz  NOT NULL DEFAULT now(),
    updated_at  timestamptz  NOT NULL DEFAULT now(),
    acked_by    varchar(50), acked_at timestamptz,
    resolved_by varchar(50), resolved_at timestamptz, -- 자동 해제면 resolved_by = 'SYSTEM'
    comment     text
);
CREATE UNIQUE INDEX uq_alert_open ON alert (dedup_key) WHERE state <> 'RESOLVED';
CREATE INDEX idx_alert_state ON alert (state, grade, opened_at DESC);

-- D4 사건(화재 대응)
CREATE TABLE incident (
    incident_id     bigint       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    type            varchar(20)  NOT NULL DEFAULT 'FIRE',
    state           varchar(20)  NOT NULL,          -- F1
    grade           varchar(10)  NOT NULL,
    x               double precision NOT NULL,
    y               double precision NOT NULL,
    pose_quality    double precision,               -- 감지 때 젯봇 위치 신뢰도
    detected_by     bigint       NOT NULL,          -- 로봇 ID
    det_id          varchar(60)  UNIQUE,            -- 감지 중복 판별
    launch_mode     varchar(10)  NOT NULL CHECK (launch_mode IN ('APPROVAL', 'AUTO')),  -- 만들어질 때의 설정
    responder_id    bigint,
    task_id         bigint       REFERENCES inspection_task (task_id),                   -- 출동 작업
    standoff        jsonb,                          -- 고른 투척 위치와 남은 후보
    detection_image text,
    recheck_image   text,
    after_image     text,
    recheck         jsonb,                          -- 도착 후 재판독 결과
    after_check     jsonb,                          -- 투척 후 재판독 결과
    approved_by     varchar(50), approved_at timestamptz,
    closed_by       varchar(50), closed_at timestamptz, close_reason text,
    created_at      timestamptz  NOT NULL DEFAULT now(),
    updated_at      timestamptz  NOT NULL DEFAULT now()
);
CREATE INDEX idx_incident_open ON incident (created_at DESC) WHERE closed_at IS NULL;

CREATE TABLE incident_event (                       -- 추가만 한다
    event_id    bigint       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    incident_id bigint       NOT NULL REFERENCES incident (incident_id),
    source      varchar(10)  NOT NULL CHECK (source IN ('USER', 'ROBOT', 'SYSTEM')),
    type        varchar(40)  NOT NULL,
    detail      jsonb        NOT NULL DEFAULT '{}',
    actor       varchar(50),
    occurred_at timestamptz  NOT NULL DEFAULT now()
);
CREATE INDEX idx_incident_event ON incident_event (incident_id, event_id);

ALTER TABLE inspection_task ADD COLUMN kind varchar(20) NOT NULL DEFAULT 'INSPECTION', ADD COLUMN incident_id bigint REFERENCES incident (incident_id);

-- D5 마커
CREATE TABLE reference_marker (
    marker_id   integer      PRIMARY KEY,           -- ArUco 번호
    purpose     varchar(10)  NOT NULL CHECK (purpose IN ('DOCK', 'ZONE')),
    dictionary  varchar(30)  NOT NULL DEFAULT 'DICT_4X4_50',
    size_m      double precision NOT NULL,
    x           double precision NOT NULL,
    y           double precision NOT NULL,
    z           double precision NOT NULL DEFAULT 0,
    yaw         double precision NOT NULL,          -- 마커가 바라보는 방향
    dock_x      double precision, dock_y double precision, dock_yaw double precision,  -- 로봇이 설 자리(DOCK)
    updated_at  timestamptz  NOT NULL DEFAULT now()
);

-- D6 설정
CREATE TABLE app_setting (
    key         varchar(60)  PRIMARY KEY,
    value       jsonb        NOT NULL,
    updated_by  varchar(50),
    updated_at  timestamptz  NOT NULL DEFAULT now()
);
```

### robot-service (Flyway V2)

```sql
-- D7
ALTER TABLE mission ADD COLUMN kind varchar(20) NOT NULL DEFAULT 'INSPECTION';
-- state 에 HOLDING 추가(표에 CHECK 가 없어 표 변경은 없다)
CREATE TABLE actuator_command (                     -- 투척 명령: 한 번만 실행
    command_id  varchar(60)  PRIMARY KEY,
    robot_id    bigint       NOT NULL REFERENCES robot (robot_id),
    mission_id  bigint,
    kind        varchar(20)  NOT NULL,
    request     jsonb        NOT NULL,
    state       varchar(10)  NOT NULL,              -- SENT ACCEPTED DONE FAILED
    result      jsonb,
    created_at  timestamptz  NOT NULL DEFAULT now(),
    updated_at  timestamptz  NOT NULL DEFAULT now()
);
```

로봇 종류(`kind`)는 `robot.config` 에 둔다(표 변경 없음). analysis-service 는 표 변경이 없다(규칙은 inspection-service 가 갖는다).

---

## 7. 상태 흐름

### F1 사건

```
            ┌──────────────────────────── DISMISSED (오탐: 사람이 닫음 · 재판독이 정상)
            │
DETECTED ─▶ DISPATCHED ─▶ ARRIVED ─▶ [재판독] ─┬─ AUTO, 비상 확인 ───────────────▶ LAUNCHING ─▶ LAUNCHED ─▶ RESOLVED
                │                              ├─ APPROVAL ─▶ AWAITING_APPROVAL ─ 승인 ─▶ ┘            │
                └─ 갈 수 없음 · 로봇 없음 ─▶ FAILED ◀── 투척 실패 ───────────────────────────────────────┘
```

| 전이 | 누가 | 조건 · 하는 일 |
| --- | --- | --- |
| → `DETECTED` | 감지 보고(S3) | 등급이 비상일 때만 사건을 만든다. 열린 사건이 `incident.merge_radius_m` 안에 있으면 새로 만들지 않고 그 사건에 붙인다. 경고 `FIRE_DETECTED` 를 연다 |
| `DETECTED` → `DISPATCHED` | 서버(자동) | 대응 로봇 고르기(설정된 로봇 또는 한가한 `INSPECTOR` 중 가까운 것) → 점검 중이면 그 작업 취소 요청 → 투척 위치 후보 받기(S2 standoff) → 출동 미션(`RESPONSE`) |
| `DISPATCHED` → `ARRIVED` | 로봇 보고 `HOLDING` | `BLOCKED_NO_PATH` 면 다음 후보로 다시 보낸다. 후보가 없으면 `FAILED` |
| `ARRIVED` → 재판독 | 서버 | 사진 받기(S2 snapshot) → 즉시 판독(C2, `THERMAL`). 안 보이면 `launch.search_steps` 번까지 다시 본다. **열원은 보이는데 조준 범위 밖이면**(로봇의 도착 방향 허용 오차 8.6° 가 조준 범위보다 크다) 그 각도만큼 제자리에서 돌리고(`POST /internal/missions/{id}/aim`, 오도메트리로 확인하며 회전) 다시 본다 — 최대 3번 |
| 재판독 → `LAUNCHING` | 서버 | **모드 `AUTO`**: 재판독 = 비상이고, 대상이 `launch.aim_tolerance_deg` 안에 있으면 투척 명령(S2 actuate). 조건을 못 채우면 `AWAITING_APPROVAL` 로 넘긴다 |
| 재판독 → `AWAITING_APPROVAL` | 서버 | **모드 `APPROVAL`**: 재판독 결과와 사진을 붙여 승인 요청. `launch.approval_remind_sec` 마다 다시 알린다 |
| `AWAITING_APPROVAL` → `LAUNCHING` | 사용자(A3 approve) | 투척 명령 |
| 재판독 → `DISMISSED` | 서버 | `launch.search_steps` 번을 다 봐도 정상(열원 없음)이면 오탐으로 닫는다 |
| `LAUNCHING` → 투척 후 판독 | 로봇 보고 `ACTUATED` | 투척 후 한 번 더 판독해 `after_check` 에 남긴다. 정상이면 `RESOLVED` |
| → `MONITORING` | 서버 | **투척 후에도 열원이 보이면 대응 로봇(터틀봇)이 그 자리에 머물며 계속 감시한다.** `incident.monitor_interval_sec` 마다 다시 찍어 판독하고 가장 최근 사진 · 결과를 남긴다(등급이 바뀌면 사건 기록). 로봇은 풀어 주지 않는다. 다시 쏘려면 수동 투척 |
| `MONITORING` → `RESOLVED` | 서버 또는 사용자 | 연속 `incident.monitor_clear_count` 회 정상이면 열원이 사라진 것으로 보고 자동으로 닫는다. 그 밖에는 사람이 닫을 때까지 감시를 계속한다 |
| `MONITORING` → `LAUNCHED` | 서버 | 대응 로봇이 자리를 떠나면(비상 정지 등) 감시가 끊겼음을 알리고 사람의 확인을 기다린다 |
| → `FAILED` | 서버 | 갈 수 없음 · 로봇 없음 · 투척 실패(`ACTUATE_FAILED`). 경고는 열린 채로 둔다 |
| 닫힌 뒤 → 새 사건 | 감지 보고(S3) | **닫는 것은 기록을 닫는 것이지 실제 상황의 종료가 아니다.** 사건을 닫은 뒤 `incident.reopen_grace_sec` 가 지나도 같은 감지(`detId`)가 계속 오면 새 사건으로 다시 연다(`REOPENED`, 이전 사건 번호를 남긴다). 그래서 robot-service 는 같은 감지도 15초마다 다시 넘긴다 |
| 닫힐 때 | 서버 | 출동 미션 끝내기(S2 finish) → 그 로봇의 밀린 예약이 이어진다 |

사건이 열려 있는 동안 대응 로봇의 예약 회차는 실행 버퍼에서 기다린다.

**두 로봇의 역할:** 터틀봇은 투척 로봇이다 — 열원 지역에 가서 투척하고, 열원이 남아 있으면 그 지역을 계속 감시한다. 젯봇은 그동안 다른 지역의 순찰을 계속한다(사건에 묶이는 것은 대응 로봇뿐이다). 젯봇은 지금 시뮬레이션에 없다.

### F2 경고

| 사건 | 처리 |
| --- | --- |
| 규칙 결과가 `WARNING` · `EMERGENCY` | `dedup_key = rule:{ruleId}` 로 열거나, 이미 열려 있으면 등급 · 근거를 고친다 |
| 같은 규칙의 다음 결과가 `NORMAL` | 자동 해제(`resolved_by = SYSTEM`) |
| 결과가 `UNKNOWN` | 열린 경고는 그대로 둔다(정상 확인이 아니다). 새 경고는 만들지 않고 지점이 "확인 필요"로 보인다 |
| 사람이 관측을 "정상"으로 판정 | 그 관측에서 나온 경고를 해제한다. "이상"이면 `EMERGENCY` 로 올린다 |
| 확인 불가 관측 · 실패한 작업 | 지금 대시보드가 계산하던 것(`OBS_UNABLE` · `TASK_FAILED` 등)을 같은 표에 `WARNING` 으로 넣는다 |
| 사건 | `FIRE_DETECTED`(`EMERGENCY`). 사건이 닫히면 같이 해제 |

지점의 등급 = 그 지점 규칙들의 가장 최근 결과 가운데 가장 나쁜 것. 사람 판정이 있으면 그것이 우선한다.

### F3 젯봇 작업 한 번 (robot-service 가 미션에 끼워 넣는다)

| 순서 | 명령 | 실패하면 |
| --- | --- | --- |
| 1 | `align START` | 미션 실패(`PREFLIGHT_FAILED`, 사유 `MARKER_NOT_FOUND`) — 출발하지 않는다 |
| 2 | 지점마다 `goal`(+ `refs`) → 촬영 → 보고 | 지점 하나의 실패는 지금처럼 "확인 불가"로 기록하고 다음 지점으로. `POSE_UNCERTAIN` 이면 남은 지점을 건너뛰고 3으로 |
| 3 | `align END` | 사건 기록 `ALIGN_FAILED` + 경고(`WARNING`, "젯봇 복귀 실패 — 위치 확인 필요") |
| 4 | 복귀 오차 기록 | `ALIGNED(kind=END)` 의 오차를 작업에 남긴다. `patrol.closure_warn_m` 을 넘으면 경고 |

순찰 중 감지(`/patrol/detection`)는 이 순서와 무관하게 언제든 온다.

### F4 두 로봇의 조정 (서버)

두 로봇이 한 지도에서 움직일 때 일을 나누는 방식이다.

| 층 | 하는 일 | 어디서 |
| --- | --- | --- |
| 임무 계획 | 누가 · 언제 · 어디로, 순서와 우선순위, **두 로봇 사이의 조정** | 서버 |
| 경로 계획 | 목적지까지의 길, 장애물 우회(터틀봇: Nav2 가 비용 지도로 경로를 다시 짠다) | 로봇 |
| 제어 | 속도 명령, 정지, 워치독 | 로봇 |

서버는 목적지만 보내고(목표 계약), 길과 조종은 로봇이 맡는다. 실시간 장애물은 로봇 센서만 알고, 반응이 통신 지연을 기다릴 수 없기 때문이다.
로봇은 서로의 계획을 모르고, 젯봇은 라이다가 없어 터틀봇을 피하기 어렵다. 그래서 두 로봇 사이의 조정은 서버가 한다.

| 조정 | 방식 |
| --- | --- |
| 자리 예약 | 점검 지점 · 투척 위치 · 대기 구역 · 좁은 통로(구역으로 등록)를 한 번에 한 로봇만 차지한다. 목표를 보내기 전에 예약하고, 못 하면 그 로봇의 대기열에서 기다린다(지금의 예약 실행 버퍼와 같은 방식, 대기 사유 "다른 로봇이 사용 중") |
| 우선순위 | 화재 출동(`RESPONSE`) > 점검 · 순찰. 출동 경로의 구역을 먼저 예약하고, 그 구역에 있는 다른 로봇은 비켜 설 자리(구역마다 등록)로 보낸다 |
| 간격 유지 | 서버는 두 로봇의 지도 위 위치를 받고 있다. 거리가 `fleet.min_separation_m` 아래로 가까워지면 우선순위가 낮은 쪽의 목표를 멈추고(`goal_cancel`), 멀어지면 같은 목표를 다시 보낸다 |

- 표: `zone`(이름 · 다각형 · 비켜 설 자리), `zone_lease`(구역 · 로봇 · 작업 · 시각). 설정: `fleet.min_separation_m`.
- 터틀봇 한 대만 쓰는 지금의 시뮬레이션 구현에는 넣지 않았다. 젯봇이 붙을 때(구현 묶음 9) 함께 만든다.

---

## 8. 설정으로 열어 둔 것

정해지지 않은 항목은 모두 여기의 설정 자리로 받는다. 값이 정해지면 화면에서 넣는다(코드 변경 없음).

| 미정 항목 | 받는 자리 | 기본값(임시) |
| --- | --- | --- |
| 투척 모드 | 설정 `launch.mode` | `APPROVAL` |
| 투척 사거리 · 허용 범위 | 설정 `launch.range_m`, `launch.range_tolerance_m` | 1.0, 0.2 |
| 좌우 조준 범위 | 설정 `launch.aim_tolerance_deg` | 5 |
| 한 번에 쏘는 수 · 기구 추가 값 | 설정 `launch.count`, `launch.params` | 1, `{}` |
| 도착 후 찾기 횟수 · 회전 각 | 설정 `launch.search_steps`, `launch.search_step_deg` | 4, 20 |
| 승인 재알림 간격 | 설정 `launch.approval_remind_sec` | 30 |
| 출동시킬 로봇 | 설정 `incident.responder_robot_id`(비우면 자동 선택) | 비움 |
| 가까운 감지를 한 사건으로 묶는 거리 | 설정 `incident.merge_radius_m` | 1.0 |
| 투척 뒤 현장 감시 간격 · 종료 기준 | 설정 `incident.monitor_interval_sec`, `incident.monitor_clear_count` | 10, 2 |
| 닫은 뒤에도 감지가 계속될 때 다시 여는 유예 | 설정 `incident.reopen_grace_sec` | 60 |
| 지도에 제어기 방향(주황 실선) 표시 | 설정 `display.control_direction`(관제 지도 · 대시보드 지도) | `false`(숨김) |
| 열화상 인쇄물의 색상표 · 열원 기준 | 감지 설정 `detect.thermal`(= `THERMAL` 규칙의 `params` · `grading`) | `iron`, 3.3 의 예 |
| 감지 보고에 필요한 연속 프레임 수 | 설정 `detect.report_frames` | 5 |
| 계기판 · 표시등의 실제 대상, 눈금 · 색 | 규칙의 `params` | — (규칙을 만들 때 입력) |
| 등급 기준 값 | 규칙의 `grading` | — |
| 로봇별 기대 영역 | 규칙의 `regions` | 사진 전체 |
| 새 판독 종류 | 판독기 파일 추가 → `GET /checkers` | — |
| 대기 구역 위치, 마커 번호 · 크기 · 높이 | 마커 표(D5) | — |
| 정렬 구역 추가(1~2곳) | 마커 표에 `ZONE` 행 추가 | 없음 |
| 위치 기준으로 쓸 대상 | 규칙의 `target` · `use_as_reference` | 꺼짐 |
| 대상 기준 보정 한도 | 설정 `patrol.max_correction_m` | 0.5 |
| 복귀 오차 경고 기준 | 설정 `patrol.closure_warn_m` | 0.3 |
| 젯봇 도착 허용 오차, 카메라 화각 · 높이 | 로봇 설정 `arrival`, `camera` | 실측 뒤 입력 |
| 두 로봇 사이 최소 간격 | 설정 `fleet.min_separation_m` | 0.8 |
| 디바이스 쪽 토픽 이름 | 로봇 설정 `topics`, 브리지 파라미터 | 2장의 이름 |
| 투척 기구의 시리얼 형식 | `launcher_bridge.py` 파라미터 | 2.2 의 줄 형식 |
| 현업용 열화상 카메라 | 로봇 설정 `camera.frame = THERMAL` | `RGB` |
| ROS 2 배포판 | 이미지 빌드 인자 `ROS_DISTRO` | `humble` |

---

## 9. 화면

| 화면 | 더하는 것 | 쓰는 API |
| --- | --- | --- |
| 관리자 · 점검 지점 | 규칙 목록과 편집(폼은 `paramsSchema` 로 그린다), 기준 사진 위 영역 지정, 규칙 시험, 대상 좌표(지도에서 찍기 · 재기) | A2 · A5 |
| 관리자 · 로봇 | 종류 · 허용 오차 · 카메라 · 토픽 | A6 |
| 관리자 · 설정(새 메뉴) | 8장의 설정, 마커 | A4 · A5 |
| 사용자 · 관측 상세 | 규칙별 등급과 근거 겹쳐 보기 | A2 |
| 사용자 · 사건(새 메뉴) | 목록 · 상세, 승인 · 수동 투척 · 닫기 | A3 |
| 사용자 · 경고(새 메뉴) | 목록, 확인 · 해제 | A1 |
| 사용자 · 관제 | 승인 대기 사건 띠(지금의 지연 안내 자리), 젯봇 표시 | A3 · A6 |
| 대시보드 | 사건 패널, 사건 상세(`Ref` 에 `incident` 추가), 지점 핀 등급 색, 머리줄에 투척 모드, 지도에 젯봇 · 화재 위치 | A6 · A1 · A3 |

대시보드는 조회만 한다. 단 **투척 승인은 대시보드에서도 한다**(투척 승인 팝업). 경고 확인 · 해제, 사건 닫기는 사용자 화면에서 한다.

**팝업 두 가지** (사용자 영역의 모든 화면과 대시보드에 뜬다)

| 팝업 | 뜨는 조건 | 내용 | 우선순위 |
| --- | --- | --- | --- |
| 투척 승인(`LaunchDialog`) | 사건이 `AWAITING_APPROVAL`(로봇이 투척 위치에 도착) | 대응 로봇의 실시간 카메라, 도착 후 재판독 결과(등급 · 열원 비율 · 조준), **투척 승인** 단추. "나중에"로 닫으면 30초 뒤 다시 뜬다 | 위 |
| 비상(`EmergencyDialog`) | 등급이 비상인 열린 경고(화재 감지, 규칙 판독 비상 등). 경고(주황)는 띄우지 않는다 | 제목 · 위치 · 시각, **확인** 단추(눌러야 닫힌다) | 아래 |

---

## 10. 구현 작업 목록

인터페이스가 정해졌으므로 아래 순서로 구현한다. 각 묶음은 앞 묶음만 있으면 시뮬레이션에서 끝까지 시험할 수 있다. 실물이 있어야 하는 것은 맨 뒤에 모았다.

| 묶음 | 작업 | 인터페이스 | 실물 필요 |
| --- | --- | --- | --- |
| 1 공용 | 설정 표와 API, 경고 표와 API, 대시보드가 경고 표를 읽게 | D3 · D6 · A1 · A4 · A6 | 아니오 |
| 2 판독 틀 | 판독기 인터페이스, 등급 공통 코드, `/check` · `/checkers`, 작업 큐 확장 | C1~C5 · S4 | 아니오 |
| 3 규칙 | 규칙 표 · 결과 표, 관리자 편집 화면, 결과 저장 → 경고 | D1 · D2 · A2 · F2 | 아니오 |
| 4 판독기 | `LAMP` · `GAUGE` → `THERMAL` → `OBJECT` · `MARKER`, 시뮬레이션 월드에 대상 추가, `target.sh` | C5 | 아니오 |
| 5 화면 | 관측 상세의 등급 · 근거, 경고 메뉴, 대시보드 등급 색 | A1 · A2 · A6 | 아니오 |
| 6 투척 계약 | 토픽 · `actuate` · 명령 표, `mock_launcher.py`, `launcher_bridge.py` | R3 · S2 · D7 | 아니오(모의) |
| 7 사건 | 사건 표 · 상태 흐름, 감지 받기, 출동 미션(`RESPONSE` · `HOLD`), 투척 위치 후보, 가로채기, 두 모드 | D4 · S1~S3 · F1 · A3 | 아니오 |
| 8 사건 화면 · 시험 | 사건 메뉴 · 승인, 대시보드 사건 패널, `fire.sh`, 전 구간 시험(E2E) 추가 | A3 · A6 | 아니오 |
| 9 젯봇 노드 | `ros/patrol`: 정렬, 오도메트리, 목표 브리지, 대상 기준 보정, 실시간 감지. 미션 앞뒤 정렬(F3), 마커 표 · 재기 | R1 · R2 · R4 · R5 · D5 · A5 · F3 | 녹화 영상(rosbag)으로 개발, 확인은 실물 |
| 10 실물 연결 | 터틀봇 실기 + 투척 기구, 젯봇 실기 연결(토픽 이름 · 시리얼 형식 맞추기) | R6 · J1 | **예** |

묶음 1~8 은 시나리오 2 전체와 시나리오 1 의 서버 · 화면 전부다. 실물 없이 완성하고 전 구간 시험으로 확인한다.

## 11. 구현 후 작업 (실측)

장비와 구현이 있어야 할 수 있는 일이다. 계획 단계의 범위가 아니며, 결과는 8장의 설정값으로 들어간다.

| 실측 | 결과가 들어갈 곳 |
| --- | --- |
| 젯봇 정렬 정확도, 마커가 보이는 거리 | 마커 크기(D5), 대기 구역 위치 |
| 젯봇 복귀 오차(대상 기준 보정을 켰을 때 · 껐을 때) | `patrol.closure_warn_m`, 계획 하나의 길이, 정렬 구역 추가 여부 |
| 젯봇 도착 정확도 | 로봇 설정 `arrival`, 규칙 `regions.PATROL` 의 여유 |
| Jetson Nano 처리 속도 | 영상 해상도, `detect.report_frames` |
| 스테레오 거리 오차 | 화재 좌표의 신뢰 범위, `incident.merge_radius_m` |
| 투척 사거리 · 좌우 편차 | `launch.range_m`, `launch.range_tolerance_m`, `launch.aim_tolerance_deg` |
| 판독기별 오판 비율(실제 대상 · 실제 조명) | 규칙의 `params` · `grading`, 필요하면 판독기를 모델로 교체 |
| 터틀봇 카메라로 마커 · 대상 좌표 재기의 편차 | 재기 횟수, 지도에서 직접 찍기로 대체할지 |
