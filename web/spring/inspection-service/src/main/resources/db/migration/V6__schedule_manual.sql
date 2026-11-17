-- 점검 요청과 예약 점검을 "점검 계획" 하나로 합친다: 정해 둔 시각 없이 실행 버튼으로만 돌리는 계획(MANUAL)을 허용한다.
ALTER TABLE inspection_schedule DROP CONSTRAINT inspection_schedule_kind_check;
ALTER TABLE inspection_schedule ADD CONSTRAINT inspection_schedule_kind_check
    CHECK (kind IN ('MANUAL', 'ONCE', 'INTERVAL', 'DAILY', 'WEEKLY'));
