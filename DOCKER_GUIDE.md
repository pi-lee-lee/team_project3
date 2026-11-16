# Docker 구동 가이드

화재 점검 로봇 서비스(웹·백엔드·DB·TurtleBot3 시뮬레이션)를 Docker Compose 로 띄우는 방법이다.
명령은 **macOS·Linux(터미널)** 와 **Windows(PowerShell)** 를 함께 적었다. 둘이 같으면 한 번만 적었다.

- 구성·코드 구조·시나리오 설명: [RUNNING.md](RUNNING.md)
- 접속 주소: http://localhost:8080

---

## 1. 준비

| 항목 | 요구 사항 |
| --- | --- |
| Docker | Docker Desktop 최신 버전 (Windows 는 **WSL 2 백엔드** 사용) |
| 메모리 | Docker 에 **8GB 이상** 할당 권장 (시뮬레이터 약 2~3.5GB + 서비스들) |
| 디스크 | 약 10GB (ROS 2·Gazebo 이미지가 크다) |
| Git | 저장소 내려받기용 |
| Python 3 | 종단 간 시험(`scripts/e2e_test.py`)을 돌릴 때만 필요 |

Docker Desktop 메모리 설정: Settings → Resources → Memory.
Windows(WSL 2)는 `%UserProfile%\.wslconfig` 에서 정한다.

```ini
[wsl2]
memory=10GB
```

CPU별 참고:
- **Intel·AMD (Windows, Linux, Intel Mac)**: 시뮬레이터가 그대로 실행된다.
- **Apple Silicon Mac**: Gazebo Classic 이 amd64 전용이라 시뮬레이터만 에뮬레이션(Rosetta)으로 실행된다. 동작하지만 느리다.
  Docker Desktop → Settings → General → "Use Rosetta for x86_64/amd64 emulation" 을 켠다.

## 2. 내려받기

```bash
git clone https://github.com/pi-lee-lee/team_project3.git
cd team_project3
git switch feat/msa-sim-stack
```

Windows 에서는 줄바꿈이 바뀌지 않도록 저장소에 `.gitattributes` 가 들어 있다(셸 스크립트는 LF 고정).
이 설정이 생기기 전에 받아 둔 사본이라면, 고친 내용이 없는 상태에서 한 번 다시 받는다(고친 내용은 사라진다):
`git rm -r --cached . ; git reset --hard`

## 3. 환경 파일(.env) 만들기

비밀번호와 키를 담는 파일이다. 저장소에는 올라가지 않는다.

macOS·Linux
```bash
cp .env.example .env
```

Windows PowerShell
```powershell
Copy-Item .env.example .env
```

`.env` 를 열어 `change-me` 로 된 값을 모두 바꾼다.

| 키 | 내용 |
| --- | --- |
| `JWT_SECRET` | 32자 이상 임의 문자열 |
| `POSTGRES_PASSWORD`, `SERVICE_DB_PASSWORD` | DB 비밀번호 |
| `INITIAL_ADMIN_LOGIN`, `INITIAL_ADMIN_PASSWORD` | 첫 실행 때 만들어지는 웹 admin 계정 |
| `DEMO_USERS_PASSWORD` | 값을 넣으면 시험 계정 sup1(1 관리자)·mgr1(2 매니저)·user1(3 사용자)을 이 비밀번호로 만든다 |
| `WEB_PORT` | 웹 접속 포트 (기본 8080) |

임의 문자열 만들기 (선택)
```bash
openssl rand -base64 32
```
```powershell
[Convert]::ToBase64String([byte[]](1..32 | ForEach-Object { Get-Random -Maximum 256 }))
```

> 계정 비밀번호는 **DB 가 처음 만들어질 때** 한 번만 적용된다. 바꾸려면 관리자 화면에서 바꾸거나 9절의 초기화를 한다.

## 4. 실행

```bash
docker compose up -d --build
```

첫 실행은 이미지 내려받기·빌드로 10~20분, 이후에는 3~5분 걸린다.
각 Spring 서비스는 시작할 때 자기 코드를 빌드하고, 시뮬레이터는 Gazebo·Nav2 를 올린다.

상태 확인 — 모두 `healthy` 가 되면 준비 완료다(`common-build`, `frontend-build` 는 빌드 후 `Exited (0)` 이 정상).
```bash
docker compose ps
```

접속: http://localhost:8080 → `.env` 의 admin 계정으로 로그인.

## 5. 확인 방법

| 확인 | 방법 |
| --- | --- |
| 서비스 상태 | admin 로그인 → 상단 "시스템" 메뉴: 모든 서비스 UP, tb3-sim 연결 |
| 로봇 영상·조종 | 시험 계정(user1 등) 로그인 → "관제" |
| 점검 흐름 | "점검 요청"에서 지점 선택 → 작업 상세에서 이동·촬영·판정 |
| 자동 시험 | 아래 명령 (Python 3 필요) |

```bash
python3 scripts/e2e_test.py                    # 전체 (장애물 시나리오 포함, 20~40분)
python3 scripts/e2e_test.py --skip-obstacles   # 장애물 제외
python3 scripts/e2e_test.py --only-obstacles   # 장애물 시나리오만
```
```powershell
python scripts\e2e_test.py --skip-obstacles
```

## 6. 로그 보기

```bash
docker compose logs -f gateway            # 서비스 하나
docker compose logs -f robot-service sim  # 여러 개
docker compose logs --tail 100 sim
```

## 7. 멈추기·다시 시작

```bash
docker compose stop          # 멈춤 (데이터 유지)
docker compose start         # 다시 시작
docker compose down          # 컨테이너 삭제 (DB·사진 데이터는 볼륨에 유지)
docker compose up -d         # 다시 띄우기
```

## 8. 코드를 고친 뒤 반영

이미지에는 실행 환경만 있고 코드는 폴더를 연결해 구동하므로, 대부분 재시작만 하면 된다.

| 고친 곳 | 명령 |
| --- | --- |
| Spring 서비스 (`web/<서비스>`) | `docker compose restart <서비스>` — 시작할 때 다시 빌드 |
| 공유 라이브러리 (`web/common`) | `docker compose run --rm common-build` 후 `docker compose restart gateway user-service inspection-service robot-service` |
| 화면 (`web/frontend`) | `docker compose run --rm frontend-build` (브라우저 새로고침) |
| 분석 서비스 (`web/analysis-service`) | `docker compose restart analysis-service` |
| ROS (`ros/sim`, `ros/robot`) | `docker compose restart sim` |
| Dockerfile·requirements 변경 | `docker compose up -d --build <서비스>` |

## 9. 초기화 (데이터 전부 삭제)

DB·사진·빌드 캐시까지 지우고 처음 상태로 돌린다. `.env` 의 계정 비밀번호가 새로 적용된다.

```bash
docker compose down -v
docker compose up -d --build
```

## 10. 시뮬레이션: 지도 만들기와 장애물 시험

지도는 `ros/maps/site.*` (SLAM 으로 만든 것)이 이미 들어 있다. 월드를 바꿨을 때만 다시 만든다.

macOS·Linux
```bash
SIM_MODE=slam docker compose up -d sim             # SLAM 모드로 시뮬레이터 재시작
docker compose exec sim /sim/tools/explore.sh       # 경유점을 돌며 지도 작성 (수 분)
docker compose exec sim /sim/tools/save_map.sh      # ros/maps/site.* 저장 + 잡음 정리
docker compose up -d sim                            # 기본(nav) 모드로 복귀
```

Windows PowerShell
```powershell
$env:SIM_MODE = "slam"; docker compose up -d sim
docker compose exec sim /sim/tools/explore.sh
docker compose exec sim /sim/tools/save_map.sh
Remove-Item Env:SIM_MODE; docker compose up -d sim
```

장애물 놓기·치우기 (시뮬레이터 안의 시설에 상자를 놓는다)
```bash
docker compose exec sim /sim/tools/obstacle.sh place detour    # C1 복도 팔레트 (돌아갈 수 있음)
docker compose exec sim /sim/tools/obstacle.sh place reroute   # C2 아래쪽 막힘 (생산동으로 돌아감)
docker compose exec sim /sim/tools/obstacle.sh place block     # C2 위쪽 막힘 (P2 진입 불가)
docker compose exec sim /sim/tools/obstacle.sh clear           # 모두 치우기
```

시뮬레이터 없이(실제 로봇 연결 등) 실행
```bash
docker compose up -d --scale sim=0
```

## 11. 문제 해결

| 증상 | 확인·해결 |
| --- | --- |
| `port is already allocated` (8080) | `.env` 의 `WEB_PORT` 를 다른 값(예: 8090)으로 바꾸고 `docker compose up -d` |
| 서비스가 `unhealthy` 로 남음 | `docker compose logs <서비스>` 확인. 첫 빌드는 3분 이상 걸릴 수 있다 |
| sim 이 재시작을 반복하거나 느림 | Docker 메모리를 늘린다(8GB 이상). Apple Silicon 은 Rosetta 설정 확인 |
| `exec /sim/entrypoint.sh: no such file` 또는 `bad interpreter` (Windows) | 줄바꿈이 CRLF 로 바뀐 것. 2절의 다시 받기 실행 |
| 로그인 안 됨 | `.env` 비밀번호는 DB 를 처음 만들 때만 적용된다. 9절 초기화 또는 관리자 화면에서 변경 |
| 로봇이 "연결 안 됨" | `docker compose ps sim` 이 healthy 인지, `docker compose logs sim` 에 `Managed nodes are active` 가 있는지 확인 |
| 점검 요청이 "주행 시스템 준비 안 됨" | 시뮬레이터 시작 후 1~2분 더 기다린다 (Nav2·위치 추정 준비) |
| 작업이 "진입 불가"로 끝남 | 장애물을 놓아 두었는지 확인: `docker compose exec sim /sim/tools/obstacle.sh clear` |
