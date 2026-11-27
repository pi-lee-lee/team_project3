"""THERMAL: 뜨거운 영역의 비율 읽기 + 가장 뜨거운 점(발화점).

열화상 카메라 대신 열화상 사진(인쇄물)을 세워 두고 로봇의 일반 카메라로 본다. 학습 모델 없이 색 → 온도로 읽는다.

locate — 시연(인쇄물)과 현업(열화상 카메라)이 갈리는 곳은 여기 하나다.
  cameraFrame 'RGB'    : 일반 카메라로 열화상 인쇄물을 본다. 색상표의 차가운 바탕색 덩어리로 판을 잡는다
                         (iron: 진보라, rainbow: 파랑 · 하늘색). 흰색(가장 뜨거움)은 흰 벽과 구분이 안 되므로
                         바탕색 사이에 낀 픽셀만 판으로 본다 — 가로(왼쪽 · 오른쪽)나 세로(위 · 아래) 어느 한쪽으로
                         끼어 있으면 된다(판 위쪽 끝까지 솟은 불꽃도 들어온다). 판 옆의 온도 막대는 바깥쪽에 바탕색이
                         없어 빠진다.
  cameraFrame 'THERMAL': 프레임 전체가 대상이다.
read — 두 경우가 같다. 픽셀 색을 색상표(LUT)로 상대 온도(0~1)로 바꾸고,
       hotThreshold 이상인 픽셀 수 ÷ 대상 픽셀 수가 값이다.
       온도 범위(tempMin · tempMax, tempScale)를 주면 상대 온도를 °C 로 바꾼다. 그러면 hotC(°C)로 뜨거운 곳을 정하고
       근거에 최고 온도(°C)를 남긴다. 시연 사진(ros/sim/src/worlds/thermal_images.py)은 15~300°C 고정 · 로그 눈금이다.
"""
from __future__ import annotations

import numpy as np

from .base import Frame, Located, Reading, blobs, color_mask, hsv_schema, ratio_box, ratio_point, region_px, to_hsv

# 색상표: (상대 온도, RGB) 를 차가운 쪽부터. 픽셀은 이 꺾은선 위의 가장 가까운 점의 온도를 갖는다.
PALETTES = {
    'iron': [(0.0, (0, 0, 0)), (0.1, (40, 0, 80)), (0.3, (120, 0, 140)), (0.5, (200, 30, 90)),
             (0.7, (255, 120, 0)), (0.85, (255, 230, 0)), (1.0, (255, 255, 255))],
    'gray': [(0.0, (0, 0, 0)), (1.0, (255, 255, 255))],
    # 무지개(검정 → 남색 → 파랑 → 하늘 → 초록 → 노랑 → 주황 → 빨강 → 흰색): 시연 열화상 사진과 같은 표
    'rainbow': [(0.00, (0, 0, 30)), (0.10, (20, 20, 160)), (0.22, (0, 90, 255)), (0.34, (0, 200, 255)),
                (0.46, (0, 230, 120)), (0.58, (200, 240, 0)), (0.70, (255, 200, 0)), (0.82, (255, 100, 0)),
                (0.93, (230, 0, 0)), (1.00, (255, 255, 255))],
}
COLD = {'h': [250, 290], 's': [0.5, 1.0], 'v': [0.1, 0.6]}     # iron 색상표의 차가운 바탕(진보라)
# 색상표별 차가운 바탕(규칙에 cold 를 따로 주지 않았을 때). rainbow 는 방 온도(15~30°C)가 파랑 · 하늘 · 청록이다
COLD_BY_PALETTE = {'iron': COLD, 'gray': COLD, 'rainbow': {'h': [160, 250], 's': [0.5, 1.0], 'v': [0.3, 1.0]}}


def celsius(u, t_min: float, t_max: float, scale: str = 'linear'):
    """상대 온도(0~1) → °C. log: u = ln(1 + T − Tmin) ÷ ln(1 + Tmax − Tmin)(높은 쪽을 눌러 방 안 물체도 색이 보이게 한 눈금)."""
    u = np.clip(np.asarray(u, dtype=np.float32), 0.0, 1.0)
    if scale == 'log':
        return t_min + np.expm1(u * np.log1p(t_max - t_min))
    return t_min + u * (t_max - t_min)


def relative(t_c: float, t_min: float, t_max: float, scale: str = 'linear') -> float:
    """°C → 상대 온도(0~1). celsius 의 역."""
    t = min(max(float(t_c), t_min), t_max)
    if scale == 'log':
        return float(np.log1p(t - t_min) / np.log1p(t_max - t_min))
    return (t - t_min) / (t_max - t_min)


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
    version = 'thermal-2'
    value_type = 'number'
    labels: list = []
    params_schema = {
        'type': 'object',
        'properties': {
            'palette': {'type': 'string', 'title': '색상표', 'enum': sorted(PALETTES), 'default': 'iron'},
            'hotThreshold': {'type': 'number', 'title': '뜨겁다고 보는 상대 온도(0~1)', 'default': 0.6, 'minimum': 0, 'maximum': 1},
            'minAreaRatio': {'type': 'number', 'title': '인쇄물로 인정하는 최소 면적(사진 넓이 대비 비율)', 'default': 0.01,
                             'minimum': 0, 'maximum': 1},
            'cold': hsv_schema('인쇄물의 차가운 바탕 색 범위(일반 카메라로 볼 때 판을 찾는 기준). '
                               '기본값 그대로면 색상표에 맞는 바탕색을 쓴다(rainbow: 파랑 · 하늘색)', COLD),
            'tempMin': {'type': 'number', 'title': '사진의 최저 온도(°C, 온도 막대 아래 끝). 주면 °C 로 읽는다', 'default': None},
            'tempMax': {'type': 'number', 'title': '사진의 최고 온도(°C, 온도 막대 위 끝)', 'default': None},
            'tempScale': {'type': 'string', 'title': '온도 막대 눈금', 'enum': ['linear', 'log'], 'default': 'linear'},
            'hotC': {'type': 'number', 'title': '뜨겁다고 보는 온도(°C). 온도 범위가 있을 때 hotThreshold 대신 쓴다', 'default': None},
        },
    }

    @staticmethod
    def _cold(params: dict) -> dict:
        """판을 찾는 바탕색: 규칙이 바꿨으면 그것, 기본값 그대로면 색상표에 맞는 것."""
        cold = params.get('cold')
        if not cold or cold == COLD:
            return COLD_BY_PALETTE.get(params.get('palette') or 'iron', COLD)
        return cold

    @staticmethod
    def _scale(params: dict):
        """(최저 °C, 최고 °C, 눈금) 또는 None(상대 온도로만 읽음)."""
        lo, hi = params.get('tempMin'), params.get('tempMax')
        if lo is None or hi is None or float(hi) <= float(lo):
            return None
        return float(lo), float(hi), params.get('tempScale') or 'linear'

    def locate(self, frame: Frame, params: dict, region=None):
        if (frame.camera_frame or 'RGB').upper() == 'THERMAL':
            return Located([0.0, 0.0, 1.0, 1.0], 1.0, {'box': (0, 0, frame.width, frame.height), 'mask': None})
        x0, y0, x1, y1 = region_px(frame, region)
        cold = self._cold(params)
        found = blobs(color_mask(to_hsv(frame.rgb[y0:y1, x0:x1]), cold, cold))
        if not found:
            return None
        b = found[0]
        bx0, by0, bx1, by1 = b.bbox
        ratio = (bx1 - bx0) * (by1 - by0) / float(frame.width * frame.height)
        if ratio < float(params.get('minAreaRatio', 0.01)):
            return None
        # 판 = 바탕색 픽셀 사이에 낀 곳(가로 또는 세로). 비스듬히 봐서 사각형 귀퉁이에 걸린 벽은 어느 쪽으로도 끼지 않아
        # 빠지고, 판 위쪽 끝까지 솟은 불꽃은 좌우 바탕 사이라 들어온다. 판 옆 온도 막대는 바깥쪽에 바탕이 없어 빠진다.
        m = b.mask[by0:by1, bx0:bx1]
        rows = np.maximum.accumulate(m, axis=1) & np.maximum.accumulate(m[:, ::-1], axis=1)[:, ::-1]
        cols = np.maximum.accumulate(m, axis=0) & np.maximum.accumulate(m[::-1], axis=0)[::-1]
        box = (x0 + bx0, y0 + by0, x0 + bx1, y0 + by1)
        return Located(ratio_box(frame, *box), min(1.0, 0.5 + ratio / 0.1), {'box': box, 'mask': rows | cols})

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
        scale = self._scale(params)
        threshold = float(params.get('hotThreshold', 0.6))
        if scale and params.get('hotC') is not None:
            threshold = relative(float(params['hotC']), *scale)
        hot = (temp >= threshold) & mask
        value = float(hot.sum()) / total
        peak_t = float(temp[mask].max())
        py, px = np.nonzero((temp >= peak_t - 0.02) & mask)
        # 발화점 = 가장 뜨거운 픽셀들의 가운데(사진 비율 좌표)
        evidence = {'peak': {'point': ratio_point(frame, x0 + px.mean(), y0 + py.mean()), 'value': round(peak_t, 3)},
                    'hotBbox': None}
        if scale:
            evidence['peak']['celsius'] = round(float(celsius(peak_t, *scale)), 1)
            evidence['hotC'] = round(float(celsius(threshold, *scale)), 1)
        if hot.any():
            hy, hx = np.nonzero(hot)
            evidence['hotBbox'] = ratio_box(frame, x0 + hx.min(), y0 + hy.min(), x0 + hx.max() + 1, y0 + hy.max() + 1)
        peak_txt = f'최고 {evidence["peak"]["celsius"]:.0f}°C' if scale else f'최고 상대 온도 {peak_t:.2f}'
        return Reading(round(value, 4), None, round(located.confidence, 2), evidence,
                       f'뜨거운 영역 {value * 100:.1f}% ({peak_txt})')
