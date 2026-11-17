package tp3.inspection;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Repository;

import java.sql.Timestamp;
import java.time.Instant;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;

/** inspectiondb 접근. 화면에 그대로 내보낼 수 있도록 대부분 Map 행으로 돌려준다. */
@Repository
public class Store {

    private final JdbcClient jdbc;
    private final ObjectMapper om = new ObjectMapper();

    public Store(JdbcClient jdbc) {
        this.jdbc = jdbc;
    }

    // ------------------------------------------------------------- 지점
    private static final String POINT = "SELECT point_id, code, name, description, x, y, yaw_deg, active FROM inspection_point";

    public List<Map<String, Object>> points(boolean includeInactive) {
        return jdbc.sql(POINT + (includeInactive ? "" : " WHERE active") + " ORDER BY code").query().listOfRows();
    }

    public Optional<Map<String, Object>> point(long id) {
        return jdbc.sql(POINT + " WHERE point_id = ?").param(id).query().listOfRows().stream().findFirst();
    }

    public long insertPoint(String code, String name, String desc, double x, double y, double yaw) {
        return jdbc.sql("""
                        INSERT INTO inspection_point (code, name, description, x, y, yaw_deg)
                        VALUES (?, ?, ?, ?, ?, ?) RETURNING point_id""")
                .params(code, name, desc, x, y, yaw).query(Long.class).single();
    }

    public void updatePoint(long id, String name, String desc, double x, double y, double yaw, boolean active) {
        jdbc.sql("""
                        UPDATE inspection_point SET name = ?, description = ?, x = ?, y = ?, yaw_deg = ?, active = ?,
                               updated_at = now() WHERE point_id = ?""")
                .params(name, desc, x, y, yaw, active, id).update();
    }

    // ------------------------------------------------------------- 작업
    public long insertTask(long robotId, String robotCode, long userId, String login, String note, Long recheckOf,
                           Long scheduleId) {
        return jdbc.sql("""
                        INSERT INTO inspection_task (robot_id, robot_code, requested_by, requester_login, note, recheck_of,
                                                     schedule_id)
                        VALUES (?, ?, ?, ?, ?, ?, ?) RETURNING task_id""")
                .params(robotId, robotCode, userId, login, note, recheckOf, scheduleId).query(Long.class).single();
    }

    public void insertTaskPoint(long taskId, int seq, long pointId) {
        jdbc.sql("INSERT INTO task_point (task_id, seq, point_id) VALUES (?, ?, ?)").params(taskId, seq, pointId).update();
    }

    public Optional<Map<String, Object>> task(long id) {
        return jdbc.sql("SELECT * FROM inspection_task WHERE task_id = ?").param(id).query().listOfRows().stream()
                .findFirst();
    }

    public String taskStatus(long id) {
        return jdbc.sql("SELECT status FROM inspection_task WHERE task_id = ?").param(id).query(String.class).optional()
                .orElse(null);
    }

    public void setStatus(long id, String status, String reason) {
        jdbc.sql("UPDATE inspection_task SET status = ?, status_reason = ?, updated_at = now() WHERE task_id = ?")
                .params(status, reason, id).update();
    }

    /** group: active / done / failed / null(전체) — SQL 에는 고정 문자열만 넣는다. */
    public List<Map<String, Object>> tasks(String group, Long userId, int limit) {
        String where = switch (group == null ? "" : group) {
            case "active" -> " WHERE t.status IN ('REQUESTED','DISPATCHED','RUNNING','CANCEL_REQUESTED')";
            case "done" -> " WHERE t.status = 'COMPLETED'";
            case "failed" -> " WHERE t.status IN ('FAILED','CANCELLED','INTERRUPTED')";
            default -> " WHERE true";
        };
        if (userId != null) {
            where += " AND t.requested_by = " + userId.longValue();
        }
        return jdbc.sql("""
                        SELECT t.task_id, t.robot_id, t.robot_code, t.requester_login, t.note, t.recheck_of, t.schedule_id, t.status,
                               t.status_reason, t.created_at, t.updated_at,
                               (SELECT string_agg(p.code, ', ' ORDER BY tp.seq) FROM task_point tp
                                  JOIN inspection_point p USING (point_id) WHERE tp.task_id = t.task_id) AS points,
                               (SELECT count(*) FROM observation o WHERE o.task_id = t.task_id) AS observations
                        FROM inspection_task t""" + where + " ORDER BY t.task_id DESC LIMIT ?")
                .param(limit).query().listOfRows();
    }

    public List<Map<String, Object>> taskPoints(long taskId) {
        return jdbc.sql("""
                        SELECT tp.seq, p.point_id, p.code, p.name, p.x, p.y, p.yaw_deg
                        FROM task_point tp JOIN inspection_point p USING (point_id)
                        WHERE tp.task_id = ? ORDER BY tp.seq""").param(taskId).query().listOfRows();
    }

    // ------------------------------------------------------------- 사건
    /** report_id 가 이미 있으면 false (중복 보고). */
    public boolean insertEvent(long taskId, UUID reportId, String source, String type, String detailJson, String actor,
                               Instant occurredAt) {
        return jdbc.sql("""
                        INSERT INTO task_event (task_id, report_id, source, type, detail, actor, occurred_at)
                        VALUES (?, ?, ?, ?, CAST(? AS jsonb), ?, ?) ON CONFLICT (report_id) DO NOTHING""")
                .params(taskId, reportId, source, type, detailJson, actor,
                        Timestamp.from(occurredAt == null ? Instant.now() : occurredAt))
                .update() > 0;
    }

    public List<Map<String, Object>> events(long taskId) {
        return withJson(jdbc.sql("""
                        SELECT event_id, source, type, detail::text AS detail, actor, occurred_at, received_at
                        FROM task_event WHERE task_id = ? ORDER BY occurred_at, event_id""")
                .param(taskId).query().listOfRows(), "detail");
    }

    // ------------------------------------------------------------- 관측
    private static final String OBS = """
            SELECT o.observation_id, o.task_id, o.point_id, p.code AS point_code, p.name AS point_name, o.seq, o.status,
                   o.reason, o.reason_code, (o.image_path IS NOT NULL) AS has_image, o.captured_at, o.received_at,
                   o.pose_x, o.pose_y, o.pose_yaw, t.recheck_of, t.requester_login, t.robot_code,
                   a.brightness, a.sharpness, a.verdict, a.reasons AS analysis_reasons, a.analyzed_at,
                   r.result AS review_result, r.comment AS review_comment, r.reviewer_login, r.reviewed_at
            FROM observation o
            JOIN inspection_point p USING (point_id)
            JOIN inspection_task t USING (task_id)
            LEFT JOIN LATERAL (SELECT * FROM observation_analysis x WHERE x.observation_id = o.observation_id
                               ORDER BY analysis_id DESC LIMIT 1) a ON true
            LEFT JOIN LATERAL (SELECT * FROM observation_review y WHERE y.observation_id = o.observation_id
                               ORDER BY review_id DESC LIMIT 1) r ON true
            """;

    public List<Map<String, Object>> observationsOfTask(long taskId) {
        return jdbc.sql(OBS + " WHERE o.task_id = ? ORDER BY o.seq, o.observation_id").param(taskId).query().listOfRows();
    }

    public List<Map<String, Object>> observationsOfPoint(long pointId, int limit) {
        return jdbc.sql(OBS + " WHERE o.point_id = ? ORDER BY o.captured_at DESC LIMIT ?").params(pointId, limit)
                .query().listOfRows();
    }

    public Optional<Map<String, Object>> observation(long id) {
        return jdbc.sql(OBS + " WHERE o.observation_id = ?").param(id).query().listOfRows().stream().findFirst();
    }

    public Optional<String> imagePath(long id) {
        return jdbc.sql("SELECT image_path FROM observation WHERE observation_id = ?").param(id).query(String.class)
                .optional();
    }

    /** report_id 가 이미 있으면 empty (중복 보고). */
    public Optional<Long> insertObservation(long taskId, long pointId, int seq, String status, String reason,
                                            String reasonCode, String imagePath, Instant capturedAt, Double x,
                                            Double y, Double yaw, UUID reportId) {
        return jdbc.sql("""
                        INSERT INTO observation (task_id, point_id, seq, status, reason, reason_code, image_path,
                                                 captured_at, pose_x, pose_y, pose_yaw, report_id)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT (report_id) DO NOTHING RETURNING observation_id""")
                .params(taskId, pointId, seq, status, reason, reasonCode, imagePath, Timestamp.from(capturedAt), x, y,
                        yaw, reportId)
                .query(Long.class).optional();
    }

    public List<Long> observationsNeedingAnalysis() {
        return jdbc.sql("""
                        SELECT o.observation_id FROM observation o
                        WHERE o.status = 'CAPTURED' AND o.image_path IS NOT NULL
                          AND NOT EXISTS (SELECT 1 FROM observation_analysis a WHERE a.observation_id = o.observation_id)
                          AND (o.analysis_requested_at IS NULL OR o.analysis_requested_at < now() - interval '60 seconds')
                        ORDER BY o.observation_id LIMIT 20""").query(Long.class).list();
    }

    public void markAnalysisRequested(long id) {
        jdbc.sql("UPDATE observation SET analysis_requested_at = now() WHERE observation_id = ?").param(id).update();
    }

    public void insertAnalysis(long obsId, Double brightness, Double sharpness, String verdict, String reasons,
                               String criteria) {
        jdbc.sql("""
                        INSERT INTO observation_analysis (observation_id, brightness, sharpness, verdict, reasons, criteria)
                        VALUES (?, ?, ?, ?, ?, CAST(? AS jsonb))""")
                .params(obsId, brightness, sharpness, verdict, reasons, criteria).update();
    }

    public void insertReview(long obsId, String result, String comment, long userId, String login) {
        jdbc.sql("""
                        INSERT INTO observation_review (observation_id, result, comment, reviewer_id, reviewer_login)
                        VALUES (?, ?, ?, ?, ?)""")
                .params(obsId, result, comment, userId, login).update();
    }

    public List<Map<String, Object>> reviewsOfTask(long taskId) {
        return jdbc.sql("""
                        SELECT r.* FROM observation_review r JOIN observation o USING (observation_id)
                        WHERE o.task_id = ? ORDER BY r.review_id""").param(taskId).query().listOfRows();
    }

    private List<Map<String, Object>> withJson(List<Map<String, Object>> rows, String col) {
        return rows.stream().map(r -> {
            Map<String, Object> m = new HashMap<>(r);
            try {
                m.put(col, om.readTree(String.valueOf(r.get(col))));
            } catch (Exception ignored) {
                // 원문 그대로 둔다
            }
            return m;
        }).toList();
    }
}
