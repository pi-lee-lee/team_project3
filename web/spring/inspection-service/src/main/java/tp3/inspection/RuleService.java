package tp3.inspection;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.core.io.ByteArrayResource;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Service;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.util.MultiValueMap;
import org.springframework.web.client.RestClient;
import org.springframework.web.server.ResponseStatusException;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * 점검 규칙과 판독 결과.
 * 규칙 = 판독기 종류(kind) + 설정(params) + 로봇 종류별 영역(regions) + 등급 기준(grading).
 * 판독은 analysis-service 가 한다. 여기서는 규칙을 보관해 넘겨 주고, 돌아온 결과를 저장하고, 등급에 따라 경고를 열거나 푼다.
 * 모양은 docs/design/INTERFACES.md 3.3 · 3.4, 흐름은 7장 F2.
 */
@Service
public class RuleService {

    private static final Logger log = LoggerFactory.getLogger(RuleService.class);
    static final List<String> GRADES = List.of("NORMAL", "UNKNOWN", "WARNING", "EMERGENCY");   // 뒤로 갈수록 나쁘다

    private final JdbcClient jdbc;
    private final Store store;
    private final AlertService alerts;
    private final TaskService tasks;
    private final RestClient analysis;
    private final ObjectMapper om = new ObjectMapper();
    private volatile JsonNode checkersCache;
    private volatile long checkersAt;

    public RuleService(JdbcClient jdbc, Store store, AlertService alerts, TaskService tasks, RestClient analysisClient) {
        this.jdbc = jdbc;
        this.store = store;
        this.alerts = alerts;
        this.tasks = tasks;
        this.analysis = analysisClient;
    }

    // ------------------------------------------------------------- 규칙
    private static final String RULE = """
            SELECT r.rule_id, r.point_id, p.code AS point_code, p.name AS point_name, r.name, r.kind, r.enabled,
                   r.params::text AS params, r.regions::text AS regions, r.grading::text AS grading,
                   r.target_x, r.target_y, r.target_yaw, r.target_size_m, r.use_as_reference, r.updated_at
            FROM inspection_rule r JOIN inspection_point p USING (point_id)
            """;

    public List<Map<String, Object>> rulesOfPoint(long pointId, boolean enabledOnly) {
        return jdbc.sql(RULE + " WHERE r.point_id = ? AND r.deleted_at IS NULL" + (enabledOnly ? " AND r.enabled" : "")
                + " ORDER BY r.rule_id").param(pointId).query().listOfRows().stream().map(this::toRule).toList();
    }

    public Map<String, Object> rule(long id) {
        return jdbc.sql(RULE + " WHERE r.rule_id = ? AND r.deleted_at IS NULL").param(id).query().listOfRows().stream()
                .findFirst().map(this::toRule)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "없는 규칙"));
    }

    /** DB 행 → 화면 · 판독기가 쓰는 규칙 모양(INTERFACES.md 3.3). */
    private Map<String, Object> toRule(Map<String, Object> r) {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("ruleId", r.get("rule_id"));
        m.put("pointId", r.get("point_id"));
        m.put("pointCode", r.get("point_code"));
        m.put("pointName", r.get("point_name"));
        m.put("name", r.get("name"));
        m.put("kind", r.get("kind"));
        m.put("enabled", r.get("enabled"));
        m.put("params", parse(r.get("params")));
        m.put("regions", parse(r.get("regions")));
        m.put("grading", parse(r.get("grading")));
        Map<String, Object> t = new LinkedHashMap<>();
        t.put("x", r.get("target_x"));
        t.put("y", r.get("target_y"));
        t.put("yaw", r.get("target_yaw"));
        t.put("sizeM", r.get("target_size_m"));
        t.put("useAsReference", r.get("use_as_reference"));
        m.put("target", t);
        m.put("updatedAt", r.get("updated_at"));
        return m;
    }

    public Map<String, Object> create(long pointId, JsonNode b) {
        store.point(pointId).orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "없는 지점"));
        validate(b);
        JsonNode t = b.path("target");
        long id = jdbc.sql("""
                        INSERT INTO inspection_rule (point_id, name, kind, params, regions, grading, target_x, target_y,
                                                     target_yaw, target_size_m, use_as_reference, enabled)
                        VALUES (?, ?, ?, CAST(? AS jsonb), CAST(? AS jsonb), CAST(? AS jsonb), ?, ?, ?, ?, ?, ?)
                        RETURNING rule_id""")
                .params(pointId, b.path("name").asText().trim(), b.path("kind").asText(), obj(b, "params"),
                        obj(b, "regions"), b.path("grading").toString(), num(t, "x"), num(t, "y"), num(t, "yaw"),
                        num(t, "sizeM"), t.path("useAsReference").asBoolean(false), b.path("enabled").asBoolean(true))
                .query(Long.class).single();
        return rule(id);
    }

    public Map<String, Object> update(long id, JsonNode b) {
        rule(id);
        validate(b);
        JsonNode t = b.path("target");
        jdbc.sql("""
                        UPDATE inspection_rule SET name = ?, kind = ?, params = CAST(? AS jsonb), regions = CAST(? AS jsonb),
                               grading = CAST(? AS jsonb), target_x = ?, target_y = ?, target_yaw = ?, target_size_m = ?,
                               use_as_reference = ?, enabled = ?, updated_at = now()
                        WHERE rule_id = ?""")
                .params(b.path("name").asText().trim(), b.path("kind").asText(), obj(b, "params"), obj(b, "regions"),
                        b.path("grading").toString(), num(t, "x"), num(t, "y"), num(t, "yaw"), num(t, "sizeM"),
                        t.path("useAsReference").asBoolean(false), b.path("enabled").asBoolean(true), id)
                .update();
        if (!b.path("enabled").asBoolean(true)) {
            alerts.resolveByKey("rule:" + id, "SYSTEM", "규칙을 껐음");
        }
        return rule(id);
    }

    public void delete(long id) {
        rule(id);
        jdbc.sql("UPDATE inspection_rule SET deleted_at = now(), enabled = false WHERE rule_id = ?").param(id).update();
        alerts.resolveByKey("rule:" + id, "SYSTEM", "규칙을 지웠음");
    }

    private void validate(JsonNode b) {
        if (b.path("name").asText("").isBlank()) {
            throw bad("규칙 이름을 넣으세요");
        }
        String kind = b.path("kind").asText("");
        JsonNode cs = checkers();
        if (cs != null && cs.isArray()) {
            boolean known = false;
            for (JsonNode c : cs) {
                known |= kind.equals(c.path("kind").asText());
            }
            if (!known) {
                throw bad("없는 판독기 종류: " + kind);
            }
        } else if (kind.isBlank()) {
            throw bad("판독기 종류를 고르세요");
        }
        JsonNode g = b.path("grading");
        String type = g.path("type").asText("");
        if (!("map".equals(type) && g.path("map").isObject()) && !("ranges".equals(type) && g.path("ranges").isArray())) {
            throw bad("등급 기준(grading)은 {type: map, map: {...}} 또는 {type: ranges, ranges: [...]} 모양이어야 합니다");
        }
        b.path("regions").fields().forEachRemaining(e -> {
            JsonNode a = e.getValue();
            if (!a.isArray() || a.size() != 4) {
                throw bad("영역은 [x0, y0, x1, y1] 네 숫자(0~1)입니다");
            }
        });
    }

    /** 판독기 목록(analysis-service). 30초 동안 기억한다. 분석 서비스가 멈춰 있으면 null. */
    public JsonNode checkers() {
        if (checkersCache != null && System.currentTimeMillis() - checkersAt < 30_000) {
            return checkersCache;
        }
        try {
            checkersCache = analysis.get().uri("/checkers").retrieve().body(JsonNode.class);
            checkersAt = System.currentTimeMillis();
        } catch (Exception e) {
            log.debug("checkers unavailable: {}", e.toString());
        }
        return checkersCache;
    }

    // ------------------------------------------------------------- 판독 요청에 넘길 것
    /** 그 관측의 지점에 걸린, 켜져 있는 규칙(S4). 사진이 없는 관측이면 빈 목록. */
    public Map<String, Object> rulesForObservation(long observationId) {
        var obs = store.observation(observationId).orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND));
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("robotKind", "INSPECTOR");      // 지금은 터틀봇뿐이다. 젯봇이 붙으면 관측의 robot_kind 를 쓴다
        m.put("cameraFrame", "RGB");
        m.put("camera", null);
        m.put("rules", "CAPTURED".equals(obs.get("status"))
                ? rulesOfPoint(((Number) obs.get("point_id")).longValue(), true) : List.of());
        return m;
    }

    /** 즉시 판독(C2): 사진과 규칙을 analysis-service 에 보내 결과를 받는다. 규칙 시험과 도착 후 재판독에 쓴다. */
    public JsonNode check(byte[] jpeg, List<?> rules, String robotKind) {
        MultiValueMap<String, Object> form = new LinkedMultiValueMap<>();
        HttpHeaders ih = new HttpHeaders();
        ih.setContentType(MediaType.IMAGE_JPEG);
        form.add("image", new HttpEntity<>(new ByteArrayResource(jpeg) {
            @Override
            public String getFilename() {
                return "image.jpg";
            }
        }, ih));
        form.add("request", json(Map.of("rules", rules, "robotKind", robotKind, "cameraFrame", "RGB")));
        return analysis.post().uri("/check").contentType(MediaType.MULTIPART_FORM_DATA).body(form).retrieve()
                .body(JsonNode.class);
    }

    // ------------------------------------------------------------- 결과 저장 → 경고
    /** analysis-service 가 보낸 규칙별 결과를 저장하고(D2), 등급에 따라 경고를 열거나 푼다(F2). */
    public void saveResults(long observationId, JsonNode results) {
        if (results == null || !results.isArray() || results.isEmpty()) {
            return;
        }
        var obs = store.observation(observationId).orElse(null);
        if (obs == null) {
            return;
        }
        long taskId = ((Number) obs.get("task_id")).longValue();
        String worst = "NORMAL";
        List<String> notes = new ArrayList<>();
        for (JsonNode r : results) {
            long ruleId = r.path("ruleId").asLong();
            Map<String, Object> rule;
            try {
                rule = rule(ruleId);
            } catch (ResponseStatusException e) {
                continue;   // 판독하는 사이 규칙이 지워졌다
            }
            String grade = GRADES.contains(r.path("grade").asText()) ? r.path("grade").asText() : "UNKNOWN";
            JsonNode v = r.path("value");
            jdbc.sql("""
                            INSERT INTO rule_result (observation_id, rule_id, grade, value_num, value_label, unit, confidence,
                                                     located, evidence, reason, checker_version, rule_snapshot)
                            VALUES (?, ?, ?, ?, ?, ?, ?, CAST(? AS jsonb), CAST(? AS jsonb), ?, ?, CAST(? AS jsonb))""")
                    .params(observationId, ruleId, grade, v.isNumber() ? v.asDouble() : null,
                            v.isTextual() ? v.asText() : null, r.path("unit").asText(null),
                            r.hasNonNull("confidence") ? r.path("confidence").asDouble() : null,
                            r.hasNonNull("located") ? r.path("located").toString() : null,
                            r.hasNonNull("evidence") ? r.path("evidence").toString() : null,
                            r.path("reason").asText(null), r.path("checkerVersion").asText(null), json(rule))
                    .update();
            if (GRADES.indexOf(grade) > GRADES.indexOf(worst)) {
                worst = grade;
            }
            String shown = v.isNumber() ? fmt(v.asDouble()) + (r.hasNonNull("unit") ? " " + r.path("unit").asText() : "")
                    : v.asText("");
            if (!"NORMAL".equals(grade)) {
                notes.add(rule.get("name") + " " + GRADE_KO.get(grade) + (shown.isBlank() ? "" : " (" + shown + ")"));
            }
            String key = "rule:" + ruleId;
            if ("WARNING".equals(grade) || "EMERGENCY".equals(grade)) {
                @SuppressWarnings("unchecked")
                Map<String, Object> t = (Map<String, Object>) rule.get("target");
                Map<String, Object> ev = new LinkedHashMap<>();
                ev.put("ruleId", ruleId);
                ev.put("kind", rule.get("kind"));
                ev.put("value", v);
                ev.put("unit", r.path("unit").asText(null));
                ev.put("observationId", observationId);
                String detail = r.path("reason").asText("");
                alerts.open(new AlertService.Draft("RULE_VIOLATION", grade, key,
                        obs.get("point_code") + " " + obs.get("point_name") + " · " + rule.get("name"),
                        (shown.isBlank() ? "" : "읽은 값 " + shown) + (detail.isBlank() ? "" : (shown.isBlank() ? "" : " · ") + detail),
                        ((Number) obs.get("point_id")).longValue(), dbl(t.get("x")), dbl(t.get("y")), "observation",
                        observationId, taskId, ev));
            } else if ("NORMAL".equals(grade)) {
                alerts.resolveByKey(key, "SYSTEM", "다음 점검에서 정상 확인 (관측 #" + observationId + ")");
            }
            // UNKNOWN: 정상 확인이 아니므로 열린 경고는 그대로 둔다
        }
        Map<String, Object> d = new LinkedHashMap<>();
        d.put("observationId", observationId);
        d.put("pointCode", obs.get("point_code"));
        d.put("grade", worst);
        if (!notes.isEmpty()) {
            d.put("reason", String.join(", ", notes));
        }
        tasks.systemEvent(taskId, "RULES_CHECKED", d);
    }

    static final Map<String, String> GRADE_KO = Map.of("NORMAL", "정상", "WARNING", "경고", "EMERGENCY", "비상",
            "UNKNOWN", "판독 불가");

    private static final String RESULT = """
            SELECT x.result_id, x.observation_id, x.rule_id, x.grade, x.value_num, x.value_label, x.unit, x.confidence,
                   x.located::text AS located, x.evidence::text AS evidence, x.reason, x.checker_version, x.analyzed_at,
                   x.rule_snapshot::text AS rule
            FROM rule_result x
            """;

    /** 관측의 규칙별 결과(규칙마다 가장 최근 것). */
    public List<Map<String, Object>> resultsOfObservation(long observationId) {
        return jdbc.sql(RESULT + """
                        WHERE x.result_id IN (SELECT max(result_id) FROM rule_result WHERE observation_id = ? GROUP BY rule_id)
                        ORDER BY x.rule_id""").param(observationId).query().listOfRows().stream().map(this::toResult).toList();
    }

    /** 규칙의 가장 최근 결과(어느 관측이든). 없으면 null. */
    public Map<String, Object> latestResult(long ruleId) {
        return jdbc.sql(RESULT + " WHERE x.rule_id = ? ORDER BY x.result_id DESC LIMIT 1").param(ruleId).query()
                .listOfRows().stream().findFirst().map(this::toResult).orElse(null);
    }

    private Map<String, Object> toResult(Map<String, Object> r) {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("resultId", r.get("result_id"));
        m.put("observationId", r.get("observation_id"));
        m.put("ruleId", r.get("rule_id"));
        m.put("grade", r.get("grade"));
        m.put("value", r.get("value_num") != null ? r.get("value_num") : r.get("value_label"));
        m.put("unit", r.get("unit"));
        m.put("confidence", r.get("confidence"));
        m.put("located", parse(r.get("located")));
        m.put("evidence", parse(r.get("evidence")));
        m.put("reason", r.get("reason"));
        m.put("checkerVersion", r.get("checker_version"));
        m.put("analyzedAt", r.get("analyzed_at"));
        m.put("rule", parse(r.get("rule")));
        return m;
    }

    // ------------------------------------------------------------- 도우미
    private JsonNode parse(Object text) {
        try {
            return text == null ? om.nullNode() : om.readTree(String.valueOf(text));
        } catch (Exception e) {
            return om.nullNode();
        }
    }

    private String json(Object o) {
        try {
            return om.writeValueAsString(o);
        } catch (Exception e) {
            return "{}";
        }
    }

    private static String obj(JsonNode b, String f) {
        return b.path(f).isObject() ? b.path(f).toString() : "{}";
    }

    private static Double num(JsonNode n, String f) {
        return n.hasNonNull(f) ? n.path(f).asDouble() : null;
    }

    private static Double dbl(Object o) {
        return o == null ? null : ((Number) o).doubleValue();
    }

    private static String fmt(double v) {
        return Math.abs(v) >= 100 ? String.format("%.0f", v) : String.format("%.2f", v);
    }

    private static ResponseStatusException bad(String msg) {
        return new ResponseStatusException(HttpStatus.BAD_REQUEST, msg);
    }
}
