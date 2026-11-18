"""GAUGE: 계기판 바늘 읽기.

대상: 판 위의 허브 점(기본 파랑)과 바늘 막대(기본 빨강).
허브색 덩어리의 무게중심 = 중심, 바늘색 덩어리의 무게중심 − 중심 = 바늘 방향.
각도는 화면 기준 수학 좌표(오른쪽 0°, 반시계 +, 화면 위쪽 +90°).
값 = minAngle 에서 시계 방향으로 바늘까지 돈 각 ÷ 전체 각 × (maxValue − minValue) + minValue.
비스듬히 보면 판이 타원으로 눌려 각도가 조금 틀어진다(보정하지 않는다).
"""
from __future__ import annotations

import math

import numpy as np

from .base import BLUE, RED, Frame, Located, Reading, blobs, color_mask, hsv_schema, ratio_box, ratio_point, region_px, to_hsv

OVERSHOOT = 0.05    # 눈금 범위를 이 비율까지 벗어난 것은 끝값으로 본다


class GaugeChecker:
    kind = 'GAUGE'
    version = 'gauge-1'
    value_type = 'number'
    labels: list = []
    params_schema = {
        'type': 'object',
        'properties': {
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

    def read(self, frame: Frame, located: Located, params: dict) -> Reading:
        (cx, cy), (nx, ny), tip = located.data['center'], located.data['needle'], located.data['tip']
        unit = params.get('unit') or None
        angle = math.degrees(math.atan2(-(ny - cy), nx - cx))
        evidence = {'center': ratio_point(frame, cx, cy), 'angleDeg': round(angle, 1), 'needleTip': ratio_point(frame, *tip)}
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
        return Reading(round(value, 4), unit, round(located.confidence, 2), evidence, f'바늘 각도 {angle:.0f}°')
