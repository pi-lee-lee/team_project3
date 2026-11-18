-- 관제 대시보드 전용 역할. 조회만 할 수 있다(게이트웨이 규칙: GET 만 허용, 조종 WebSocket 불가).
-- 상황실 모니터에 띄워 두는 공용 계정용이라 사용자 등급(1·2·3)과 분리한다.
INSERT INTO role (role_id, code, name, description) VALUES
    (4, 'DASHBOARD', '대시보드', '관제 대시보드 전용 (조회만)');
