-- 금지구역: 관리자가 지도에 그려 둔 직사각형. 로봇은 이 안으로 계획하지도, 들어가지도 않는다(공사 중인 구역 등).
-- 좌표는 지도 좌표(m). 로봇마다 지도가 다르므로 로봇에 딸린다.
CREATE TABLE keepout_zone (
    zone_id    bigserial PRIMARY KEY,
    robot_id   bigint           NOT NULL REFERENCES robot (robot_id) ON DELETE CASCADE,
    name       varchar(60)      NOT NULL DEFAULT '',
    x_min      double precision NOT NULL,
    y_min      double precision NOT NULL,
    x_max      double precision NOT NULL,
    y_max      double precision NOT NULL,
    created_by varchar(60)      NOT NULL,
    created_at timestamptz      NOT NULL DEFAULT now(),
    CHECK (x_max > x_min AND y_max > y_min)
);
CREATE INDEX keepout_zone_robot ON keepout_zone (robot_id);
