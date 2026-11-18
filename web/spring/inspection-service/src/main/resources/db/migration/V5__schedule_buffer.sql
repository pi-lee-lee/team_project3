-- 예약 실행 버퍼: 로봇이 바쁘면 회차를 건너뛰지 않고 대기열에 담아 두었다가 이어서 실행한다.
-- 대기 중에 예약을 끄거나 지우거나 사용자가 대기를 취소하면 CANCELLED 로 남긴다.
-- (SKIPPED_BUSY / SKIPPED_OFFLINE 은 이전 방식의 기록이라 값은 그대로 허용한다)
ALTER TABLE schedule_run DROP CONSTRAINT schedule_run_outcome_check;
ALTER TABLE schedule_run ADD CONSTRAINT schedule_run_outcome_check
    CHECK (outcome IN ('CREATED', 'SKIPPED_BUSY', 'SKIPPED_OFFLINE', 'MISSED', 'FAILED', 'CANCELLED'));
-- 대기열에 담긴 시각과 지연 시간(초): 예정 시각보다 늦게 실행된 회차를 화면에서 구분한다
ALTER TABLE schedule_run ADD COLUMN delay_sec integer;
