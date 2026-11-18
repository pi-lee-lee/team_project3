package tp3.inspection;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RequestPart;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.web.server.ResponseStatusException;
import tp3.common.CurrentUser;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** 화면이 부르는 API: 점검 규칙(A2) · 경고(A1) · 설정(A4). 역할 제한은 게이트웨이 규칙이 한다. */
@RestController
public class RuleController {

    private final RuleService rules;
    private final AlertService alerts;
    private final SettingsService settings;
    private final ObjectMapper om = new ObjectMapper();

    public RuleController(RuleService rules, AlertService alerts, SettingsService settings) {
        this.rules = rules;
        this.alerts = alerts;
        this.settings = settings;
    }

    // ------------------------------------------------------------- A2 규칙
    /** 지점의 규칙과 규칙별 최근 결과. */
    @GetMapping("/api/points/{id}/rules")
    public List<Map<String, Object>> ofPoint(@PathVariable long id) {
        List<Map<String, Object>> out = new ArrayList<>();
        for (var r : rules.rulesOfPoint(id, false)) {
            Map<String, Object> m = new LinkedHashMap<>(r);
            m.put("latest", rules.latestResult(((Number) r.get("ruleId")).longValue()));
            out.add(m);
        }
        return out;
    }

    @GetMapping("/api/admin/checkers")
    public JsonNode checkers() {
        JsonNode c = rules.checkers();
        if (c == null) {
            throw new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE, "분석 서비스에 연결할 수 없습니다");
        }
        return c;
    }

    @PostMapping("/api/admin/points/{id}/rules")
    public ResponseEntity<Map<String, Object>> create(@PathVariable long id, @RequestBody JsonNode b) {
        return ResponseEntity.status(HttpStatus.CREATED).body(rules.create(id, b));
    }

    @PutMapping("/api/admin/rules/{id}")
    public Map<String, Object> update(@PathVariable long id, @RequestBody JsonNode b) {
        return rules.update(id, b);
    }

    @DeleteMapping("/api/admin/rules/{id}")
    public ResponseEntity<Void> delete(@PathVariable long id) {
        rules.delete(id);
        return ResponseEntity.noContent().build();
    }

    /** 저장 전에 사진 한 장으로 규칙을 시험한다. rule 은 규칙 JSON 글자(ruleId 는 없어도 된다). */
    @PostMapping(value = "/api/admin/rules/test", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public JsonNode test(@RequestPart("image") MultipartFile image, @RequestPart("rule") String ruleText,
                         @RequestParam(defaultValue = "INSPECTOR") String robotKind) throws Exception {
        JsonNode rule = om.readTree(ruleText);
        try {
            return rules.check(image.getBytes(), List.of(rule), robotKind);
        } catch (ResponseStatusException e) {
            throw e;
        } catch (Exception e) {
            throw new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE, "분석 서비스 호출 실패: " + e.getMessage());
        }
    }

    @GetMapping("/api/observations/{id}/results")
    public List<Map<String, Object>> results(@PathVariable long id) {
        return rules.resultsOfObservation(id);
    }

    // ------------------------------------------------------------- A1 경고
    @GetMapping("/api/alerts")
    public List<Map<String, Object>> alerts(@RequestParam(defaultValue = "OPEN,ACKED") String state,
                                            @RequestParam(defaultValue = "100") int limit) {
        return alerts.list(Arrays.asList(state.toUpperCase().split(",")), limit);
    }

    @GetMapping("/api/alerts/{id}")
    public Map<String, Object> alert(@PathVariable long id) {
        var a = alerts.get(id);
        if (a == null) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND);
        }
        return a;
    }

    @PostMapping("/api/alerts/{id}/ack")
    public Map<String, Object> ack(@PathVariable long id, @RequestBody(required = false) JsonNode b,
                                   HttpServletRequest req) {
        alerts.ack(id, CurrentUser.from(req).login(), b == null ? null : b.path("comment").asText(null));
        return alerts.get(id);
    }

    @PostMapping("/api/alerts/{id}/resolve")
    public Map<String, Object> resolve(@PathVariable long id, @RequestBody(required = false) JsonNode b,
                                       HttpServletRequest req) {
        alerts.resolve(id, CurrentUser.from(req).login(), b == null ? null : b.path("comment").asText(null));
        return alerts.get(id);
    }

    // ------------------------------------------------------------- A4 설정
    @GetMapping("/api/settings")
    public Map<String, JsonNode> settings() {
        return settings.all();
    }

    @PutMapping("/api/settings/{key}")
    public Map<String, JsonNode> put(@PathVariable String key, @RequestBody JsonNode b, HttpServletRequest req) {
        settings.put(key, b.get("value"), CurrentUser.from(req).login());
        return settings.all();
    }
}
