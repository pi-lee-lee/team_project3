"""빌드용 컨테이너 도면: common-build · frontend-build 가 어떻게 동작하고 왜 필요한가.

읽는 법
- 1절: compose.yaml 에 선언된 컨테이너 11개 전부(선언 순서 그대로). 빌드용 둘만 색을 넣고 나머지는 흐리게 했다 —
  빌드용 컨테이너는 계속 떠 있지 않고 빌드할 때만 쓰인다는 것을 보이기 위해서다.
- 2절: 빌드를 어디서 할지의 세 가지 방법과 지금 방식(빌드용 컨테이너)을 고른 이유.
- 3절: docker compose up 뒤의 시작 순서. 가로가 시간이다. 빌드용 컨테이너가 '성공해서 끝난 뒤에만' 뒤 컨테이너가 시작한다.
- 4절: 두 컨테이너가 각각 무엇을 읽어 무엇을 만들고, 그 결과를 누가 쓰는가(위에서 아래로).
- 5절: 코드를 고친 뒤 무엇을 다시 돌리는가. 6절: 이미지 빌드와의 차이.
글 설명은 docs/guide/BUILD_CONTAINERS.md, 값의 원본은 compose.yaml 이다. compose 를 바꾸면 이 스크립트도 고친 뒤 다시 생성한다.
실행: python3 docs/architecture/build_build_containers.py  →  docs/architecture/build_containers.svg
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / '_lib'))   # 공용 그리기 도구 docs/_lib/svg.py
from svg import C, Svg, text_width

OUT = Path(__file__).resolve().parent / 'build_containers.svg'
W = 1640
S = Svg(W, 1800)
GREEN, VIOLET, ORANGE, RED, GRAY = C['spring'][0], C['edge'][0], C['py'][0], '#d70015', '#636366'
BUILD = ('#b25000', '#fff4e5')          # 빌드용 컨테이너 색


def heading(y, n, title, sub=''):
    S.rect(40, y - 22, 30, 30, fill='#1c1c1e', stroke='#1c1c1e', rx=8)
    S.text(55, y - 1, str(n), 16, 700, '#ffffff', 'middle')
    S.text(82, y, title, 19, 700)
    if sub:
        S.text(82, y + 22, sub, 12.5, 400, GRAY)


def lines(x, y, rows, size=12.5, gap=20, color='#3a3a3c', mono=False):
    for i, r in enumerate(rows):
        S.text(x, y + i * gap, r, size, 400, color, mono=mono)


# ---------------------------------------------------------------- 1 전체 컨테이너 목록
# compose.yaml 의 services 선언 순서 그대로: (이름, 이미지, 하는 일, 빌드용인가)
ROSTER = [
    ('common-build', 'maven:3.9-eclipse-temurin-21', '공유 라이브러리 tp3:common 설치', True),
    ('db', 'postgres:17', '서비스별 DB', False),
    ('user-service', '직접 만든 이미지(Maven · JDK)', '로그인 · 사용자 · 역할', False),
    ('inspection-service', '직접 만든 이미지(Maven · JDK)', '점검 · 판정 · 사건 · 예약', False),
    ('robot-service', '직접 만든 이미지(Maven · JDK)', '로봇 연결 계층', False),
    ('gateway', '직접 만든 이미지(Maven · JDK)', '인증 · 경로별 권한', False),
    ('analysis-service', '직접 만든 이미지(Python)', '사진 분석 · 판독', False),
    ('frontend-build', 'node:20-alpine', 'React 화면을 dist/ 로 빌드', True),
    ('web', 'nginx:1.27-alpine', '원본 서버(화면 · 프록시)', False),
    ('cdn', 'nginx:1.27-alpine', '엣지 캐시 · 외부 :8080', False),
    ('sim', '직접 만든 이미지(ROS 2)', '시뮬레이션 · Nav2 · 브리지', False),
]


def roster(y):
    n_build = sum(1 for r in ROSTER if r[3])
    heading(y, 1, f'compose 에 선언된 컨테이너 {len(ROSTER)}개 — 그중 빌드용은 {n_build}개뿐이다',
            'compose.yaml 의 선언 순서 그대로 늘어놓았다. 색이 있는 상자 = 빌드용(빌드할 때만 쓰이고 끝난다) · 흐린 상자 = 실행 컨테이너(계속 떠 있다)')
    y += 44
    cols, gap = 6, 14
    cw, ch = (W - 80 - (cols - 1) * gap) / cols, 124
    for i, (name, image, role, is_build) in enumerate(ROSTER):
        x, by = 40 + (i % cols) * (cw + gap), y + (i // cols) * (ch + gap)
        if is_build:
            S.rect(x, by, cw, ch, fill=BUILD[1], stroke=BUILD[0], sw=3.2, rx=12)
            c1, c2, c3 = BUILD[0], '#1c1c1e', '#3a3a3c'
        else:
            S.rect(x, by, cw, ch, fill='#f7f7fa', stroke='#d1d1d6', sw=1, rx=12, dash='4 4')
            c1, c2, c3 = '#aeaeb2', '#aeaeb2', '#c7c7cc'
        S.text(x + 14, by + 20, f'{i + 1:02d}', 10.5, 700, c3, mono=True)
        S.text(x + 14, by + 43, name, 14.5, 700, c1, mono=True)
        S.text(x + 14, by + 63, role, 11.5, 600 if is_build else 400, c2)
        S.text(x + 14, by + 81, image, 10.5, 400, c3)
        if is_build:
            S.rect(x + 14, by + 92, 96, 22, fill='#1c1c1e', stroke='#1c1c1e', rx=11)
            S.text(x + 62, by + 107, 'Exited (0)', 11, 700, '#ffffff', 'middle', mono=True)
            S.text(x + 118, by + 107, '빌드하고 끝남', 11.5, 700, BUILD[0])
            S.rect(x + cw - 62, by + 9, 50, 19, fill=BUILD[0], stroke=BUILD[0], rx=9)
            S.text(x + cw - 37, by + 22.5, '빌드용', 10.5, 700, '#ffffff', 'middle')
        else:
            S.rect(x + 14, by + 92, 42, 22, fill='#ffffff', stroke='#d1d1d6', rx=11)
            S.text(x + 35, by + 107, 'Up', 11, 700, '#aeaeb2', 'middle', mono=True)
            S.text(x + 64, by + 107, '계속 실행', 11.5, 400, '#aeaeb2')
    # 마지막 칸: 셈
    i = len(ROSTER)
    x, by = 40 + (i % cols) * (cw + gap), y + (i // cols) * (ch + gap)
    S.rect(x, by, cw, ch, fill='#1c1c1e', stroke='#1c1c1e', rx=12)
    S.text(x + 14, by + 28, f'선언 {len(ROSTER)}개', 15, 700, '#ffffff')
    S.text(x + 14, by + 54, f'= 계속 실행 {len(ROSTER) - n_build}개', 13, 500, '#d1d1d6')
    S.text(x + 14, by + 76, f'+ 빌드하고 끝남 {n_build}개', 13, 700, '#ffb340')
    S.text(x + 14, by + 104, 'docker compose ps -a 로 확인', 10.5, 400, '#aeaeb2')
    y += 2 * ch + gap + 14
    S.rect(40, y, W - 80, 62, fill=BUILD[1], stroke=BUILD[0], sw=1.4, rx=10)
    S.text(56, y + 25, '빌드용 컨테이너는 서비스가 아니다.', 13.5, 700, BUILD[0])
    S.text(56 + text_width('빌드용 컨테이너는 서비스가 아니다.', False, 13.5) + 10, y + 25,
           '요청을 받지 않고, 포트를 열지 않고, 서비스용 네트워크(front · edge · backend · robot)에도 붙지 않고, restart: "no" 라 다시 뜨지 않는다. 마치면 끝난다.', 12.5, 500, '#3a3a3c')
    S.text(56, y + 47, 'compose 에 함께 선언해 둔 이유는 하나다: 실행 컨테이너가 "빌드가 성공해서 끝난 뒤에만" 시작하도록 순서를 걸기 위해서다(3절). '
                       '다시 쓰이는 때는 코드를 고쳐 다시 빌드할 때뿐이다(5절).', 12.5, 500, '#3a3a3c')
    return y + 62


# ---------------------------------------------------------------- 2 왜 필요한가
def why(y):
    heading(y, 2, '왜 필요한가', '이 저장소는 코드를 이미지에 굽지 않는다(폴더를 볼륨으로 연결해 실행). 그래서 실행 전에 누군가 코드를 빌드해 두어야 한다.')
    y += 44
    cw = (W - 80 - 40) / 3
    cards = [
        ('방법 A · 호스트에서 빌드', '쓰지 않음', RED, '#fff5f5', [
            '각자 PC 에 Maven · JDK 21 · Node 20 을 설치한다.',
            '✗ 사람마다 버전이 달라 결과가 달라진다',
            '✗ 새로 온 사람은 설치부터 해야 한다',
            '✗ Windows · macOS · Linux 마다 명령이 다르다']),
        ('방법 B · 이미지에 코드를 굽기', '개발 중에는 쓰지 않음', RED, '#fff5f5', [
            'Dockerfile 안에서 빌드해 jar · dist 를 이미지에 넣는다.',
            '✗ 한 줄 고칠 때마다 이미지를 다시 만든다(느리다)',
            '✗ 화면만 고쳐도 web 이미지를 새로 만들어야 한다',
            '○ 실제 배포에는 이 방식이 맞다(CI 가 한다)']),
        ('방법 C · 빌드용 컨테이너', '지금 방식', GREEN, '#f1faf4', [
            '빌드 도구가 든 공개 이미지를 띄워 코드를 빌드하고 끝낸다.',
            '✓ Docker 만 있으면 된다. 모두 같은 버전으로 빌드',
            '✓ 실행 컨테이너가 가볍다(web 은 nginx 뿐)',
            '✓ 한 번 빌드해 여럿이 쓴다 · 순서는 compose 가 지킨다']),
    ]
    for i, (title, badge, col, fill, rows) in enumerate(cards):
        x = 40 + i * (cw + 20)
        S.rect(x, y, cw, 158, fill=fill, stroke=col, sw=2.4 if i == 2 else 1.2, rx=12)
        S.text(x + 16, y + 28, title, 15, 700, col)
        bw = text_width(badge, False, 11) + 16
        S.rect(x + cw - bw - 12, y + 12, bw, 20, fill=col, stroke=col, rx=10)
        S.text(x + cw - bw / 2 - 12, y + 26, badge, 11, 700, '#ffffff', 'middle')
        S.text(x + 16, y + 54, rows[0], 12.5, 600, '#1c1c1e')
        lines(x + 16, y + 82, rows[1:], gap=24)
    return y + 158


# ---------------------------------------------------------------- 3 시작 순서
def order(y):
    heading(y, 3, '어떻게 동작하나 — 시작 순서', 'docker compose up -d 뒤. 가로가 시간이다(길이는 실제 시간이 아니라 순서를 보인다).')
    y += 40
    X0, X1 = 250, W - 60
    S.rect(40, y, W - 80, 356, fill='#ffffff', stroke='#d1d1d6', rx=12)
    t = lambda f: X0 + (X1 - X0) * f
    LH, top = 46, y + 44
    S.text(X0, y + 26, '▶ docker compose up', 12, 700, '#1c1c1e')
    S.raw(f'<path d="M{X0} {y + 34} V{top + 6 * LH + 2}" stroke="#1c1c1e" stroke-width="1.2" stroke-dasharray="3 3"/>')

    def lane(i, name, sub, kind):
        ly = top + i * LH
        col = BUILD[0] if kind == 'build' else C[kind][0]
        S.text(56, ly + 20, name, 13.5, 700, col, mono=True)
        S.text(56, ly + 36, sub, 10.5, 400, '#8e8e93')
        if i:
            S.raw(f'<path d="M48 {ly} H{W - 48}" stroke="#f2f2f7" stroke-width="1"/>')
        return ly + 8

    def bar(ly, a, b, label, col, fill, dash=None, tcol=None):
        S.rect(t(a), ly, t(b) - t(a), 28, fill=fill, stroke=col, sw=1.4, rx=7, dash=dash)
        S.text(t(a) + 10, ly + 18.5, label, 11.5, 600, tcol or col)

    def done(ly, a):
        S.rect(t(a) + 6, ly + 3, 86, 22, fill='#1c1c1e', stroke='#1c1c1e', rx=11)
        S.text(t(a) + 49, ly + 18, 'Exited (0)', 11, 700, '#ffffff', 'middle', mono=True)

    TB, TD, TS, TF, TW, TC = 0.30, 0.16, 0.56, 0.40, 0.66, 0.72
    l0 = lane(0, 'common-build', '빌드용 · 끝나면 종료', 'build')
    bar(l0, 0, TB, 'mvn install — tp3:common 을 m2 볼륨에 설치', BUILD[0], BUILD[1])
    done(l0, TB)
    l1 = lane(1, 'db', 'PostgreSQL', 'data')
    bar(l1, 0, TD, '시작 → healthy', C['data'][0], C['data'][1])
    bar(l1, TD, 1, '실행 중', C['data'][0], '#ffffff')
    l2 = lane(2, 'Spring 서비스 4개', 'gateway · user · inspection · robot', 'spring')
    bar(l2, 0, TB, '기다림 (common-build 성공 + db healthy)', '#aeaeb2', '#fafafc', '5 4', '#8e8e93')
    bar(l2, TB, TS, 'mvn package — 자기 코드 빌드(m2 에서 tp3:common 사용)', GREEN, C['spring'][1])
    bar(l2, TS, 1, 'java -jar · 실행 중', GREEN, '#ffffff')
    l3 = lane(3, 'frontend-build', '빌드용 · 끝나면 종료', 'build')
    bar(l3, 0, TF, 'npm install → npm run build — dist/ 를 만든다', BUILD[0], BUILD[1])
    done(l3, TF)
    l4 = lane(4, 'web', 'nginx 원본 서버', 'edge')
    bar(l4, 0, TW, '기다림 (frontend-build 성공 + gateway 시작)', '#aeaeb2', '#fafafc', '5 4', '#8e8e93')
    bar(l4, TW, 1, '실행 중 — dist/ 를 그대로 내준다', VIOLET, '#ffffff')
    l5 = lane(5, 'cdn', 'nginx 엣지 캐시 · 외부 :8080', 'edge')
    bar(l5, 0, TC, '기다림 (web 시작)', '#aeaeb2', '#fafafc', '5 4', '#8e8e93')
    bar(l5, TC, 1, '실행 중 — 접속 가능', VIOLET, '#ffffff')
    # 의존 화살표
    S.line([(t(TB), l0 + 28), (t(TB), l2)], color=BUILD[0], sw=2)
    S.line([(t(TD), l1 + 28), (t(TD), l2)], color=C['data'][0], sw=1.6)
    S.line([(t(TF), l3 + 28), (t(TF), l4)], color=BUILD[0], sw=2)
    S.line([(t(TS) + 40, l2 + 28), (t(TS) + 40, l3 - 14), (t(TW) - 14, l3 - 14), (t(TW) - 14, l4)], color=GREEN, sw=1.4)
    S.line([(t(TC) - 8, l4 + 28), (t(TC) - 8, l5)], color=VIOLET, sw=1.4)
    fy = top + 6 * LH + 22
    S.text(56, fy, 'depends_on: { condition: service_completed_successfully } — 빌드용 컨테이너가 성공해서 끝난 뒤에만 뒤 컨테이너가 시작한다. '
                   '빌드가 실패(Exited 1)하면 뒤 컨테이너는 뜨지 않는다.', 12, 600, '#3a3a3c')
    return y + 356


# ---------------------------------------------------------------- 4 두 컨테이너의 안
def flow(x, y, w, title, sub, steps):
    """위에서 아래로 흐르는 상자 네 개. steps: (종류, 이름, 꼬리표, 줄들, 화살표 이름표)"""
    S.rect(x, y, w, 520, fill='#ffffff', stroke='#d1d1d6', rx=12)
    S.text(x + 18, y + 30, title, 16, 700, BUILD[0], mono=True)
    S.text(x + 26 + text_width(title, True, 16), y + 30, sub, 12.5, 500, GRAY)
    by = y + 48
    for i, (kind, name, badge, rows, arrow) in enumerate(steps):
        if kind == 'build':
            col, fill, sw, dash = BUILD[0], BUILD[1], 2.6, None
        elif kind == 'store':
            col, fill, sw, dash = '#3a3a3c', '#f2f2f7', 1.4, '6 4'
        else:
            col, fill, sw, dash = C[kind][0], C[kind][1], 1.6, None
        S.rect(x + 18, by, w - 36, 88, fill=fill, stroke=col, sw=sw, rx=10, dash=dash)
        S.text(x + 32, by + 25, name, 14, 700, col)
        bw = text_width(badge, False, 10.5) + 14
        S.rect(x + w - 30 - bw, by + 10, bw, 19, fill=col, stroke=col, rx=9)
        S.text(x + w - 30 - bw / 2, by + 23.5, badge, 10.5, 700, '#ffffff', 'middle')
        lines(x + 32, by + 47, rows, size=12, gap=19)
        if arrow:
            S.line([(x + w / 2, by + 88), (x + w / 2, by + 118)], color='#636366', sw=1.8)
            S.text(x + w / 2 + 12, by + 108, arrow, 11.5, 600, GRAY, late=True)
        by += 118


def inside(y):
    heading(y, 4, '두 컨테이너의 안 — 무엇을 읽어 무엇을 만들고, 누가 쓰는가',
            '굵은 주황 상자 = 빌드용 컨테이너(끝나면 사라진다) · 점선 상자 = 결과가 남는 곳(볼륨 · 폴더) · 결과물은 컨테이너가 끝나도 남는다')
    y += 40
    pw = (W - 80 - 24) / 2
    flow(40, y, pw, 'common-build', '공유 라이브러리를 한 번 설치한다', [
        ('dev', '호스트 폴더  web/spring/common', '입력 · 코드',
         ['pom.xml · src/ — 서비스들이 함께 지키는 약속', 'JwtCodec(토큰 발급 · 검증) · AuthHeaders(X-User-*) · CurrentUser'],
         '/workspace 로 연결'),
        ('build', 'common-build 컨테이너', 'maven:3.9-eclipse-temurin-21',
         ['mvn -q -B install -DskipTests', '빌드해서 로컬 Maven 저장소에 설치하고 종료(restart: "no")'],
         '/root/.m2 에 쓴다'),
        ('store', '볼륨  m2', '결과 · 남는다',
         ['tp3:common:0.1.0.jar', '+ 내려받은 의존 라이브러리(두 번째부터는 다시 받지 않는다)'],
         '네 서비스가 같은 볼륨을 연결'),
        ('spring', 'gateway · user-service · inspection-service · robot-service', '쓰는 쪽 · 실행 컨테이너',
         ['시작할 때 mvn package 로 자기 코드를 빌드한다', '이때 tp3:common 을 인터넷이 아니라 m2 볼륨에서 찾는다'],
         None),
    ])
    flow(40 + pw + 24, y, pw, 'frontend-build', 'React 화면을 브라우저가 읽는 파일로 바꾼다', [
        ('dev', '호스트 폴더  web/nginx/frontend', '입력 · 코드',
         ['src/*.tsx · package.json — TypeScript · JSX', '브라우저가 그대로는 읽지 못하는 코드다'],
         '/app 으로 연결'),
        ('build', 'frontend-build 컨테이너', 'node:20-alpine',
         ['npm install → npm run build (Vite)', 'node_modules 는 볼륨 frontend_modules 에 둔다(호스트와 안 섞임)'],
         'dist/ 에 쓴다'),
        ('store', '호스트 폴더  web/nginx/frontend/dist/', '결과 · 남는다',
         ['index.html + assets/*.js · *.css', '파일 이름에 해시가 붙어 새 빌드는 이름이 달라진다'],
         '읽기 전용으로 연결'),
        ('edge', 'web (nginx)  →  cdn  →  브라우저', '쓰는 쪽 · 실행 컨테이너',
         ['web 은 dist/ 를 그대로 내준다(web 안에는 Node 도 React 도 없다)', 'cdn 은 assets/ 만 보관한다. 다시 빌드해도 web · cdn 재시작이 필요 없다'],
         None),
    ])
    return y + 520


# ---------------------------------------------------------------- 5 고친 뒤
def after(y):
    heading(y, 5, '코드를 고친 뒤 — 무엇을 다시 돌리는가')
    y += 22
    cols = [(40, 300, '고친 곳'), (340, 860, '할 일'), (1200, 400, '빌드용 컨테이너')]
    S.rect(40, y, W - 80, 34, fill='#1c1c1e', stroke='#1c1c1e', rx=10)
    for x, _, name in cols:
        S.text(x + 16, y + 22, name, 12.5, 700, '#ffffff')
    y += 40
    rows = [
        ('화면  web/nginx/frontend', 'docker compose run --rm frontend-build   → 브라우저 새로고침', 'frontend-build 를 다시', True),
        ('공유 라이브러리  web/spring/common', 'docker compose run --rm common-build   → Spring 서비스 4개 restart', 'common-build 를 다시', True),
        ('Spring 서비스 하나', 'docker compose up -d --force-recreate <서비스>', '필요 없음 — 서비스가 시작하며 스스로 빌드', False),
        ('분석 서비스(Python) · ROS 코드', 'docker compose restart analysis-service  /  sim', '필요 없음 — 빌드 단계가 없다', False),
        ('nginx 설정', 'docker compose exec web nginx -s reload   (cdn 도 같음)', '필요 없음', False),
    ]
    for a, b, c, need in rows:
        S.rect(40, y, W - 80, 38, fill=BUILD[1] if need else '#ffffff', stroke=BUILD[0] if need else '#e5e5ea',
               sw=1.4 if need else 1, rx=9)
        S.text(56, y + 24, a, 13, 700, '#1c1c1e')
        S.text(356, y + 24, b, 12, 500, '#3a3a3c', mono=True)
        S.text(1216, y + 24, c, 12.5, 700 if need else 400, BUILD[0] if need else '#8e8e93')
        y += 44
    return y


# ---------------------------------------------------------------- 6 헷갈리기 쉬운 것
def confuse(y):
    heading(y, 6, '헷갈리기 쉬운 것 — 이미지 빌드와는 다른 단계다')
    y += 22
    cw = (W - 80 - 24) / 2
    S.rect(40, y, cw, 132, fill='#ffffff', stroke='#8e8e93', sw=1.4, rx=12)
    S.text(58, y + 28, '이미지 빌드  (docker compose up --build)', 14.5, 700, '#3a3a3c')
    lines(58, y + 54, ['Dockerfile 로 실행 환경을 만든다: Spring 서비스 · analysis-service · sim.',
                       '안에 든 것 = JDK · Maven · Python · ROS 같은 도구. 우리 코드는 들어 있지 않다.',
                       '도구나 Dockerfile 을 바꿨을 때만 다시 한다.'], gap=23)
    x = 40 + cw + 24
    S.rect(x, y, cw, 132, fill=BUILD[1], stroke=BUILD[0], sw=2.4, rx=12)
    S.text(x + 18, y + 28, '빌드용 컨테이너  (common-build · frontend-build)', 14.5, 700, BUILD[0])
    lines(x + 18, y + 54, ['공개 이미지를 그대로 띄워 우리 코드를 빌드한다(Dockerfile 없음).',
                           '결과물 = jar · dist. 볼륨과 폴더에 남고, 컨테이너는 Exited (0) 으로 끝난다.',
                           '공유 라이브러리나 화면 코드를 고칠 때마다 다시 한다.'], gap=23)
    y += 148
    S.text(40, y + 6, '실제 배포에서는 CI 가 jar · dist 를 미리 만들어 이미지에 넣는다(방법 B). 그때는 이 두 컨테이너의 일이 CI 단계로 옮겨 간다. '
                      '글 설명과 문제 해결은 docs/guide/BUILD_CONTAINERS.md', 12.5, 500, GRAY)
    return y + 24


def build():
    S.text(40, 48, '빌드용 컨테이너 — 어떻게 동작하고 왜 필요한가', 24, 700)
    S.text(40, 74, 'common-build · frontend-build 는 코드를 빌드하고 바로 끝나는 컨테이너다. docker compose ps -a 에서 Exited (0) 으로 보이는 것이 정상이다 '
                   '(실행 컨테이너 9 · 빌드용 2).', 13, 400, GRAY)
    y = roster(128)
    y = why(y + 62)
    y = order(y + 62)
    y = inside(y + 62)
    y = after(y + 62)
    y = confuse(y + 50)
    S.h = int(y + 20)
    S.render(OUT)


if __name__ == '__main__':
    build()
