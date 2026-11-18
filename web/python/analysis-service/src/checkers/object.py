"""OBJECT: 물체 유무·위치.

detector 'color'(지금 구현): 지정한 색의 가장 큰 덩어리를 물체로 본다. 사진 전체에서 찾고 영역은 판정에만 쓴다.
detector 'model'(자리만): 학습 모델이 아직 없어 UNKNOWN 을 낸다.
못 찾음 자체가 값이다: expect PRESENT → IN_REGION / OUT_OF_REGION / MISSING, expect ABSENT → ABSENT / PRESENT.
"""
from __future__ import annotations

from .base import RED, Frame, Located, Reading, blobs, color_mask, hsv_schema, ratio_box, to_hsv


class ObjectChecker:
    kind = 'OBJECT'
    version = 'object-1'
    value_type = 'label'
    labels = ['IN_REGION', 'OUT_OF_REGION', 'MISSING', 'ABSENT', 'PRESENT']
    params_schema = {
        'type': 'object',
        'properties': {
            'label': {'type': 'string', 'title': '물체 이름표(기록용)', 'default': ''},
            'expect': {'type': 'string', 'title': '기대 상태(PRESENT: 있어야 함, ABSENT: 없어야 함)',
                       'enum': ['PRESENT', 'ABSENT'], 'default': 'PRESENT'},
            'detector': {'type': 'string', 'title': '찾는 방식(color: 색 덩어리, model: 인식 모델 — 아직 없음)',
                         'enum': ['color', 'model'], 'default': 'color'},
            'color': hsv_schema('물체 색 범위(color 방식)', RED),
            'minAreaRatio': {'type': 'number', 'title': '물체로 인정하는 최소 면적(사진 넓이 대비 비율)', 'default': 0.003,
                             'minimum': 0, 'maximum': 1},
            'minConfidence': {'type': 'number', 'title': '찾았다고 보는 최소 신뢰도(0~1)', 'default': 0.4,
                              'minimum': 0, 'maximum': 1},
            'model': {'type': 'string', 'title': '인식 모델 이름(model 방식)', 'default': ''},
        },
    }

    def locate(self, frame: Frame, params: dict, region=None):
        data = {'region': list(region) if region is not None else None, 'areaRatio': 0.0}
        if params.get('detector', 'color') == 'model':
            return Located(None, 0.0, dict(data, unsupported=True))
        if params.get('detector', 'color') != 'color':
            raise ValueError(f'알 수 없는 찾는 방식: {params.get("detector")}')
        h, s, v = hsv = to_hsv(frame.rgb)
        found = blobs(color_mask(hsv, params.get('color'), RED))
        if not found:
            return Located(None, 0.0, data)
        b = found[0]
        area = b.count / float(frame.width * frame.height)
        min_area = max(float(params.get('minAreaRatio', 0.003)), 1e-9)
        confidence = 0.5 * min(1.0, area / (4 * min_area)) + 0.5 * float(s[b.mask].mean())
        data['areaRatio'] = round(area, 5)
        if area < min_area or confidence < float(params.get('minConfidence', 0.4)):
            return Located(None, confidence, data)     # 너무 작거나 흐릿함: 못 찾은 것으로 본다
        return Located(ratio_box(frame, *b.bbox), confidence, data)

    def read(self, frame: Frame, located: Located, params: dict) -> Reading:
        evidence = {'label': params.get('label') or None, 'areaRatio': located.data.get('areaRatio', 0.0)}
        if located.data.get('unsupported'):
            return Reading(None, None, 0.0, evidence, '인식 모델이 설치되지 않음')
        region, box = located.data.get('region'), located.bbox
        inside = False
        if box is not None:
            cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
            inside = region is None or (region[0] <= cx <= region[2] and region[1] <= cy <= region[3])
        conf = round(located.confidence, 2)
        if params.get('expect', 'PRESENT') == 'ABSENT':
            if inside:
                return Reading('PRESENT', None, conf, evidence, '없어야 할 물체가 기대 영역 안에 있음')
            return Reading('ABSENT', None, round(1.0 - located.confidence, 2) if box is None else conf, evidence,
                           '기대 영역에 물체 없음')
        if box is None:
            return Reading('MISSING', None, round(1.0 - located.confidence, 2), evidence, '물체를 찾지 못함')
        if inside:
            return Reading('IN_REGION', None, conf, evidence, '기대 영역 안에서 발견')
        return Reading('OUT_OF_REGION', None, conf, evidence, '기대 영역 밖에서 발견')
