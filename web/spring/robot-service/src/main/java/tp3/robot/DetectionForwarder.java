package tp3.robot;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.io.ByteArrayResource;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.stereotype.Component;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.web.client.RestClient;

import java.time.Instant;
import java.util.Base64;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * 로봇이 스스로 감지해 보낸 것(/patrol/detection)을 inspection-service 로 넘긴다(design_02_INTERFACES.md 2.3 · 4.2).
 * 로봇은 같은 것을 보는 동안 같은 detId 로 계속 보낸다. 매번 넘기지는 않되, 등급이 바뀌었거나 마지막으로 넘긴 지
 * RESEND_MS 가 지났으면 다시 넘긴다 — 사람이 사건을 닫았는데 감지가 계속되면 inspection-service 가 사건을 다시 열어야 하기 때문이다.
 * 넘기지 못하면 다음 보고 때 다시 시도한다(로봇이 계속 보내 준다).
 */
@Component
public class DetectionForwarder {

    private static final Logger log = LoggerFactory.getLogger(DetectionForwarder.class);

    private final RestClient http;
    private final MissionService missions;
    private final ObjectMapper om = new ObjectMapper();
    private static final long RESEND_MS = 15_000;
    private final Map<String, String> sent = new ConcurrentHashMap<>();   // detId → 넘긴 등급
    private final Map<String, Long> sentAt = new ConcurrentHashMap<>();   // detId → 마지막으로 넘긴 시각
    private final ExecutorService pool = Executors.newSingleThreadExecutor(r -> {
        Thread t = new Thread(r, "detection");
        t.setDaemon(true);
        return t;
    });

    public DetectionForwarder(RobotRegistry registry, MissionService missions,
                              @Value("${app.inspection-url}") String inspectionUrl) {
        SimpleClientHttpRequestFactory f = new SimpleClientHttpRequestFactory();
        f.setConnectTimeout(3000);
        f.setReadTimeout(10000);
        this.http = RestClient.builder().baseUrl(inspectionUrl).requestFactory(f).build();
        this.missions = missions;
        registry.setDetectionListener((robotId, data) -> pool.submit(() -> forward(robotId, data)));
    }

    private void forward(long robotId, String data) {
        try {
            JsonNode d = om.readTree(data);
            String detId = d.path("detId").asText("");
            String grade = d.path("grade").asText("");
            if (detId.isBlank()) {
                return;
            }
            Long last = sentAt.get(detId);
            if (grade.equals(sent.get(detId)) && last != null && System.currentTimeMillis() - last < RESEND_MS) {
                return;
            }
            boolean first = last == null;
            ObjectNode meta = om.createObjectNode();
            meta.put("robotId", robotId).put("detId", detId).put("kind", d.path("kind").asText("THERMAL"))
                    .put("grade", grade).put("x", d.path("x").asDouble()).put("y", d.path("y").asDouble())
                    .put("capturedAt", d.path("stamp").asText(Instant.now().toString()));
            if (d.hasNonNull("value")) {
                meta.put("value", d.path("value").asDouble());
            }
            if (d.hasNonNull("confidence")) {
                meta.put("confidence", d.path("confidence").asDouble());
            }
            if (d.hasNonNull("poseQuality")) {
                meta.put("poseQuality", d.path("poseQuality").asDouble());
            }
            Long mission = missions.activeMissionId(robotId);
            if (mission != null) {
                meta.put("missionId", mission);
            }
            var form = new LinkedMultiValueMap<String, Object>();
            HttpHeaders jh = new HttpHeaders();
            jh.setContentType(MediaType.APPLICATION_JSON);
            form.add("meta", new HttpEntity<>(meta.toString(), jh));
            String b64 = d.path("image").asText("");
            if (!b64.isBlank()) {
                HttpHeaders ih = new HttpHeaders();
                ih.setContentType(MediaType.IMAGE_JPEG);
                form.add("image", new HttpEntity<>(new ByteArrayResource(Base64.getDecoder().decode(b64)) {
                    @Override
                    public String getFilename() {
                        return "detection.jpg";
                    }
                }, ih));
            }
            http.post().uri("/internal/detections").contentType(MediaType.MULTIPART_FORM_DATA).body(form).retrieve()
                    .toBodilessEntity();
            sent.put(detId, grade);
            sentAt.put(detId, System.currentTimeMillis());
            if (sent.size() > 500) {
                sent.clear();
                sentAt.clear();
            }
            if (first) log.info("감지 보고 전달: {} {} ({}, {})", detId, grade, meta.path("x").asDouble(), meta.path("y").asDouble());
        } catch (Exception e) {
            log.info("감지 보고 전달 실패(다음 보고 때 다시 시도): {}", e.toString());
        }
    }
}
