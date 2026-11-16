-- C2 복도를 1.1m 로 넓히면서 P2(비상구 앞) 위치를 복도 가운데로 옮긴다
UPDATE inspection_point SET x = 7.65, updated_at = now() WHERE code = 'P2';
