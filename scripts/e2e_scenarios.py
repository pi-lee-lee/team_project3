#!/usr/bin/env python3
"""시나리오 전 구간 시험: 소방 관제(규칙 → 등급 → 경고)와 소화액 투척(감지 → 출동 → 재판독 → 투척)을
compose 로 띄운 실제 스택과 시뮬레이션에 대고 확인한다. 설계는 docs/design/SCENARIOS.md · INTERFACES.md.

실행(저장소 루트, 스택이 떠 있고 Nav2 가 준비된 상태에서):
    python3 scripts/e2e_scenarios.py              # 전부 (로봇이 실제로 주행하므로 20~40분)
    python3 scripts/e2e_scenarios.py --only rules # 소방 관제만
    python3 scripts/e2e_scenarios.py --only fire  # 소화액 투척만
    python3 scripts/e2e_scenarios.py --only fire --skip-preempt   # 점검 중 가로채기 시험 제외

젯봇은 시뮬레이션에 없다. 감지 보고는 fire.sh 가 대신 보낸다(/patrol/detection).
시뮬레이션 터틀봇에는 투척 기구가 없다. 모의 노드(mock_launcher.py)가 투척 명령에 답한다.
"""
import argparse
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from e2e_test import ENV, Client, check, wait   # noqa: E402  (로그인·대기 도우미를 같이 쓴다)

ROOT = Path(__file__).resolve().parent.parent
TAG = '[e2e]'                    # 이 시험이 만든 규칙의 이름 머리. 시작할 때 지우고 다시 만든다
TERMINAL = ('COMPLETED', 'FAILED', 'CANCELLED', 'INTERRUPTED')

# 지점별 규칙. 영역(regions)은 그 지점에서 찍은 사진에서 대상이 있어야 할 곳(사진 크기 대비 비율)이다.
# 값은 시뮬레이션 사진에서 잰 것이다(ros/sim/src/worlds/world_spec.py 의 대상 정의가 바뀌면 다시 잰다).
# 로봇의 도착 방향 허용 오차(0.15rad)만큼 대상이 사진에서 좌우로 ±15% 쯤 움직이므로, 영역은 가로 전체로 두고
# 세로로만 나눈다(표시등·계기판은 상자 위쪽에 있다). 그래서 소화기는 '있다/없다'만 가린다 — '옆으로 옮겨짐'은
# 이 영역으로는 가릴 수 없다.
# 지점: P1 = 소화기 사진 판(인식 모델 fire_v1), P3 = 비상구 표시등, P4 = 분전반 계기판.
# P2(받침만 있는 사진 판, 늘 '없음')는 비교용이라 이 시나리오에 넣지 않는다.
RULES = {
    'P1': [{
        'name': f'{TAG} 소화기 비치', 'kind': 'OBJECT',
        'params': {'label': 'fire_extinguisher', 'expect': 'PRESENT', 'detector': 'model',
                   'model': 'fire_v1', 'className': 'fire_extinguisher'},
        'regions': {},
        'grading': {'type': 'map', 'default': 'UNKNOWN',
                    'map': {'IN_REGION': 'NORMAL', 'OUT_OF_REGION': 'WARNING', 'MISSING': 'WARNING'}},
    }],
    'P3': [{
        'name': f'{TAG} 상태 표시등', 'kind': 'LAMP', 'params': {},
        'regions': {'INSPECTOR': [0.0, 0.0, 1.0, 0.33]},
        'grading': {'type': 'map', 'default': 'UNKNOWN',
                    'map': {'green': 'NORMAL', 'yellow': 'WARNING', 'red': 'EMERGENCY', 'off': 'WARNING'}},
    }],
    'P4': [{
        'name': f'{TAG} 압력계', 'kind': 'GAUGE',
        'params': {'minAngle': 225, 'maxAngle': -45, 'minValue': 0, 'maxValue': 1, 'unit': 'MPa'},
        'regions': {'INSPECTOR': [0.0, 0.0, 1.0, 0.37]},
        'grading': {'type': 'ranges', 'default': 'EMERGENCY',
                    'ranges': [{'min': 0.7, 'max': 0.98, 'grade': 'NORMAL'}, {'min': 0.5, 'max': 0.7, 'grade': 'WARNING'}]},
    }],
}


def tool(name, *args):
    """시뮬레이션 도구(/sim/tools/*.sh)를 컨테이너 안에서 실행한다."""
    r = subprocess.run(['docker', 'compose', 'exec', '-T', 'sim', f'/sim/tools/{name}.sh', *args],
                       capture_output=True, text=True, cwd=ROOT)
    if r.returncode != 0:
        print(f'     {name}.sh {" ".join(args)} 실패:\n{r.stdout[-400:]}{r.stderr[-400:]}')
    return r.returncode == 0, r.stdout


def login(login_id, password):
    c = Client()
    s, me = c.post('/api/auth/login', {'loginId': login_id, 'password': password})
    check(s == 200, f'{login_id} 로그인', str(me))
    return c


def run_task(user, rid, point_ids, note, timeout=900):
    s, t = user.post('/api/inspections', {'robotId': rid, 'pointIds': point_ids, 'note': note})
    check(s == 201, f"작업 #{t.get('task_id')} 생성 ({note})", str(t))
    return wait(lambda: (lambda s, d: d if d['status'] in TERMINAL else None)(*user.get(f"/api/inspections/{t['task_id']}")),
                timeout, f'{note} 종료', every=5)


def results_of(user, task, expected_rules):
    """작업의 관측마다 규칙 결과가 다 올 때까지 기다려 {지점 코드: 결과 목록} 으로 돌려준다."""
    out = {}
    for o in task['observations']:
        need = expected_rules.get(o['point_code'], 0)
        if o['status'] != 'CAPTURED' or not need:
            out[o['point_code']] = []
            continue
        out[o['point_code']] = wait(
            lambda oid=o['observation_id'], n=need: (lambda s, r: r if s == 200 and len(r) >= n else None)(
                *user.get(f'/api/observations/{oid}/results')), 120, f"{o['point_code']} 규칙 판독 결과 수신")
    return out


def grades(res):
    return {code: [(r['rule']['name'].replace(TAG, '').strip(), r['grade'], r['value']) for r in rs] for code, rs in res.items()}


def open_rule_alerts(user, rule_ids):
    s, alerts = user.get('/api/alerts?state=OPEN,ACKED&limit=200')
    return [a for a in alerts if a['type'] == 'RULE_VIOLATION' and (a.get('evidence') or {}).get('ruleId') in rule_ids]


# ---------------------------------------------------------------- 시나리오 2: 소방 관제
def scenario_rules(admin, user, rid, by):
    print('\n[소방 관제] 1. 규칙 만들기')
    s, checkers = admin.get('/api/admin/checkers')
    check(s == 200 and {'OBJECT', 'GAUGE', 'LAMP', 'THERMAL'} <= {c['kind'] for c in checkers}, '판독기 목록(OBJECT·GAUGE·LAMP·THERMAL)')
    rule_ids = {}
    for code, rules in RULES.items():
        s, old = admin.get(f'/api/points/{by[code]}/rules')
        for r in old:
            if r['name'].startswith(TAG):
                admin.call('DELETE', f"/api/admin/rules/{r['ruleId']}")
        for rule in rules:
            s, made = admin.post(f'/api/admin/points/{by[code]}/rules', {**rule, 'enabled': True})
            check(s == 201, f"{code} 규칙 '{rule['name']}' 만들기", str(made))
            rule_ids[made['ruleId']] = code
    s, bad = admin.post(f"/api/admin/points/{by['P1']}/rules", {'name': 'x', 'kind': 'NOPE', 'grading': {'type': 'map', 'map': {}}})
    check(s == 400, '없는 판독기 종류는 거부')
    s, _ = user.post(f"/api/admin/points/{by['P1']}/rules", RULES['P1'][0])
    check(s == 403, '규칙 만들기는 관리자만')
    need = {code: len(rs) for code, rs in RULES.items()}
    pts = [by['P1'], by['P3'], by['P4']]

    print('[소방 관제] 2. 모두 정상인 상태로 점검')
    check(tool('target', 'reset')[0], '대상 원위치(계기판 0.8 · 표시등 초록 · 소화기 제자리)')
    d = run_task(user, rid, pts, '소방 관제: 정상')
    check(d['status'] == 'COMPLETED' and all(o['status'] == 'CAPTURED' for o in d['observations']), '세 지점 도착 · 촬영')
    g = grades(results_of(user, d, need))
    print('     등급:', g)
    check(all(x[1] == 'NORMAL' for rs in g.values() for x in rs), '세 규칙 모두 정상')
    check(not open_rule_alerts(user, rule_ids), '규칙 경고 없음')

    print('[소방 관제] 3. 대상을 바꾸고 점검: 소화기 치움 · 표시등 빨강 · 계기판 0.6')
    check(tool('target', 'extinguisher', 'remove')[0] and tool('target', 'lamp', 'red')[0] and tool('target', 'gauge', '0.6')[0],
          '대상 바꾸기')
    d = run_task(user, rid, pts, '소방 관제: 이상')
    g = grades(results_of(user, d, need))
    print('     등급:', g)
    check(g['P1'][0][1] == 'WARNING' and g['P1'][0][2] == 'MISSING', '소화기 없음 → 경고')
    check(g['P3'][0][1] == 'EMERGENCY' and g['P3'][0][2] == 'red', '표시등 빨강 → 비상')
    check(g['P4'][0][1] == 'WARNING' and abs(g['P4'][0][2] - 0.6) < 0.08, f"계기판 0.6 → 경고 (읽은 값 {g['P4'][0][2]})")
    alerts = wait(lambda: (lambda a: a if len(a) == 3 else None)(open_rule_alerts(user, rule_ids)), 30, '규칙 경고 3건 열림')
    check(sorted(a['grade'] for a in alerts) == ['EMERGENCY', 'WARNING', 'WARNING'], '경고 등급: 비상 1 · 경고 2')
    s, ov = user.get('/api/dashboard/overview')
    rank = {p['code']: p.get('grade_rank') for p in ov['points']}
    check(rank.get('P1') == 2 and rank.get('P3') == 3 and rank.get('P4') == 2, f'대시보드 지점 등급 {rank}')
    check(any(a.get('alert_id') == alerts[0]['alert_id'] for a in ov['alerts']), '대시보드 경고 목록에 표시')
    warn = next(a for a in alerts if a['grade'] == 'WARNING')
    s, a = user.post(f"/api/alerts/{warn['alert_id']}/ack", {'comment': 'e2e 확인'})
    check(s == 200 and a['state'] == 'ACKED', '경고 확인(ACKED)')
    s, _ = user.post(f"/api/alerts/{warn['alert_id']}/resolve")
    check(s == 403, '경고 해제는 3 사용자에게 거부')

    print('[소방 관제] 4. 원위치 후 다시 점검 → 경고가 스스로 풀림')
    check(tool('target', 'reset')[0], '대상 원위치')
    d = run_task(user, rid, pts, '소방 관제: 복구')
    g = grades(results_of(user, d, need))
    print('     등급:', g)
    check(all(x[1] == 'NORMAL' for rs in g.values() for x in rs), '세 규칙 모두 정상')
    wait(lambda: not open_rule_alerts(user, rule_ids), 30, '규칙 경고 자동 해제')
    s, done = user.get('/api/alerts?state=RESOLVED&limit=50')
    check(any(a['resolved_by'] == 'SYSTEM' and (a.get('evidence') or {}).get('ruleId') in rule_ids for a in done), '해제 주체 = SYSTEM')


# ---------------------------------------------------------------- 시나리오 1: 소화액 투척
def set_mode(sup, mode):
    s, st = sup.call('PUT', '/api/settings/launch.mode', {'value': mode})
    check(s == 200 and st['launch.mode'] == mode, f'투척 모드 = {mode}')


def close_open_incidents(sup):
    s, inc = sup.get('/api/incidents?state=open')
    for i in inc:
        sup.post(f"/api/incidents/{i['incidentId']}/dismiss", {'comment': 'e2e 정리'})


def wait_incident(user, since_id, timeout=120):
    return wait(lambda: (lambda s, l: next((i for i in l if i['incidentId'] > since_id), None))(*user.get('/api/incidents?state=open')),
                timeout, '사건 생성')


def wait_state(user, iid, states, timeout=900):
    def f():
        s, d = user.get(f'/api/incidents/{iid}')
        if d['state'] in states:
            return d
        if d['state'] in ('FAILED', 'DISMISSED', 'RESOLVED') and d['state'] not in states:
            check(False, f"사건 #{iid} 가 {states} 로 가야 하는데 {d['state']}", str(d.get('closeReason')) + ' ' + str([e['type'] for e in d['events']]))
        return None
    return wait(f, timeout, f'사건 #{iid} → {"/".join(states)}', every=3)


def last_incident_id(user):
    s, l = user.get('/api/incidents?state=all&limit=1')
    return l[0]['incidentId'] if l else 0


def launcher(user, rid):
    s, st = user.get(f'/api/robots/{rid}/status')
    return st.get('launcher') or {}


def scenario_fire(sup, user, dash, rid, by, skip_preempt):
    ok, out = tool('fire', 'list')
    check(ok, '화재 자리 목록(fire.sh list)')
    import json
    spots = list(json.loads(out[out.index('{'):out.rindex('}') + 1])['spots'].keys())
    check(len(spots) >= 2, f'화재 자리 2곳 이상: {spots}')
    close_open_incidents(sup)
    tool('fire', 'clear')
    check(launcher(user, rid).get('ready') is True, '투척 기구(모의) 준비됨')

    print('\n[소화액 투척] 1. 사람 승인 모드')
    set_mode(sup, 'APPROVAL')
    base = last_incident_id(user)
    left = launcher(user, rid).get('remaining')
    check(tool('fire', 'place', spots[0], 'emergency', '--detect')[0], f'{spots[0]} 에 열화상 인쇄물(비상) 세우고 감지 보고')
    inc = wait_incident(user, base)
    iid = inc['incidentId']
    check(inc['launchMode'] == 'APPROVAL' and inc['grade'] == 'EMERGENCY', f'사건 #{iid} (승인 모드 · 비상)')
    s, alerts = user.get('/api/alerts')
    check(any(a['type'] == 'FIRE_DETECTED' and a['ref_id'] == iid and a['grade'] == 'EMERGENCY' for a in alerts), '비상 경고 FIRE_DETECTED 열림')
    d = wait_state(user, iid, ('AWAITING_APPROVAL',))
    print('     기록:', ' → '.join(e['type'] for e in d['events']))
    print('     재판독:', d['recheck'])
    check(d['recheck'].get('grade') == 'EMERGENCY', '도착 후 재판독 = 비상')
    check(d['images']['recheck'], '재판독 사진 저장')
    s, t = user.get(f"/api/inspections/{d['taskId']}")
    check(t.get('kind') == 'RESPONSE' and any(e['type'] == 'HOLDING' for e in t['events']), f"출동 작업 #{d['taskId']} 이 투척 위치에서 대기(HOLDING)")
    check(launcher(user, rid).get('remaining') == left, '승인 전에는 쏘지 않음')
    s, ov = user.get('/api/dashboard/overview')
    check(any(i['incidentId'] == iid for i in ov['incidents']) and ov['launchMode'] == 'APPROVAL', '대시보드에 사건 · 투척 모드 표시')
    s, _ = dash.post(f'/api/incidents/{iid}/dismiss')
    check(s == 403, '대시보드 계정은 사건을 닫을 수 없음(조회 전용)')
    s, d = dash.post(f'/api/incidents/{iid}/approve')
    check(s == 200 and d['approvedBy'] == 'dash1', '대시보드 계정이 투척 승인(조회 전용의 예외)')
    d = wait_state(user, iid, ('MONITORING', 'RESOLVED'), timeout=60)
    check(any(e['type'] == 'LAUNCHED' for e in d['events']), '투척 완료')
    check(d['state'] == 'MONITORING', '열원이 남아 있어 현장 감시로 넘어감')
    if left is not None and left >= 0:
        check(launcher(user, rid).get('remaining') == left - 1, f'모의 기구의 남은 수 {left} → {left - 1}')
    s, _ = user.post(f'/api/incidents/{iid}/resolve')
    check(s == 403, '조치 완료는 3 사용자에게 거부')
    s, d = sup.post(f'/api/incidents/{iid}/resolve', {'comment': 'e2e 조치 완료'})
    check(s == 200 and d['state'] == 'RESOLVED', '1 관리자가 조치 완료로 닫음')
    wait(lambda: (lambda s, t: t['status'] in TERMINAL)(*user.get(f"/api/inspections/{d['taskId']}")), 30, '출동 작업 종료(로봇 풀림)')
    s, alerts = user.get('/api/alerts')
    check(not any(a['type'] == 'FIRE_DETECTED' and a['ref_id'] == iid for a in alerts), '사건 경고 해제')
    tool('fire', 'clear')

    print('[소화액 투척] 2. 자동 투척 모드')
    set_mode(sup, 'AUTO')
    base = last_incident_id(user)
    check(tool('fire', 'place', spots[1], 'emergency', '--detect')[0], f'{spots[1]} 에 인쇄물(비상) + 감지 보고')
    iid = wait_incident(user, base)['incidentId']
    d = wait_state(user, iid, ('MONITORING', 'RESOLVED'))
    types = [e['type'] for e in d['events']]
    print('     기록:', ' → '.join(types))
    check('LAUNCH_ORDERED' in types and 'APPROVED' not in types, '승인 없이 자동 투척')
    check(d['recheck'].get('grade') == 'EMERGENCY' and d['recheck'].get('aimed') is True, f"재판독 비상 + 조준 범위 안 ({d['recheck'].get('bearingDeg')}°)")
    check(d['images']['after'], '투척 후 사진 저장')
    # 현장 감시: 로봇이 그 자리에 머물며 계속 찍는다 → 열원이 사라지면 스스로 닫는다
    first_at = d['afterCheck'].get('at')
    m = wait(lambda: (lambda s, x: x if x['state'] == 'MONITORING' and x['afterCheck'].get('at') != first_at
                      and x['afterCheck'].get('checks', 0) >= 2 else None)(*user.get(f'/api/incidents/{iid}')), 60, '현장 감시 중 다시 촬영 · 판독')
    s, t = user.get(f"/api/inspections/{m['taskId']}")
    check(t['status'] not in TERMINAL and m['afterCheck'].get('grade') == 'EMERGENCY', '로봇이 자리를 지키고 있고 열원은 그대로(비상)')
    check(tool('fire', 'place', spots[1], 'normal')[0], '열원이 사라짐(인쇄물을 열원 없는 것으로 교체)')
    d = wait_state(user, iid, ('RESOLVED',), timeout=120)
    print('     기록:', ' → '.join(e['type'] for e in d['events']))
    check(d['closedBy'] == 'SYSTEM' and '열원이 사라짐' in (d['closeReason'] or ''), f"감시 중 열원이 사라져 스스로 닫음 ({d['closeReason']})")
    wait(lambda: (lambda s, t: t['status'] in TERMINAL)(*user.get(f"/api/inspections/{d['taskId']}")), 30, '출동 작업 종료(로봇 풀림)')
    tool('fire', 'clear')

    print('[소화액 투척] 3. 오탐: 가 보니 열원이 없음(자동 모드여도 쏘지 않는다)')
    base = last_incident_id(user)
    left = launcher(user, rid).get('remaining')
    check(tool('fire', 'place', spots[0], 'normal')[0] and tool('fire', 'detect', spots[0], 'emergency')[0], f'{spots[0]} 에 열원 없는 인쇄물 + 비상 감지 보고')
    iid = wait_incident(user, base)['incidentId']
    d = wait_state(user, iid, ('DISMISSED',))
    print('     기록:', ' → '.join(e['type'] for e in d['events']))
    check(d['closedBy'] == 'SYSTEM' and launcher(user, rid).get('remaining') == left, '재판독 정상 → 쏘지 않고 오탐으로 닫음')
    tool('fire', 'clear')

    if not skip_preempt:
        print('[소화액 투척] 4. 점검 중 가로채기')
        set_mode(sup, 'APPROVAL')
        s, t = user.post('/api/inspections', {'robotId': rid, 'pointIds': [by['P1'], by['P3'], by['P4']], 'note': '가로채기 대상 점검'})
        check(s == 201, f"점검 작업 #{t['task_id']} 시작")
        wait(lambda: (lambda s, x: x['status'] == 'RUNNING')(*user.get(f"/api/inspections/{t['task_id']}")), 120, '점검 진행 중')
        base = last_incident_id(user)
        check(tool('fire', 'place', spots[1], 'emergency', '--detect')[0], '점검 중 화재 감지 보고')
        iid = wait_incident(user, base)['incidentId']
        d = wait_state(user, iid, ('AWAITING_APPROVAL',))
        types = [e['type'] for e in d['events']]
        print('     기록:', ' → '.join(types))
        s, x = user.get(f"/api/inspections/{t['task_id']}")
        check('PREEMPTED' in types and x['status'] == 'CANCELLED', f"점검 작업 #{t['task_id']} 을 멈추고 출동")
        s, d = sup.post(f'/api/incidents/{iid}/dismiss', {'comment': 'e2e 종료'})
        check(d['state'] == 'DISMISSED', '사건 닫기')
        tool('fire', 'clear')

    print('[소화액 투척] 5. 닫은 뒤에도 감지가 계속되면 다시 연다')
    set_mode(sup, 'APPROVAL')
    s, st = sup.call('PUT', '/api/settings/incident.reopen_grace_sec', {'value': 5})
    check(s == 200, '다시 여는 유예 = 5초(시험용)')
    try:
        det = f'--id=e2e-reopen-{int(time.time())}'
        base = last_incident_id(user)
        check(tool('fire', 'place', spots[0], 'emergency')[0] and tool('fire', 'detect', spots[0], 'emergency', det)[0],
              f'{spots[0]} 에 인쇄물(비상) + 감지 보고')
        first = wait_incident(user, base)['incidentId']
        s, d = sup.post(f'/api/incidents/{first}/dismiss', {'comment': 'e2e: 불이 남아 있는데 닫음'})
        check(d['state'] == 'DISMISSED', f'사건 #{first} 을 사람이 닫음(열원은 그대로)')
        time.sleep(17)       # 유예(5초)와 로봇 쪽 재전달 간격(15초)이 지나도록
        check(tool('fire', 'detect', spots[0], 'emergency', det)[0], '같은 감지가 계속 옴(같은 detId)')
        again = wait_incident(user, first, timeout=30)
        s, d = user.get(f"/api/incidents/{again['incidentId']}")
        types = [e['type'] for e in d['events']]
        check('REOPENED' in types, f"새 사건 #{again['incidentId']} 으로 다시 열림 (기록: {' → '.join(types)})")
        s, alerts = user.get('/api/alerts?state=OPEN')
        check(any(a['type'] == 'FIRE_DETECTED' and a['ref_id'] == again['incidentId'] and a['grade'] == 'EMERGENCY' for a in alerts),
              '비상 경고가 다시 열림')
        sup.post(f"/api/incidents/{again['incidentId']}/dismiss", {'comment': 'e2e 종료'})
    finally:
        sup.call('PUT', '/api/settings/incident.reopen_grace_sec', {'value': 60})
        tool('fire', 'clear')

    set_mode(sup, 'APPROVAL')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--only', choices=['rules', 'fire'])
    ap.add_argument('--skip-preempt', action='store_true')
    a = ap.parse_args()
    demo = ENV.get('DEMO_USERS_PASSWORD', 'User1234!')
    admin = login(ENV.get('INITIAL_ADMIN_LOGIN', 'admin'), ENV.get('INITIAL_ADMIN_PASSWORD', 'Admin1234!'))
    user = login('user1', demo)
    sup = login('sup1', demo)
    # 서비스를 막 다시 띄운 직후에는 로봇 연결(rosbridge)이 잡힐 때까지 잠깐 걸린다
    robot = wait(lambda: (lambda s, robots: next((r for r in robots if r['enabled'] and r['connected']
                                                  and r['adapterType'] == 'ROSBRIDGE'), None) if s == 200 else None)(
        *user.get('/api/robots')), 90, '연결된 로봇 찾기')
    rid = robot['robotId']
    s, pts = wait(lambda: (lambda s, p: (s, p) if s == 200 else None)(*user.get('/api/points')), 60, '점검 지점 조회')
    by = {p['code']: p['point_id'] for p in pts}
    check({'P1', 'P2', 'P3', 'P4'} <= set(by), f"로봇 {robot['code']} 연결, 점검 지점 P1~P4")
    try:
        if a.only in (None, 'rules'):
            scenario_rules(admin, user, rid, by)
        if a.only in (None, 'fire'):
            scenario_fire(sup, user, login('dash1', demo), rid, by, a.skip_preempt)
    finally:
        tool('target', 'reset')
        tool('fire', 'clear')
    import e2e_test
    print(f'\n통과: {e2e_test.passed}개 확인')


if __name__ == '__main__':
    main()
