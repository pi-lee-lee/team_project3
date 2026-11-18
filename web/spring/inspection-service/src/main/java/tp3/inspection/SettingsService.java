package tp3.inspection;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;

import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Set;

/**
 * 설정: 값이 정해지지 않은 항목(투척 사거리, 열화상 기준 등)을 코드가 아니라 여기서 받는다.
 * 표(app_setting)에 없는 키는 아래 기본값을 쓴다. 키 목록과 뜻은 docs/plan/INTERFACES.md 8장.
 */
@Service
public class SettingsService {

    /** 키 → 기본값(JSON 글자). 여기 없는 키는 저장할 수 없다. */
    private static final Map<String, String> DEFAULTS = new LinkedHashMap<>();

    static {
        DEFAULTS.put("launch.mode", "\"APPROVAL\"");            // APPROVAL(사람 승인) | AUTO(자동 투척)
        DEFAULTS.put("launch.range_m", "1.0");                  // 투척 사거리
        DEFAULTS.put("launch.range_tolerance_m", "0.2");
        DEFAULTS.put("launch.aim_tolerance_deg", "8");          // 대상이 정면에서 이 각도 안에 있어야 자동 투척
        DEFAULTS.put("launch.count", "1");
        DEFAULTS.put("launch.params", "{}");                    // 기구가 받는 추가 값(세기 등)의 자리
        DEFAULTS.put("launch.search_steps", "3");               // 도착 후 재판독을 다시 해 보는 횟수
        DEFAULTS.put("launch.approval_remind_sec", "30");
        DEFAULTS.put("incident.responder_robot_id", "null");    // 비우면 감지한 로봇이 아닌 한가한 로봇, 없으면 아무 로봇
        DEFAULTS.put("incident.merge_radius_m", "1.0");         // 이 거리 안의 감지는 열린 사건 하나로 묶는다
        DEFAULTS.put("incident.reopen_grace_sec", "60");     // 사건을 닫은 뒤 이 시간이 지나도 같은 감지가 계속 오면 새 사건으로 다시 연다
        DEFAULTS.put("incident.monitor_interval_sec", "10"); // 투척 뒤 열원이 남았을 때 현장에서 다시 찍어 보는 간격
        DEFAULTS.put("incident.monitor_clear_count", "2");   // 연속으로 이만큼 정상이면 열원이 사라진 것으로 보고 닫는다
        DEFAULTS.put("detect.thermal", """
                {"params": {"palette": "iron", "hotThreshold": 0.6},
                 "grading": {"type": "ranges", "ranges": [{"max": 0.01, "grade": "NORMAL"},
                             {"min": 0.01, "max": 0.08, "grade": "WARNING"}], "default": "EMERGENCY"}}""");
        DEFAULTS.put("camera.hfov_deg", "62.2");                // 로봇 카메라 수평 화각(조준 각 계산)
    }

    private final JdbcClient jdbc;
    private final ObjectMapper om = new ObjectMapper();

    public SettingsService(JdbcClient jdbc) {
        this.jdbc = jdbc;
    }

    public Map<String, JsonNode> all() {
        Map<String, JsonNode> m = new LinkedHashMap<>();
        DEFAULTS.forEach((k, v) -> m.put(k, parse(v)));
        jdbc.sql("SELECT key, value::text AS value FROM app_setting").query().listOfRows()
                .forEach(r -> {
                    if (DEFAULTS.containsKey(String.valueOf(r.get("key")))) {
                        m.put(String.valueOf(r.get("key")), parse(String.valueOf(r.get("value"))));
                    }
                });
        return m;
    }

    public JsonNode get(String key) {
        String v = jdbc.sql("SELECT value::text FROM app_setting WHERE key = ?").param(key).query(String.class)
                .optional().orElse(DEFAULTS.get(key));
        return parse(v == null ? "null" : v);
    }

    public String text(String key) {
        return get(key).asText();
    }

    public double number(String key) {
        return get(key).asDouble();
    }

    public int integer(String key) {
        return get(key).asInt();
    }

    public void put(String key, JsonNode value, String by) {
        if (!DEFAULTS.containsKey(key)) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, "없는 설정: " + key);
        }
        if (value == null || value.isMissingNode()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "value 가 필요합니다");
        }
        if ("launch.mode".equals(key) && !Set.of("APPROVAL", "AUTO").contains(value.asText())) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "launch.mode 는 APPROVAL 또는 AUTO");
        }
        JsonNode def = parse(DEFAULTS.get(key));
        if (def.isNumber() && !value.isNumber()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, key + " 는 숫자여야 합니다");
        }
        if (def.isObject() && !value.isObject()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, key + " 는 객체(JSON)여야 합니다");
        }
        jdbc.sql("""
                        INSERT INTO app_setting (key, value, updated_by) VALUES (?, CAST(? AS jsonb), ?)
                        ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_by = EXCLUDED.updated_by,
                                                        updated_at = now()""")
                .params(key, value.toString(), by).update();
    }

    private JsonNode parse(String s) {
        try {
            return om.readTree(s);
        } catch (Exception e) {
            return om.nullNode();
        }
    }
}
