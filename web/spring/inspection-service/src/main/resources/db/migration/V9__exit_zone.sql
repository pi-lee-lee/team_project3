-- 비상구 점검 지점의 "비상구 앞 구역": 지도 좌표 직사각형 [x1, y1, x2, y2](m). 없으면 일반 지점.
-- 그 지점으로 가는 목표에만 함께 보낸다. 로봇이 이 구역 안에서 막히면 복구 · 우회 없이 바로 '진입 불가'로 끝내고
-- 목적지 쪽 사진을 올린다(비상구 앞 적재 = 피난 통로 막힘). 구역 밖에서 막히면 지금까지처럼 복구 · 우회한다.
ALTER TABLE inspection_point ADD COLUMN exit_zone jsonb;

-- P3(C2 복도 끝 비상구): 생산동 → C2 문(y 3.6) 위쪽부터 비상구 벽까지의 C2 복도. ros/sim/src/worlds/world_spec.py 의 EXIT_ZONES 와 같다.
UPDATE inspection_point SET exit_zone = '[7.1, 3.6, 8.2, 7.2]', updated_at = now() WHERE code = 'P3';
