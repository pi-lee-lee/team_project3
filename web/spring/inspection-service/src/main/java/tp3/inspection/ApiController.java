package tp3.inspection;

import com.fasterxml.jackson.databind.JsonNode;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;
import tp3.common.CurrentUser;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

/** 사용자·관리자 화면용 API. 권한(경로별 역할)은 게이트웨이가 확인한다. */
@RestController
public class ApiController {

    private final Store store;
    private final TaskService tasks;
    private final AlertService alerts;

    public ApiController(Store store, TaskService tasks, AlertService alerts) {
        this.store = store;
        this.tasks = tasks;
        this.alerts = alerts;
    }

    // ------------------------------------------------------------- 지점
    @GetMapping("/api/points")
    public List<Map<String, Object>> points() {
        return store.points(false);
    }

    /** U5 지점 이력: 같은 지점의 관측을 최근 순으로. */
    @GetMapping("/api/points/{id}/history")
    public Map<String, Object> history(@PathVariable long id) {
        var p = store.point(id).orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND));
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("point", p);
        m.put("observations", store.observationsOfPoint(id, 50));
        return m;
    }

    @GetMapping("/api/admin/points")
    public List<Map<String, Object>> adminPoints() {
        return store.points(true);
    }

    @PostMapping("/api/admin/points")
    public Map<String, Object> createPoint(@RequestBody JsonNode b) {
        String code = b.path("code").asText().trim();
        String name = b.path("name").asText().trim();
        if (code.isEmpty() || name.isEmpty()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "코드와 이름이 필요합니다");
        }
        try {
            long id = store.insertPoint(code, name, b.path("description").asText(null), b.path("x").asDouble(),
                    b.path("y").asDouble(), b.path("yawDeg").asDouble());
            if (b.has("exitZone")) {
                store.updateExitZone(id, exitZone(b.path("exitZone")));
            }
            return store.point(id).orElseThrow();
        } catch (DuplicateKeyException e) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, "이미 있는 코드입니다");
        }
    }

    @PutMapping("/api/admin/points/{id}")
    public Map<String, Object> updatePoint(@PathVariable long id, @RequestBody JsonNode b) {
        var cur = store.point(id).orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND));
        store.updatePoint(id, b.path("name").asText((String) cur.get("name")),
                b.has("description") ? b.path("description").asText(null) : (String) cur.get("description"),
                b.path("x").asDouble(((Number) cur.get("x")).doubleValue()),
                b.path("y").asDouble(((Number) cur.get("y")).doubleValue()),
                b.path("yawDeg").asDouble(((Number) cur.get("yaw_deg")).doubleValue()),
                b.path("active").asBoolean((Boolean) cur.get("active")));
        if (b.has("exitZone")) {
            store.updateExitZone(id, exitZone(b.path("exitZone")));
        }
        return store.point(id).orElseThrow();
    }

    /** 비상구 앞 구역: [x1, y1, x2, y2](지도 좌표, m) → 정렬한 사각형. null · 빈 배열이면 지운다. 한 변이 0.3m 보다 작으면 거부. */
    private static double[] exitZone(JsonNode z) {
        if (z == null || z.isNull() || (z.isArray() && z.isEmpty())) {
            return null;
        }
        if (!z.isArray() || z.size() != 4 || !z.get(0).isNumber() || !z.get(1).isNumber() || !z.get(2).isNumber()
                || !z.get(3).isNumber()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "비상구 앞 구역은 [x1, y1, x2, y2] 숫자 네 개입니다");
        }
        double x1 = Math.min(z.get(0).asDouble(), z.get(2).asDouble()), x2 = Math.max(z.get(0).asDouble(), z.get(2).asDouble());
        double y1 = Math.min(z.get(1).asDouble(), z.get(3).asDouble()), y2 = Math.max(z.get(1).asDouble(), z.get(3).asDouble());
        if (x2 - x1 < 0.3 || y2 - y1 < 0.3) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "비상구 앞 구역이 너무 작습니다(한 변 0.3m 이상)");
        }
        return new double[]{x1, y1, x2, y2};
    }

    // ------------------------------------------------------------- 작업
    @GetMapping("/api/inspections")
    public List<Map<String, Object>> list(@RequestParam(required = false) String group,
                                          @RequestParam(defaultValue = "false") boolean mine,
                                          @RequestParam(defaultValue = "100") int limit, HttpServletRequest req) {
        Long uid = mine ? CurrentUser.from(req).id() : null;
        return store.tasks(group, uid, Math.min(limit, 500));
    }

    /** body: {"robotId":1, "pointIds":[1,2], "note":"..."} */
    @PostMapping("/api/inspections")
    public ResponseEntity<Map<String, Object>> create(@RequestBody JsonNode b, HttpServletRequest req) {
        List<Long> ids = new ArrayList<>();
        b.path("pointIds").forEach(n -> ids.add(n.asLong()));
        var d = tasks.create(CurrentUser.from(req), b.path("robotId").asLong(), ids, b.path("note").asText(null), null);
        return ResponseEntity.status(HttpStatus.CREATED).body(d);
    }

    @GetMapping("/api/inspections/{id}")
    public Map<String, Object> detail(@PathVariable long id) {
        return tasks.detail(id);
    }

    @PostMapping("/api/inspections/{id}/cancel")
    public Map<String, Object> cancel(@PathVariable long id, HttpServletRequest req) {
        return tasks.cancel(id, CurrentUser.from(req));
    }

    // ------------------------------------------------------------- 관측
    @GetMapping("/api/observations/{id}/image")
    public ResponseEntity<byte[]> image(@PathVariable long id) throws Exception {
        String p = store.imagePath(id).orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND));
        return ResponseEntity.ok().contentType(MediaType.IMAGE_JPEG).header("Cache-Control", "private, max-age=86400")
                .body(Files.readAllBytes(Path.of(p)));
    }

    /** 사람 판정. 덮어쓰지 않고 쌓는다. 확인 불가는 사유가 필요하다. */
    @PostMapping("/api/observations/{id}/reviews")
    public Map<String, Object> review(@PathVariable long id, @RequestBody JsonNode b, HttpServletRequest req) {
        String result = b.path("result").asText();
        String comment = b.path("comment").asText("").trim();
        if (!Set.of("NORMAL", "ABNORMAL", "UNABLE").contains(result)) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "판정은 NORMAL / ABNORMAL / UNABLE");
        }
        if ("UNABLE".equals(result) && comment.isEmpty()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "확인 불가는 사유를 적어야 합니다");
        }
        var obs = store.observation(id).orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND));
        var u = CurrentUser.from(req);
        store.insertReview(id, result, comment.isEmpty() ? null : comment, u.id(), u.login());
        alerts.onReview(id, result, u.login());
        tasks.userEvent(((Number) obs.get("task_id")).longValue(), "REVIEWED",
                Map.of("observationId", id, "pointCode", obs.get("point_code"), "result", result), u.login());
        return store.observation(id).orElseThrow();
    }

    /** 재점검: 같은 로봇·같은 지점으로 새 작업을 만들고 원래 관측과 연결한다. */
    @PostMapping("/api/observations/{id}/recheck")
    public ResponseEntity<Map<String, Object>> recheck(@PathVariable long id, @RequestBody(required = false) JsonNode b,
                                                       HttpServletRequest req) {
        var obs = store.observation(id).orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND));
        var task = store.task(((Number) obs.get("task_id")).longValue()).orElseThrow();
        String note = b == null ? null : b.path("note").asText(null);
        var d = tasks.create(CurrentUser.from(req), ((Number) task.get("robot_id")).longValue(),
                List.of(((Number) obs.get("point_id")).longValue()),
                note == null ? "재점검 (관측 #" + id + ")" : note, id);
        return ResponseEntity.status(HttpStatus.CREATED).body(d);
    }
}
