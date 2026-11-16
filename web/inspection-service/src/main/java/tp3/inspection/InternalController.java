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
    private final Path photoDir;
    private final ObjectMapper om = new ObjectMapper();

    public InternalController(Store store, TaskService tasks, @Value("${app.photo-dir}") String photoDir) throws Exception {
        this.store = store;
        this.tasks = tasks;
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
        }
        return Map.of("ok", true, "duplicate", obsId.isEmpty());
    }

    @GetMapping("/observations/{id}/image")
    public ResponseEntity<byte[]> image(@PathVariable long id) throws Exception {
        String p = store.imagePath(id).orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND));
        if (p == null) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND);
        }
        return ResponseEntity.ok().contentType(MediaType.IMAGE_JPEG).body(Files.readAllBytes(Path.of(p)));
    }

    /** body: {"brightness":132.1,"sharpness":210.5,"verdict":"OK","reasons":"","criteria":{...}} */
    @PostMapping("/observations/{id}/analysis")
    public Map<String, Object> analysis(@PathVariable long id, @RequestBody JsonNode b) {
        store.insertAnalysis(id, num(b, "brightness"), num(b, "sharpness"), b.path("verdict").asText("OK"),
                b.path("reasons").asText(""), b.path("criteria").toString());
        return Map.of("ok", true);
    }

    private static Double num(JsonNode n, String f) {
        return n.hasNonNull(f) ? n.path(f).asDouble() : null;
    }
}
