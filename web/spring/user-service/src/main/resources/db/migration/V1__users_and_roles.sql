-- 사용자·역할 테이블
-- 역할: ADMIN(웹사이트 admin) / 1 관리자 / 2 매니저 / 3 사용자
-- 역할별 세부 권한은 서비스 구현 단계에서 정한다 (permission, role_permission 테이블을 그때 추가).

CREATE TABLE role (
    role_id     smallint     PRIMARY KEY,
    code        varchar(20)  NOT NULL UNIQUE,   -- 코드에서 쓰는 이름 (Spring Security: ROLE_<code>)
    name        varchar(50)  NOT NULL,          -- 화면에 보이는 이름
    description text
);

INSERT INTO role (role_id, code, name, description) VALUES
    (0, 'ADMIN',      '웹사이트 admin', '웹사이트 관리자 (웹용)'),
    (1, 'SUPERVISOR', '관리자',         '사용자 1등급'),
    (2, 'MANAGER',    '매니저',         '사용자 2등급'),
    (3, 'USER',       '사용자',         '사용자 3등급');

CREATE TABLE users (
    user_id       bigint       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    login_id      varchar(50)  NOT NULL UNIQUE,
    password_hash varchar(255) NOT NULL,          -- BCrypt 등 해시만 저장, 평문 금지
    name          varchar(50)  NOT NULL,
    role_id       smallint     NOT NULL REFERENCES role (role_id),
    status        varchar(10)  NOT NULL DEFAULT 'ACTIVE'
                  CHECK (status IN ('ACTIVE', 'SUSPENDED')),
    created_at    timestamptz  NOT NULL DEFAULT now(),
    updated_at    timestamptz  NOT NULL DEFAULT now(),
    last_login_at timestamptz
);

CREATE INDEX idx_users_role ON users (role_id);
