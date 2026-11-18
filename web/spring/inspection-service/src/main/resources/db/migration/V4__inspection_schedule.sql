-- 예약 점검: 정한 시각에 같은 로봇·같은 지점 순서로 점검 작업을 자동으로 만든다.
-- 시각 계산은 app.schedule-zone(기본 Asia/Seoul) 기준이고, 다음 실행 시각(next_run_at)은 서버가 계산해 둔다.
CREATE TABLE inspection_schedule (
    schedule_id      bigint       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name             varchar(100) NOT NULL,
    robot_id         bigint       NOT NULL,
    point_ids        bigint[]     NOT NULL,           -- 방문 순서대로
    note             text,
    -- ONCE: run_at 에 한 번 / INTERVAL: interval_minutes 마다 / DAILY: 매일 time_of_day / WEEKLY: days_of_week 의 time_of_day
    kind             varchar(10)  NOT NULL CHECK (kind IN ('ONCE', 'INTERVAL', 'DAILY', 'WEEKLY')),
    run_at           timestamptz,
    interval_minutes integer      CHECK (interval_minutes IS NULL OR interval_minutes >= 5),
    time_of_day      time,
    days_of_week     integer[],                       -- 1=월 … 7=일 (ISO)
    -- INTERVAL 만: 하루 중 실행 허용 시간대(예: 09:00~18:00). 비우면 하루 종일
    window_start     time,
    window_end       time,
    enabled          boolean      NOT NULL DEFAULT true,
    next_run_at      timestamptz,                     -- 꺼졌거나 더 실행할 시각이 없으면 NULL
    created_by       bigint       NOT NULL,
    creator_login    varchar(50)  NOT NULL,
    creator_role     varchar(20)  NOT NULL,
    created_at       timestamptz  NOT NULL DEFAULT now(),
    updated_at       timestamptz  NOT NULL DEFAULT now(),
    deleted_at       timestamptz                      -- 지워도 실행 기록·작업 연결은 남긴다
);
CREATE INDEX idx_schedule_due ON inspection_schedule (next_run_at) WHERE enabled AND deleted_at IS NULL;

-- 실행 기록: 추가만 한다. 왜 실행되지 않았는지(로봇 작업 중·연결 안 됨·서버가 꺼져 있어 늦음 등)도 남긴다.
CREATE TABLE schedule_run (
    run_id      bigint       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    schedule_id bigint       NOT NULL REFERENCES inspection_schedule (schedule_id),
    planned_at  timestamptz  NOT NULL,
    ran_at      timestamptz  NOT NULL DEFAULT now(),
    outcome     varchar(20)  NOT NULL CHECK (outcome IN ('CREATED', 'SKIPPED_BUSY', 'SKIPPED_OFFLINE', 'MISSED', 'FAILED')),
    task_id     bigint       REFERENCES inspection_task (task_id),
    reason      text
);
CREATE INDEX idx_run_schedule ON schedule_run (schedule_id, run_id DESC);

-- 예약으로 만들어진 작업 표시
ALTER TABLE inspection_task ADD COLUMN schedule_id bigint REFERENCES inspection_schedule (schedule_id);
