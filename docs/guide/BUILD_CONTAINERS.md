# 빌드용 컨테이너

`docker compose up` 을 하면 컨테이너 11개가 뜨는데, 그중 2개는 **일을 하고 바로 끝나는 빌드용 컨테이너**다.
`docker compose ps -a` 에서 `Exited (0)` 으로 보이는 것이 정상이다 — 죽은 것이 아니라 할 일을 마친 것이다.

| 컨테이너 | 만드는 것 | 결과가 놓이는 곳 | 그 결과를 쓰는 컨테이너 |
| --- | --- | --- | --- |
| `common-build` | 공유 라이브러리 `tp3:common` (jar) | 볼륨 `m2` (`/root/.m2`, 로컬 Maven 저장소) | gateway · user-service · inspection-service · robot-service |
| `frontend-build` | React 화면 (HTML · JS · CSS) | 호스트 폴더 `web/nginx/frontend/dist/` | web (nginx) |

나머지 9개(cdn · web · gateway · 서비스 4개 · db · sim)는 계속 떠 있는 실행 컨테이너다.

그림으로 보려면 [build_containers.svg](../architecture/build_containers.svg) 를 본다(시작 순서 · 두 컨테이너의 입력과 결과).

## 0. 전체 컨테이너 가운데 빌드용은 둘뿐이다

`compose.yaml` 에 선언된 컨테이너 전부다(선언 순서 그대로). **굵은 두 줄만 빌드용**이고, 나머지는 계속 떠 있는 실행 컨테이너다.

| # | 컨테이너 | 종류 | 하는 일 | 평소 상태 |
| --- | --- | --- | --- | --- |
| 1 | **`common-build`** | **빌드용** | **공유 라이브러리 `tp3:common` 설치** | **`Exited (0)` — 빌드하고 끝남** |
| 2 | `db` | 실행 | 서비스별 DB | Up |
| 3 | `user-service` | 실행 | 로그인 · 사용자 · 역할 | Up |
| 4 | `inspection-service` | 실행 | 점검 · 판정 · 사건 · 예약 | Up |
| 5 | `robot-service` | 실행 | 로봇 연결 계층 | Up |
| 6 | `gateway` | 실행 | 인증 · 경로별 권한 | Up |
| 7 | `analysis-service` | 실행 | 사진 분석 · 판독 | Up |
| 8 | **`frontend-build`** | **빌드용** | **React 화면을 `dist/` 로 빌드** | **`Exited (0)` — 빌드하고 끝남** |
| 9 | `web` | 실행 | 원본 서버(화면 · 프록시) | Up |
| 10 | `cdn` | 실행 | 엣지 캐시 · 외부 포트 8080 | Up |
| 11 | `sim` | 실행 | 시뮬레이션 · Nav2 · 브리지 | Up |

빌드용 컨테이너는 **서비스가 아니다.** 요청을 받지 않고, 포트를 열지 않고, `restart: "no"` 라 다시 뜨지 않는다.
compose 에 함께 선언해 둔 이유는 하나다 — 실행 컨테이너가 "빌드가 성공해서 끝난 뒤에만" 시작하도록 순서를 걸기 위해서다. 다시 쓰이는 때는 코드를 고쳐 다시 빌드할 때뿐이다(4장).

## 1. 왜 따로 두는가

이 저장소는 **코드를 이미지에 굽지 않는다.** 이미지에는 실행 환경(JDK · Maven, Node, nginx)만 있고, 코드는 폴더를 볼륨으로 연결해 쓴다.
그래서 코드를 고친 뒤 이미지를 다시 만들 필요가 없지만, 대신 **누군가 실행 전에 코드를 빌드해 두어야** 한다. 그 일을 하는 것이 빌드용 컨테이너다.

- **호스트에 아무것도 설치하지 않는다.** Maven · JDK · Node 가 없어도 Docker 만 있으면 빌드된다. 사람마다 버전이 달라 생기는 차이도 없다.
- **실행 컨테이너를 가볍게 둔다.** web 은 nginx 만 있으면 된다. Node 는 화면을 만들 때만 필요하므로 만들고 끝나는 컨테이너에 둔다.
- **한 번 만들어 여럿이 쓴다.** `tp3:common` 은 Spring 서비스 4개가 함께 쓰는 라이브러리다. 서비스마다 따로 빌드하지 않고 한 번 설치해 두면 넷이 가져다 쓴다.
- **순서를 compose 가 지킨다.** 실행 컨테이너는 빌드용 컨테이너가 **성공해서 끝난 뒤에만** 시작한다(`depends_on` 의 `service_completed_successfully`). 빌드가 실패하면 뒤 컨테이너는 뜨지 않는다.

## 2. common-build — 공유 라이브러리

| 항목 | 내용 |
| --- | --- |
| 이미지 | `maven:3.9-eclipse-temurin-21` (공개 이미지 그대로, 따로 만들지 않음) |
| 명령 | `mvn -q -B install -DskipTests` |
| 읽는 곳 | `web/spring/common` → 컨테이너 안 `/workspace` |
| 쓰는 곳 | 볼륨 `m2` → `/root/.m2` (로컬 Maven 저장소에 `tp3:common:0.1.0` 설치) |
| 네트워크 | 서비스용 네트워크(front · edge · backend · robot)에 붙지 않는다(다른 컨테이너와 통신하지 않는다. 처음에는 의존 라이브러리를 인터넷에서 내려받는다) |

`tp3:common` 은 서비스들이 함께 지켜야 하는 약속을 담은 작은 라이브러리다: JWT 발급 · 검증(`JwtCodec`), 게이트웨이가 붙이는 사용자 헤더(`AuthHeaders`), 현재 사용자(`CurrentUser`).

Spring 서비스 4개도 같은 `m2` 볼륨을 `/root/.m2` 에 연결한다. 서비스는 시작할 때 자기 코드를 `mvn package` 로 빌드하는데, 이때 `tp3:common` 을 인터넷이 아니라 이 볼륨에서 찾는다. 그래서 순서가 정해진다.

```
common-build (설치하고 끝남)  →  gateway · user-service · inspection-service · robot-service (시작하며 자기 코드 빌드)
```

`m2` 볼륨에는 내려받은 의존 라이브러리도 쌓인다. 처음 한 번만 오래 걸리고, 그 뒤로는 다시 받지 않는다.

## 3. frontend-build — 화면

| 항목 | 내용 |
| --- | --- |
| 이미지 | `node:20-alpine` (공개 이미지 그대로) |
| 명령 | `npm install --no-audit --no-fund && npm run build` |
| 읽는 곳 | `web/nginx/frontend` → 컨테이너 안 `/app` |
| 쓰는 곳 | `web/nginx/frontend/dist/` (호스트 폴더에 그대로 생긴다), 볼륨 `frontend_modules` → `/app/node_modules` |
| 네트워크 | 서비스용 네트워크(front · edge · backend · robot)에 붙지 않는다(처음에는 npm 패키지를 인터넷에서 내려받는다) |

React 화면은 브라우저가 바로 읽을 수 없는 코드(TypeScript · JSX)로 쓰여 있다. `npm run build`(Vite)가 이것을 `index.html` 하나와 `assets/` 아래 JS · CSS 파일로 바꿔 `dist/` 에 놓는다.

web 컨테이너는 그 `dist/` 폴더를 **읽기 전용으로 연결해 그대로 내준다.** web 안에는 Node 도 React 도 없다.

```
frontend-build (dist/ 를 만들고 끝남)  →  web (dist/ 를 내줌)  →  cdn (assets/ 를 보관해 대신 내줌)  →  브라우저
```

`node_modules` 를 볼륨(`frontend_modules`)에 따로 두는 이유는 둘이다. 호스트 폴더에 수만 개 파일이 생기지 않고, 컨테이너(리눅스)용으로 설치된 패키지가 호스트(macOS · Windows)의 것과 섞이지 않는다.

## 4. 언제 다시 돌리는가

`docker compose up -d --build` 로 전체를 띄우면 둘 다 한 번씩 돈다. 그 뒤 코드를 고쳤을 때는 고친 곳에 따라 다르다.

| 고친 곳 | 할 일 | 빌드용 컨테이너 |
| --- | --- | --- |
| 화면 (`web/nginx/frontend`) | `docker compose run --rm frontend-build` 뒤 브라우저 새로고침 | **frontend-build 를 다시** |
| 공유 라이브러리 (`web/spring/common`) | `docker compose run --rm common-build` 뒤 `docker compose restart gateway user-service inspection-service robot-service` | **common-build 를 다시** |
| Spring 서비스 하나 | `docker compose up -d --force-recreate <서비스>` | 필요 없음(서비스가 시작하며 스스로 빌드) |
| 분석 서비스 · ROS 코드 | `docker compose restart analysis-service` / `sim` | 필요 없음(빌드 단계가 없다) |
| nginx 설정 | `docker compose exec web nginx -s reload` (cdn 도 같음) | 필요 없음 |

- 화면을 다시 빌드해도 **web · cdn 을 다시 띄울 필요가 없다.** web 은 폴더를 보고 있을 뿐이고, 새 빌드는 파일 이름(해시)이 달라져 cdn 의 옛 보관본과 겹치지 않는다. `index.html` 은 cdn 이 보관하지 않는다.
- 화면이 안 바뀐 것처럼 보이면 먼저 브라우저를 새로고침했는지 확인한다.
- `run --rm` 은 끝난 컨테이너를 지운다. 결과물(dist · m2)은 폴더와 볼륨에 있어 남는다.

## 5. 확인과 문제 해결

```bash
docker compose ps -a
```

```bash
docker compose logs common-build
```

```bash
docker compose logs frontend-build
```

| 증상 | 원인 | 해결 |
| --- | --- | --- |
| 빌드용 컨테이너가 `Exited (0)` | 정상. 할 일을 마쳤다 | — |
| 빌드용 컨테이너가 `Exited (1)` 이고 뒤 컨테이너가 뜨지 않는다 | 빌드 실패(문법 오류 · 형식 오류, 처음 실행 때 인터넷 끊김) | 위 `logs` 로 오류를 보고 고친 뒤 `docker compose up -d` |
| 화면이 비어 있거나 403 · 404 | `dist/` 가 없다(frontend-build 가 한 번도 성공하지 못함) | `docker compose run --rm frontend-build` |
| Spring 서비스가 `tp3:common` 을 찾지 못한다 | `m2` 볼륨에 설치되지 않았다(볼륨을 지웠거나 common-build 실패) | `docker compose run --rm common-build` 뒤 서비스 재시작 |
| 패키지를 바꿨는데(`package.json`) 반영되지 않는다 | `frontend_modules` 볼륨에 옛 패키지가 남아 있다 | `docker compose run --rm frontend-build` 가 `npm install` 부터 다시 한다. 그래도 이상하면 볼륨을 지우고 다시 빌드 |
| 처음 실행이 오래 걸린다 | 의존 라이브러리 · npm 패키지를 내려받는 중 | 기다린다. 두 번째부터는 볼륨에 있는 것을 쓴다 |

볼륨을 지우고 처음부터 다시 빌드하려면(내려받기를 다시 한다):

```bash
docker compose down
```

```bash
docker volume rm tp3_m2 tp3_frontend_modules
```

```bash
docker compose up -d --build
```

## 6. 헷갈리기 쉬운 것

- **빌드용 컨테이너 ≠ 이미지 빌드.** `docker compose up --build` 의 `--build` 는 Dockerfile 로 **이미지**를 만드는 일이다(Spring 서비스 · analysis-service · sim 의 실행 환경). 빌드용 컨테이너는 이미 있는 공개 이미지를 띄워 **우리 코드**를 빌드한다. 둘은 다른 단계다.
- **Spring 서비스는 빌드용 컨테이너가 따로 없다.** 서비스 컨테이너가 시작할 때 `mvn package` 를 하고 이어서 jar 를 실행한다. 그래서 재시작이 곧 다시 빌드다(시작이 느린 이유이기도 하다).
- **analysis-service(Python)와 sim(ROS)은 빌드할 것이 없다.** 코드를 그대로 읽어 실행하므로 재시작만 하면 된다.
- **실제 배포에서는 방식이 달라진다.** 지금은 개발 편의를 위해 실행할 때 빌드한다. 배포할 때는 CI 가 jar · dist 를 미리 만들어 이미지에 넣는 것이 보통이고, 그때는 이 두 컨테이너의 일이 CI 단계로 옮겨 간다.

관련 문서: 전체 구성은 [RUNNING.md](RUNNING.md), 단계별 실행은 [DOCKER_GUIDE.md](DOCKER_GUIDE.md), 구성도에서의 위치는 [system_architecture.svg](../architecture/system_architecture.svg), 새 빌드가 브라우저에 닿는 과정은 [spa_cycle.svg](../architecture/spa_cycle.svg) 를 본다.
