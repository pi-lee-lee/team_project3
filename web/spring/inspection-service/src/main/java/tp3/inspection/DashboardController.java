package tp3.inspection;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * 관제 대시보드용 요약. 화면 하나가 몇 초마다 부르므로 한 번에 모아 준다(조회만 한다).
 *
 * - today  : 오늘(DB 시간대 기준 0시부터) 작업·관측 집계
 * - points : 점검 지점별 가장 최근 관측(지도 위 상태 표시용)
 * - alerts : 최근 hours 시간 안의 주의할 일. 모양이 하나로 정해져 있어(ALERT 한 줄 = type·severity·ref)
 *            새 종류(예: 소화기 미비치, 화재 감지)를 더할 때 아래 UNION 에 한 덩어리만 붙이면 된다.
 * - events : 최근 진행 기록(모든 작업)
 */
@RestController
public class DashboardController {

    private final JdbcClient jdbc;
    private final ObjectMapper om = new ObjectMapper();

    public DashboardController(JdbcClient jdbc) {
        this.jdbc = jdbc;
    }

    /** 관측 한 건의 현재 상태(최근 분석·최근 판정을 붙인 것) */
    private static final String OBS_STATE = """
            SELECT o.observation_id, o.task_id, o.point_id, o.status, o.reason, o.reason_code, o.captured_at,
                   (o.image_path IS NOT NULL) AS has_image, a.verdict, r.result AS review_result, r.reviewed_at
            FROM observation o
            LEFT JOIN LATERAL (SELECT verdict FROM observation_analysis x WHERE x.observation_id = o.observation_id
                               ORDER BY analysis_id DESC LIMIT 1) a ON true
            LEFT JOIN LATERAL (SELECT result, reviewed_at FROM observation_review y
                               WHERE y.observation_id = o.observation_id ORDER BY review_id DESC LIMIT 1) r ON true
            """;

    @GetMapping("/api/dashboard/overview")
    public Map<String, Object> overview(@RequestParam(defaultValue = "24") int hours,
                                        @RequestParam(defaultValue = "40") int events) {
        int h = Math.max(1, Math.min(hours, 168));
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("hours", h);
        out.put("today", today());
        out.put("points", points());
        out.put("alerts", alerts(h));
        out.put("events", events(Math.max(1, Math.min(events, 200))));
        return out;
    }

    private Map<String, Object> today() {
        Map<String, Object> tasks = jdbc.sql("""
                SELECT count(*) AS total,
                       count(*) FILTER (WHERE status IN ('REQUESTED','DISPATCHED','RUNNING','CANCEL_REQUESTED')) AS active,
                       count(*) FILTER (WHERE status = 'COMPLETED') AS completed,
                       count(*) FILTER (WHERE status IN ('FAILED','INTERRUPTED')) AS failed,
                       count(*) FILTER (WHERE status = 'CANCELLED') AS cancelled
                FROM inspection_task WHERE created_at >= date_trunc('day', now())""").query().singleRow();
        Map<String, Object> obs = jdbc.sql("SELECT count(*) AS total,"
                + " count(*) FILTER (WHERE s.status = 'UNABLE') AS unable,"
                + " count(*) FILTER (WHERE s.review_result = 'NORMAL') AS normal,"
                + " count(*) FILTER (WHERE s.review_result = 'ABNORMAL') AS abnormal,"
                + " count(*) FILTER (WHERE s.status = 'CAPTURED' AND s.review_result IS NULL) AS unreviewed,"
                + " count(*) FILTER (WHERE s.verdict = 'RETAKE') AS retake"
                + " FROM (" + OBS_STATE + " WHERE o.captured_at >= date_trunc('day', now())) s").query().singleRow();
        return Map.of("tasks", tasks, "observations", obs);
    }

    private List<Map<String, Object>> points() {
        return jdbc.sql("SELECT p.point_id, p.code, p.name, p.x, p.y, p.yaw_deg,"
                + " s.observation_id, s.task_id, s.status, s.reason_code, s.captured_at, s.has_image, s.verdict,"
                + " s.review_result"
                + " FROM inspection_point p LEFT JOIN LATERAL (" + OBS_STATE
                + " WHERE o.point_id = p.point_id ORDER BY o.captured_at DESC LIMIT 1) s ON true"
                + " WHERE p.active ORDER BY p.code").query().listOfRows();
    }

    /**
     * 주의할 일. 한 줄의 모양: type · severity(CRITICAL/WARNING) · title · detail · at · ref_kind · ref_id · task_id.
     * 화면은 ref_kind 로 어떤 상세 창을 열지 정한다.
     */
    private List<Map<String, Object>> alerts(int hours) {
        return jdbc.sql("WITH s AS (" + OBS_STATE + " WHERE o.captured_at >= now() - make_interval(hours => ?)), "
                + """
                a AS (
                    SELECT 'OBS_ABNORMAL' AS type, 'CRITICAL' AS severity, s.reviewed_at AS at, 'observation' AS ref_kind,
                           s.observation_id AS ref_id, s.task_id, s.point_id, NULL::text AS detail FROM s
                    WHERE s.review_result = 'ABNORMAL'
                  UNION ALL
                    SELECT 'OBS_UNABLE', 'WARNING', s.captured_at, 'observation', s.observation_id, s.task_id, s.point_id,
                           coalesce(s.reason_code, s.reason) FROM s
                    WHERE s.status = 'UNABLE' AND s.review_result IS NULL
                  UNION ALL
                    SELECT 'OBS_RETAKE', 'WARNING', s.captured_at, 'observation', s.observation_id, s.task_id, s.point_id,
                           NULL FROM s
                    WHERE s.status = 'CAPTURED' AND s.verdict = 'RETAKE' AND s.review_result IS NULL
                  UNION ALL
                    SELECT 'TASK_' || t.status, 'WARNING', t.updated_at, 'task', t.task_id, t.task_id, NULL,
                           t.status_reason FROM inspection_task t
                    WHERE t.status IN ('FAILED', 'INTERRUPTED') AND t.updated_at >= now() - make_interval(hours => ?)
                )
                SELECT a.type, a.severity, a.at, a.ref_kind, a.ref_id, a.task_id, a.detail,
                       p.code AS point_code, p.name AS point_name
                FROM a LEFT JOIN inspection_point p USING (point_id)
                ORDER BY (a.severity = 'CRITICAL') DESC, a.at DESC LIMIT 60""")
                .params(hours, hours).query().listOfRows();
    }

    private List<Map<String, Object>> events(int limit) {
        List<Map<String, Object>> rows = jdbc.sql("""
                SELECT e.event_id, e.task_id, e.source, e.type, e.detail::text AS detail, e.actor, e.occurred_at,
                       t.robot_code, t.status AS task_status
                FROM task_event e JOIN inspection_task t USING (task_id)
                ORDER BY e.event_id DESC LIMIT ?""").param(limit).query().listOfRows();
        List<Map<String, Object>> out = new ArrayList<>(rows.size());
        for (Map<String, Object> r : rows) {
            Map<String, Object> m = new HashMap<>(r);
            try {
                m.put("detail", om.readTree(String.valueOf(r.get("detail"))));
            } catch (Exception ignored) {
                // 원문 그대로 둔다
            }
            out.add(m);
        }
        return out;
    }
}
