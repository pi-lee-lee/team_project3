"""React SPA 사이클 도면: cdn 에서 받은 파일로 브라우저가 화면을 조립하고, 데이터만 서버와 주고받는 과정(스윔레인).

시스템 사이클(build_cycle.py)의 'A 화면 불러오기'와 'B 인증'을 브라우저 안쪽에서 본 그림이다.
값(파일·주기·경로)은 코드에서 확인한 것이다:
  web/nginx/frontend/src — main.tsx(createRoot · BrowserRouter) · App.tsx(api.me · Routes · Shell) ·
  util.tsx(usePoll · useAction · AuthContext) · api/http.ts(fetch · auth:expired) · pages/*(화면별 폴링 주기) ·
  pages/user/Monitor.tsx(상태 1초 · mapview 0.2초 · 지도 정보 10초 · 조종 100ms)
  web/nginx/web/default.conf(try_files · Cache-Control) · cdn/default.conf(보관·통과 경로)
파일 크기는 dist/assets 의 현재 빌드 기준(해시와 크기는 빌드마다 달라진다).
실행: python3 docs/architecture/build_spa_cycle.py  →  docs/architecture/spa_cycle.svg
"""
from pathlib import Path

from svg import C, Svg, text_width

OUT = Path(__file__).resolve().parent / 'spa_cycle.svg'

LANES = [  # 키, 이름, 설명, 색
    ('u', '사용자', '주소 입력 · 클릭 · 키 입력', 'dev'),
    ('d', '브라우저', '문서 · DOM · 주소창 · HTTP 캐시', 'client'),
    ('r', 'React 앱', 'main.tsx · App · Router · Shell', 'bridge'),
    ('p', '화면 컴포넌트', 'pages/* · state · usePoll', 'bridge'),
    ('c', 'cdn · web', '화면 파일 (정적)', 'edge'),
    ('g', 'gateway → 서비스', '데이터 /api · /ws (JSON)', 'spring'),
]
X0, DX = 330, 262
LX = {k: X0 + i * DX for i, (k, *_) in enumerate(LANES)}
ROW = 38
W = LX['g'] + 230

SECTIONS = [
    ('A', '첫 접속 — 빈 껍데기와 묶음 파일 받기', '어떤 주소로 들어와도 같은 index.html 을 받는다. 이 단계가 끝나도 화면에는 아직 아무것도 없다', 'edge', [
        ('u', 'd', '주소 입력 http://localhost:8080/app/tasks'),
        ('d', 'c', 'GET /app/tasks — 그런 파일은 없다 → web 의 try_files 가 index.html 을 대신 응답(no-cache, cdn 은 보관 안 함)'),
        ('c', 'd', 'index.html: <div id="root"></div> 와 <script src="/assets/index-<해시>.js"> · <link css> 뿐 — 화면 내용 없음'),
        ('d', 'c', 'GET /assets/index-<해시>.js · .css — cdn 보관본(HIT · gzip). 전에 받았으면 브라우저 캐시에서 꺼내고 요청하지 않는다'),
        ('d', 'd', 'CSS 적용 → JS 모듈 실행 시작. React · Router · 모든 화면 코드가 이 한 파일에 들어 있다'),
        ('d', 'c', 'GET /assets/material-symbols-rounded-<해시>.woff2 — 아이콘 글꼴. CSS 가 처음 쓸 때 받는다'),
    ]),
    ('B', '화면 조립 — 브라우저 안에서 React 가 그린다', '서버는 화면을 만들지 않는다. 받은 JS 가 주소를 읽고, 로그인 상태를 묻고, 맞는 화면을 #root 안에 만든다', 'bridge', [
        ('d', 'r', 'main.tsx: createRoot(#root).render(<BrowserRouter><App/></BrowserRouter>)'),
        ('r', 'r', 'App 첫 렌더: checked=false → "불러오는 중…" 만 표시'),
        ('r', 'g', 'useEffect: api.me() → fetch GET /api/auth/me — HttpOnly 쿠키는 브라우저가 자동으로 붙인다(JS 는 읽지 못한다)'),
        ('g', 'r', '200 Me{이름 · 역할} → setMe / 401 → me=null. setChecked(true) → App 다시 렌더'),
        ('r', 'r', 'Routes 가 주소창 경로와 맞는 Route 를 고른다 → Shell: me 없으면 /login, 역할이 다르면 자기 홈으로 Navigate'),
        ('r', 'p', 'Shell(사이드바 · 탭 바)의 <Outlet/> 자리에 화면 컴포넌트(Tasks)를 마운트'),
        ('p', 'd', 'React 가 컴포넌트 결과(가상 DOM)를 실제 DOM 으로 반영 → 이때 처음 화면이 보인다(표는 아직 비어 있음)'),
    ]),
    ('C', '데이터 채우기 — 화면은 틀, 내용은 JSON', '화면마다 자기 데이터를 직접 요청한다. /api 는 cdn · web 이 보관 없이 gateway 로 넘긴다', 'spring', [
        ('p', 'g', 'usePoll(() => api.tasks(group), 2000): 마운트 직후 1회 + 2초마다 fetch GET /api/inspections'),
        ('g', 'p', 'JSON 배열 → setData → 그 컴포넌트만 다시 렌더'),
        ('p', 'd', 'React 가 이전 결과와 비교해 바뀐 DOM(표의 행)만 고친다 — 문서를 다시 받지 않는다'),
        ('p', 'p', '실패하면 error 상태 → ErrorBox 표시. 다음 주기에 다시 시도'),
        ('g', 'r', '401 이면 http.ts 가 window 이벤트 auth:expired → App 이 me=null · navigate("/login")'),
    ]),
    ('D', '화면 이동 — 서버에 가지 않는다', '일반 웹과 가장 다른 부분. 주소는 바뀌지만 문서 요청이 없고, 이미 받은 JS 가 화면을 바꾼다', 'client', [
        ('u', 'p', '메뉴(NavLink) 클릭 · 표의 행 클릭 → navigate("/app/tasks/12")'),
        ('r', 'd', 'history.pushState 로 주소창만 바꾼다 — cdn · web 으로 가는 요청 없음'),
        ('r', 'p', 'Routes 다시 매칭 → 이전 화면 언마운트(폴링 타이머 clearInterval · WebSocket close) → 새 화면(TaskDetail) 마운트'),
        ('p', 'g', '새 화면이 자기 데이터 요청 GET /api/inspections/12 (2초마다) → C 사이클'),
        ('u', 'd', '뒤로 가기: popstate → Router 가 다시 매칭 — 역시 서버 요청 없음'),
        ('u', 'c', '새로고침 · 주소 직접 입력: A1 부터 다시. 메모리의 상태(me · 목록)는 사라지고 쿠키로 B3 에서 로그인 상태를 되찾는다'),
    ]),
    ('E', '입력 → 변경 요청', '입력값은 컴포넌트 state 로 브라우저 메모리에만 있다가, 제출할 때 JSON 으로 나간다', 'py', [
        ('u', 'p', '로그인 폼 입력: onChange → setState → 다시 렌더(글자마다)'),
        ('p', 'g', 'submit → useAction.run: api.login POST /api/auth/login {loginId, password} — 요청 중에는 버튼 비활성(busy)'),
        ('g', 'r', '200 + Set-Cookie(HttpOnly) · 본문 Me → setMe(AuthContext) → navigate(홈) → D2 처럼 화면만 바뀐다'),
        ('p', 'g', '그 밖의 변경(점검 실행 · 판정 · 취소): POST → 성공하면 reload() 나 navigate, 실패하면 ErrorBox'),
    ]),
    ('F', '실시간 화면(관제) — React 렌더를 거치지 않는 통로', '영상 · 조종 · 지도는 state 로 다시 그리기에는 너무 빠르다. 브라우저 기능을 직접 쓴다', 'ros', [
        ('p', 'g', '폴링: 로봇 상태 1초 · 지도 위치(mapview) 0.2초 · 지도 정보 10초 — 화면을 떠나면 모두 멈춘다'),
        ('g', 'd', '영상: <img src="/api/robots/{id}/stream"> — MJPEG 를 브라우저가 직접 받아 그린다(JS · state 를 거치지 않음)'),
        ('p', 'g', '조종: new WebSocket("/ws/robots/{id}/teleop") — 제어권이 있는 동안 열어 두고, 누르는 동안 100ms 마다 속도 전송'),
        ('p', 'd', '지도: <canvas> 에 직접 그린다 — map.png?v=버전 + requestAnimationFrame 으로 0.2초 사이의 로봇 위치를 보간'),
    ]),
    ('G', '새 빌드 반영', 'docker compose run --rm frontend-build 뒤. cdn 을 비울 필요가 없다', 'data', [
        ('c', 'c', '빌드하면 JS · CSS 파일 이름의 해시가 바뀌고, index.html 이 새 이름을 가리킨다'),
        ('d', 'd', '이미 열려 있는 탭은 메모리의 옛 JS 로 계속 동작한다(화면 이동을 해도 문서를 받지 않으므로)'),
        ('u', 'c', '새로고침하면 index.html(no-cache)을 다시 받아 새 파일 이름을 알게 되고, 새 JS 를 받는다 → A1'),
    ]),
]

FILES = [  # 이름, 내용, 보관
    ('index.html', '빈 껍데기: <div id="root"> 와 아래 JS · CSS 의 주소', 'no-cache (매번 확인)'),
    ('assets/index-<해시>.js', 'React + React Router + 모든 화면 코드 한 묶음 · 약 218KB', '1년 · immutable'),
    ('assets/index-<해시>.css', '스타일 · 약 14KB', '1년 · immutable'),
    ('assets/material-symbols-rounded-<해시>.woff2', '아이콘 글꼴 · 약 4.6MB', '1년 · immutable'),
]
DIFF = [
    ('일반 웹', '주소마다 서버가 완성된 HTML 을 만들어 보낸다. 화면을 옮길 때마다 문서를 새로 받는다.'),
    ('이 화면(SPA)', '서버(cdn)는 어떤 주소에도 같은 빈 HTML 과 JS 묶음을 준다. 화면은 브라우저에서 JS 가 만든다.'),
    ('그 뒤의 통신', '서버와 주고받는 것은 데이터(JSON)뿐이다. 화면 이동은 주소창만 바뀌고 문서 요청이 없다.'),
    ('권한', 'JS 는 누구나 받을 수 있다. 화면에서 메뉴를 막는 것은 편의이고, 실제 확인은 gateway 가 요청마다 한다.'),
]

PANEL_Y, PANEL_H = 92, 156
HEAD_Y = PANEL_Y + PANEL_H + 46
TOP = HEAD_Y + 74
H = TOP + sum(58 + len(st) * ROW + 14 for *_, st in SECTIONS) + 40
S = Svg(W, H)


def halo(x, y, s, size=12, weight=500, color='#1c1c1e', anchor='start'):
    from xml.sax.saxutils import escape
    S.raw(f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" font-weight="{weight}" fill="{color}" '
          f'text-anchor="{anchor}" paint-order="stroke" stroke="#ffffff" stroke-width="5" '
          f'stroke-linejoin="round">{escape(s)}</text>', late=True)


def panels():
    """머리 설명 두 칸: cdn 이 내주는 파일 / 일반 웹과 다른 점."""
    lw = 840
    S.rect(16, PANEL_Y, lw, PANEL_H, fill='#ffffff', stroke=C['edge'][0], sw=1.4, rx=14)
    S.text(34, PANEL_Y + 26, 'cdn 이 내주는 것 — frontend-build 가 미리 만들어 둔 dist/ 파일 4개가 전부다', 14, 700, C['edge'][0])
    for i, (name, what, keep) in enumerate(FILES):
        y = PANEL_Y + 54 + i * 26
        S.text(34, y, name, 12, 600, '#1c1c1e', mono=True)
        S.text(34 + 360, y, what, 12, 400, '#3a3a3c')
        S.text(16 + lw - 18, y, keep, 11.5, 600, C['edge'][0], 'end')
    rx = 16 + lw + 14
    S.rect(rx, PANEL_Y, W - 16 - rx, PANEL_H, fill='#ffffff', stroke=C['client'][0], sw=1.4, rx=14)
    S.text(rx + 18, PANEL_Y + 26, '일반 웹과 다른 점', 14, 700, C['client'][0])
    for i, (k, v) in enumerate(DIFF):
        y = PANEL_Y + 54 + i * 26
        S.text(rx + 18, y, k, 12, 700, '#1c1c1e')
        S.text(rx + 18 + 96, y, v, 12, 400, '#3a3a3c')


def groups():
    """레인 묶음: 브라우저 안(사용자 PC) / 서버(Docker 호스트). 화면이 어디서 만들어지는지 보이게 한다."""
    for a, b, label, kind in [('d', 'p', '브라우저 안 (사용자 PC) — 화면은 여기서 만들어진다', 'client'),
                              ('c', 'g', '서버 (Docker 호스트) — 파일과 데이터만 준다', 'edge')]:
        x0, x1 = LX[a] - 118, LX[b] + 118
        col, fill = C[kind]
        S.rect(x0, HEAD_Y - 32, x1 - x0, H - HEAD_Y + 12, fill=fill, stroke=col, sw=1.2, rx=16, dash='6 5', opacity=0.5)
        S.text((x0 + x1) / 2, HEAD_Y - 12, label, 12.5, 700, col, 'middle')


def build():
    S.text(24, 44, '화재 점검 로봇 서비스 — React SPA 사이클 (화면이 만들어지는 과정)', 24, 700)
    S.text(24, 70, '세로 줄 = 일하는 주체, 화살표 = 호출 · 응답(번호 순서), 동그라미 = 그 안에서 하는 일. '
                   '예시 화면은 작업 목록(/app/tasks). 다른 화면도 같은 순서로 돈다.', 13, 400, '#636366')
    panels()
    groups()
    for k, name, sub, kind in LANES:
        x = LX[k]
        S.rect(x - 106, HEAD_Y, 212, 54, fill=C[kind][1], stroke=C[kind][0], sw=1.6, rx=12)
        S.text(x, HEAD_Y + 23, name, 14, 700, C[kind][0], 'middle')
        S.text(x, HEAD_Y + 42, sub, 11.5, 400, '#636366', 'middle')
        S.raw(f'<line x1="{x}" y1="{HEAD_Y + 54}" x2="{x}" y2="{H - 30}" stroke="#c7c7cc" stroke-width="1.2" '
              f'stroke-dasharray="4 5"/>')

    y = TOP
    for sid, title, desc, kind, steps in SECTIONS:
        col = C[kind][0]
        hh = 58 + len(steps) * ROW
        S.rect(16, y, S.w - 32, hh, fill='#ffffff', stroke='#d1d1d6', sw=1, rx=14, opacity=0.6)
        S.rect(16, y, 8, hh, fill=col, stroke=col, rx=4)
        S.text(40, y + 28, f'{sid}  {title}', 16, 700, col)
        S.text(40, y + 47, desc, 12, 400, '#636366')
        sy = y + 58 + ROW / 2
        for n, (f, t, label) in enumerate(steps, 1):
            S.raw(f'<circle cx="54" cy="{sy}" r="13" fill="{col}"/>')
            S.text(54, sy + 4.5, f'{sid}{n}', 11, 700, '#ffffff', 'middle')
            if f == t:      # 그 주체 안에서 하는 일
                x = LX[f]
                S.raw(f'<circle cx="{x}" cy="{sy}" r="7" fill="#ffffff" stroke="{col}" stroke-width="2.4"/>', late=True)
                if x + 14 + text_width(label, False) > S.w - 20:      # 오른쪽 끝을 넘으면 원의 왼쪽에
                    halo(x - 14, sy + 4.5, label, 12, 500, '#1c1c1e', 'end')
                else:
                    halo(x + 14, sy + 4.5, label, 12, 500, '#1c1c1e')
            else:
                x1, x2 = LX[f], LX[t]
                d = 1 if x2 > x1 else -1
                S.raw(f'<circle cx="{x1}" cy="{sy}" r="4" fill="{col}"/>', late=True)
                S.line([(x1, sy), (x2 - d * 2, sy)], color=col, sw=2)
                lx = min(x1, x2) + 10
                if lx + text_width(label, False) > S.w - 20:          # 넘치면 화살표 오른쪽 끝에 맞춘다
                    halo(max(x1, x2) - 10, sy - 6, label, 12, 500, '#1c1c1e', 'end')
                else:
                    halo(lx, sy - 6, label, 12, 500, '#1c1c1e')
            sy += ROW
        y += hh + 14
    S.render(OUT)


if __name__ == '__main__':
    build()
