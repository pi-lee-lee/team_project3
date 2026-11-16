"""화면 트리(스크린 플로우맵) SVG 생성기.

모바일웹 스토리보드처럼 '화면 하나 = 노드 하나'로, 화면 썸네일을 트리로 연결한다.
선 위 라벨은 그 화면으로 들어가는 조작이다. 와이어프레임 데이터는 build_storyboard.py 의 SCREENS 를 쓴다.
실행: python3 build_screen_tree.py  →  docs/web_screen_tree.svg
"""
from pathlib import Path

import build_storyboard as sb

OUT = Path(__file__).resolve().parent.parent / 'web_screen_tree.svg'
BY_ID = {s['id']: s for s in sb.SCREENS}

# 스토리보드 본문에는 없고 트리에만 있는 하위 화면(모달·편집)
EXTRA = {
    'A1-1': dict(id='A1-1', name='사용자 추가 (모달)', path='/admin/users', nav=0, area='A',
                 wire=[('table', 10, 40, 520, ['아이디', '이름', '역할', '상태'],
                        [['admin', '관리자', 'ADMIN', '활성'], ['sup1', '김관리', '1 관리자', '활성']]),
                       ('modal', 130, 110, 280, 130, '사용자 추가', ['아이디', '이름', '비밀번호', '역할 ▾'])]),
    'A2-1': dict(id='A2-1', name='로봇 연결 설정', path='/admin/robots/:id', nav=1, area='A',
                 wire=[('label', 10, 54, '로봇 연결 설정 · tb3-sim'),
                       ('field', 10, 66, '이름', 'TurtleBot3 (시뮬레이션)'),
                       ('field', 10, 92, '어댑터', 'ROSBRIDGE ▾  (ROSBRIDGE / MOCK)'),
                       ('field', 10, 118, 'rosbridge 주소', 'ws://sim:9090'),
                       ('field', 10, 144, '영상 주소', 'http://sim:8080'),
                       ('field', 10, 170, '토픽 매핑', '{"odom":"/odom","scan":"/scan", …}'),
                       ('field', 10, 196, '사용', '사용함 ▾'),
                       ('btn', 330, 232, 96, 26, '취소', 'mute'), ('btn', 434, 232, 96, 26, '저장·재연결', 'blue')]),
    'A3-1': dict(id='A3-1', name='지점 수정', path='/admin/points/:id', nav=2, area='A',
                 wire=[('label', 10, 54, '지점 수정 · P1'),
                       ('field', 10, 66, '코드', 'P1 (변경 불가)'), ('field', 10, 92, '이름', '소화기 앞'),
                       ('field', 10, 118, 'x · y', '1.0 · 0.0'), ('field', 10, 144, '방향(도)', '0'),
                       ('field', 10, 170, '상태', '사용 ▾ (사용 / 비활성)'),
                       ('btn', 330, 208, 96, 26, '취소', 'mute'), ('btn', 434, 208, 96, 26, '저장', 'blue')]),
    'U4-1': dict(id='U4-1', name='관측 판정 입력', path='/app/tasks/:id', nav=2, area='U',
                 wire=[('label', 10, 54, 'P1 관측 판정'),
                       ('video', 10, 64, 250, 170, 'P1 · 10:23 촬영'),
                       ('label', 276, 80, '품질: 밝기 132 · 선명도 210'),
                       ('btn', 276, 92, 76, 26, '정상', 'green'), ('btn', 358, 92, 76, 26, '이상', 'red'),
                       ('btn', 440, 92, 90, 26, '확인 불가', 'orange'),
                       ('input', 276, 128, 254, 60, '확인 불가 사유 (필수)'),
                       ('btn', 276, 198, 254, 28, '판정 저장', 'blue'),
                       ('note', 276, 252, '판정은 덮어쓰지 않고 이력으로 쌓인다', 'mute', 'start')]),
}

CARD_W, CARD_H = 262, 214
SCALE = 0.43
COL = [30, 400, 770, 1140, 1510]
ROW_H = 240

# (화면 ID, 열, 행, 진입 조작 라벨, 노드 설명)
NODES = [
    ('L', 0, None, None, '접속하면 첫 화면'),
    ('A1', 1, None, '로그인 (ADMIN)', '관리자 기본 화면'),
    ('A1-1', 2, 0, '+ 사용자 추가', '목록 위에 뜨는 모달'),
    ('A2', 2, 1, '메뉴 › 로봇', ''),
    ('A2-1', 3, 1, '편집', '주소·토픽만 바꿔 실제 로봇으로 교체'),
    ('A3', 2, 2, '메뉴 › 점검 지점', ''),
    ('A3-1', 3, 2, '수정', ''),
    ('A4', 2, 3, '메뉴 › 분석 기준', ''),
    ('A5', 2, 4, '메뉴 › 감사 로그', ''),
    ('A6', 2, 5, '메뉴 › 시스템', ''),
    ('U1', 1, None, '로그인 (역할 1·2·3)', '사용자 기본 화면'),
    ('U2', 2, 6, '메뉴 › 점검 요청', ''),
    ('U3', 2, 7, '메뉴 › 작업 목록', ''),
    ('U4', 3, 7, '작업 행 선택', '진행 기록 · 관측 · 취소 · 재점검'),
    ('U4-1', 4, 7, '판정 버튼', ''),
    ('U5', 2, 8, '메뉴 › 지점 이력', ''),
]
# 다른 가지에서 이미 그린 화면으로 가는 이동 (점선 참조 노드)
REFS = [
    ('U2', 3, 6, '요청 제출', 'U4 작업 상세', '방금 만든 작업'),
    ('U5', 3, 8, '사진 선택', 'U4 작업 상세', '그 관측의 작업'),
    ('U4', 4, 8, '재점검 요청', 'U4 작업 상세', '새 작업 (같은 지점)'),
]
PARENT = {'L': None, 'A1': 'L', 'A1-1': 'A1', 'A2': 'A1', 'A2-1': 'A2', 'A3': 'A1', 'A3-1': 'A3', 'A4': 'A1',
          'A5': 'A1', 'A6': 'A1', 'U1': 'L', 'U2': 'U1', 'U3': 'U1', 'U4': 'U3', 'U4-1': 'U4', 'U5': 'U1'}

TOP = 150
USER_GAP = 50


def row_y(r):
    return TOP + r * ROW_H + (USER_GAP if r >= 6 else 0)


def screen(sid):
    return BY_ID.get(sid) or EXTRA[sid]


def thumb(s, x, y):
    """화면 썸네일: 브라우저 틀 + 상단 메뉴 + 와이어프레임을 축소해 그린다(번호 마커 제외)."""
    sb.out.append(f'<g transform="translate({x},{y}) scale({SCALE})">')
    bw, bh = 560, 366
    sb.rect(0, 0, bw, bh, '#fff', '#94a3b8', 6, 2)
    sb.rect(0, 0, bw, 20, '#f1f5f9', '#94a3b8', 6, 2)
    sb.t(50, 14, 'localhost:8080' + s['path'], 10, sb.C['sub'])
    for i, col in enumerate(['#f87171', '#fbbf24', '#4ade80']):
        sb.out.append(f'<circle cx="{10 + i * 12}" cy="10" r="4" fill="{col}"/>')
    ox, oy = 10, 28
    if s.get('nav') is not None:
        is_admin = s['id'].startswith('A')
        nav = sb.ADMIN_NAV if is_admin else sb.USER_NAV
        color = sb.C['admin'] if is_admin else sb.C['user']
        sb.rect(0, 20, bw, 26, color, color, 0)
        xx = 12
        for i, n in enumerate(nav):
            on = i == s['nav']
            sb.t(xx, 37, n, 11, '#fff', 'start', 'bold' if on else 'normal')
            xx += 16 + 11 * len(n)
        oy = 26
    for el in s['wire']:
        if el[0] != 'm':
            sb.wire(el, ox, oy)
    sb.out.append('</g>')


def card(sid, col, y, note):
    s = screen(sid)
    x = COL[col]
    area = 'A' if sid.startswith('A') else 'U' if sid.startswith('U') else 'L'
    color = {'A': sb.C['admin'], 'U': sb.C['user'], 'L': sb.C['login']}[area]
    sb.rect(x + 3, y + 3, CARD_W, CARD_H, '#e2e8f0', '#e2e8f0', 8)
    sb.rect(x, y, CARD_W, CARD_H, '#fff', color, 8, 1.6)
    sb.rect(x, y, CARD_W, 28, color, color, 8)
    sb.rect(x, y + 20, CARD_W, 8, color, color, 0)
    sb.t(x + 10, y + 19, f'{sid}  {s["name"]}', 12, '#fff', 'start', 'bold')
    thumb(s, x + 10, y + 34)
    sb.t(x + 10, y + 34 + 366 * SCALE + 16, note or s['path'], 10, sb.C['sub'])
    return x, y


def ref_card(col, y, label, note):
    x = COL[col]
    cy = y + CARD_H / 2
    sb.rect(x, cy - 34, CARD_W, 68, '#f8fafc', sb.C['user'], 8, 1.4, '6 4')
    sb.t(x + 14, cy - 8, '→ ' + label, 12, sb.C['user'], 'start', 'bold')
    sb.t(x + 14, cy + 14, note + ' (같은 화면으로 이동)', 10, sb.C['sub'])
    return x, cy


def edge(px, py, cx, cy, label):
    mid = px + (cx - px) * 0.35
    sb.path(f'M{px},{py} H{mid} V{cy} H{cx - 2}', sb.C['line'], 1.5, arrow=True)
    if label:
        sb.t(cx - 10, cy - 7, label, 10.5, sb.C['ink'], 'end', 'bold')


def build():
    sb.out.clear()
    W = COL[-1] + CARD_W + 40
    pos = {}
    # 행이 정해진 노드부터 배치하고, 부모는 자식들의 가운데에 둔다
    rows = {sid: r for sid, _, r, _, _ in NODES if r is not None}
    a_mid = (row_y(0) + row_y(5)) / 2
    u_mid = row_y(7)
    rows_y = {sid: row_y(r) for sid, r in rows.items()}
    rows_y['A1'] = a_mid
    rows_y['U1'] = u_mid
    rows_y['L'] = (a_mid + u_mid) / 2

    H = int(row_y(8) + CARD_H + 90)
    sb.t(30, 44, '웹 화면 트리', 24, sb.C['ink'], 'start', 'bold')
    sb.t(190, 44, '화면 하나 = 노드 하나 · 선 위 글자 = 그 화면으로 들어가는 조작 · 점선 상자 = 다른 가지에 있는 화면으로 이동',
         11.5, sb.C['sub'])
    for i, label in enumerate(['로그인', '역할별 기본 화면', '메뉴 화면', '하위 화면', '하위 화면 2']):
        sb.t(COL[i] + CARD_W / 2, 92, f'Depth {i} · {label}', 11, sb.C['mute'], 'middle', 'bold')
    # 영역 배경
    sb.rect(COL[1] - 16, row_y(0) - 26, W - COL[1], row_y(5) + CARD_H - row_y(0) + 40, sb.C['admin_bg'],
            '#ddd6fe', 12)
    sb.t(COL[1], row_y(0) - 8, '관리자 영역 (ADMIN)', 12, sb.C['admin'], 'start', 'bold')
    sb.rect(COL[1] - 16, row_y(6) - 26, W - COL[1], row_y(8) + CARD_H - row_y(6) + 40, sb.C['user_bg'],
            '#99f6e4', 12)
    sb.t(COL[1], row_y(6) - 8, '사용자 영역 (역할 1 관리자 · 2 매니저 · 3 사용자)', 12, sb.C['user'], 'start', 'bold')

    for sid, col, _, label, note in NODES:
        x, y = card(sid, col, rows_y[sid], note)
        pos[sid] = (x, y, label)
    for sid, (x, y, label) in pos.items():
        p = PARENT[sid]
        if p:
            px, py, _ = pos[p]
            edge(px + CARD_W, py + CARD_H / 2, x, y + CARD_H / 2, label)
    for parent, col, r, label, target, note in REFS:
        x, cy = ref_card(col, row_y(r), target, note)
        px, py, _ = pos[parent]
        edge(px + CARD_W, py + CARD_H / 2, x, cy, label)

    sb.t(30, H - 24, '공통: 모든 화면 상단 오른쪽에 로그아웃. 세션 만료(401)·계정 정지·역할 변경 시 L 로그인으로, 권한 없는 화면(403)은 역할 기본 화면으로 이동.',
         11, sb.C['sub'])
    body = '\n'.join(sb.out)
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" font-family="{sb.FONT}">
<defs><marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse">
<path d="M0,0 L10,5 L0,10 z" fill="{sb.C['line']}"/></marker></defs>
<rect width="{W}" height="{H}" fill="#ffffff"/>
{body}
</svg>
'''
    OUT.write_text(svg, encoding='utf-8')
    print(f'wrote {OUT} ({W}x{H})')


if __name__ == '__main__':
    build()
