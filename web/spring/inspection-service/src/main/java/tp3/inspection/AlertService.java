package tp3.inspection;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * 경고(alert 표). 같은 대상 · 같은 종류(dedup_key)의 열린 경고는 하나만 둔다:
 * 다시 생기면 그 줄의 등급 · 근거를 고치고, 비상으로 올라가면 확인(ACKED)했던 것도 다시 연다.
 * 흐름은 docs/design/INTERFACES.md 7장 F2.
 */
@Service
public class AlertService {

    public record Draft(String type, String grade, String dedupKey, String title, String detail, Long pointId,
                        Double x, Double y, String refKind, long refId, Long taskId, Map<String, ?> evidence) {
    }

    private final JdbcClient jdbc;
    private final ObjectMapper om = new ObjectMapper();

    public AlertService(JdbcClient jdbc) {
        this.jdbc = jdbc;
    }

    public long open(Draft d) {
        return jdbc.sql("""
                        INSERT INTO alert (type, grade, dedup_key, title, detail, point_id, x, y, ref_kind, ref_id, task_id, evidence)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CAST(? AS jsonb))
                        ON CONFLICT (dedup_key) WHERE state <> 'RESOLVED' DO UPDATE SET
                            state = CASE WHEN alert.grade <> 'EMERGENCY' AND EXCLUDED.grade = 'EMERGENCY' THEN 'OPEN'
                                         ELSE alert.state END,
                            grade = EXCLUDED.grade, title = EXCLUDED.title, detail = EXCLUDED.detail,
                            ref_kind = EXCLUDED.ref_kind, ref_id = EXCLUDED.ref_id, task_id = EXCLUDED.task_id,
                            evidence = EXCLUDED.evidence, updated_at = now()
                        RETURNING alert_id""")
                .params(d.type(), d.grade(), d.dedupKey(), cut(d.title(), 200), d.detail(), d.pointId(), d.x(), d.y(),
                        d.refKind(), d.refId(), d.taskId(), json(d.evidence()))
                .query(Long.class).single();
    }

    /** 열린 경고를 푼다. 없으면 아무 일도 없다. */
    public int resolveByKey(String dedupKey, String by, String comment) {
        return jdbc.sql("""
                        UPDATE alert SET state = 'RESOLVED', resolved_by = ?, resolved_at = now(), updated_at = now(),
                                         comment = coalesce(?, comment)
                        WHERE dedup_key = ? AND state <> 'RESOLVED'""").params(by, comment, dedupKey).update();
    }

    /** 사람이 관측을 판정했을 때: 정상이면 그 관측에서 나온 경고를 풀고, 이상이면 비상으로 올린다. */
    public void onReview(long observationId, String result, String by) {
        if ("NORMAL".equals(result)) {
            jdbc.sql("""
                            UPDATE alert SET state = 'RESOLVED', resolved_by = ?, resolved_at = now(), updated_at = now(),
                                             comment = '사람 판정: 정상'
                            WHERE ref_kind = 'observation' AND ref_id = ? AND state <> 'RESOLVED'""")
                    .params(by, observationId).update();
        } else if ("ABNORMAL".equals(result)) {
            jdbc.sql("""
                            UPDATE alert SET grade = 'EMERGENCY', state = 'OPEN', updated_at = now(), comment = '사람 판정: 이상'
                            WHERE ref_kind = 'observation' AND ref_id = ? AND state <> 'RESOLVED'""")
                    .param(observationId).update();
        }
    }

    public void ack(long id, String by, String comment) {
        int n = jdbc.sql("""
                        UPDATE alert SET state = 'ACKED', acked_by = ?, acked_at = now(), updated_at = now(),
                                         comment = coalesce(?, comment)
                        WHERE alert_id = ? AND state = 'OPEN'""").params(by, blank(comment), id).update();
        if (n == 0) {
            throw new ResponseStatusException(get(id) == null ? HttpStatus.NOT_FOUND : HttpStatus.CONFLICT,
                    "열려 있는 경고가 아닙니다");
        }
    }

    public void resolve(long id, String by, String comment) {
        int n = jdbc.sql("""
                        UPDATE alert SET state = 'RESOLVED', resolved_by = ?, resolved_at = now(), updated_at = now(),
                                         comment = coalesce(?, comment)
                        WHERE alert_id = ? AND state <> 'RESOLVED'""").params(by, blank(comment), id).update();
        if (n == 0) {
            throw new ResponseStatusException(get(id) == null ? HttpStatus.NOT_FOUND : HttpStatus.CONFLICT,
                    "이미 해제된 경고입니다");
        }
    }

    private static final String SELECT = """
            SELECT a.alert_id, a.type, a.grade, a.state, a.title, a.detail, a.point_id, p.code AS point_code,
                   p.name AS point_name, a.x, a.y, a.ref_kind, a.ref_id, a.task_id, a.evidence::text AS evidence,
                   a.opened_at, a.updated_at, a.acked_by, a.acked_at, a.resolved_by, a.resolved_at, a.comment
            FROM alert a LEFT JOIN inspection_point p USING (point_id)
            """;

    /** states: OPEN, ACKED, RESOLVED 중에서. 비상 먼저, 그다음 최근 순. */
    public List<Map<String, Object>> list(List<String> states, int limit) {
        List<String> ok = states.stream().filter(s -> List.of("OPEN", "ACKED", "RESOLVED").contains(s)).toList();
        if (ok.isEmpty()) {
            ok = List.of("OPEN", "ACKED");
        }
        String in = String.join(",", ok.stream().map(s -> "'" + s + "'").toList());   // 고정 문자열만 들어간다
        return parse(jdbc.sql(SELECT + " WHERE a.state IN (" + in + ")"
                + " ORDER BY (a.state = 'RESOLVED'), (a.grade = 'EMERGENCY') DESC, a.updated_at DESC LIMIT ?")
                .param(Math.max(1, Math.min(limit, 500))).query().listOfRows());
    }

    public Map<String, Object> get(long id) {
        return parse(jdbc.sql(SELECT + " WHERE a.alert_id = ?").param(id).query().listOfRows()).stream().findFirst()
                .orElse(null);
    }

    private List<Map<String, Object>> parse(List<Map<String, Object>> rows) {
        List<Map<String, Object>> out = new ArrayList<>(rows.size());
        for (var r : rows) {
            Map<String, Object> m = new HashMap<>(r);
            try {
                m.put("evidence", om.readTree(String.valueOf(r.get("evidence"))));
            } catch (Exception ignored) {
                // 원문 그대로 둔다
            }
            out.add(m);
        }
        return out;
    }

    private String json(Object o) {
        try {
            return om.writeValueAsString(o == null ? Map.of() : o);
        } catch (Exception e) {
            return "{}";
        }
    }

    private static String cut(String s, int n) {
        return s == null ? "" : s.length() <= n ? s : s.substring(0, n);
    }

    private static String blank(String s) {
        return s == null || s.isBlank() ? null : s.trim();
    }
}
