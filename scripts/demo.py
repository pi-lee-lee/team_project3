#!/usr/bin/env python3
"""시연 시나리오 자동 실행(시뮬레이션 전용). 관리자 "시연" 화면의 단추와 같은 일을 터미널에서 한다.

서버(inspection-service 의 DemoService)가 시뮬레이션 대상 바꾸기 · 설정 · 점검 시작 · 기다리기를 차례로 하고,
이 스크립트는 실행을 요청한 뒤 진행 기록을 끝날 때까지 따라 출력한다.

    python3 scripts/demo.py                 # 시나리오 목록
    python3 scripts/demo.py fire-approval   # 순찰 중 화재 발견 · 사람 승인 (도착하면 화면의 투척 승인 팝업에서 승인)
    python3 scripts/demo.py fire-auto       # 순찰 중 화재 발견 · 자동 투척 → 불이 꺼짐 → 해결 → 순찰 이어 감
    python3 scripts/demo.py fire-false      # 화재 · 오탐(사진은 정상인데 보고만 옴)
    python3 scripts/demo.py heat-check      # 순찰 중 과열 발견 → 그 앞에서 확인 → 경고 → 순찰 이어 감 → 정상이면 경고 해제
    python3 scripts/demo.py rules-abnormal  # 소방 관제 · 이상 발생
    python3 scripts/demo.py rules-restore   # 소방 관제 · 복구
    python3 scripts/demo.py rules-gauge     # 소방 관제 · 압력계 단계(정상 → 주의 → 위험 → 정상, P4 만)
    python3 scripts/demo.py reset           # 초기화
    python3 scripts/demo.py all             # 소방 관제(이상 → 복구) → 화재(오탐 → 자동 투척) → 열원 확인을 이어서
    python3 scripts/demo.py stop            # 실행 중인 시나리오 중지

스택이 떠 있고 시뮬레이션(Nav2)이 준비되어 있어야 한다. 관리자 계정은 .env 의 INITIAL_ADMIN_* 를 쓴다.
비상 팝업 · 투척 승인 팝업은 사용자 화면(user1)이나 대시보드(dash1)를 브라우저에 띄워 두고 본다.
"""
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from e2e_test import ENV, Client   # noqa: E402

MARK = {'step': '▶', 'wait': '…', 'info': ' ', 'ok': '✓', 'warn': '!', 'error': '✗'}


def run(c, key):
    s, d = c.post(f'/api/admin/demo/{key}/run')
    if s != 200:
        print(f'실행할 수 없습니다 ({s}): {d.get("message", d) if isinstance(d, dict) else d}')
        return False
    print(f"\n=== {d['run']['name']} ===")
    shown = 0
    while True:
        s, d = c.get('/api/admin/demo')
        r = d['run']
        for line in r['log'][shown:]:
            at = datetime.fromisoformat(line['at'][:19] + '+00:00').astimezone().strftime('%H:%M:%S')   # 서버는 UTC 로 준다
            print(f"  {at} {MARK.get(line['level'], ' ')} {line['text']}")
        shown = len(r['log'])
        if r['state'] != 'RUNNING':
            return r['state'] == 'DONE'
        time.sleep(1.5)


def main():
    c = Client()
    s, me = c.post('/api/auth/login', {'loginId': ENV.get('INITIAL_ADMIN_LOGIN', 'admin'),
                                      'password': ENV.get('INITIAL_ADMIN_PASSWORD', 'Admin1234!')})
    if s != 200:
        sys.exit(f'관리자 로그인 실패 ({s})')
    s, d = c.get('/api/admin/demo')
    if s != 200:
        sys.exit(f'시연 API 를 부를 수 없습니다 ({s})')
    keys = [x['key'] for x in d['scenarios']]
    arg = sys.argv[1] if len(sys.argv) > 1 else ''
    if arg == 'stop':
        c.post('/api/admin/demo/stop')
        print('중지를 요청했습니다')
        return
    if arg not in keys:
        print(__doc__)
        print('시나리오:')
        for x in d['scenarios']:
            print(f"  {x['key']:<16} [{x['group']}] {x['name']} — {x['description']}")
        sys.exit(0 if not arg else 1)
    sys.exit(0 if run(c, arg) else 1)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\n(출력만 멈췄습니다. 시나리오는 서버에서 계속 실행됩니다 — 멈추려면: python3 scripts/demo.py stop)')
