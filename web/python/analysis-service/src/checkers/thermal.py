"""THERMAL: 뜨거운 영역의 비율 읽기.

locate — 시연(인쇄물)과 현업(열화상 카메라)이 갈리는 곳은 여기 하나다.
  cameraFrame 'RGB'    : 일반 카메라로 열화상 인쇄물을 본다. 차가운 바탕색(진보라) 덩어리로 판을 잡는다.
                         흰색(가장 뜨거움)은 흰 벽과 구분이 안 되므로 바탕색 사이에 낀 픽셀만 판으로 본다.
  cameraFrame 'THERMAL': 프레임 전체가 대상이다.
read — 두 경우가 같다. 픽셀 색을 색상표(LUT)로 상대 온도(0~1)로 바꾸고,
       hotThreshold 이상인 픽셀 수 ÷ 대상 픽셀 수가 값이다.
"""
from __future__ import annotations

import numpy as np

from .base import Frame, Located, Reading, blobs, color_mask, hsv_schema, ratio_box, ratio_point, region_px, to_hsv

# 색상표: (상대 온도, RGB) 를 차가운 쪽부터. 픽셀은 이 꺾은선 위의 가장 가까운 점의 온도를 갖는다.
PALETTES = {
    'iron': [(0.0, (0, 0, 0)), (0.1, (40, 0, 80)), (0.3, (120, 0, 140)), (0.5, (200, 30, 90)),
             (0.7, (255, 120, 0)), (0.85, (255, 230, 0)), (1.0, (255, 255, 255))],
    'gray': [(0.0, (0, 0, 0)), (1.0, (255, 255, 255))],
}
COLD = {'h': [250, 290], 's': [0.5, 1.0], 'v': [0.1, 0.6]}     # iron 색상표의 차가운 바탕(진보라)


def temperature(rgb: np.ndarray, palette: str) -> np.ndarray:
    """(N, 3) 색 → (N,) 상대 온도."""
    if palette not in PALETTES:
        raise ValueError(f'알 수 없는 색상표: {palette}')
    lut = PALETTES[palette]
    p = rgb.astype(np.float32)
    best_d = np.full(len(p), np.inf, dtype=np.float32)
    best_t = np.zeros(len(p), dtype=np.float32)
    for (ta, ca), (tb, cb) in zip(lut[:-1], lut[1:]):
        a, d = np.array(ca, np.float32), np.array(cb, np.float32) - np.array(ca, np.float32)
        u = np.clip(((p - a) @ d) / float(d @ d), 0.0, 1.0)
        dist = ((p - a - u[:, None] * d) ** 2).sum(axis=1)
        closer = dist < best_d
        best_d = np.where(closer, dist, best_d)
        best_t = np.where(closer, ta + u * (tb - ta), best_t)
    return best_t


class ThermalChecker:
    kind = 'THERMAL'
    version = 'thermal-1'
    value_type = 'number'
    labels: list = []
    params_schema = {
        'type': 'object',
        'properties': {
            'palette': {'type': 'string', 'title': '색상표', 'enum': sorted(PALETTES), 'default': 'iron'},
            'hotThreshold': {'type': 'number', 'title': '뜨겁다고 보는 상대 온도(0~1)', 'default': 0.6, 'minimum': 0, 'maximum': 1},
            'minAreaRatio': {'type': 'number', 'title': '인쇄물로 인정하는 최소 면적(사진 넓이 대비 비율)', 'default': 0.01,
                             'minimum': 0, 'maximum': 1},
            'cold': hsv_schema('인쇄물의 차가운 바탕 색 범위(일반 카메라로 볼 때 판을 찾는 기준)', COLD),
        },
    }

    def locate(self, frame: Frame, params: dict, region=None):
        if (frame.camera_frame or 'RGB').upper() == 'THERMAL':
            return Located([0.0, 0.0, 1.0, 1.0], 1.0, {'box': (0, 0, frame.width, frame.height), 'mask': None})
        x0, y0, x1, y1 = region_px(frame, region)
        found = blobs(color_mask(to_hsv(frame.rgb[y0:y1, x0:x1]), params.get('cold'), COLD))
        if not found:
            return None
        b = found[0]
        bx0, by0, bx1, by1 = b.bbox
        ratio = (bx1 - bx0) * (by1 - by0) / float(frame.width * frame.height)
        if ratio < float(params.get('minAreaRatio', 0.01)):
            return None
        # 판 = 바탕색 픽셀 사이에 낀 곳(가로로도 세로로도). 비스듬히 봐서 사각형 귀퉁이에 걸린 벽은 빠진다.
        m = b.mask[by0:by1, bx0:bx1]
        rows = np.maximum.accumulate(m, axis=1) & np.maximum.accumulate(m[:, ::-1], axis=1)[:, ::-1]
        cols = np.maximum.accumulate(m, axis=0) & np.maximum.accumulate(m[::-1], axis=0)[::-1]
        box = (x0 + bx0, y0 + by0, x0 + bx1, y0 + by1)
        return Located(ratio_box(frame, *box), min(1.0, 0.5 + ratio / 0.1), {'box': box, 'mask': rows & cols})

    def read(self, frame: Frame, located: Located, params: dict) -> Reading:
        x0, y0, x1, y1 = located.data['box']
        crop = frame.rgb[y0:y1, x0:x1]
        mask = located.data.get('mask')
        if mask is None:
            mask = np.ones(crop.shape[:2], dtype=bool)
        total = int(mask.sum())
        if total == 0:
            return Reading(None, None, 0.0, {}, '대상 픽셀이 없음')
        temp = np.zeros(mask.shape, dtype=np.float32)
        temp[mask] = temperature(crop[mask], params.get('palette') or 'iron')
        hot = (temp >= float(params.get('hotThreshold', 0.6))) & mask
        value = float(hot.sum()) / total
        peak_t = float(temp[mask].max())
        py, px = np.nonzero((temp >= peak_t - 0.02) & mask)
        evidence = {'peak': {'point': ratio_point(frame, x0 + px.mean(), y0 + py.mean()), 'value': round(peak_t, 3)},
                    'hotBbox': None}
        if hot.any():
            hy, hx = np.nonzero(hot)
            evidence['hotBbox'] = ratio_box(frame, x0 + hx.min(), y0 + hy.min(), x0 + hx.max() + 1, y0 + hy.max() + 1)
        return Reading(round(value, 4), None, round(located.confidence, 2), evidence,
                       f'뜨거운 영역 {value * 100:.1f}% (최고 상대 온도 {peak_t:.2f})')
