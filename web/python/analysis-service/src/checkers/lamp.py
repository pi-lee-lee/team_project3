"""LAMP: 표시등 색 읽기.

영역 안에서 색 범위별로 켜진 픽셀을 세어 가장 넓은 색 이름이 값이다.
어느 색도 기준 면적(minAreaRatio, 영역 넓이 대비)을 못 넘으면 값은 'off'(꺼짐도 읽은 값이다).
"""
from __future__ import annotations

from .base import GREEN, RED, YELLOW, Frame, Located, Reading, blobs, color_mask, hsv_schema, ratio_box, region_px, to_hsv

DEFAULT_COLORS = {'green': GREEN, 'yellow': YELLOW, 'red': RED}


class LampChecker:
    kind = 'LAMP'
    version = 'lamp-1'
    value_type = 'label'
    labels = list(DEFAULT_COLORS) + ['off']
    params_schema = {
        'type': 'object',
        'properties': {
            'colors': {
                'type': 'object', 'title': '색 이름별 색 범위(HSV)', 'default': DEFAULT_COLORS,
                'additionalProperties': hsv_schema('색 범위', RED),
            },
            'minAreaRatio': {'type': 'number', 'title': '켜짐으로 보는 최소 면적(영역 넓이 대비 비율)', 'default': 0.002,
                             'minimum': 0, 'maximum': 1},
            'offBelow': {'type': 'number', 'title': '이 밝기(0~1) 미만인 픽셀은 꺼진 것으로 본다', 'default': 0.3,
                         'minimum': 0, 'maximum': 1},
        },
    }

    def locate(self, frame: Frame, params: dict, region=None):
        x0, y0, x1, y1 = region_px(frame, region)
        hsv = to_hsv(frame.rgb[y0:y1, x0:x1])
        lit = hsv[2] >= float(params.get('offBelow', 0.3))
        area = float((y1 - y0) * (x1 - x0))
        masks = {name: color_mask(hsv, spec, {'h': [0, 360], 's': [0.5, 1.0], 'v': [0.0, 1.0]}) & lit
                 for name, spec in (params.get('colors') or DEFAULT_COLORS).items()}
        ratios = {name: float(m.sum()) / area for name, m in masks.items()}
        best = max(ratios, key=ratios.get) if ratios else None
        data = {'ratios': {k: round(v, 5) for k, v in ratios.items()}, 'best': None}
        if best is None or ratios[best] < float(params.get('minAreaRatio', 0.002)) or ratios[best] <= 0:
            return Located(None, 1.0, data)          # 꺼짐: 위치는 없지만 값('off')은 있다
        b = blobs(masks[best])[0]
        data['best'] = best
        return Located(ratio_box(frame, x0 + b.bbox[0], y0 + b.bbox[1], x0 + b.bbox[2], y0 + b.bbox[3]), 1.0, data)

    def read(self, frame: Frame, located: Located, params: dict) -> Reading:
        ratios, best = located.data['ratios'], located.data['best']
        evidence = {'areaRatios': ratios}
        min_ratio = max(float(params.get('minAreaRatio', 0.002)), 1e-9)
        top = max(ratios.values()) if ratios else 0.0
        if best is None:
            return Reading('off', None, round(1.0 - min(1.0, top / min_ratio) * 0.5, 2), evidence, '켜진 색이 없음')
        share = ratios[best] / max(sum(ratios.values()), 1e-9)          # 다른 색이 섞여 있으면 낮아진다
        size = min(1.0, 0.5 + 0.5 * ratios[best] / (min_ratio * 3))
        return Reading(best, None, round(share * size, 2), evidence, f'{best} 켜짐')
