#!/usr/bin/env python3
"""종단 간 시험: compose 로 띄운 전체 서비스를 실제 API 로 검사한다.

실행: python3 scripts/e2e_test.py   (프로젝트 루트의 .env 를 읽는다)
흐름: admin 로그인 → 시스템 상태 → 사용자 생성 → 그 사용자로 점검 요청 → 로봇 이동·촬영 → 품질 분석
      → 사람 판정 → 재점검·취소 → 지점 이력 → 권한 거부 → 제어권·비상 정지 → 감사 로그
"""
import http.cookiejar
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = 'http://localhost:8080'
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'ros/sim/src/worlds'))
from world_spec import OBSTACLES  # noqa: E402  (장애물 자리: 계획 경로 위인지 확인하는 데 쓴다)

ENV_FILE = ROOT / '.env' if (ROOT / '.env').exists() else ROOT / '.env.example'   # .env 가 없으면 기본값
ENV = dict(line.split('=', 1) for line in ENV_FILE.read_text().splitlines()
           if '=' in line and not line.startswith('#'))
BASE = f"http://localhost:{ENV.get('WEB_PORT', '8080')}"
passed = 0


class Client:
    def __init__(self):
        self.op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def call(self, method, path, body=None):
        data = None if body is None else json.dumps(body).encode()
        req = urllib.request.Request(BASE + path, data=data, method=method,
                                     headers={'Content-Type': 'application/json'} if data else {})
        try:
            with self.op.open(req, timeout=15) as r:
                raw = r.read()
                ctype = r.headers.get('Content-Type', '')
                return r.status, (json.loads(raw) if raw and 'json' in ctype else raw)
        except urllib.error.HTTPError as e:
            raw = e.read()
            try:
                return e.code, json.loads(raw)
            except ValueError:
                return e.code, raw

    def get(self, p):
        return self.call('GET', p)

    def post(self, p, b=None):
        return self.call('POST', p, {} if b is None else b)


def check(cond, label, extra=''):
    global passed
    if not cond:
        print(f'  ✗ {label} {extra}')
        sys.exit(1)
    passed += 1
    print(f'  ✓ {label}')


def wait(fn, timeout, label, every=2):
    end = time.time() + timeout
    while time.time() < end:
        v = fn()
        if v:
            return v
        time.sleep(every)
    check(False, label, '(시간 초과)')


def obstacle(*args):
    import subprocess
    r = subprocess.run(['docker', 'compose', 'exec', '-T', 'sim', '/sim/tools/obstacle.sh', *args],
                       capture_output=True, text=True, cwd=Path(__file__).resolve().parent.parent)
    return r.returncode == 0 and 'False' not in r.stdout


def run_task(user, rid, point_ids, note, timeout=600):
    s, t = user.post('/api/inspections', {'robotId': rid, 'pointIds': point_ids, 'note': note})
    check(s == 201, f"작업 #{t.get('task_id')} 생성 ({note})", str(t))
    return wait(lambda: (lambda s, d: d if d['status'] in ('COMPLETED', 'FAILED', 'CANCELLED', 'INTERRUPTED') else None)(
        *user.get(f"/api/inspections/{t['task_id']}")), timeout, f'{note} 종료', every=5)


def drive_and_block(user, rid, point_id, note, name, reached, timeout=600):
    """점검 작업을 시작하고, 로봇이 reached(pose) 자리에 오면 장애물 name 을 놓는다(달리는 도중에 생기는 장애물).
    놓기 직전에 그 자리가 지금 계획 경로를 막는지 확인한다 — 경로와 상관없는 곳에 놓으면 시험이 아니다."""
    s, t = user.post('/api/inspections', {'robotId': rid, 'pointIds': [point_id], 'note': note})
    check(s == 201, f"작업 #{t.get('task_id')} 생성 ({note})", str(t))
    view = {}

    def there():
        view.update(user.get(f'/api/robots/{rid}/mapview')[1] or {})
        return view.get('pose') and view.get('path') and reached(view['pose'])
    wait(there, 180, f'{note}: 장애물을 놓을 자리 도착', every=0.3)
    ox, oy, sx, sy = OBSTACLES[name]
    # 경로가 장애물에서 로봇 반지름(0.22m) + 여유 안으로 지나가면 '경로를 막는다'. 통로를 반만 막는 장애물(aisle60)은
    # 경로 선 바로 옆에 놓이므로 선과 겹치는지로 보면 안 된다.
    reach = 0.22 + 0.08
    on_path = any(abs(x - ox) <= sx / 2 + reach and abs(y - oy) <= sy / 2 + reach for x, y in view['path'])
    check(on_path, f'{name} 자리가 지금 계획 경로를 막음(로봇이 지나갈 자리와 겹침)')
    check(obstacle('place', name), f'달리는 도중에 {name} 놓기')
    d = wait(lambda: (lambda s, d: d if d['status'] in ('COMPLETED', 'FAILED', 'CANCELLED', 'INTERRUPTED') else None)(
        *user.get(f"/api/inspections/{t['task_id']}")), timeout, f'{note} 종료', every=5)
    print('     사건:', ' → '.join(e['type'] for e in d['events']))
    return d


def obstacle_scenarios(user, rid, by):
    """시험 시설의 적재물 시나리오. 장애물은 로봇이 달리는 도중에, 그때의 계획 경로 위에 놓는다(9-3 만 출발 전에 막는다).
    장애물이 실제로 서기까지 2.5초쯤 걸리므로 0.5m 쯤 앞서 놓으라고 한다."""
    print('9-1. 장애물: 경로 위 팔레트 (P1 → P3, 제어기가 비켜 지나감)')
    obstacle('clear')
    run_task(user, rid, [by['P1']], 'P1 로 이동')
    d = drive_and_block(user, rid, by['P3'], '팔레트 비켜 가기', 'pallet', lambda p: p['x'] > 4.9 and p['y'] > 3.5)
    check(d['status'] == 'COMPLETED' and d['observations'][0]['status'] == 'CAPTURED', '팔레트를 비켜 P3 도착·촬영')

    print('9-2. 장애물: 가던 문이 막힘 (P1 → P3, 생산동 → C2 문 막힘 → C1 · C2 로 돌아감)')
    obstacle('clear')
    run_task(user, rid, [by['P1']], 'P1 로 이동')
    d = drive_and_block(user, rid, by['P3'], '문 막힘', 'door', lambda p: p['x'] > 5.6 and p['y'] > 3.5)
    check(d['status'] == 'COMPLETED' and d['observations'][0]['status'] == 'CAPTURED', '다시 계획해 C1 · C2 로 돌아 P3 도착·촬영')

    print('9-3. 장애물: C2 위쪽 막힘 (진입 불가)')
    obstacle('clear')
    d = run_task(user, rid, [by['P1']], '막기 전에 생산동으로 이동')     # 로봇이 막힘 위쪽(P3)에 갇히지 않게
    check(obstacle('place', 'block'), 'C2 위쪽 막기')
    d = run_task(user, rid, [by['P3'], by['P4']], '진입 불가')
    print('     사건:', ' → '.join(e['type'] for e in d['events']))
    o2 = next(o for o in d['observations'] if o['point_code'] == 'P3')
    o3 = next(o for o in d['observations'] if o['point_code'] == 'P4')
    check(o2['status'] == 'UNABLE' and o2['reason_code'] == 'BLOCKED_NO_PATH',
          f"P3 확인 불가 · 사유 코드 {o2['reason_code']} ({o2['reason']})")
    check('ARRIVAL_BLOCKED' in [e['type'] for e in d['events']], '사건 기록 ARRIVAL_BLOCKED')
    check(o3['status'] == 'CAPTURED', '막힌 지점은 건너뛰고 다음 지점(P4)은 촬영')

    print('9-4. 장애물: 가던 골목이 막힘 (P4 → P1, 전기실 문 바로 아래 막힘 → 랙 위로 돌아 나옴)')
    obstacle('clear')                                                    # 로봇은 9-3 을 마치고 P4 에 있다
    # 놓으라는 명령에서 실제로 서기까지 2.5~4초 → 문 0.7m 앞에서 명령한다(늦으면 블록이 로봇 위에 생긴다)
    d = drive_and_block(user, rid, by['P1'], '골목 막힘', 'aisle', lambda p: p['x'] > 2.3 and p['y'] > 4.9)
    check(d['status'] == 'COMPLETED' and d['observations'][0]['status'] == 'CAPTURED', '다시 계획해 랙 위로 돌아 P1 도착·촬영')

    print('9-5. 장애물: 같은 자리가 반쯤 막힘 (P4 → P1, 문을 지날 때 폭 0.6m 틈만 남음)')
    obstacle('clear')
    run_task(user, rid, [by['P4']], 'P4 로 이동')                          # 9-4 를 마치고 P1 에 있다
    d = drive_and_block(user, rid, by['P1'], '골목 반쯤 막힘(P4 → P1)', 'aisle60', lambda p: p['x'] > 2.6 and p['y'] > 5.0)
    check(d['status'] == 'COMPLETED' and d['observations'][0]['status'] == 'CAPTURED', '틈으로 지나거나 랙 위로 돌아 P1 도착·촬영')

    # P1 은 그 자리에서 1.6m 뿐이라, 출발한 뒤에 놓으면 장애물이 로봇 코앞(0.3m)에 생긴다(실제로 서기까지 2.5초).
    # 그래서 되돌아가는 길은 9-5 의 장애물을 치우지 않고 그대로 둔다.
    print('9-6. 장애물: 그 장애물을 둔 채 되돌아감 (P1 → P4, 같은 자리 폭 0.6m 틈)')
    d = run_task(user, rid, [by['P4']], '반쯤 막힌 골목으로 되돌아감')
    print('     사건:', ' → '.join(e['type'] for e in d['events']))
    check(d['status'] == 'COMPLETED' and d['observations'][0]['status'] == 'CAPTURED', '틈으로 지나거나 랙 위로 돌아 P4 도착·촬영')
    obstacle('clear')


ZONE = {'name': 'e2e 공사 중', 'x1': 3.05, 'y1': 4.7, 'x2': 4.0, 'y2': 5.0}    # 전기실 문 바로 아래 골목(서쪽 벽 ↔ 랙 1)


def drive_watch(user, rid, point_id, note, tick=None, timeout=600):
    """점검 작업을 시작해 끝날 때까지 로봇 위치를 0.3초마다 모은다. tick(view) 가 있으면 매번 부른다(주행 중에 할 일)."""
    s, t = user.post('/api/inspections', {'robotId': rid, 'pointIds': [point_id], 'note': note})
    check(s == 201, f"작업 #{t.get('task_id')} 생성 ({note})", str(t))
    poses, end = [], time.time() + timeout
    while time.time() < end:
        v = user.get(f'/api/robots/{rid}/mapview')[1] or {}
        if v.get('pose'):
            poses.append((v['pose']['x'], v['pose']['y']))
        if tick:
            tick(v)
        if len(poses) % 10 == 0:
            s, d = user.get(f"/api/inspections/{t['task_id']}")
            if s == 200 and d['status'] in ('COMPLETED', 'FAILED', 'CANCELLED', 'INTERRUPTED'):
                print('     사건:', ' → '.join(e['type'] for e in d['events']))
                return d, poses
        time.sleep(0.3)
    check(False, f'{note} 종료', '(시간 초과)')


def zone_scenarios(admin, user, rid, by):
    """금지구역: 관리자가 지도에 그린 직사각형. 실제 장애물이 없어도 로봇이 그 안으로 가지 않아야 한다."""
    def inside(poses, z=ZONE):
        return [p for p in poses if z['x1'] < p[0] < z['x2'] and z['y1'] < p[1] < z['y2']]

    def clear_zones():
        for z in admin.get(f'/api/robots/{rid}/zones')[1]:
            admin.call('DELETE', f"/api/robots/{rid}/zones/{z['zoneId']}")
    print('Z-1. 금지구역: 권한')
    obstacle('clear')
    clear_zones()
    sup_login = f'e2es{int(time.time()) % 100000}'
    check(admin.post('/api/admin/users', {'loginId': sup_login, 'password': 'e2e-password-1', 'name': '시험 관리자', 'roleId': 1})[0] == 201,
          f'사용자 생성 {sup_login} (1 관리자)')
    sup = Client()
    check(sup.post('/api/auth/login', {'loginId': sup_login, 'password': 'e2e-password-1'})[0] == 200, f'{sup_login} 로그인')
    check(user.post(f'/api/robots/{rid}/zones', ZONE)[0] == 403, '2 매니저는 금지구역을 설정할 수 없음(403)')
    check(user.get(f'/api/robots/{rid}/zones')[0] == 200, '조회는 누구나')
    check(sup.post(f'/api/robots/{rid}/zones', {'x1': 1, 'y1': 1, 'x2': 1.05, 'y2': 1.05})[0] == 400, '너무 작은 구역 거부(400)')

    print('Z-2. 금지구역: 미리 설정 (P4 → P1, 문 아래 골목이 금지구역 → 랙 위로 돌아감)')
    run_task(user, rid, [by['P4']], 'P4 로 이동')
    s, zs = sup.post(f'/api/robots/{rid}/zones', ZONE)
    check(s == 200 and len(zs) == 1 and zs[0]['name'] == ZONE['name'], '1 관리자가 금지구역 설정')
    time.sleep(4)                                    # 로봇의 계획 맵 · 제어 맵에 들어갈 시간
    d, poses = drive_watch(user, rid, by['P1'], '금지구역을 두고 P1 로')
    check(d['status'] == 'COMPLETED' and d['observations'][0]['status'] == 'CAPTURED', 'P1 도착·촬영')
    check(not inside(poses), f'주행 내내 금지구역에 들어가지 않음(위치 {len(poses)}개)', str(inside(poses)[:3]))
    check(max(y for _, y in poses) > 6.4, f"랙 위로 돌아감(가장 위 y={max(y for _, y in poses):.2f})")

    print('Z-3. 금지구역: 로봇이 있는 자리에는 설정할 수 없음')
    x, y = poses[-1]
    s, e = sup.post(f'/api/robots/{rid}/zones', {'x1': x - 0.3, 'y1': y - 0.3, 'x2': x + 0.3, 'y2': y + 0.3})
    check(s == 409, f"로봇 위 구역 거부(409: {e.get('message', '') if isinstance(e, dict) else ''})")

    print('Z-4. 금지구역: 삭제하면 다시 지나감 (P1 → P4 직행)')
    check(sup.call('DELETE', f"/api/robots/{rid}/zones/{zs[0]['zoneId']}")[0] == 200, '금지구역 삭제')
    time.sleep(4)
    d, poses = drive_watch(user, rid, by['P4'], '금지구역을 지우고 P4 로')
    check(d['status'] == 'COMPLETED', 'P4 도착')
    check(inside(poses) and max(y for _, y in poses) < 6.3, f"골목으로 직행(가장 위 y={max(y for _, y in poses):.2f})")

    print('Z-5. 금지구역: 달리는 도중에 설정 (P4 → P1, 가던 골목이 금지구역이 됨 → 다시 계획해 돌아감)')
    state = {}

    def tick(v):
        p = v.get('pose')
        if not state and p and v.get('path') and p['x'] > 1.6 and p['y'] > 4.7:     # 전기실 가운데: 구역까지 1.5m 남짓
            state['on_path'] = any(ZONE['x1'] < x < ZONE['x2'] and ZONE['y1'] < y < ZONE['y2'] for x, y in v['path'])
            state['status'] = sup.post(f'/api/robots/{rid}/zones', ZONE)[0]
    d, poses = drive_watch(user, rid, by['P1'], '달리는 도중 금지구역', tick)
    check(state.get('on_path'), '설정하는 순간 계획 경로가 그 구역을 지나고 있었음')
    check(state.get('status') == 200, '달리는 도중 금지구역 설정')
    check(d['status'] == 'COMPLETED' and d['observations'][0]['status'] == 'CAPTURED', '다시 계획해 P1 도착·촬영')
    check(not inside(poses), f'금지구역에 들어가지 않음(위치 {len(poses)}개)', str(inside(poses)[:3]))
    check(max(y for _, y in poses) > 6.4, f"랙 위로 돌아감(가장 위 y={max(y for _, y in poses):.2f})")
    clear_zones()
    check(admin.get(f'/api/robots/{rid}/zones')[1] == [], '금지구역 정리')


def main():
    print('1. 접속·로그인')
    anon = Client()
    wait(lambda: anon.get('/api/auth/me')[0] == 401, 180, 'web·gateway 응답')
    check(anon.get('/api/inspections')[0] == 401, '로그인 없이 API 거부(401)')
    s, body = anon.get('/internal/robots/status')
    check(isinstance(body, bytes) and b'<!doctype html>' in body.lower(), '/internal 경로는 내부 서비스에 닿지 않음')
    admin = Client()
    s, me = admin.post('/api/auth/login', {'loginId': ENV['INITIAL_ADMIN_LOGIN'], 'password': ENV['INITIAL_ADMIN_PASSWORD']})
    check(s == 200 and me['role'] == 'ADMIN', 'admin 로그인')
    check(admin.post('/api/auth/login', {'loginId': 'admin', 'password': 'wrong-password'})[0] == 401, '틀린 비밀번호 거부')

    print('2. 시스템 상태 (A6)')
    def all_up():
        s, d = admin.get('/api/admin/system')
        return s == 200 and all(x['status'] == 'UP' for x in d['services']) and d
    sysinfo = wait(all_up, 180, '모든 서비스 UP')
    check(True, '서비스: ' + ', '.join(x['name'] for x in sysinfo['services']))

    print('3. 사용자 관리 (A1)')
    login = f'e2e{int(time.time()) % 100000}'
    s, u = admin.post('/api/admin/users', {'loginId': login, 'password': 'e2e-password-1', 'name': '시험', 'roleId': 2})
    check(s == 201 and u['role'] == 'MANAGER', f'사용자 생성 {login} (2 매니저)')
    check(admin.post('/api/admin/users', {'loginId': login, 'password': 'e2e-password-1', 'name': 'x', 'roleId': 3})[0] == 409,
          '중복 아이디 거부')

    print('4. 로봇 연결')
    user = Client()
    check(user.post('/api/auth/login', {'loginId': login, 'password': 'e2e-password-1'})[0] == 200, f'{login} 로그인')
    check(user.get('/api/admin/users')[0] == 403, '사용자 역할로 관리자 API 거부(403)')

    def robot():
        s, rs = user.get('/api/robots')
        r = next((x for x in rs if x['code'] == 'tb3-sim'), None) if s == 200 else None
        return r if r and r['connected'] else None
    r = wait(robot, 300, 'tb3-sim 연결')
    rid = r['robotId']
    st = wait(lambda: (lambda s, d: d if d.get('capabilities', {}).get('odom') == 'VERIFIED'
                       and d.get('capabilities', {}).get('camera') == 'VERIFIED' else None)(*user.get(f'/api/robots/{rid}/status')),
              120, 'odom·camera 수신')
    check(True, f"제공 기능 {st['capabilities']}")
    s, img = user.get(f'/api/robots/{rid}/snapshot')
    check(s == 200 and isinstance(img, bytes) and img[:2] == b'\xff\xd8', f'카메라 스냅샷 JPEG {len(img)} bytes')
    if '--only-zones' in sys.argv:
        s, pts = user.get('/api/points')
        zone_scenarios(admin, user, rid, {p['code']: p['point_id'] for p in pts})
        print(f'\n모두 통과: {passed}개 확인')
        return
    if '--only-obstacles' in sys.argv:
        s, pts = user.get('/api/points')
        obstacle_scenarios(user, rid, {p['code']: p['point_id'] for p in pts})
        print(f'\n모두 통과: {passed}개 확인')
        return

    print('5. 점검 요청 → 이동·촬영 (U2·U4)')
    s, pts = user.get('/api/points')
    by = {p['code']: p['point_id'] for p in pts}
    s, t = user.post('/api/inspections', {'robotId': rid, 'pointIds': [by['P1'], by['P3']], 'note': 'e2e'})
    check(s == 201, f"작업 생성 #{t.get('task_id')}", str(t))
    tid = t['task_id']

    def finished():
        s, d = user.get(f'/api/inspections/{tid}')
        return d if d['status'] in ('COMPLETED', 'FAILED', 'CANCELLED', 'INTERRUPTED') else None
    d = wait(finished, 900, '작업 종료', every=3)
    events = [e['type'] for e in d['events']]
    print('     사건:', ' → '.join(events))
    check(d['status'] == 'COMPLETED', f"작업 완료 (상태 {d['status']})", d.get('status_reason') or '')
    obs = d['observations']
    check(len(obs) == 2 and all(o['status'] == 'CAPTURED' and o['has_image'] for o in obs), '관측 2건 촬영 저장')
    for need in ['REQUESTED', 'ACCEPTED', 'PREFLIGHT_OK', 'MOVING', 'ARRIVED', 'OBSERVATION_SAVED', 'COMPLETED']:
        check(need in events, f'사건 기록 {need}')
    s, img = user.get(f"/api/observations/{obs[0]['observation_id']}/image")
    check(s == 200 and img[:2] == b'\xff\xd8', '관측 사진 조회')

    print('6. 품질 분석')
    def analyzed():
        s, d = user.get(f'/api/inspections/{tid}')
        return d if all(o['verdict'] for o in d['observations']) else None
    d = wait(analyzed, 90, '분석 결과 도착')
    for o in d['observations']:
        check(True, f"{o['point_code']}: 밝기 {o['brightness']} 선명도 {o['sharpness']} → {o['verdict']} {o['analysis_reasons'] or ''}")

    print('7. 사람 판정 (U4-1)')
    o1, o2 = d['observations']
    check(user.post(f"/api/observations/{o1['observation_id']}/reviews", {'result': 'UNABLE', 'comment': ''})[0] == 400,
          '확인 불가는 사유 없으면 거부')
    s, r1 = user.post(f"/api/observations/{o1['observation_id']}/reviews", {'result': 'NORMAL', 'comment': '이상 없음'})
    check(s == 200 and r1['review_result'] == 'NORMAL', '판정 저장 (정상)')
    s, r1 = user.post(f"/api/observations/{o1['observation_id']}/reviews", {'result': 'ABNORMAL', 'comment': '재확인'})
    s, d = user.get(f'/api/inspections/{tid}')
    check(len(d['observations'][0]['reviews']) == 2, '판정 이력이 쌓임 (덮어쓰지 않음)')

    print('8. 재점검 → 취소 (U4)')
    s, t2 = user.post(f"/api/observations/{o2['observation_id']}/recheck")
    check(s == 201 and t2['recheck_of'] == o2['observation_id'], f"재점검 작업 #{t2['task_id']} 생성, 원래 관측과 연결")
    wait(lambda: user.get(f"/api/inspections/{t2['task_id']}")[1]['status'] == 'COMPLETED', 600, '재점검 작업 완료')
    check(user.post(f"/api/inspections/{t2['task_id']}/cancel")[0] == 409, '끝난 작업의 취소는 거부(409)')
    s, t3 = user.post('/api/inspections', {'robotId': rid, 'pointIds': [by['P4'], by['P1']], 'note': 'e2e 취소 시험'})
    check(s == 201, f"먼 지점 작업 #{t3['task_id']} 생성")
    wait(lambda: user.get(f"/api/inspections/{t3['task_id']}")[1]['status'] == 'RUNNING', 60, '이동 시작')
    time.sleep(2)
    s, c = user.post(f"/api/inspections/{t3['task_id']}/cancel")
    check(s == 200, '이동 중 취소 요청')
    d3 = wait(lambda: (lambda s, d: d if d['status'] in ('CANCELLED', 'COMPLETED', 'FAILED') else None)(
        *user.get(f"/api/inspections/{t3['task_id']}")), 60, '취소 결과 확인')
    ev3 = [e['type'] for e in d3['events']]
    print('     사건:', ' → '.join(ev3))
    check('CANCEL_REQUESTED' in ev3 and 'CANCELLED' in ev3 and d3['status'] == 'CANCELLED',
          '취소 요청(사용자)과 실제 취소(로봇)를 따로 기록')

    print('9. 지점 이력 (U5)')
    s, h = user.get(f"/api/points/{by['P1']}/history")
    check(s == 200 and any(o['observation_id'] == o1['observation_id'] for o in h['observations']), 'P1 이력에 관측 포함')

    if '--skip-obstacles' not in sys.argv:
        obstacle_scenarios(user, rid, by)
        zone_scenarios(admin, user, rid, by)

    print('10. 제어권·비상 정지 (U1·A2)')
    s, lease = user.post(f'/api/robots/{rid}/control/acquire')
    check(s == 200 and lease['kind'] == 'USER', '제어권 획득')
    s, rs = admin.get('/api/admin/robots')
    check(next(x for x in rs if x['robotId'] == rid)['control']['login'] == login, '관리자 화면에 조종자 표시')
    s, rv = admin.post(f'/api/admin/robots/{rid}/revoke-control')
    check(s == 200 and rv['revoked'], '관리자 제어권 회수')
    check(user.post(f'/api/robots/{rid}/estop')[0] == 200, '비상 정지')

    print('11. 세션 강제 종료·감사 로그 (A1·A5)')
    check(admin.post(f"/api/admin/users/{u['userId']}/revoke-sessions")[0] == 200, '세션 강제 종료')
    wait(lambda: user.get('/api/robots')[0] == 401, 20, '종료된 세션 거부(401)', every=2)
    check(True, '종료된 세션 거부(401)')
    s, logs = admin.get('/api/admin/audit?limit=200')
    actions = {(x['login_id'], x['action']) for x in logs}
    check((login, 'POST') in actions and ('admin', 'LOGIN') in actions, '감사 로그에 로그인·변경 요청 기록')

    print(f'\n모두 통과: {passed}개 확인')


if __name__ == '__main__':
    main()
