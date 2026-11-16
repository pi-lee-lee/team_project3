-- 확인 불가 사유를 종류별로 나눈다: BLOCKED_NO_PATH(통로 막힘·진입 불가), NAV_FAILED, NO_PROGRESS,
-- PREFLIGHT_FAILED, CAPTURE_FAILED, TIMEOUT, NAV_UNAVAILABLE
ALTER TABLE observation ADD COLUMN reason_code varchar(30);
CREATE INDEX idx_obs_reason ON observation (point_id, reason_code) WHERE reason_code IS NOT NULL;

-- 시험 시설(공장) 월드로 바꾸면서 점검 지점 좌표를 옮긴다 (sim/worlds/world_spec.py 의 POINTS 와 같다)
UPDATE inspection_point SET x = 4.3,  y = 3.9,  yaw_deg = 180, description = '생산동 서쪽 벽 소화기',   updated_at = now() WHERE code = 'P1';
UPDATE inspection_point SET x = 7.55, y = 6.1,  yaw_deg = 90,  description = 'C2 복도 끝 비상구 표시', updated_at = now() WHERE code = 'P2';
UPDATE inspection_point SET x = 0.3,  y = 4.6,  yaw_deg = 180, description = '전기실 서쪽 벽 분전반',   updated_at = now() WHERE code = 'P3';
