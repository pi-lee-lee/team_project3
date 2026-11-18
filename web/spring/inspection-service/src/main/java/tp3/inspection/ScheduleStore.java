package tp3.inspection;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Repository;

import java.sql.Timestamp;
import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.stream.Collectors;

/** 예약 점검(inspection_schedule)과 실행 기록(schedule_run). 배열·시각 열은 화면에 바로 쓸 모양으로 바꿔 돌려준다. */
@Repository
public class ScheduleStore {

    private final JdbcClient jdbc;
    private final ObjectMapper om = new ObjectMapper();

    public ScheduleStore(JdbcClient jdbc) {
        this.jdbc = jdbc;
    }

    private static final String SELECT = """
            SELECT s.schedule_id, s.name, s.robot_id, array_to_json(s.point_ids)::text AS point_ids, s.note, s.kind,
                   s.run_at, s.interval_minutes, to_char(s.time_of_day, 'HH24:MI') AS time_of_day,
                   array_to_json(s.days_of_week)::text AS days_of_week,
                   to_char(s.window_start, 'HH24:MI') AS window_start, to_char(s.window_end, 'HH24:MI') AS window_end,
                   s.enabled, s.next_run_at, s.deleted_at, s.created_by, s.creator_login, s.creator_role, s.created_at, s.updated_at,
                   (SELECT string_agg(p.code, ' → ' ORDER BY u.ord)
                      FROM unnest(s.point_ids) WITH ORDINALITY AS u(pid, ord)
                      JOIN inspection_point p ON p.point_id = u.pid) AS points,
                   lr.outcome AS last_outcome, lr.ran_at AS last_ran_at, lr.task_id AS last_task_id,
                   lr.reason AS last_reason, lr.delay_sec AS last_delay_sec
            FROM inspection_schedule s
            LEFT JOIN LATERAL (SELECT * FROM schedule_run r WHERE r.schedule_id = s.schedule_id
                               ORDER BY r.run_id DESC LIMIT 1) lr ON true
            WHERE s.deleted_at IS NULL""";

    /** 지운 예약도 포함해 하나(대기열의 회차가 실행 직전에 예약 상태를 다시 확인할 때). */
    public Optional<Map<String, Object>> getIncludingDeleted(long id) {
        return jdbc.sql(SELECT.replace("WHERE s.deleted_at IS NULL", "WHERE true") + " AND s.schedule_id = ?")
                .param(id).query().listOfRows().stream().map(this::shape).findFirst();
    }

    public List<Map<String, Object>> list() {
        return jdbc.sql(SELECT + " ORDER BY s.schedule_id DESC").query().listOfRows().stream().map(this::shape).toList();
    }

    public Optional<Map<String, Object>> get(long id) {
        return jdbc.sql(SELECT + " AND s.schedule_id = ?").param(id).query().listOfRows().stream().map(this::shape)
                .findFirst();
    }

    /** 실행할 때가 된 예약. */
    public List<Map<String, Object>> due(int limit) {
        return jdbc.sql(SELECT + " AND s.enabled AND s.next_run_at <= now() ORDER BY s.next_run_at LIMIT ?")
                .param(limit).query().listOfRows().stream().map(this::shape).toList();
    }

    /** body 값은 ScheduleService 가 검사한 뒤 넘긴다. 시각 열은 'HH:mm' 문자열, 배열은 리스트. */
    public long insert(Map<String, Object> v, long userId, String login, String role) {
        return jdbc.sql("""
                        INSERT INTO inspection_schedule (name, robot_id, point_ids, note, kind, run_at, interval_minutes,
                            time_of_day, days_of_week, window_start, window_end, enabled, next_run_at,
                            created_by, creator_login, creator_role)
                        VALUES (?, ?, CAST(? AS bigint[]), ?, ?, ?, ?, CAST(? AS time), CAST(? AS integer[]),
                                CAST(? AS time), CAST(? AS time), ?, ?, ?, ?, ?)
                        RETURNING schedule_id""")
                .params(v.get("name"), v.get("robotId"), pgArray(v.get("pointIds")), v.get("note"), v.get("kind"),
                        ts(v.get("runAt")), v.get("intervalMinutes"), v.get("timeOfDay"), pgArray(v.get("days")),
                        v.get("windowStart"), v.get("windowEnd"), v.get("enabled"), ts(v.get("nextRunAt")), userId,
                        login, role)
                .query(Long.class).single();
    }

    public void update(long id, Map<String, Object> v) {
        jdbc.sql("""
                        UPDATE inspection_schedule SET name = ?, robot_id = ?, point_ids = CAST(? AS bigint[]), note = ?,
                            kind = ?, run_at = ?, interval_minutes = ?, time_of_day = CAST(? AS time),
                            days_of_week = CAST(? AS integer[]), window_start = CAST(? AS time),
                            window_end = CAST(? AS time), enabled = ?, next_run_at = ?, updated_at = now()
                        WHERE schedule_id = ?""")
                .params(v.get("name"), v.get("robotId"), pgArray(v.get("pointIds")), v.get("note"), v.get("kind"),
                        ts(v.get("runAt")), v.get("intervalMinutes"), v.get("timeOfDay"), pgArray(v.get("days")),
                        v.get("windowStart"), v.get("windowEnd"), v.get("enabled"), ts(v.get("nextRunAt")), id)
                .update();
    }

    public void setEnabled(long id, boolean enabled, Instant next) {
        jdbc.sql("UPDATE inspection_schedule SET enabled = ?, next_run_at = ?, updated_at = now() WHERE schedule_id = ?")
                .params(enabled, ts(next), id).update();
    }

    public void delete(long id) {
        jdbc.sql("""
                        UPDATE inspection_schedule SET deleted_at = now(), enabled = false, next_run_at = NULL,
                            updated_at = now() WHERE schedule_id = ?""").param(id).update();
    }

    /**
     * 회차를 가져간다: next_run_at 이 아직 planned 일 때만 다음 시각으로 바꾼다(한 회차를 두 번 실행하지 않도록).
     * 작업 생성과 같은 트랜잭션에 묶지 않는다 — 생성이 실패해도 같은 회차를 계속 다시 시도하지 않게 하려는 것이다.
     */
    public boolean claim(long id, Instant planned, Instant next, boolean stillEnabled) {
        return jdbc.sql("""
                        UPDATE inspection_schedule SET next_run_at = ?, enabled = ?
                        WHERE schedule_id = ? AND enabled AND next_run_at = ?""")
                .params(ts(next), stillEnabled, id, ts(planned)).update() > 0;
    }

    public void insertRun(long scheduleId, Instant planned, String outcome, Long taskId, String reason, Integer delaySec) {
        jdbc.sql("""
                        INSERT INTO schedule_run (schedule_id, planned_at, outcome, task_id, reason, delay_sec)
                        VALUES (?, ?, ?, ?, ?, ?)""")
                .params(scheduleId, ts(planned), outcome, taskId, reason, delaySec).update();
    }

    public List<Map<String, Object>> runs(long scheduleId, int limit) {
        return jdbc.sql("""
                        SELECT r.run_id, r.planned_at, r.ran_at, r.outcome, r.task_id, r.reason, r.delay_sec, t.status AS task_status
                        FROM schedule_run r LEFT JOIN inspection_task t USING (task_id)
                        WHERE r.schedule_id = ? ORDER BY r.run_id DESC LIMIT ?""")
                .params(scheduleId, limit).query().listOfRows();
    }

    // ------------------------------------------------------------- 변환
    private Map<String, Object> shape(Map<String, Object> row) {
        Map<String, Object> m = new LinkedHashMap<>(row);
        for (String k : List.of("point_ids", "days_of_week")) {
            Object raw = m.get(k);
            try {
                m.put(k, raw == null ? null : om.readValue(raw.toString(), List.class));
            } catch (Exception e) {
                m.put(k, null);
            }
        }
        return m;
    }

    private static String pgArray(Object list) {
        if (!(list instanceof List<?> l) || l.isEmpty()) {
            return null;
        }
        return l.stream().map(String::valueOf).collect(Collectors.joining(",", "{", "}"));
    }

    private static Timestamp ts(Object instant) {
        return instant instanceof Instant i ? Timestamp.from(i) : null;
    }
}
