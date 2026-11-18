"""카메라 판독기: 종류별 "찾기(locate)·읽기(read)" + 공통 "등급 매기기(grade)".

    사진 + 규칙 목록 ─▶ 규칙마다: locate ─▶ read ─▶ grade ─▶ 결과 목록

- 판독기는 종류마다 파일 하나(gauge.py, lamp.py, thermal.py, object.py)이고 아래 등록표에 올린다.
  새 종류는 파일을 더하고 등록표에 한 줄 넣으면 GET /checkers 에 나타난다.
- 서비스(DB·HTTP)에 의존하지 않는다(numpy + Pillow). 로봇 안에서도 이 폴더를 그대로 쓴다.
"""
from __future__ import annotations

import math
from typing import Optional

from .base import Frame, Located, Reading, grade, with_defaults
from .gauge import GaugeChecker
from .lamp import LampChecker
from .object import ObjectChecker
from .thermal import ThermalChecker

# 판독기 등록표: kind → 판독기
CHECKERS = {c.kind: c for c in (ObjectChecker(), GaugeChecker(), LampChecker(), ThermalChecker())}

__all__ = ['CHECKERS', 'Frame', 'Located', 'Reading', 'grade', 'describe', 'run_rule', 'run_rules', 'unknown_results']


def describe() -> list:
    """GET /checkers 응답."""
    return [{'kind': c.kind, 'version': c.version, 'valueType': c.value_type,
             'paramsSchema': c.params_schema, 'labels': list(c.labels)} for c in CHECKERS.values()]


def _blank(rule: dict, reason: str = '') -> dict:
    checker = CHECKERS.get(rule.get('kind'))
    return {'ruleId': rule.get('ruleId'), 'kind': rule.get('kind'), 'grade': 'UNKNOWN', 'value': None, 'unit': None,
            'confidence': 0.0, 'evidence': {}, 'reason': reason, 'checkerVersion': checker.version if checker else None}


def unknown_results(rules: list, reason: str) -> list:
    """판독하지 않고 모든 규칙을 UNKNOWN 으로 낸다(예: 사진 품질 불량)."""
    return [_blank(r, reason) for r in rules or []]


def _region(rule: dict, robot_kind: Optional[str]):
    r = (rule.get('regions') or {}).get(robot_kind) if robot_kind else None
    if r is None:
        return None
    if len(r) != 4 or not (0 <= r[0] < r[2] <= 1 and 0 <= r[1] < r[3] <= 1):
        raise ValueError(f'영역은 0~1 비율 [x0, y0, x1, y1] 이며 x0<x1, y0<y1 이어야 함: {r}')
    return [float(v) for v in r]


def _relative(frame: Frame, bbox: list, rule: dict) -> Optional[dict]:
    """카메라 기준 방향(rad, 오른쪽이 −)과 거리(m, 겉보기 폭으로 추정). 실제 크기와 화각이 둘 다 있을 때만."""
    size = (rule.get('target') or {}).get('sizeM')
    hfov = (frame.camera or {}).get('hfovDeg')
    width_px = (bbox[2] - bbox[0]) * frame.width
    if not size or not hfov or width_px < 1:
        return None
    focal = (frame.width / 2.0) / math.tan(math.radians(float(hfov)) / 2.0)
    center_px = (bbox[0] + bbox[2]) / 2.0 * frame.width
    return {'bearing': round(-math.atan((center_px - frame.width / 2.0) / focal), 4),
            'distance': round(float(size) * focal / width_px, 3)}


def run_rule(frame: Frame, rule: dict, robot_kind: Optional[str] = None) -> dict:
    """규칙 하나를 판독한다. 판독기 예외는 그 규칙만 UNKNOWN 으로 만든다."""
    out = _blank(rule)
    checker = CHECKERS.get(rule.get('kind'))
    if checker is None:
        out['reason'] = f'알 수 없는 판독 종류: {rule.get("kind")}'
        return out
    try:
        params = with_defaults(checker.params_schema, rule.get('params'))
        region = _region(rule, robot_kind)
        if region is not None:
            out['evidence']['expectedRegion'] = region
        located = checker.locate(frame, params, region)
        if located is None:
            out['reason'] = '대상을 찾지 못함'
            return out
        reading = checker.read(frame, located, params)
        if located.bbox is not None:
            out['located'] = {'bbox': located.bbox}
            relative = _relative(frame, located.bbox, rule)
            if relative:
                out['located']['relative'] = relative
        out.update(value=reading.value, unit=reading.unit, confidence=round(float(reading.confidence), 2),
                   reason=reading.reason, grade=grade(reading, rule.get('grading')))
        out['evidence'].update(reading.evidence)
    except Exception as e:  # noqa: BLE001 - 규칙 하나의 실패가 나머지를 막지 않게
        out.update(grade='UNKNOWN', reason=f'판독기 오류: {e}')
    return out


def run_rules(frame: Frame, rules: list, robot_kind: Optional[str] = None) -> list:
    return [run_rule(frame, r, robot_kind) for r in rules or []]
