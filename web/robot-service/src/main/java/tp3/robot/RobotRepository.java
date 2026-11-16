package tp3.robot;

import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;

@Repository
public class RobotRepository {

    public record Robot(long robotId, String code, String name, String adapterType, String config, boolean enabled) {
    }

    public record Mission(long missionId, long robotId, String waypoints, String state, String reason) {
    }

    public record Report(UUID reportId, long missionId, String kind, String payload, byte[] image, int attempts) {
    }

    private final JdbcClient jdbc;

    public RobotRepository(JdbcClient jdbc) {
        this.jdbc = jdbc;
    }

    // ---- robot
    private static final String ROBOT = "SELECT robot_id, code, name, adapter_type, config::text AS config, enabled FROM robot";

    public List<Robot> robots() {
        return jdbc.sql(ROBOT + " ORDER BY robot_id").query(Robot.class).list();
    }

    public Optional<Robot> robot(long id) {
        return jdbc.sql(ROBOT + " WHERE robot_id = ?").param(id).query(Robot.class).optional();
    }

    public long insertRobot(String code, String name, String adapterType, String config, boolean enabled) {
        return jdbc.sql("""
                        INSERT INTO robot (code, name, adapter_type, config, enabled)
                        VALUES (?, ?, ?, CAST(? AS jsonb), ?) RETURNING robot_id""")
                .params(code, name, adapterType, config, enabled).query(Long.class).single();
    }

    public void updateRobot(long id, String name, String adapterType, String config, boolean enabled) {
        jdbc.sql("""
                        UPDATE robot SET name = ?, adapter_type = ?, config = CAST(? AS jsonb), enabled = ?, updated_at = now()
                        WHERE robot_id = ?""")
                .params(name, adapterType, config, enabled, id).update();
    }

    // ---- mission
    private static final String MISSION = "SELECT mission_id, robot_id, waypoints::text AS waypoints, state, reason FROM mission";

    public Optional<Mission> mission(long id) {
        return jdbc.sql(MISSION + " WHERE mission_id = ?").param(id).query(Mission.class).optional();
    }

    public List<Mission> unfinishedMissions() {
        return jdbc.sql(MISSION + " WHERE state IN ('ACCEPTED', 'RUNNING')").query(Mission.class).list();
    }

    public void insertMission(long id, long robotId, String waypoints) {
        jdbc.sql("INSERT INTO mission (mission_id, robot_id, waypoints, state) VALUES (?, ?, CAST(? AS jsonb), 'ACCEPTED')")
                .params(id, robotId, waypoints).update();
    }

    public void missionState(long id, String state, String reason) {
        jdbc.sql("UPDATE mission SET state = ?, reason = ?, updated_at = now() WHERE mission_id = ?")
                .params(state, reason, id).update();
    }

    // ---- outbox
    public void enqueue(long missionId, String kind, String payload, byte[] image) {
        jdbc.sql("""
                        INSERT INTO report_outbox (report_id, mission_id, kind, payload, image)
                        VALUES (?, ?, ?, CAST(? AS jsonb), ?)""")
                .params(UUID.randomUUID(), missionId, kind, payload, image).update();
    }

    public List<Report> pending(int limit) {
        return jdbc.sql("""
                        SELECT report_id, mission_id, kind, payload::text AS payload, image, attempts
                        FROM report_outbox WHERE sent_at IS NULL ORDER BY created_at LIMIT ?""")
                .param(limit).query(Report.class).list();
    }

    public void markSent(UUID id) {
        jdbc.sql("UPDATE report_outbox SET sent_at = now(), attempts = attempts + 1 WHERE report_id = ?").param(id).update();
    }

    public void markFailed(UUID id, String error) {
        jdbc.sql("UPDATE report_outbox SET attempts = attempts + 1, last_error = ? WHERE report_id = ?")
                .params(error, id).update();
    }

    public Map<String, Object> outboxStats() {
        return jdbc.sql("""
                        SELECT count(*) FILTER (WHERE sent_at IS NULL) AS pending,
                               count(*) FILTER (WHERE sent_at IS NOT NULL) AS sent
                        FROM report_outbox""").query().singleRow();
    }
}
