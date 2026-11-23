-- 소화기 판독을 색 상자에서 학습한 인식 모델(OBJECT detector='model', fire_v1)로 바꾸면서 지점 번호를 다시 매긴다.
--   P1 = 생산동 서쪽 벽 소화기 사진 판(소화기 있음), P2 = 랙 1 남쪽 면 사진 판(받침만 — 비교용, 늘 '없음')
--   기존 P2(비상구 표시등) → P3, 기존 P3(분전반 계기판) → P4
-- 좌표는 ros/sim/src/worlds/world_spec.py 의 POINTS 와 같다. 규칙은 지점(point_id)에 붙어 있어 번호를 바꿔도 따라간다.

-- 손으로 만든 P4 · P5 가 있으면(시험용) 이름을 바꿔 비활성으로 둔다(관측 이력은 남긴다)
UPDATE inspection_point SET code = 'OLD-' || code, active = false, updated_at = now() WHERE code IN ('P4', 'P5');

UPDATE inspection_point SET code = 'P4', updated_at = now() WHERE code = 'P3';
UPDATE inspection_point SET code = 'P3', updated_at = now() WHERE code = 'P2';

UPDATE inspection_point
   SET name = '소화기 앞', x = 3.95, y = 3.9, yaw_deg = 180,
       description = '생산동 서쪽 벽 소화기 사진 판(인식 모델)', updated_at = now()
 WHERE code = 'P1';

INSERT INTO inspection_point (code, name, description, x, y, yaw_deg)
VALUES ('P2', '소화기 빈 자리', '랙 1 남쪽 면 받침만 있는 사진 판(인식 모델 비교용)', 4.3, 3.5, 90);

-- 시연 규칙(DemoService 가 만든 것)이 이미 있으면 색 방식 → 인식 모델로. 소화기 없음은 경고(비상은 화재·위험 상황에만)
UPDATE inspection_rule
   SET params  = '{"label": "fire_extinguisher", "expect": "PRESENT", "detector": "model", "model": "fire_v1", "className": "fire_extinguisher"}',
       regions = '{}',
       grading = jsonb_set(grading, '{map,MISSING}', '"WARNING"'),
       updated_at = now()
 WHERE name = '[시연] 소화기 비치' AND kind = 'OBJECT' AND deleted_at IS NULL;
