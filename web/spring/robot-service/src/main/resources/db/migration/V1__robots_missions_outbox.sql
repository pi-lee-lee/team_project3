-- 로봇 등록: 어댑터 종류와 연결 설정(JSON). 시뮬레이션 → 실제 로봇 교체는 config 만 바꾼다.
CREATE TABLE robot (
    robot_id     bigint       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    code         varchar(50)  NOT NULL UNIQUE,
    name         varchar(100) NOT NULL,
    adapter_type varchar(20)  NOT NULL CHECK (adapter_type IN ('ROSBRIDGE', 'MOCK')),
    config       jsonb        NOT NULL DEFAULT '{}',
    enabled      boolean      NOT NULL DEFAULT true,
    created_at   timestamptz  NOT NULL DEFAULT now(),
    updated_at   timestamptz  NOT NULL DEFAULT now()
);

-- 미션 = inspection-service 의 작업 한 건을 로봇에서 실행한 기록. mission_id 는 작업 ID 와 같다(중복 명령 판별).
CREATE TABLE mission (
    mission_id  bigint       PRIMARY KEY,
    robot_id    bigint       NOT NULL REFERENCES robot (robot_id),
    waypoints   jsonb        NOT NULL,
    state       varchar(20)  NOT NULL,   -- ACCEPTED RUNNING COMPLETED FAILED CANCELLED INTERRUPTED
    reason      text,
    created_at  timestamptz  NOT NULL DEFAULT now(),
    updated_at  timestamptz  NOT NULL DEFAULT now()
);

-- 결과 보관·재전송: 보고를 먼저 여기에 저장하고, 전송에 성공하면 sent_at 을 채운다.
CREATE TABLE report_outbox (
    report_id   uuid         PRIMARY KEY,
    mission_id  bigint       NOT NULL,
    kind        varchar(20)  NOT NULL CHECK (kind IN ('EVENT', 'OBSERVATION')),
    payload     jsonb        NOT NULL,
    image       bytea,
    created_at  timestamptz  NOT NULL DEFAULT clock_timestamp(),
    sent_at     timestamptz,
    attempts    integer      NOT NULL DEFAULT 0,
    last_error  text
);

CREATE INDEX idx_outbox_pending ON report_outbox (created_at) WHERE sent_at IS NULL;
