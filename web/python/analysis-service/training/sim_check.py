#!/usr/bin/env python3
"""시뮬레이션에서 소화기 인식 모델(fire_v1)을 끝까지 시험한다(Windows·WSL 어디서든, 스택이 떠 있어야 함).

    python web/python/analysis-service/training/sim_check.py            # 규칙 준비 → P1, P2 점검 → 판독 결과 출력
    python web/python/analysis-service/training/sim_check.py --setup    # 규칙만 준비

월드(ros/sim/src/worlds/world_spec.py)에 실제 현장에서 찍은 사진 판 두 개가 걸려 있다.
    P1 = 생산동 서쪽 벽 "소화기 있음" 사진  → 기대: IN_REGION(정상)
    P2 = 랙 1 남쪽 면 "받침만 있음" 사진    → 기대: MISSING(경고)
지점은 DB 마이그레이션(V8)이 만든다. 규칙은 지점에 없으면 관리자 API 로 만든다(관리자 화면에서도 보이고 고칠 수 있다).
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / 'scripts'))
from e2e_test import ENV, Client   # noqa: E402

POINTS = {   # world_spec.POINTS 와 같은 값
    'P1': {'name': '소화기 앞', 'x': 3.95, 'y': 3.9, 'yawDeg': 180, 'expect': 'IN_REGION'},
    'P2': {'name': '소화기 빈 자리', 'x': 4.3, 'y': 3.5, 'yawDeg': 90, 'expect': 'MISSING'},
}
RULE = {
    'name': '소화기 제자리(인식 모델)',
    'kind': 'OBJECT',
    'params': {'detector': 'model', 'model': 'fire_v1', 'className': 'fire_extinguisher', 'expect': 'PRESENT',
               'label': '소화기', 'minConfidence': 0.4},
    'regions': {},
    'grading': {'type': 'map', 'map': {'IN_REGION': 'NORMAL', 'OUT_OF_REGION': 'WARNING', 'MISSING': 'WARNING'},
                'default': 'UNKNOWN'},
    'enabled': True,
}


def login(user, pw):
    c = Client()
    s, _ = c.post('/api/auth/login', {'loginId': user, 'password': pw})
    if s != 200:
        sys.exit(f'로그인 실패 {user} ({s})')
    return c


def setup(admin):
    s, pts = admin.get('/api/admin/points')
    by_code = {p['code']: p for p in pts}
    ids = {}
    for code, p in POINTS.items():
        if code not in by_code:
            s, d = admin.post('/api/admin/points', {'code': code, 'name': p['name'], 'description': '소화기 모델 시험용 사진 판',
                                                    'x': p['x'], 'y': p['y'], 'yawDeg': p['yawDeg']})
            if s not in (200, 201):
                sys.exit(f'지점 {code} 만들기 실패 ({s}): {d}')
            print(f'지점 {code} 만듦')
            by_code[code] = d
        ids[code] = by_code[code]['point_id']
        s, rules = admin.get(f"/api/points/{ids[code]}/rules")
        if s == 200 and any(r.get('kind') == 'OBJECT' and (r.get('params') or {}).get('detector') == 'model' for r in rules):
            continue
        s, d = admin.post(f"/api/admin/points/{ids[code]}/rules", RULE)
        if s not in (200, 201):
            sys.exit(f'규칙 만들기 실패 {code} ({s}): {d}')
        print(f'{code} 규칙 만듦')
    return ids


def main():
    admin = login(ENV.get('INITIAL_ADMIN_LOGIN', 'admin'), ENV.get('INITIAL_ADMIN_PASSWORD', 'Admin1234!'))
    ids = setup(admin)
    if '--setup' in sys.argv:
        return
    user = login('user1', 'User1234!')
    s, robots = user.get('/api/robots')
    rid = robots[0]['robotId']
    s, t = user.post('/api/inspections', {'robotId': rid, 'pointIds': [ids['P1'], ids['P2']], 'note': '소화기 모델 시험'})
    if s != 201:
        sys.exit(f'점검 시작 실패 ({s}): {t}')
    tid = t['task_id']
    print(f'점검 #{tid} 시작 (P1 → P2)')
    end = time.time() + 600
    while time.time() < end:
        s, d = user.get(f'/api/inspections/{tid}')
        if d.get('status') in ('COMPLETED', 'FAILED', 'CANCELLED', 'INTERRUPTED'):
            break
        time.sleep(5)
    print('점검 상태:', d.get('status'))
    ok = True
    for ob in d.get('observations') or d.get('points') or []:
        oid = ob.get('id') or ob.get('observation_id')
        code = ob.get('code') or ob.get('point_code')
        if ob.get('status') != 'CAPTURED':
            print(f"  ✗ {code}: 촬영하지 못함 ({ob.get('reason')})")
            ok = False
            continue
        res = []
        for _ in range(30):                      # 판독은 사진이 올라온 뒤 따로 돈다 → 결과가 올 때까지 기다림
            s, res = admin.get(f'/api/observations/{oid}/results')
            if s == 200 and res:
                break
            time.sleep(3)
        print(f'  사진: http://localhost/api/observations/{oid}/image (관리자 로그인 필요)')
        for r in res if s == 200 else []:
            value = r.get('value') if r.get('value') is not None else r.get('valueLabel', r.get('value_label'))
            r = {**r, 'value': value}
            exp = POINTS.get(code, {}).get('expect')
            mark = '✓' if r.get('value') == exp else '✗'
            ok &= r.get('value') == exp
            print(f"  {mark} {code}: {r.get('value')} / {r.get('grade')} (기대 {exp}) 신뢰도 {r.get('confidence')} — {r.get('reason')}")
    if not d.get('observations') and not d.get('points'):
        print('관측 목록을 찾지 못함. 응답 키:', list(d))
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
