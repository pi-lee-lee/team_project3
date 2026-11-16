-- 세션 강제 종료: 토큰에 넣은 버전보다 DB 버전이 크면 게이트웨이가 토큰을 거부한다.
ALTER TABLE users ADD COLUMN token_version integer NOT NULL DEFAULT 0;

-- 감사 로그: 추가만 한다(수정·삭제하지 않음).
CREATE TABLE audit_log (
    audit_id    bigint       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    occurred_at timestamptz  NOT NULL DEFAULT now(),
    user_id     bigint,
    login_id    varchar(50),
    role_code   varchar(20),
    action      varchar(20)  NOT NULL,   -- HTTP 메서드 또는 LOGIN / LOGIN_FAILED
    target      varchar(255) NOT NULL,   -- 요청 경로 등
    status      integer,                 -- 응답 코드
    detail      text
);

CREATE INDEX idx_audit_time ON audit_log USING brin (occurred_at);
