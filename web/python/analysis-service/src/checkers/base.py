"""판독기 공통: 자료 모양(Frame·Located·Reading), 색·덩어리 도구, 등급 매기기.

이 폴더는 서비스(DB·HTTP)에 의존하지 않는다. numpy 와 Pillow 만 쓰므로 로봇 안에서도 같은 파일을 쓴다.
좌표 약속: 비율 사각형은 [x0, y0, x1, y1](사진 크기 대비 0~1, 왼쪽 위가 원점).
색 범위 약속: {"h": [하한, 상한](도, 0~360, 하한 > 상한이면 0도를 넘어 감는다), "s": [0~1], "v": [0~1]}.
"""
from __future__ import annotations

import io
import math
from dataclasses import dataclass, field
from typing import Any, Optional

import numpy as np

GRADES = ('NORMAL', 'WARNING', 'EMERGENCY', 'UNKNOWN')


@dataclass
class Frame:
    """사진 한 장. rgb 는 (높이, 너비, 3) uint8."""
    rgb: np.ndarray
    camera_frame: str = 'RGB'            # 'RGB' | 'THERMAL'
    camera: Optional[dict] = None        # 카메라 정보(예: {"hfovDeg": 62.2})

    @property
    def height(self) -> int:
        return int(self.rgb.shape[0])

    @property
    def width(self) -> int:
        return int(self.rgb.shape[1])

    @classmethod
    def from_bytes(cls, data: bytes, camera_frame: str = 'RGB', camera: Optional[dict] = None) -> 'Frame':
        from PIL import Image
        img = Image.open(io.BytesIO(data)).convert('RGB')
        return cls(np.asarray(img, dtype=np.uint8), camera_frame or 'RGB', camera)


@dataclass
class Located:
    """찾은 대상. bbox 는 사진 전체 기준 비율 사각형(없으면 None: 값은 있지만 위치는 없는 경우)."""
    bbox: Optional[list] = None
    confidence: float = 1.0
    data: dict = field(default_factory=dict)   # locate → read 로 넘기는 내부 자료(결과에 싣지 않는다)


@dataclass
class Reading:
    """읽은 값. value 가 None 이면 읽지 못한 것(등급 UNKNOWN)."""
    value: Any = None
    unit: Optional[str] = None
    confidence: float = 0.0
    evidence: dict = field(default_factory=dict)
    reason: str = ''


# ------------------------------------------------------------------ 등급
def grade(reading: Reading, grading: Optional[dict]) -> str:
    """읽은 값을 등급으로 바꾼다. 기준은 설정(grading)이다.

    {"type": "map", "map": {값: 등급}, "default": "UNKNOWN"}
    {"type": "ranges", "ranges": [{"min"?, "max"?, "grade"}], "default": "EMERGENCY"}  — min 이상 max 미만, 위에서부터 처음 맞는 구간
    """
    if reading is None or reading.value is None or not grading:
        return 'UNKNOWN'
    default = grading.get('default') or 'UNKNOWN'
    kind = grading.get('type')
    if kind == 'map':
        return _valid((grading.get('map') or {}).get(str(reading.value), default))
    if kind == 'ranges':
        if isinstance(reading.value, bool) or not isinstance(reading.value, (int, float)):
            return 'UNKNOWN'
        v = float(reading.value)
        for r in grading.get('ranges') or []:
            lo, hi = r.get('min'), r.get('max')
            if (lo is None or v >= lo) and (hi is None or v < hi):
                return _valid(r.get('grade'))
        return _valid(default)
    return 'UNKNOWN'


def _valid(g) -> str:
    return g if g in GRADES else 'UNKNOWN'


# ------------------------------------------------------------------ 설정
def with_defaults(schema: dict, params: Optional[dict]) -> dict:
    """params_schema 의 default 로 빠진 항목을 채운다."""
    out = {k: v['default'] for k, v in (schema.get('properties') or {}).items() if 'default' in v}
    out.update({k: v for k, v in (params or {}).items() if v is not None})
    return out


def hsv_schema(title: str, default: dict) -> dict:
    """색 범위 하나의 JSON Schema."""
    pair = {'type': 'array', 'items': {'type': 'number'}, 'minItems': 2, 'maxItems': 2}
    return {
        'type': 'object', 'title': title, 'default': default,
        'properties': {
            'h': dict(pair, title='색상 범위(도, 0~360. 하한이 상한보다 크면 0도를 넘어 감는다)', default=default['h']),
            's': dict(pair, title='채도 범위(0~1)', default=default['s']),
            'v': dict(pair, title='밝기 범위(0~1)', default=default['v']),
        },
    }


RED = {'h': [340, 20], 's': [0.5, 1.0], 'v': [0.3, 1.0]}
GREEN = {'h': [90, 150], 's': [0.5, 1.0], 'v': [0.3, 1.0]}
YELLOW = {'h': [35, 70], 's': [0.5, 1.0], 'v': [0.3, 1.0]}
BLUE = {'h': [210, 270], 's': [0.5, 1.0], 'v': [0.3, 1.0]}


# ------------------------------------------------------------------ 영역
def region_px(frame: Frame, region) -> tuple:
    """비율 영역을 픽셀 (x0, y0, x1, y1)(끝은 제외)로. None 이면 사진 전체."""
    w, h = frame.width, frame.height
    if region is None:
        return 0, 0, w, h
    x0, y0, x1, y1 = (min(max(float(v), 0.0), 1.0) for v in region)
    px0, py0 = int(x0 * w), int(y0 * h)
    px1, py1 = max(int(math.ceil(x1 * w)), px0 + 1), max(int(math.ceil(y1 * h)), py0 + 1)
    return px0, py0, min(px1, w), min(py1, h)


def ratio_box(frame: Frame, x0, y0, x1, y1) -> list:
    """픽셀 사각형을 비율 사각형으로."""
    w, h = frame.width, frame.height
    return [round(min(max(x0 / w, 0.0), 1.0), 4), round(min(max(y0 / h, 0.0), 1.0), 4),
            round(min(max(x1 / w, 0.0), 1.0), 4), round(min(max(y1 / h, 0.0), 1.0), 4)]


def ratio_point(frame: Frame, x, y) -> list:
    return [round(float(x) / frame.width, 4), round(float(y) / frame.height, 4)]


# ------------------------------------------------------------------ 색
def to_hsv(rgb: np.ndarray):
    """(…, 3) uint8 → h(도 0~360), s(0~1), v(0~1)."""
    a = rgb.astype(np.float32) / 255.0
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    mx, mn = a.max(axis=-1), a.min(axis=-1)
    d = mx - mn
    nz = d > 1e-6
    safe = np.where(nz, d, 1.0)
    h = np.where(mx == r, ((g - b) / safe) % 6.0, np.where(mx == g, (b - r) / safe + 2.0, (r - g) / safe + 4.0)) * 60.0
    h = np.where(nz, h, 0.0)
    s = np.where(mx > 1e-6, d / np.where(mx > 1e-6, mx, 1.0), 0.0)
    return h, s, mx


def color_mask(hsv, spec: Optional[dict], default: Optional[dict] = None) -> np.ndarray:
    """색 범위에 드는 픽셀. spec 에 빠진 항목은 default 로 채운다."""
    h, s, v = hsv
    rng = dict(default or {'h': [0, 360], 's': [0, 1], 'v': [0, 1]})
    rng.update({k: val for k, val in (spec or {}).items() if val is not None})
    h0, h1 = (float(x) for x in rng['h'])
    hm = (h >= h0) & (h <= h1) if h0 <= h1 else (h >= h0) | (h <= h1)
    return hm & (s >= rng['s'][0]) & (s <= rng['s'][1]) & (v >= rng['v'][0]) & (v <= rng['v'][1])


# ------------------------------------------------------------------ 덩어리
@dataclass
class Blob:
    mask: np.ndarray      # 입력 mask 와 같은 크기
    count: int            # 픽셀 수
    bbox: tuple           # (x0, y0, x1, y1) 픽셀, 끝 제외
    centroid: tuple       # (x, y)


def blobs(mask: np.ndarray, max_cells: int = 160, top: int = 8) -> list:
    """붙어 있는 픽셀 덩어리를 큰 순서로 돌려준다(최대 top 개).

    OpenCV 없이 하려고 mask 를 긴 변 max_cells 칸으로 줄여 칸 단위(8방향)로 묶는다.
    그래서 한 칸(몇 픽셀) 이내로 떨어진 조각은 한 덩어리로 본다.
    """
    h, w = mask.shape
    if not mask.any():
        return []
    step = max(1, -(-max(h, w) // max_cells))
    hh, ww = -(-h // step), -(-w // step)
    pad = np.zeros((hh * step, ww * step), dtype=bool)
    pad[:h, :w] = mask
    small = pad.reshape(hh, step, ww, step).any(axis=(1, 3))
    ys, xs = np.nonzero(small)
    cells = set(zip(ys.tolist(), xs.tolist()))
    groups = []
    while cells:
        start = cells.pop()
        stack, group = [start], [start]
        while stack:
            cy, cx = stack.pop()
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    n = (cy + dy, cx + dx)
                    if n in cells:
                        cells.remove(n)
                        stack.append(n)
                        group.append(n)
        groups.append(group)
    groups.sort(key=len, reverse=True)
    out = []
    for group in groups[:top]:
        g = np.zeros((hh, ww), dtype=bool)
        gy, gx = zip(*group)
        g[list(gy), list(gx)] = True
        full = np.repeat(np.repeat(g, step, axis=0), step, axis=1)[:h, :w] & mask
        py, px = np.nonzero(full)
        if len(px) == 0:
            continue
        out.append(Blob(full, int(len(px)), (int(px.min()), int(py.min()), int(px.max()) + 1, int(py.max()) + 1),
                        (float(px.mean()), float(py.mean()))))
    out.sort(key=lambda b: b.count, reverse=True)
    return out
