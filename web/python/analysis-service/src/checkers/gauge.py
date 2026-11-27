"""GAUGE: 계기판 바늘 읽기.

대상: 판 위의 허브 점(기본 파랑)과 바늘 막대(기본 빨강).
허브색 덩어리의 무게중심 = 중심, 바늘색 덩어리의 무게중심 − 중심 = 바늘 방향.
각도는 화면 기준 수학 좌표(오른쪽 0°, 반시계 +, 화면 위쪽 +90°).
값 = minAngle 에서 시계 방향으로 바늘까지 돈 각 ÷ 전체 각 × (maxValue − minValue) + minValue.
비스듬히 보면 판이 타원으로 눌려 각도가 조금 틀어진다(보정하지 않는다).

style='dial'(실물·인쇄 압력계): 색 허브가 없고 바늘이 검다.
  1) 어두운 덩어리 중 가장 넓게 퍼진 것 = 테두리 고리. 그 외접 사각형으로 중심과 가로·세로 반지름(타원)을 얻는다.
  2) 타원을 원으로 펴서(가로 ÷ rx, 세로 ÷ ry) 반지름 0.2~0.65 띠 안의 어두운 픽셀을 각도별로 센다.
     바늘은 띠를 안쪽부터 바깥까지 곧게 가로지르므로, 차지하는 반지름 칸 수가 가장 많은 각도를 바늘로 본다
     (글자·눈금은 한 반지름에 몰려 있어 밀린다).
  3) 바늘 끝 바깥(반지름 0.8~0.95)의 색을 근거(zoneColor)로 함께 남긴다(초록·노랑·빨강 구간).
  타원을 원으로 펴므로 비스듬히 본 각도도 보정된다.
  한계: 실제 카메라 화면에서는 모니터 틀 · 그림자처럼 테두리보다 큰 어두운 덩어리가 있으면 그것을 테두리로 잡는다.

style='zone'(초록 · 노랑 · 빨강 구간 띠가 있는 압력계 — 시연 압력계): 어두운 덩어리 대신 색 띠로 계기판을 찾는다.
  1) 초록 · 노랑 · 빨강 덩어리(각각 가장 큰 것)의 픽셀에 타원(축 정렬)을 맞춰 중심과 반지름을 얻는다.
  2) 계기판으로 인정하는 조건(하나라도 어긋나면 '대상을 찾지 못함' → 판독 불가):
     - 세 색이 모두 있고, 색 픽셀이 둥근 띠 모양(중심에서 거의 같은 거리)에 놓이며, 눈금 방향으로 150° 넘게 퍼져 있다
     - 색 순서가 눈금을 따라 초록 → 노랑 → 빨강이다
     - 띠 안쪽이 흰 눈금판이다(밝고 색이 옅은 픽셀이 대부분)
     배경(모니터 틀 · 책상)이나 열화상 사진(세 색이 있지만 띠 · 순서 · 흰 판이 아님)은 여기서 걸러진다.
  3) 바늘은 dial 과 같은 방법(타원을 원으로 편 반지름 0.2~0.65 띠를 곧게 가로지르는 어두운 직선)으로 찾는다.
  4) 바늘이 가리키는 쪽의 색 띠 색을 바로 읽어 zoneColor 로 남긴다.
"""
from __future__ import annotations

import math

import numpy as np

from .base import BLUE, GREEN, RED, YELLOW, Frame, Located, Reading, blobs, color_mask, hsv_schema, ratio_box, ratio_point, region_px, to_hsv

OVERSHOOT = 0.05    # 눈금 범위를 이 비율까지 벗어난 것은 끝값으로 본다
BAND = (0.2, 0.65)  # dial: 바늘을 찾는 반지름 띠(테두리 반지름 대비)
ZONE = (0.8, 0.95)  # dial: 바늘 끝 바깥 색 구간을 보는 반지름 띠
ANGLE_BIN = 2.0     # dial: 각도 칸(도)
RADIAL_BINS = 9     # dial: 띠를 나눈 반지름 칸 수
# zone: 구간 띠 색(카메라 · 화면 색 틀어짐을 생각해 base 의 색보다 넉넉하게). 흰 판의 옅은 분홍 · 파랑 빛은 채도가 낮아 빠진다
ZONE_COLORS = (('green', {'h': [75, 165], 's': [0.35, 1.0], 'v': [0.25, 1.0]}),
               ('yellow', {'h': [35, 72], 's': [0.40, 1.0], 'v': [0.35, 1.0]}),
               ('red', {'h': [335, 25], 's': [0.40, 1.0], 'v': [0.25, 1.0]}))
ZONE_MIN_SPAN = 150.0        # zone: 색 띠가 눈금 방향으로 이만큼(도) 넘게 퍼져야 계기판
ZONE_RING_SPREAD = 0.45      # zone: 색 픽셀 반지름의 (90% − 10%) ÷ 가운데 값 상한(띠 모양인지)
ZONE_FACE_WHITE = 0.45       # zone: 띠 안쪽(반지름 0.25~0.55)에서 흰 픽셀 비율 하한
ZONE_LABEL = {'green': '정상 구간(초록)', 'yellow': '주의 구간(노랑)', 'red': '위험 구간(빨강)'}   # 판독 이유 글자


class GaugeChecker:
    kind = 'GAUGE'
    version = 'gauge-3'
    value_type = 'number'
    labels: list = []
    params_schema = {
        'type': 'object',
        'properties': {
            'style': {'type': 'string', 'enum': ['color', 'dial', 'zone'], 'default': 'color',
                      'title': '찾는 방식(color: 파란 허브·빨간 바늘(시뮬레이션), dial: 검은 테두리·검은 바늘(실물), '
                               'zone: 초록·노랑·빨강 구간 띠로 계기판을 찾고 검은 바늘을 읽음(시연 압력계))'},
            'darkV': {'type': 'number', 'title': 'dial: 검은색으로 보는 밝기 상한(0~1)', 'default': 0.4,
                      'minimum': 0, 'maximum': 1},
            'minAngle': {'type': 'number', 'title': '최소 눈금 각도(도, 오른쪽 0·반시계 +)', 'default': 225},
            'maxAngle': {'type': 'number', 'title': '최대 눈금 각도(도, 최소에서 시계 방향으로 돈다)', 'default': -45},
            'minValue': {'type': 'number', 'title': '최소 눈금 값', 'default': 0},
            'maxValue': {'type': 'number', 'title': '최대 눈금 값', 'default': 1},
            'unit': {'type': 'string', 'title': '단위', 'default': ''},
            'needle': hsv_schema('바늘 색 범위', RED),
            'hub': hsv_schema('허브(중심 점) 색 범위', BLUE),
            'minPixels': {'type': 'integer', 'title': '허브·바늘로 인정하는 최소 픽셀 수', 'default': 6, 'minimum': 1},
        },
    }

    def locate(self, frame: Frame, params: dict, region=None):
        x0, y0, x1, y1 = region_px(frame, region)
        hsv = to_hsv(frame.rgb[y0:y1, x0:x1])
        min_px = int(params.get('minPixels', 6))
        if params.get('style') == 'dial':
            return self._locate_dial(frame, hsv, (x0, y0), params, min_px)
        if params.get('style') == 'zone':
            return self._locate_zone(frame, hsv, (x0, y0), params, min_px)
        hubs = [b for b in blobs(color_mask(hsv, params.get('hub'), BLUE)) if b.count >= min_px]
        needles = [b for b in blobs(color_mask(hsv, params.get('needle'), RED)) if b.count >= min_px]
        if not hubs or not needles:
            return None
        hub = hubs[0]
        cx, cy = hub.centroid

        def gap(b):   # 허브 중심에서 그 덩어리의 가장 가까운 픽셀까지
            py, px = np.nonzero(b.mask)
            return float(np.hypot(px - cx, py - cy).min())

        needle = min(needles, key=gap)     # 영역 안에 다른 빨간 물체가 있어도 허브에 붙은 것을 바늘로 본다
        py, px = np.nonzero(needle.mask)
        dist = np.hypot(px - cx, py - cy)
        tip = int(dist.argmax())
        radius = float(dist[tip])
        r = radius * 1.15
        return Located(
            bbox=ratio_box(frame, x0 + cx - r, y0 + cy - r, x0 + cx + r, y0 + cy + r),
            confidence=min(1.0, 0.5 + needle.count / 400.0),
            data={'center': (x0 + cx, y0 + cy), 'needle': (x0 + needle.centroid[0], y0 + needle.centroid[1]),
                  'tip': (x0 + float(px[tip]), y0 + float(py[tip])), 'radius': radius})

    def _locate_dial(self, frame: Frame, hsv, origin, params: dict, min_px: int):
        h, s, v = hsv
        dark = v <= float(params.get('darkV', 0.4))
        cands = [b for b in blobs(dark) if b.count >= min_px * 10]
        if not cands:
            return None

        def spread(b):
            bx0, by0, bx1, by1 = b.bbox
            return (bx1 - bx0) * (by1 - by0)

        ring = max(cands, key=spread)                    # 테두리: 가장 넓게 퍼진 어두운 덩어리
        bx0, by0, bx1, by1 = ring.bbox
        rx, ry = (bx1 - bx0) / 2.0, (by1 - by0) / 2.0
        if min(rx, ry) < 12 or max(rx, ry) / min(rx, ry) > 3.0:
            return None                                  # 너무 작거나 너무 납작함 → 계기판 아님
        cx, cy = bx0 + rx, by0 + ry
        yy, xx = np.mgrid[0:dark.shape[0], 0:dark.shape[1]]
        nx_, ny_ = (xx - cx) / rx, -(yy - cy) / ry      # 원으로 편 좌표(위쪽 +)
        rho = np.hypot(nx_, ny_)
        theta = np.degrees(np.arctan2(ny_, nx_)) % 360.0
        # 테두리가 닫힌 고리인지: 반지름 0.9~1.1 의 어두운 픽셀이 대부분의 방향에 있어야 한다
        edge = dark & (rho > 0.85) & (rho < 1.1)
        if len(np.unique((theta[edge] // 10).astype(int))) < 30:
            return None
        found = _needle(dark, rho, theta, min_px)
        if found is None:
            return None
        angle, tip_r, near_n, sel_n = found
        ar = math.radians(angle)
        tip = (cx + tip_r * rx * math.cos(ar), cy - tip_r * ry * math.sin(ar))
        # 바늘 끝 바깥 색 구간
        zone_sel = (rho >= ZONE[0]) & (rho <= ZONE[1]) & (np.abs((theta - angle + 180.0) % 360.0 - 180.0) <= 6.0)
        zone = None
        if zone_sel.any():
            sub = (h[zone_sel], s[zone_sel], v[zone_sel])
            share = {name: float(color_mask(sub, None, rng).mean()) for name, rng in
                     (('green', GREEN), ('yellow', YELLOW), ('red', RED))}
            best = max(share, key=share.get)
            zone = best if share[best] >= 0.3 else None
        ox, oy = origin
        conf = 0.5 + 0.5 * min(1.0, near_n / max(1.0, sel_n) * 2)
        return Located(
            bbox=ratio_box(frame, ox + bx0, oy + by0, ox + bx1, oy + by1),
            confidence=min(1.0, conf),
            data={'center': (ox + cx, oy + cy), 'tip': (ox + tip[0], oy + tip[1]), 'angle': angle,
                  'radius': (rx, ry), 'zoneColor': zone})

    def _locate_zone(self, frame: Frame, hsv, origin, params: dict, min_px: int):
        h, s, v = hsv
        masks = {name: color_mask(hsv, None, rng) for name, rng in ZONE_COLORS}
        cands = {}
        for name, m in masks.items():
            found = [b.mask for b in blobs(m) if b.count >= min_px * 10][:3]
            if not found:
                return None                              # 세 색이 다 있어야 계기판
            cands[name] = found
        # 색마다 가장 큰 덩어리만 쓰면 주변의 같은 색 물체(노란 함, 옆에 걸린 열화상 사진 등)를 집는다
        # → 큰 것부터 3개씩 조합해 검사를 모두 통과한 것 가운데 가장 고르게 둥근 띠(퍼짐이 작은 것)를 쓴다
        best = None
        for g in cands['green']:
            for y in cands['yellow']:
                for r in cands['red']:
                    got = self._zone_from({'green': g, 'yellow': y, 'red': r}, frame, hsv, origin, params, min_px)
                    if got is not None and (best is None or got.data['ringSpread'] < best.data['ringSpread']):
                        best = got
        return best

    def _zone_from(self, parts, frame: Frame, hsv, origin, params: dict, min_px: int):
        h, s, v = hsv
        ys, xs = np.nonzero(parts['green'] | parts['yellow'] | parts['red'])
        if len(xs) < min_px * 30:
            return None
        fit = _fit_ellipse(xs.astype(np.float64), ys.astype(np.float64))
        if fit is None:
            return None
        cx, cy, ex, ey = fit
        r_band = np.hypot((xs - cx) / ex, (ys - cy) / ey)
        p10, p50, p90 = np.percentile(r_band, [10, 50, 90])
        spread = float((p90 - p10) / max(p50, 1e-6))
        if spread > ZONE_RING_SPREAD:
            return None                                  # 둥근 띠가 아님(넓게 흩어진 색)
        rx, ry = ex * p90 * 1.03, ey * p90 * 1.03        # 띠 바깥 끝 ≈ 테두리 반지름(dial 과 같은 기준)
        if min(rx, ry) < 12 or max(rx, ry) / min(rx, ry) > 3.0:
            return None
        min_a = float(params.get('minAngle', 225))
        total = (min_a - float(params.get('maxAngle', -45))) % 360.0 or 360.0

        def along(mask):                                 # 그 색 픽셀이 눈금을 따라 놓인 자리(0 ~ total 도)
            my, mx = np.nonzero(mask)
            a = np.degrees(np.arctan2(-(my - cy) / ry, (mx - cx) / rx))
            return (min_a - a) % 360.0
        pos = {name: along(m) for name, m in parts.items()}
        allpos = np.concatenate(list(pos.values()))
        allpos = allpos[allpos <= total * 1.05]
        if len(allpos) == 0 or np.percentile(allpos, 95) - np.percentile(allpos, 5) < ZONE_MIN_SPAN:
            return None                                  # 눈금 방향으로 충분히 퍼지지 않음
        med = {name: float(np.median(p)) for name, p in pos.items()}
        if not (med['green'] < med['yellow'] < med['red']):
            return None                                  # 초록 → 노랑 → 빨강 순서가 아님
        yy, xx = np.mgrid[0:h.shape[0], 0:h.shape[1]]
        nx_, ny_ = (xx - cx) / rx, -(yy - cy) / ry
        rho = np.hypot(nx_, ny_)
        theta = np.degrees(np.arctan2(ny_, nx_)) % 360.0
        face = (rho >= 0.25) & (rho <= 0.55)
        if face.sum() < min_px * 10 or float(((v > 0.5) & (s < 0.35))[face].mean()) < ZONE_FACE_WHITE:
            return None                                  # 띠 안쪽이 흰 눈금판이 아님
        dark = (v <= float(params.get('darkV', 0.4))) & (rho < 1.0)
        found = _needle(dark, rho, theta, min_px)
        if found is None:
            return None
        angle, tip_r, near_n, sel_n = found
        ar = math.radians(angle)
        tip = (cx + tip_r * rx * math.cos(ar), cy - tip_r * ry * math.sin(ar))
        # 바늘이 가리키는 쪽(±6°)의 색 띠에서 가장 많은 색(고른 띠 덩어리만 센다 — 둘레의 같은 색 물체는 빼고)
        side = np.abs((theta - angle + 180.0) % 360.0 - 180.0) <= 6.0
        counts = {name: int((m & side).sum()) for name, m in parts.items()}
        best = max(counts, key=counts.get)
        zone = best if counts[best] >= min_px else None
        ox, oy = origin
        conf = 0.5 + 0.5 * min(1.0, near_n / max(1.0, sel_n) * 2)
        return Located(
            bbox=ratio_box(frame, ox + cx - rx, oy + cy - ry, ox + cx + rx, oy + cy + ry),
            confidence=min(1.0, conf),
            data={'center': (ox + cx, oy + cy), 'tip': (ox + tip[0], oy + tip[1]), 'angle': angle,
                  'radius': (rx, ry), 'zoneColor': zone, 'ringSpread': spread})

    def read(self, frame: Frame, located: Located, params: dict) -> Reading:
        (cx, cy), tip = located.data['center'], located.data['tip']
        unit = params.get('unit') or None
        if 'angle' in located.data:                      # dial: 원으로 편 좌표에서 구한 각도
            angle = float(located.data['angle'])
            nx, ny = tip
        else:
            nx, ny = located.data['needle']
            angle = math.degrees(math.atan2(-(ny - cy), nx - cx))
        evidence = {'center': ratio_point(frame, cx, cy), 'angleDeg': round(angle, 1), 'needleTip': ratio_point(frame, *tip)}
        if 'zoneColor' in located.data:
            evidence['zoneColor'] = located.data['zoneColor']
        if math.hypot(nx - cx, ny - cy) < 2.0:
            return Reading(None, unit, 0.0, evidence, '바늘 방향을 알 수 없음(바늘이 너무 짧게 보임)')
        min_a, max_a = float(params.get('minAngle', 225)), float(params.get('maxAngle', -45))
        min_v, max_v = float(params.get('minValue', 0)), float(params.get('maxValue', 1))
        total = (min_a - max_a) % 360.0 or 360.0
        swept = (min_a - angle) % 360.0
        if swept > total:
            if swept <= total * (1 + OVERSHOOT):
                swept = total                      # 최대 눈금을 살짝 넘음
            elif swept >= 360.0 - total * OVERSHOOT:
                swept = 0.0                        # 최소 눈금보다 살짝 아래
            else:
                return Reading(None, unit, 0.0, evidence, f'바늘이 눈금 범위 밖({angle:.0f}°)')
        value = min_v + swept / total * (max_v - min_v)
        zone = located.data.get('zoneColor')
        # 화면 · 경고는 "읽은 값 0.70 MPa · <사유>" 로 붙여 보이므로 사유에는 값을 다시 쓰지 않는다
        reason = ZONE_LABEL[zone] if zone in ZONE_LABEL else f'바늘 각도 {angle:.0f}°'
        return Reading(round(value, 4), unit, round(located.confidence, 2), evidence, reason)


def _needle(dark, rho, theta, min_px):
    """원으로 편 좌표(rho · theta)에서 반지름 BAND 띠를 곧게 가로지르는 어두운 직선 = 바늘.
    (각도(도), 바늘 끝 반지름, 바늘 근처 픽셀 수, 띠 안 어두운 픽셀 수) 또는 None."""
    sel = dark & (rho >= BAND[0]) & (rho <= BAND[1])
    if sel.sum() < min_px:
        return None
    n_ang = int(360 / ANGLE_BIN)
    a_idx = (theta[sel] / ANGLE_BIN).astype(int) % n_ang
    r_idx = np.minimum(((rho[sel] - BAND[0]) / (BAND[1] - BAND[0]) * RADIAL_BINS).astype(int), RADIAL_BINS - 1)
    occ = np.zeros((n_ang, RADIAL_BINS), dtype=bool)
    occ[a_idx, r_idx] = True
    cnt = np.bincount(a_idx, minlength=n_ang).astype(float)
    # 이웃 칸(±1)까지 합쳐 바늘 두께가 칸 경계에 걸려도 한 각도로 본다
    occ3 = occ | np.roll(occ, 1, axis=0) | np.roll(occ, -1, axis=0)
    score = occ3.sum(axis=1) * 1e6 + (cnt + np.roll(cnt, 1) + np.roll(cnt, -1))
    peak = int(score.argmax())
    if int(occ3[peak].sum()) < RADIAL_BINS * 0.6:
        return None                                  # 띠를 가로지르는 곧은 바늘이 없음
    # 봉우리 ±4° 안 픽셀의 원형 평균으로 각도를 다듬는다
    pa = np.radians(theta[sel])
    diff = (theta[sel] - (peak + 0.5) * ANGLE_BIN + 180.0) % 360.0 - 180.0
    near = np.abs(diff) <= 4.0 + ANGLE_BIN
    angle = math.degrees(math.atan2(np.sin(pa[near]).mean(), np.cos(pa[near]).mean()))
    return angle, float(rho[sel][near].max()), int(near.sum()), int(sel.sum())


def _fit_ellipse(xs, ys):
    """점들에 축 정렬 타원 A·x² + B·y² + C·x + D·y = 1 을 최소제곱으로 맞춘다 → (중심 x, 중심 y, 반지름 x, 반지름 y) 또는 None.
    점이 많으면 고르게 줄여 쓴다. 비스듬히 보면 원이 가로로 눌린 타원이 되므로 축 정렬 타원으로 충분하다."""
    if len(xs) > 4000:
        k = np.linspace(0, len(xs) - 1, 4000).astype(int)
        xs, ys = xs[k], ys[k]
    mx, my, sc = xs.mean(), ys.mean(), max(xs.std(), ys.std(), 1.0)
    x, y = (xs - mx) / sc, (ys - my) / sc                # 숫자가 커지지 않게 옮기고 줄인다
    A = np.stack([x * x, y * y, x, y], axis=1)
    try:
        a, b, c, d = np.linalg.lstsq(A, np.ones(len(x)), rcond=None)[0]
    except np.linalg.LinAlgError:
        return None
    if a <= 0 or b <= 0:
        return None
    x0, y0 = -c / (2 * a), -d / (2 * b)
    f = 1 + a * x0 * x0 + b * y0 * y0
    if f <= 0:
        return None
    return mx + x0 * sc, my + y0 * sc, math.sqrt(f / a) * sc, math.sqrt(f / b) * sc
