-- 점검 지점: 로봇이 서서 대상을 촬영할 위치(로봇 지도 좌표)와 방향.
CREATE TABLE inspection_point (
    point_id    bigint           GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    code        varchar(20)      NOT NULL UNIQUE,
    name        varchar(100)     NOT NULL,
    description text,
    x           double precision NOT NULL,
    y           double precision NOT NULL,
    yaw_deg     double precision NOT NULL DEFAULT 0,
    active      boolean          NOT NULL DEFAULT true,
    created_at  timestamptz      NOT NULL DEFAULT now(),
    updated_at  timestamptz      NOT NULL DEFAULT now()
);

-- 시뮬레이션 월드(sim/worlds/inspection.world)의 대상 상자 앞 지점
INSERT INTO inspection_point (code, name, description, x, y, yaw_deg) VALUES
    ('P1', '소화기 앞', '빨간 상자 (2.2, 0)', 1.0, 0.0, 0),
    ('P2', '비상구 앞', '초록 상자 (0, 2.2)', 0.0, 1.0, 90),
    ('P3', '분전반 앞', '노란 상자 (-2.2, 0)', -1.0, 0.0, 180);

-- 점검 작업(요청 한 건). status 는 아래 task_event 에서 계산한 현재 값이다.
CREATE TABLE inspection_task (
    task_id         bigint       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    robot_id        bigint       NOT NULL,
    robot_code      varchar(50),
    requested_by    bigint       NOT NULL,
    requester_login varchar(50)  NOT NULL,
    note            text,
    recheck_of      bigint,      -- 재점검이면 원래 관측 ID
    status          varchar(20)  NOT NULL DEFAULT 'REQUESTED',
    status_reason   text,
    created_at      timestamptz  NOT NULL DEFAULT now(),
    updated_at      timestamptz  NOT NULL DEFAULT now()
);

CREATE TABLE task_point (
    task_id  bigint  NOT NULL REFERENCES inspection_task (task_id),
    seq      integer NOT NULL,
    point_id bigint  NOT NULL REFERENCES inspection_point (point_id),
    PRIMARY KEY (task_id, seq)
);

-- 사건 기록: 추가만 한다. 로봇 보고는 report_id 로 중복을 걸러 낸다.
CREATE TABLE task_event (
    event_id    bigint       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    task_id     bigint       NOT NULL REFERENCES inspection_task (task_id),
    report_id   uuid         UNIQUE,
    source      varchar(10)  NOT NULL CHECK (source IN ('USER', 'ROBOT', 'SYSTEM')),
    type        varchar(40)  NOT NULL,
    detail      jsonb        NOT NULL DEFAULT '{}',
    actor       varchar(50),
    occurred_at timestamptz  NOT NULL DEFAULT now(),
    received_at timestamptz  NOT NULL DEFAULT now()
);
CREATE INDEX idx_event_task ON task_event (task_id, event_id);

-- 관측: 지점 하나의 촬영 결과. 촬영하지 못했으면 UNABLE + 사유.
CREATE TABLE observation (
    observation_id         bigint           GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    task_id                bigint           NOT NULL REFERENCES inspection_task (task_id),
    point_id               bigint           NOT NULL REFERENCES inspection_point (point_id),
    seq                    integer          NOT NULL,
    status                 varchar(10)      NOT NULL CHECK (status IN ('CAPTURED', 'UNABLE')),
    reason                 text,
    image_path             text,
    captured_at            timestamptz      NOT NULL,
    received_at            timestamptz      NOT NULL DEFAULT now(),
    pose_x                 double precision,
    pose_y                 double precision,
    pose_yaw               double precision,
    report_id              uuid             NOT NULL UNIQUE,
    analysis_requested_at  timestamptz
);
CREATE INDEX idx_obs_point ON observation (point_id, captured_at DESC);
CREATE INDEX idx_obs_task ON observation (task_id);

-- 품질 분석 결과(analysis-service 가 보낸다). 다시 분석하면 행이 추가된다.
CREATE TABLE observation_analysis (
    analysis_id    bigint           GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    observation_id bigint           NOT NULL REFERENCES observation (observation_id),
    brightness     double precision,
    sharpness      double precision,
    verdict        varchar(10)      NOT NULL CHECK (verdict IN ('OK', 'RETAKE')),
    reasons        text,
    criteria       jsonb,
    analyzed_at    timestamptz      NOT NULL DEFAULT now()
);
CREATE INDEX idx_analysis_obs ON observation_analysis (observation_id, analysis_id DESC);

-- 사람 판정: 덮어쓰지 않고 쌓는다. 가장 최근 행이 현재 판정이다.
CREATE TABLE observation_review (
    review_id      bigint       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    observation_id bigint       NOT NULL REFERENCES observation (observation_id),
    result         varchar(10)  NOT NULL CHECK (result IN ('NORMAL', 'ABNORMAL', 'UNABLE')),
    comment        text,
    reviewer_id    bigint       NOT NULL,
    reviewer_login varchar(50)  NOT NULL,
    reviewed_at    timestamptz  NOT NULL DEFAULT now()
);
CREATE INDEX idx_review_obs ON observation_review (observation_id, review_id DESC);
