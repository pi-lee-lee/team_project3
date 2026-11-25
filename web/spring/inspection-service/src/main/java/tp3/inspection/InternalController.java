package tp3.inspection;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestPart;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.web.server.ResponseStatusException;

import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Instant;
import java.util.Map;
import java.util.UUID;

/** 내부망 전용: robot-service(보고)와 analysis-service(분석 결과)가 호출한다. */
@RestController
@RequestMapping("/internal")
public class InternalController {

    private final Store store;
    private final TaskService tasks;
    private final RuleService rules;
    private final IncidentService incidents;
    private final AlertService alerts;
    /** 목표 브리지(nav2_goal_bridge.py exit_blocked)가 비상구 앞 적재로 가렸을 때 보내는 이유 글귀 */
    private static final String EXIT_REASON = "비상구 앞 통로가 막힘";
    private final Path photoDir;
    private final ObjectMapper om = new ObjectMapper();

    public InternalController(Store store, TaskService tasks, RuleService rules, IncidentService incidents, AlertService alerts,
                              @Value("${app.photo-dir}") String photoDir) throws Exception {
        this.store = store;
        this.tasks = tasks;
        this.rules = rules;
        this.incidents = incidents;
        this.alerts = alerts;
        this.photoDir = Path.of(photoDir);
        Files.createDirectories(this.photoDir);
    }

    @PostMapping("/tasks/{id}/events")
    public Map<String, Object> event(@PathVariable long id, @RequestHeader("X-Report-Id") UUID reportId,
                                     @RequestBody JsonNode body) {
        tasks.robotEvent(id, reportId, body);
        return Map.of("ok", true);
    }

    /** 같은 X-Report-Id 로 다시 오면 저장하지 않고 성공으로 답한다(재전송 허용). */
    @PostMapping(value = "/tasks/{id}/observations", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public Map<String, Object> observation(@PathVariable long id, @RequestHeader("X-Report-Id") UUID reportId,
                                           @RequestPart("meta") String metaText,
                                           @RequestPart(value = "image", required = false) MultipartFile image)
            throws Exception {
        if (store.taskStatus(id) == null) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, "없는 작업");
        }
        JsonNode meta = om.readTree(metaText);
        String path = null;
        if (image != null && !image.isEmpty()) {
            Path file = photoDir.resolve(reportId + ".jpg");
            image.transferTo(file);
            path = file.toString();
        }
        String status = meta.path("status").asText();
        Instant capturedAt = Instant.parse(meta.path("capturedAt").asText());
        var obsId = store.insertObservation(id, meta.path("pointId").asLong(), meta.path("seq").asInt(), status,
                meta.path("reason").asText(null), meta.path("reasonCode").asText(null), path, capturedAt,
                num(meta, "poseX"), num(meta, "poseY"), num(meta, "poseYaw"), reportId);
        if (obsId.isPresent()) {
            var point = store.point(meta.path("pointId").asLong()).orElse(Map.of());
            tasks.systemEvent(id, "CAPTURED".equals(status) ? "OBSERVATION_SAVED" : "OBSERVATION_UNABLE",
                    Map.of("observationId", obsId.get(), "pointCode", String.valueOf(point.get("code")),
                            "reason", meta.path("reason").asText(""),
                            "reasonCode", meta.path("reasonCode").asText("")), capturedAt);
            exitCheck(id, obsId.get(), point, status, meta);
        }
        return Map.of("ok", true, "duplicate", obsId.isEmpty());
    }

    /**
     * 비상구 점검 지점(비상구 앞 구역이 있는 지점): 진입 불가(통로 막힘)는 소화기 없음과 같은 급의 점검 결과(경고)다.
     * 같은 지점의 열린 경고는 하나로 두고(dedup "exit:지점"), 다음 점검에서 도착해 촬영하면(통로가 비어 있음) 스스로 푼다.
     * 사람이 관측을 '정상'으로 판정해도 풀린다(AlertService.onReview). 다른 지점의 진입 불가는 주행 문제라 경고로 만들지 않는다.
     */
    private void exitCheck(long taskId, long obsId, Map<String, Object> point, String status, JsonNode meta) {
        if (point.get("exit_zone") == null || point.get("point_id") == null) {
            return;
        }
        long pointId = ((Number) point.get("point_id")).longValue();
        String key = "exit:" + pointId;
        Double x = num(meta, "poseX"), y = num(meta, "poseY");
        // 비상구 통로 막힘인지는 목표 브리지가 가린다: 막은 물건(저장 지도에 없는 장애물)이 비상구 앞 구역 안에 있을 때만
        // 이유를 EXIT_REASON 으로 보낸다. 가는 길(통로로 들어가는 문 등)이 막힌 것은 주행 문제라 경고로 만들지 않는다.
        // 로봇 위치로 다시 가리지 않는다 — 로봇은 통로 밖에서 통로 안의 물건을 먼저 볼 수 있다.
        if ("UNABLE".equals(status) && "BLOCKED_NO_PATH".equals(meta.path("reasonCode").asText())
                && meta.path("reason").asText("").contains(EXIT_REASON)) {
            Map<String, Object> ev = new java.util.LinkedHashMap<>();
            ev.put("observationId", obsId);
            ev.put("reason", meta.path("reason").asText(""));
            if (x != null && y != null) {
                ev.put("robotX", x);
                ev.put("robotY", y);
            }
            alerts.open(new AlertService.Draft("EXIT_BLOCKED", "WARNING", key,
                    point.get("code") + " " + point.get("name") + " · 비상구 앞 통로 막힘",
                    "비상구 앞 통로에 물건이 있어 진입하지 못함" + (x != null && y != null
                            ? String.format(" (로봇 위치 %.2f, %.2f)", x, y) : "") + " · 근거 사진 확인",
                    pointId, x, y, "observation", obsId, taskId, ev));
        } else if ("CAPTURED".equals(status)) {
            alerts.resolveByKey(key, "SYSTEM", "다음 점검에서 비상구 앞 통로 확인 (관측 #" + obsId + ")");
        }
    }

    /**
     * 로봇이 스스로 감지해 보낸 것(robot-service 가 넘겨 준다). meta: {"robotId","detId","kind","grade","x","y",...}
     * 비상이면 사건을 만들고 경고를 연다. 같은 detId · 가까운 열린 사건은 하나로 합친다.
     */
    @PostMapping(value = "/detections", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public Map<String, Object> detection(@RequestPart("meta") String metaText,
                                         @RequestPart(value = "image", required = false) MultipartFile image)
            throws Exception {
        return incidents.detect(om.readTree(metaText), image == null || image.isEmpty() ? null : image.getBytes());
    }

    @GetMapping("/observations/{id}/image")
    public ResponseEntity<byte[]> image(@PathVariable long id) throws Exception {
        String p = store.imagePath(id).orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND));
        if (p == null) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND);
        }
        return ResponseEntity.ok().contentType(MediaType.IMAGE_JPEG).body(Files.readAllBytes(Path.of(p)));
    }

    /** 그 관측의 지점에 걸린 규칙(analysis-service 가 판독 전에 받아 간다). */
    @GetMapping("/observations/{id}/rules")
    public Map<String, Object> rules(@PathVariable long id) {
        return rules.rulesForObservation(id);
    }

    /**
     * body: {"brightness":132.1,"sharpness":210.5,"verdict":"OK","reasons":"","criteria":{...}, "results":[규칙별 결과…]}
     * results 가 있으면 규칙별 등급을 저장하고 경고를 열거나 푼다.
     */
    @PostMapping("/observations/{id}/analysis")
    public Map<String, Object> analysis(@PathVariable long id, @RequestBody JsonNode b) {
        store.insertAnalysis(id, num(b, "brightness"), num(b, "sharpness"), b.path("verdict").asText("OK"),
                b.path("reasons").asText(""), b.path("criteria").toString());
        rules.saveResults(id, b.path("results"));
        return Map.of("ok", true);
    }

    private static Double num(JsonNode n, String f) {
        return n.hasNonNull(f) ? n.path(f).asDouble() : null;
    }
}
