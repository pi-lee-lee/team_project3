"""판독기 시험: Pillow 로 시뮬레이션 대상의 생김새를 그린 합성 사진(640×480, JPEG 한 번 거침)으로 검사한다.

실행(pytest 없이): python tests/test_checkers.py
컨테이너: docker compose run --rm --no-deps -v ./web/python/analysis-service/tests:/tests:ro analysis-service python /tests/test_checkers.py
"""
import io
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.getcwd()
sys.path[:0] = [os.path.join(HERE, '..', 'src'), '/app']

import numpy as np  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

from checkers import CHECKERS, Frame, Reading, describe, grade, run_rule, run_rules, unknown_results  # noqa: E402

W, H = 640, 480
WALL = (150, 150, 150)


def canvas(wall=WALL):
    img = Image.new('RGB', (W, H), wall)
    return img, ImageDraw.Draw(img)


def frame(img, camera_frame='RGB', camera=None):
    """JPEG 로 한 번 저장했다 읽는다(실제 사진과 같은 잡음)."""
    buf = io.BytesIO()
    img.save(buf, 'JPEG', quality=85)
    return Frame.from_bytes(buf.getvalue(), camera_frame, camera)


def shade(img, k):
    """전체를 조금 어둡게(음영)."""
    return Image.fromarray((np.asarray(img).astype(np.float32) * k).astype(np.uint8))


# ------------------------------------------------------------------ 그리기
def draw_gauge(value, cx=320, cy=240, r=90, squash=1.0):
    """흰 원판 + 검은 테두리 + 빨간 바늘 + 파란 허브. squash<1 이면 가로로 눌린 모습(비스듬히 봄)."""
    img, d = canvas()
    rx = r * squash
    d.ellipse([cx - rx, cy - r, cx + rx, cy + r], fill=(255, 255, 255), outline=(0, 0, 0), width=max(2, r // 15))
    a = math.radians(225 - value * 270)
    d.line([cx, cy, cx + 0.8 * rx * math.cos(a), cy - 0.8 * r * math.sin(a)], fill=(255, 0, 0), width=max(3, r // 10))
    hub = max(3, r // 9)
    d.ellipse([cx - hub * squash, cy - hub, cx + hub * squash, cy + hub], fill=(0, 0, 255))
    return img


def draw_dial(value, cx=320, cy=240, r=100, squash=1.0, wall=(235, 235, 230), labels=True):
    """실물 압력계 인쇄물: 흰 판 + 굵은 검은 테두리 + 빨강·초록·빨강 구간 + 검은 눈금·숫자 + 검은 바늘·허브.
    눈금은 225°(값 0)에서 시계 방향으로 -45°(값 1)까지. 초록 구간은 0.3~0.7."""
    img, d = canvas(wall)
    rx = r * squash

    def pt(rho, deg):
        a = math.radians(deg)
        return cx + rho * rx * math.cos(a), cy - rho * r * math.sin(a)

    def ang(val):
        return 225 - val * 270

    d.ellipse([cx - rx, cy - r, cx + rx, cy + r], fill=(0, 0, 0))
    d.ellipse([cx - 0.92 * rx, cy - 0.92 * r, cx + 0.92 * rx, cy + 0.92 * r], fill=(255, 255, 255))
    for lo, hi, col in ((0.0, 0.3, (220, 30, 30)), (0.3, 0.7, (30, 170, 60)), (0.7, 1.0, (220, 30, 30))):
        steps = int((hi - lo) * 120) + 2
        outer = [pt(0.9, ang(lo + (hi - lo) * i / (steps - 1))) for i in range(steps)]
        inner = [pt(0.8, ang(hi - (hi - lo) * i / (steps - 1))) for i in range(steps)]
        d.polygon(outer + inner, fill=col)
    for i in range(11):
        d.line([pt(0.68, ang(i / 10)), pt(0.78, ang(i / 10))], fill=(0, 0, 0), width=2 if i % 5 else 4)
    if labels:
        for i in (0, 5, 10):
            x, y = pt(0.55, ang(i / 10))
            d.text((x - 5, y - 6), str(i / 10 * 2)[:3], fill=(0, 0, 0))
        d.text((cx - 12, cy + 0.35 * r), 'MPa', fill=(0, 0, 0))
    a = ang(value)
    w = max(3, r // 20)
    d.line([pt(-0.15, a), pt(0.75, a)], fill=(10, 10, 10), width=w)
    hub = 0.08
    d.ellipse([cx - hub * rx, cy - hub * r, cx + hub * rx, cy + hub * r], fill=(10, 10, 10))
    return img


def test_gauge_dial():
    rule = {'ruleId': 11, 'kind': 'GAUGE', 'params': {'style': 'dial', 'unit': 'MPa', 'maxValue': 2},
            'grading': {'type': 'ranges', 'ranges': [{'min': 0.6, 'max': 1.4, 'grade': 'NORMAL'}], 'default': 'EMERGENCY'}}
    cases = [('가운데·큼', dict(), None), ('작음', dict(cx=180, cy=150, r=55), None),
             ('비스듬히(가로 0.7배)', dict(squash=0.7), None), ('어두운 음영(0.7배)', dict(), 'shade'),
             ('영역 지정', dict(cx=470, cy=300, r=80), [0.5, 0.3, 1.0, 1.0])]
    zones = {0.1: 'red', 0.5: 'green', 0.9: 'red'}
    for name, kw, region in cases:
        for v in (0.1, 0.5, 0.9):
            img = draw_dial(v, **kw)
            rl = dict(rule)
            if region == 'shade':
                img = shade(img, 0.7)
            elif region:
                rl['regions'] = {'INSPECTOR': region}
            out = run_rule(frame(img), rl, 'INSPECTOR')
            assert out['value'] is not None, (name, v, out)
            assert abs(out['value'] - v * 2) <= 0.08, (name, v, out)
            assert out['grade'] == ('NORMAL' if v == 0.5 else 'EMERGENCY'), (name, v, out)
            assert out['evidence']['zoneColor'] == zones[v], (name, v, out)
            print(f'dial {name}: 기대 {v * 2:.1f} → {out["value"]} (각도 {out["evidence"]["angleDeg"]}°, '
                  f'구간 {out["evidence"]["zoneColor"]}, {out["grade"]})')
    # 계기판이 없으면(빈 벽, 검은 막대 하나) 못 찾음
    img, d = canvas((235, 235, 230))
    d.line([100, 200, 400, 220], fill=(0, 0, 0), width=8)
    for im in (canvas((235, 235, 230))[0], img):
        out = run_rule(frame(im), rule)
        assert out['grade'] == 'UNKNOWN' and 'located' not in out, out
    print('dial 없음: ok')


def draw_zone_gauge(value, cx=320, cy=240, r=150, squash=1.0, wall=(225, 225, 228), bezel=False):
    """시연 압력계: 흰 판 + 검은 테두리 + 굵은 초록(0~0.6) · 노랑(0.6~0.8) · 빨강(0.8~1.0) 띠(0.62~0.92) + 검은 바늘(0.78).
    bezel: 화면 둘레에 모니터 틀 같은 큰 검은 테두리(dial 방식이 테두리로 오인하던 것)."""
    img, d = canvas(wall)
    if bezel:
        d.rectangle([0, 0, W - 1, H - 1], outline=(15, 15, 15), width=40)
    rx = r * squash

    def pt(rho, deg):
        a = math.radians(deg)
        return cx + rho * rx * math.cos(a), cy - rho * r * math.sin(a)

    def ang(val):
        return 225 - val * 270

    d.ellipse([cx - rx, cy - r, cx + rx, cy + r], fill=(20, 20, 20))
    d.ellipse([cx - 0.92 * rx, cy - 0.92 * r, cx + 0.92 * rx, cy + 0.92 * r], fill=(250, 250, 247))
    for lo, hi, col in ((0.0, 0.6, (20, 165, 60)), (0.6, 0.8, (250, 195, 0)), (0.8, 1.0, (225, 25, 25))):
        steps = int((hi - lo) * 120) + 2
        outer = [pt(0.92, ang(lo + (hi - lo) * i / (steps - 1))) for i in range(steps)]
        inner = [pt(0.62, ang(hi - (hi - lo) * i / (steps - 1))) for i in range(steps)]
        d.polygon(outer + inner, fill=col)
    for k in (0.0, 0.6, 0.8, 1.0):
        d.line([pt(0.6, ang(k)), pt(0.92, ang(k))], fill=(20, 20, 20), width=max(2, r // 30))
    a = ang(value)
    d.line([pt(-0.15, a), pt(0.78, a)], fill=(10, 10, 10), width=max(4, r // 14))
    d.ellipse([cx - 0.11 * rx, cy - 0.11 * r, cx + 0.11 * rx, cy + 0.11 * r], fill=(10, 10, 10))
    return img


def test_gauge_zone():
    rule = {'ruleId': 12, 'kind': 'GAUGE', 'params': {'style': 'zone', 'unit': 'MPa'},
            'grading': {'type': 'ranges', 'ranges': [{'min': 0.0, 'max': 0.6, 'grade': 'NORMAL'}], 'default': 'WARNING'}}
    zones = {0.35: 'green', 0.7: 'yellow', 0.9: 'red'}
    cases = [('가운데·큼', dict(), None), ('작음', dict(cx=200, cy=170, r=70), None),
             ('비스듬히(가로 0.75배)', dict(squash=0.75), None), ('어두운 음영(0.7배)', dict(), 'shade'),
             ('모니터 틀 같은 검은 테두리', dict(bezel=True, r=120), None),
             ('아래에 큰 노란 함(시뮬레이션 P4)', dict(cy=130, r=80), 'box')]
    for name, kw, how in cases:
        for v, z in zones.items():
            img = draw_zone_gauge(v, **kw)
            if how == 'shade':
                img = shade(img, 0.7)
            if how == 'box':                          # 계기판보다 훨씬 큰 같은 색 물체가 옆에 있어도 띠만 골라야 한다
                ImageDraw.Draw(img).rectangle([60, 230, 580, 400], fill=(180, 170, 60))
            out = run_rule(frame(img), rule)
            assert out['value'] is not None and abs(out['value'] - v) <= 0.05, (name, v, out)
            assert out['evidence']['zoneColor'] == z, (name, v, out)
            assert out['grade'] == ('NORMAL' if v < 0.6 else 'WARNING'), (name, v, out)
            print(f'zone {name}: 기대 {v} → {out["value"]} 구간 {out["evidence"]["zoneColor"]} {out["grade"]}')
    # 압력계가 아닌 것: 빈 벽, 검은 막대, 모니터 틀만, 색 순서가 다른 계기판(dial 시험판: 빨강·초록·빨강), 무지개 열화상
    img, d = canvas((225, 225, 228))
    d.line([100, 200, 400, 220], fill=(0, 0, 0), width=8)
    bezel, bd = canvas((225, 225, 228))
    bd.rectangle([0, 0, W - 1, H - 1], outline=(15, 15, 15), width=40)
    for what, im in (('빈 벽', canvas((225, 225, 228))[0]), ('검은 막대', img), ('모니터 틀만', bezel),
                     ('색 순서가 다른 계기판', draw_dial(0.5)), ('무지개 열화상', draw_thermal_rainbow(0.08))):
        out = run_rule(frame(im), rule)
        assert out['grade'] == 'UNKNOWN' and out['value'] is None, (what, out)
    print('zone 압력계 아님(빈 벽 · 막대 · 모니터 틀 · 다른 계기판 · 열화상): 찾지 못함 ok')


def draw_lamp(color, cx=320, cy=240, r=26):
    img, d = canvas()
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color)
    return img


def draw_thermal(hot_fraction, x=200, y=150, w=240, h=180, wall=WALL, skew=0):
    """진보라 판 위에 주황 → 노랑 → 흰색이 겹친 뜨거운 부분. skew: 오른쪽 변이 위아래로 줄어드는 원근."""
    img, d = canvas(wall)
    d.polygon([(x, y), (x + w, y + skew), (x + w, y + h - skew), (x, y + h)], fill=(40, 0, 80))
    if hot_fraction > 0:
        area = w * (h - skew) * hot_fraction          # 판 넓이(사다리꼴) × 비율
        r = math.sqrt(area / math.pi)
        cx, cy = x + w * 0.45, y + h * 0.5
        for k, c in ((1.0, (255, 120, 0)), (0.6, (255, 230, 0)), (0.3, (255, 255, 255))):
            d.ellipse([cx - r * k, cy - r * k, cx + r * k, cy + r * k], fill=c)
    return img


def draw_object(x=None, y=180, w=60, h=140):
    img, d = canvas()
    if x is not None:
        d.rectangle([x, y, x + w, y + h], fill=(255, 0, 0))
    return img


# ------------------------------------------------------------------ 시험
def test_grade():
    m = {'type': 'map', 'map': {'green': 'NORMAL', 'red': 'EMERGENCY'}, 'default': 'WARNING'}
    assert grade(Reading('green'), m) == 'NORMAL'
    assert grade(Reading('blue'), m) == 'WARNING'
    assert grade(Reading('blue'), {'type': 'map', 'map': {}}) == 'UNKNOWN'
    r = {'type': 'ranges', 'ranges': [{'min': 0.7, 'max': 0.98, 'grade': 'NORMAL'}, {'min': 0.5, 'max': 0.7, 'grade': 'WARNING'}],
         'default': 'EMERGENCY'}
    assert grade(Reading(0.7), r) == 'NORMAL'          # min 이상
    assert grade(Reading(0.98), r) == 'EMERGENCY'      # max 미만
    assert grade(Reading(0.6), r) == 'WARNING'
    assert grade(Reading(0.1), r) == 'EMERGENCY'
    assert grade(Reading(0.005), {'type': 'ranges', 'ranges': [{'max': 0.01, 'grade': 'NORMAL'}]}) == 'NORMAL'
    assert grade(Reading(None), r) == 'UNKNOWN'
    assert grade(Reading('green'), r) == 'UNKNOWN'
    assert grade(Reading(0.5), None) == 'UNKNOWN'
    print('grade: ok')


def test_gauge():
    rule = {'ruleId': 1, 'kind': 'GAUGE', 'params': {'unit': 'MPa'},
            'grading': {'type': 'ranges', 'ranges': [{'min': 0.3, 'max': 0.7, 'grade': 'NORMAL'}], 'default': 'WARNING'}}
    cases = [('가운데·큼', dict(), None), ('작고 왼쪽 위', dict(cx=140, cy=120, r=40), None),
             ('오른쪽·영역 지정', dict(cx=480, cy=300, r=60), [0.55, 0.35, 0.95, 0.9]),
             ('비스듬히(가로 0.8배)', dict(squash=0.8), None), ('어두운 음영(0.75배)', dict(), 'shade')]
    for name, kw, region in cases:
        for v in (0.1, 0.5, 0.9):
            img = draw_gauge(v, **kw)
            rl = dict(rule)
            if region == 'shade':
                img = shade(img, 0.75)
            elif region:
                rl['regions'] = {'INSPECTOR': region}
            out = run_rule(frame(img), rl, 'INSPECTOR')
            assert out['value'] is not None, (name, v, out)
            assert abs(out['value'] - v) <= 0.05, (name, v, out)
            assert out['unit'] == 'MPa' and out['grade'] == ('NORMAL' if v == 0.5 else 'WARNING'), out
            assert {'center', 'angleDeg', 'needleTip'} <= set(out['evidence']) and 'bbox' in out['located'], out
            print(f'gauge {name}: 기대 {v} → {out["value"]} (각도 {out["evidence"]["angleDeg"]}°, {out["grade"]})')
    # 다른 눈금: 반원(180° → 0°), 0~10
    out = run_rule(frame(draw_gauge(0.5)), {'kind': 'GAUGE', 'params': {'minAngle': 180, 'maxAngle': 0, 'maxValue': 10}})
    assert abs(out['value'] - 5.0) <= 0.3, out
    # 눈금 범위 밖(아래쪽 270°)을 가리키면 UNKNOWN
    img, d = canvas()
    d.ellipse([230, 150, 410, 330], fill=(255, 255, 255), outline=(0, 0, 0), width=6)
    d.line([320, 240, 320, 310], fill=(255, 0, 0), width=9)
    d.ellipse([310, 230, 330, 250], fill=(0, 0, 255))
    out = run_rule(frame(img), rule)
    assert out['grade'] == 'UNKNOWN' and out['value'] is None and '범위 밖' in out['reason'], out
    # 계기판이 없으면 못 찾음
    out = run_rule(frame(canvas()[0]), rule)
    assert out['grade'] == 'UNKNOWN' and 'located' not in out, out
    print('gauge 범위 밖·없음: ok')


def test_lamp():
    rule = {'ruleId': 2, 'kind': 'LAMP', 'regions': {'INSPECTOR': [0.3, 0.25, 0.7, 0.75]},
            'grading': {'type': 'map', 'map': {'green': 'NORMAL', 'yellow': 'WARNING', 'red': 'EMERGENCY', 'off': 'WARNING'}}}
    colors = {'green': (0, 255, 0), 'yellow': (255, 220, 0), 'red': (255, 0, 0), 'off': (40, 40, 40)}
    for name, c in colors.items():
        for kw, k in ((dict(), 1.0), (dict(cx=250, cy=200, r=14), 0.8)):     # 기본 / 작고 치우치고 어두움
            out = run_rule(frame(shade(draw_lamp(c, **kw), k)), rule, 'INSPECTOR')
            assert out['value'] == name, (name, kw, out)
            assert out['grade'] == rule['grading']['map'][name], out
            assert ('located' in out) == (name != 'off'), out
            print(f'lamp {name} (r={kw.get("r", 26)}): {out["value"]} {out["grade"]} 신뢰도 {out["confidence"]} {out["evidence"]["areaRatios"]}')
    # 영역 밖의 등은 세지 않는다
    out = run_rule(frame(draw_lamp((255, 0, 0), cx=60, cy=60)), rule, 'INSPECTOR')
    assert out['value'] == 'off', out
    # 색 범위를 설정으로 바꾼다(파랑 추가)
    out = run_rule(frame(draw_lamp((0, 0, 255))), {'kind': 'LAMP', 'params': {'colors': {'blue': {'h': [210, 270]}}}})
    assert out['value'] == 'blue', out
    print('lamp 영역 밖·색 설정: ok')


def test_thermal():
    rule = {'ruleId': 3, 'kind': 'THERMAL',
            'grading': {'type': 'ranges', 'ranges': [{'max': 0.01, 'grade': 'NORMAL'}, {'min': 0.01, 'max': 0.08, 'grade': 'WARNING'}],
                        'default': 'EMERGENCY'}}
    expect = {0.0: (0.0, 0.004, 'NORMAL'), 0.03: (0.02, 0.045, 'WARNING'), 0.15: (0.12, 0.18, 'EMERGENCY')}
    cases = [('회색 벽', dict()), ('흰 벽', dict(wall=(250, 250, 250))), ('작고 치우침', dict(x=60, y=60, w=160, h=120)),
             ('원근(사다리꼴)·흰 벽', dict(wall=(250, 250, 250), skew=20))]
    for name, kw in cases:
        for frac, (lo, hi, g) in expect.items():
            out = run_rule(frame(draw_thermal(frac, **kw)), rule, 'INSPECTOR')
            assert out['value'] is not None and lo <= out['value'] <= hi, (name, frac, out)
            assert out['grade'] == g and 'bbox' in out['located'], out
            assert (out['evidence']['hotBbox'] is None) == (frac == 0.0), out
            print(f'thermal {name}: 기대 {frac} → {out["value"]} {out["grade"]} 판 {out["located"]["bbox"]} 최고 {out["evidence"]["peak"]["value"]}')
    # 열화상 카메라 프레임: 프레임 전체가 대상
    for frac, (lo, hi, g) in expect.items():
        out = run_rule(frame(draw_thermal(frac, x=0, y=0, w=W, h=H), 'THERMAL'), rule)
        assert lo <= out['value'] <= hi and out['grade'] == g and out['located']['bbox'] == [0.0, 0.0, 1.0, 1.0], (frac, out)
        print(f'thermal 열화상 프레임: 기대 {frac} → {out["value"]} {out["grade"]}')
    # 인쇄물이 없으면(흰 벽만) 못 찾음. 뜨거운 영역으로 잘못 세지 않는다
    out = run_rule(frame(canvas((250, 250, 250))[0]), rule)
    assert out['grade'] == 'UNKNOWN' and out['value'] is None, out
    out = run_rule(frame(draw_thermal(0.03)), dict(rule, params={'palette': 'nope'}))
    assert out['grade'] == 'UNKNOWN' and '판독기 오류' in out['reason'], out
    print('thermal 없음·판독기 오류: ok')


def rainbow_rgb(t_c, lo=15.0, hi=300.0):
    """°C → 무지개 색표 색(시연 사진과 같은 15~300°C 로그 눈금)."""
    from checkers.thermal import PALETTES, relative
    u = relative(t_c, lo, hi, 'log')
    lut = PALETTES['rainbow']
    for (a, ca), (b, cb) in zip(lut[:-1], lut[1:]):
        if a <= u <= b:
            k = (u - a) / (b - a)
            return tuple(int(round(ca[i] + (cb[i] - ca[i]) * k)) for i in range(3))
    return lut[-1][1]


def draw_thermal_rainbow(hot_fraction, x=160, y=120, w=300, h=225, wall=(205, 205, 200)):
    """무지개 열화상 인쇄물: 방 온도(22°C) 바탕 위 가운데 아래에 뜨거운 부분(120°C 고리 · 250°C 심부),
    판 오른쪽 검은 띠 위에 온도 막대(위 = 300°C). 막대의 뜨거운 색은 판이 아니므로 세면 안 된다."""
    img, d = canvas(wall)
    d.rectangle([x, y, x + w, y + h], fill=rainbow_rgb(22))
    d.rectangle([x, y + h * 0.7, x + w, y + h], fill=rainbow_rgb(19))          # 바닥(조금 차가움)
    if hot_fraction > 0:
        r = math.sqrt(w * h * hot_fraction / math.pi)
        cx, cy = x + w * 0.5, y + h * 0.6
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=rainbow_rgb(120))
        d.ellipse([cx - r * 0.45, cy - r * 0.45, cx + r * 0.45, cy + r * 0.45], fill=rainbow_rgb(250))
    bx = x + w + 4                                                            # 판 옆 검은 띠 + 온도 막대
    d.rectangle([bx, y, bx + 26, y + h], fill=(0, 0, 0))
    for k in range(int(h) - 20):
        t = 300 - (300 - 15) * k / (h - 21)
        d.line([bx + 8, y + 10 + k, bx + 18, y + 10 + k], fill=rainbow_rgb(t))
    return img


def test_thermal_rainbow():
    rule = {'ruleId': 5, 'kind': 'THERMAL',
            'params': {'palette': 'rainbow', 'tempMin': 15, 'tempMax': 300, 'tempScale': 'log', 'hotC': 80},
            'grading': {'type': 'ranges', 'ranges': [{'max': 0.002, 'grade': 'NORMAL'},
                                                     {'min': 0.002, 'max': 0.03, 'grade': 'WARNING'}], 'default': 'EMERGENCY'}}
    for frac, (lo, hi, g) in {0.0: (0.0, 0.001, 'NORMAL'), 0.01: (0.006, 0.014, 'WARNING'), 0.08: (0.065, 0.095, 'EMERGENCY')}.items():
        for name, img in (('정면', draw_thermal_rainbow(frac)), ('어둡게', shade(draw_thermal_rainbow(frac), 0.8))):
            out = run_rule(frame(img), rule)
            ev = out['evidence']
            assert out['value'] is not None and lo <= out['value'] <= hi, (name, frac, out)
            assert out['grade'] == g, (name, frac, out)
            box = out['located']['bbox']
            assert box[2] <= (160 + 300 + 4) / W + 0.01, ('온도 막대가 판에 들어감', box)
            assert ev['hotC'] == 80.0, ev
            if frac:
                px, py = ev['peak']['point']                                   # 발화점 = 심부(판 가운데 아래)
                assert abs(px - (160 + 150) / W) < 0.03 and abs(py - (120 + 225 * 0.6) / H) < 0.03, ev['peak']
                if name == '정면':
                    assert 200 <= ev['peak']['celsius'] <= 300, ev['peak']
            print(f'thermal rainbow {name} {frac}: {out["value"]} {out["grade"]} 최고 {ev["peak"].get("celsius")}°C 판 {box}')
    from checkers.thermal import celsius, relative
    assert abs(float(celsius(relative(80, 15, 300, 'log'), 15, 300, 'log')) - 80) < 0.01
    print('thermal rainbow °C 변환: ok')


def test_object():
    region = [0.30, 0.30, 0.70, 0.95]
    rule = {'ruleId': 4, 'kind': 'OBJECT', 'params': {'label': 'fire_extinguisher', 'expect': 'PRESENT'},
            'regions': {'INSPECTOR': region, 'PATROL': [0.0, 0.0, 0.2, 0.2]},
            'grading': {'type': 'map', 'map': {'IN_REGION': 'NORMAL', 'OUT_OF_REGION': 'WARNING', 'MISSING': 'WARNING'},
                        'default': 'UNKNOWN'},
            'target': {'sizeM': 0.15}}
    cam = {'hfovDeg': 62.2}
    for name, x, value, g in (('영역 안', 300, 'IN_REGION', 'NORMAL'), ('영역 밖', 40, 'OUT_OF_REGION', 'WARNING'),
                              ('없음', None, 'MISSING', 'WARNING')):
        out = run_rule(frame(draw_object(x), camera=cam), rule, 'INSPECTOR')
        assert out['value'] == value and out['grade'] == g, (name, out)
        assert out['evidence']['expectedRegion'] == region and ('located' in out) == (x is not None), out
        print(f'object {name}: {out["value"]} {out["grade"]} 신뢰도 {out["confidence"]} {out.get("located")}')
    # 방향·거리: 폭 60px, 화각 62.2° → 초점거리 530px, 거리 0.15×530/60 ≈ 1.33m. 왼쪽에 있으면 방향 +
    out = run_rule(frame(draw_object(40), camera=cam), rule, 'INSPECTOR')
    rel = out['located']['relative']
    assert abs(rel['distance'] - 1.33) < 0.1 and rel['bearing'] > 0.3, out
    assert 'relative' not in run_rule(frame(draw_object(40)), rule, 'INSPECTOR')['located']
    # 로봇 종류별 영역, 영역 없음(사진 전체)
    assert run_rule(frame(draw_object(300)), rule, 'PATROL')['value'] == 'OUT_OF_REGION'
    assert run_rule(frame(draw_object(40)), rule, None)['value'] == 'IN_REGION'
    # 너무 작으면 못 찾은 것
    assert run_rule(frame(draw_object(300, w=12, h=20)), rule, 'INSPECTOR')['value'] == 'MISSING'
    # 없어야 하는 물체
    absent = dict(rule, params={'expect': 'ABSENT'}, grading={'type': 'map', 'map': {'ABSENT': 'NORMAL', 'PRESENT': 'WARNING'}})
    assert run_rule(frame(draw_object(300)), absent, 'INSPECTOR')['value'] == 'PRESENT'
    assert run_rule(frame(draw_object(40)), absent, 'INSPECTOR')['value'] == 'ABSENT'
    out = run_rule(frame(draw_object(None)), absent, 'INSPECTOR')
    assert out['value'] == 'ABSENT' and out['grade'] == 'NORMAL', out
    # 인식 모델 방식: 모델 이름이 없거나 파일이 없으면 그 규칙만 UNKNOWN(판독기 오류)
    out = run_rule(frame(draw_object(300)), dict(rule, params={'detector': 'model'}), 'INSPECTOR')
    assert out['grade'] == 'UNKNOWN' and '판독기 오류' in out['reason'], out
    out = run_rule(frame(draw_object(300)), dict(rule, params={'detector': 'model', 'model': '../x'}), 'INSPECTOR')
    assert out['grade'] == 'UNKNOWN' and '판독기 오류' in out['reason'], out
    print('object 방향·거리·ABSENT·model: ok')


def test_engine():
    kinds = [c['kind'] for c in describe()]
    assert kinds == ['OBJECT', 'GAUGE', 'LAMP', 'THERMAL'] and set(kinds) == set(CHECKERS), kinds
    for c in describe():
        assert c['valueType'] in ('number', 'label') and c['version']
        for name, prop in c['paramsSchema']['properties'].items():
            assert prop.get('title') and 'default' in prop, (c['kind'], name)
    rules = [{'ruleId': 1, 'kind': 'LAMP'}, {'ruleId': 2, 'kind': 'NOPE'},
             {'ruleId': 3, 'kind': 'OBJECT', 'regions': {'INSPECTOR': [0.5, 0.5, 0.2, 0.9]}}]
    out = run_rules(frame(draw_lamp((0, 255, 0))), rules, 'INSPECTOR')
    assert [o['ruleId'] for o in out] == [1, 2, 3]
    assert out[0]['value'] == 'green' and out[0]['grade'] == 'UNKNOWN'          # grading 없음
    assert out[1]['grade'] == 'UNKNOWN' and '알 수 없는 판독 종류' in out[1]['reason']
    assert out[2]['grade'] == 'UNKNOWN' and '판독기 오류' in out[2]['reason']    # 잘못된 영역은 그 규칙만
    u = unknown_results(rules, '사진 품질 불량')
    assert all(x['grade'] == 'UNKNOWN' and x['reason'] == '사진 품질 불량' for x in u) and u[0]['checkerVersion'] == 'lamp-1'
    import json
    json.dumps(out)       # 결과는 JSON 으로 나갈 수 있어야 한다
    print('engine: ok')


if __name__ == '__main__':
    for t in (test_grade, test_gauge, test_gauge_dial, test_gauge_zone, test_lamp, test_thermal, test_thermal_rainbow, test_object, test_engine):
        t()
    print('ALL OK')
