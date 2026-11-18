-- 미션 종류: INSPECTION(점검) / RESPONSE(화재 출동: 투척 위치에 도착하면 HOLDING 으로 기다린다)
ALTER TABLE mission ADD COLUMN kind varchar(20) NOT NULL DEFAULT 'INSPECTION';

-- 투척 명령: command_id 로 한 번만 실행한다(같은 ID 가 다시 오면 지난 결과를 돌려준다).
CREATE TABLE actuator_command (
    command_id  varchar(60)  PRIMARY KEY,
    robot_id    bigint       NOT NULL REFERENCES robot (robot_id),
    mission_id  bigint,
    kind        varchar(20)  NOT NULL,
    request     jsonb        NOT NULL,
    state       varchar(10)  NOT NULL,              -- SENT ACCEPTED DONE FAILED
    result      jsonb,
    created_at  timestamptz  NOT NULL DEFAULT now(),
    updated_at  timestamptz  NOT NULL DEFAULT now()
);
