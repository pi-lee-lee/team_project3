-- 시나리오(소방 관제 · 소화액 투척)용 표. 모양의 근거는 docs/plan/INTERFACES.md 6장.

-- D1 점검 규칙: 지점에서 찍은 사진을 무엇으로(판독기 종류) 어떤 기준으로(등급) 볼지.
CREATE TABLE inspection_rule (
    rule_id          bigint       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    point_id         bigint       NOT NULL REFERENCES inspection_point (point_id),
    name             varchar(100) NOT NULL,
    kind             varchar(30)  NOT NULL,              -- 판독기 종류. 값 검사는 analysis-service 의 GET /checkers 로 한다
    params           jsonb        NOT NULL DEFAULT '{}',
    regions          jsonb        NOT NULL DEFAULT '{}', -- {"INSPECTOR":[x0,y0,x1,y1], "PATROL":[...]} 사진 크기 대비 비율
    grading          jsonb        NOT NULL,
    target_x         double precision,                   -- 대상의 지도 좌표(없어도 된다)
    target_y         double precision,
    target_yaw       double precision,
    target_size_m    double precision,
    use_as_reference boolean      NOT NULL DEFAULT false,
    enabled          boolean      NOT NULL DEFAULT true,
    created_at       timestamptz  NOT NULL DEFAULT now(),
    updated_at       timestamptz  NOT NULL DEFAULT now(),
    deleted_at       timestamptz
);
CREATE INDEX idx_rule_point ON inspection_rule (point_id) WHERE deleted_at IS NULL;

-- D2 규칙별 판독 결과. 다시 판독하면 행이 추가된다(가장 최근 행이 현재 값).
CREATE TABLE rule_result (
    result_id       bigint       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    observation_id  bigint       NOT NULL REFERENCES observation (observation_id),
    rule_id         bigint       NOT NULL REFERENCES inspection_rule (rule_id),
    grade           varchar(10)  NOT NULL CHECK (grade IN ('NORMAL', 'WARNING', 'EMERGENCY', 'UNKNOWN')),
    value_num       double precision,
    value_label     varchar(50),
    unit            varchar(20),
    confidence      double precision,
    located         jsonb,
    evidence        jsonb,
    reason          text,
    checker_version varchar(40),
    rule_snapshot   jsonb        NOT NULL,               -- 판독 당시의 규칙(나중에 규칙을 고쳐도 근거가 남는다)
    analyzed_at     timestamptz  NOT NULL DEFAULT now()
);
CREATE INDEX idx_result_obs ON rule_result (observation_id, result_id DESC);
CREATE INDEX idx_result_rule ON rule_result (rule_id, result_id DESC);

ALTER TABLE observation
    ADD COLUMN robot_kind       varchar(20),
    ADD COLUMN camera_frame     varchar(10),
    ADD COLUMN arrival_error_xy double precision;

-- D3 경고: 확인(ACKED) · 해제(RESOLVED)를 남긴다. 같은 대상 · 같은 종류의 열린 경고는 하나다.
CREATE TABLE alert (
    alert_id    bigint       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    type        varchar(40)  NOT NULL,                   -- RULE_VIOLATION, FIRE_DETECTED, ...
    grade       varchar(10)  NOT NULL CHECK (grade IN ('WARNING', 'EMERGENCY')),
    state       varchar(10)  NOT NULL DEFAULT 'OPEN' CHECK (state IN ('OPEN', 'ACKED', 'RESOLVED')),
    dedup_key   varchar(100) NOT NULL,                   -- 'rule:12', 'incident:5'
    title       varchar(200) NOT NULL,
    detail      text,
    point_id    bigint       REFERENCES inspection_point (point_id),
    x           double precision,
    y           double precision,
    ref_kind    varchar(20)  NOT NULL,                   -- observation | task | incident | rule
    ref_id      bigint       NOT NULL,
    task_id     bigint,
    evidence    jsonb        NOT NULL DEFAULT '{}',
    opened_at   timestamptz  NOT NULL DEFAULT now(),
    updated_at  timestamptz  NOT NULL DEFAULT now(),
    acked_by    varchar(50),
    acked_at    timestamptz,
    resolved_by varchar(50),                             -- 자동 해제면 'SYSTEM'
    resolved_at timestamptz,
    comment     text
);
CREATE UNIQUE INDEX uq_alert_open ON alert (dedup_key) WHERE state <> 'RESOLVED';
CREATE INDEX idx_alert_state ON alert (state, grade, opened_at DESC);

-- D4 사건(화재 대응). 상태 흐름은 INTERFACES.md 7장 F1.
CREATE TABLE incident (
    incident_id     bigint       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    type            varchar(20)  NOT NULL DEFAULT 'FIRE',
    state           varchar(20)  NOT NULL,
    grade           varchar(10)  NOT NULL,
    x               double precision NOT NULL,
    y               double precision NOT NULL,
    pose_quality    double precision,
    detected_by     bigint       NOT NULL,               -- 감지한 로봇 ID
    det_id          varchar(60)  UNIQUE,                 -- 감지 중복 판별
    launch_mode     varchar(10)  NOT NULL CHECK (launch_mode IN ('APPROVAL', 'AUTO')),  -- 만들어질 때의 설정
    responder_id    bigint,
    task_id         bigint       REFERENCES inspection_task (task_id),                   -- 출동 작업
    standoff        jsonb,
    detection_image text,
    recheck_image   text,
    after_image     text,
    recheck         jsonb,
    after_check     jsonb,
    command_seq     integer      NOT NULL DEFAULT 0,     -- 투척 명령 순번(commandId = inc-{id}-{seq})
    approved_by     varchar(50),
    approved_at     timestamptz,
    closed_by       varchar(50),
    closed_at       timestamptz,
    close_reason    text,
    created_at      timestamptz  NOT NULL DEFAULT now(),
    updated_at      timestamptz  NOT NULL DEFAULT now()
);
CREATE INDEX idx_incident_open ON incident (created_at DESC) WHERE closed_at IS NULL;

CREATE TABLE incident_event (                            -- 추가만 한다
    event_id    bigint       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    incident_id bigint       NOT NULL REFERENCES incident (incident_id),
    source      varchar(10)  NOT NULL CHECK (source IN ('USER', 'ROBOT', 'SYSTEM')),
    type        varchar(40)  NOT NULL,
    detail      jsonb        NOT NULL DEFAULT '{}',
    actor       varchar(50),
    occurred_at timestamptz  NOT NULL DEFAULT now()
);
CREATE INDEX idx_incident_event ON incident_event (incident_id, event_id);

-- 작업 종류: 점검(INSPECTION) / 화재 출동(RESPONSE)
ALTER TABLE inspection_task
    ADD COLUMN kind        varchar(20) NOT NULL DEFAULT 'INSPECTION',
    ADD COLUMN incident_id bigint REFERENCES incident (incident_id);

-- D6 설정: 값이 정해지지 않은 항목을 받는 자리. 표에 없는 키는 코드의 기본값을 쓴다(SettingsService).
CREATE TABLE app_setting (
    key         varchar(60)  PRIMARY KEY,
    value       jsonb        NOT NULL,
    updated_by  varchar(50),
    updated_at  timestamptz  NOT NULL DEFAULT now()
);
