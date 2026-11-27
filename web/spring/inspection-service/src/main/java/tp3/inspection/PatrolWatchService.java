package tp3.inspection;

import com.fasterxml.jackson.databind.JsonNode;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestClient;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

/**
 * 순찰 감시: 점검(순찰) 작업을 하는 로봇의 카메라 사진을 1.5초마다 받아 열화상 판독(설정 detect.thermal)한다.
 * 젯봇(순찰 로봇)이 붙기 전까지 터틀봇이 지나가며 보는 열화상으로 화재 · 과열을 찾는 자리다. 판단은 서버가 한다.
 *
 * - 열화상 판이 사진 가로의 patrol.watch_min_width 보다 작게 보이면 판단하지 않는다(멀리서 본 것).
 * - 같은 등급이 patrol.watch_confirm 번 연속 나와야 감지로 본다(한 장만 잘못 보인 것은 넘긴다). 판단하지 않은 사진은 연속을 끊지 않는다.
 * - 사진 속 판의 방향(가운데에서 벗어난 각도)과 로봇 위치로, 지도에서 그 방향으로 처음 만나는 벽을 열원 자리로 본다(robot-service raycast).
 *   로봇이 돌고 있을 때(사진과 위치의 시각이 어긋난다)는 쓰지 않고, 연속 사진들의 자리가 한곳에 모일 때 그 평균을 쓴다.
 * - 비상(화재) → 화재 사건(점검을 멈추고 출동 · 투척). 경고(과열) → 열원 확인 사건(그 앞에 가서 몇 초 확인).
 *   감지 보고와 같은 길(IncidentService.detect)이라 중복 · 같은 자리 묶기 · 열린 열원 경고 건너뛰기가 같다.
 * - 정상이 연속으로 보이면 그 자리의 열린 열원 경고를 푼다(다음 순찰에서 정상 확인).
 * 점검 지점에 서서 찍는 동안에도 같은 간격으로 본다(그 사진도 판독된다).
 */
@Service
public class PatrolWatchService {

    private static final Logger log = LoggerFactory.getLogger(PatrolWatchService.class);

    private final JdbcClient jdbc;
    private final RuleService rules;
    private final IncidentService incidents;
    private final SettingsService settings;
    private final RestClient robot;

    /** 로봇별 최근 판독: 같은 등급이 이어진 사진들의 열원 자리, 이번 연속에서 이미 넣었는지, 직전 방향 */
    private static final class Track {
        String grade;
        final List<double[]> hits = new java.util.ArrayList<>();
        boolean fired;
        Double lastYaw;
    }

    private final Map<Long, Track> tracks = new ConcurrentHashMap<>();
    private static final double MAX_TURN_RAD = 0.25;   // 직전 사진(1.5초 전)보다 이만큼 넘게 돌았으면 돌고 있는 중 — 방향이 어긋나 쓰지 않는다
    private static final double EDGE = 0.02;           // 판이 사진 끝에 걸림(잘림) — 기록에만 남긴다
    private static final double AGREE_M = 0.5;         // 연속 사진들의 열원 자리가 이 안에 모여야 같은 열원으로 본다

    public PatrolWatchService(JdbcClient jdbc, RuleService rules, IncidentService incidents, SettingsService settings,
                              RestClient robotClient) {
        this.jdbc = jdbc;
        this.rules = rules;
        this.incidents = incidents;
        this.settings = settings;
        this.robot = robotClient;
    }

    @Scheduled(fixedDelay = 1500, initialDelay = 15000)
    public void tick() {
        if (!settings.get("patrol.watch").asBoolean(true)) {
            return;
        }
        List<Map<String, Object>> running = jdbc.sql("""
                SELECT task_id, robot_id FROM inspection_task WHERE status = 'RUNNING' AND kind = 'INSPECTION'
                ORDER BY task_id""").query().listOfRows();
        if (running.isEmpty()) {
            tracks.clear();
            return;
        }
        for (var t : running) {
            long robotId = ((Number) t.get("robot_id")).longValue();
            try {
                watch(robotId, ((Number) t.get("task_id")).longValue());
            } catch (Exception e) {
                log.info("순찰 감시({}) 실패: {}", robotId, e.toString());
            }
        }
    }

    private void watch(long robotId, long taskId) {
        ResponseEntity<byte[]> snap = robot.get().uri("/internal/robots/{id}/snapshot", robotId).retrieve().toEntity(byte[].class);
        byte[] img = snap.getBody();
        String pose = snap.getHeaders().getFirst("X-Pose");
        if (img == null || img.length == 0 || pose == null) {
            return;
        }
        String[] p = pose.split(",");
        double rx = Double.parseDouble(p[0]);
        double ry = Double.parseDouble(p[1]);
        double ryaw = Double.parseDouble(p[2]);

        Track tr = tracks.computeIfAbsent(robotId, k -> new Track());
        boolean turning = tr.lastYaw != null
                && Math.abs(Math.atan2(Math.sin(ryaw - tr.lastYaw), Math.cos(ryaw - tr.lastYaw))) > MAX_TURN_RAD;
        tr.lastYaw = ryaw;

        JsonNode cfg = settings.get("detect.thermal");
        Map<String, Object> rule = new LinkedHashMap<>();
        rule.put("ruleId", 0);
        rule.put("name", "순찰 감시");
        rule.put("kind", "THERMAL");
        rule.put("params", cfg.path("params"));
        rule.put("regions", Map.of());
        rule.put("grading", cfg.path("grading"));
        JsonNode res = rules.check(img, List.of(rule), "INSPECTOR").path("results").path(0);
        String grade = res.path("grade").asText("UNKNOWN");
        JsonNode bbox = res.path("located").path("bbox");
        if ("UNKNOWN".equals(grade) || !bbox.isArray() || bbox.size() != 4) {
            return;                                // 판이 안 보인다 — 이 사진은 판단하지 않는다(연속은 그대로 둔다)
        }
        double x0 = bbox.get(0).asDouble();
        double x1 = bbox.get(2).asDouble();
        // 판이 사진 끝에 잘린 사진도 쓴다: 순찰 길에서 옆 벽의 판은 대개 끝에 걸려 보인다. 가운데가 치우쳐 방향이 조금 틀려도
        // 아래의 자리 모임 검사(연속 사진의 자리가 AGREE_M 안)가 거른다
        String skip = turning ? "회전 중" : x1 - x0 < settings.number("patrol.watch_min_width") ? "판이 작음" : null;
        boolean cut = x0 < EDGE || x1 > 1 - EDGE;
        log.debug("순찰 감시: 작업 #{} {} 판 가로 {} 로봇 ({}, {}){}", taskId, grade, Math.round((x1 - x0) * 100) / 100.0,
                Math.round(rx * 100) / 100.0, Math.round(ry * 100) / 100.0, (cut ? " · 끝에 걸림" : "") + (skip == null ? "" : " — 건너뜀(" + skip + ")"));
        if (skip != null) {
            return;                                // 움직이며 찍으면 이런 사진이 끼기 쉽다. 판단만 하지 않고 연속은 그대로 둔다
        }
        // 판의 방향 → 지도 위 벽 자리
        double bearing = Math.toRadians((0.5 - (x0 + x1) / 2) * settings.number("camera.hfov_deg"));   // 왼쪽이 +
        JsonNode hit = robot.post().uri("/internal/robots/{id}/raycast", robotId).contentType(MediaType.APPLICATION_JSON)
                .body(Map.of("x", rx, "y", ry, "angleRad", ryaw + bearing, "maxM", 6.0)).retrieve().body(JsonNode.class);
        if (hit == null || !hit.path("hit").isObject()) {
            return;
        }
        double hx = hit.path("hit").path("x").asDouble();
        double hy = hit.path("hit").path("y").asDouble();
        double[] prev = tr.hits.isEmpty() ? null : tr.hits.get(tr.hits.size() - 1);
        // 등급이 바뀌거나 다른 자리의 판으로 넘어가면 새 연속(같은 정상이어도 다른 열원 자리는 따로 센다)
        if (!grade.equals(tr.grade) || (prev != null && Math.hypot(hx - prev[0], hy - prev[1]) > 2 * AGREE_M)) {
            tr.grade = grade;
            tr.hits.clear();
            tr.fired = false;
        }
        tr.hits.add(new double[]{hx, hy});
        int need = Math.max(1, settings.integer("patrol.watch_confirm"));
        if (tr.fired || tr.hits.size() < need) {
            return;                                // 이번 연속에서 이미 넣었거나 아직 모자란다
        }
        // 최근 need 장의 열원 자리가 한곳에 모였는지(방향이 어긋난 사진이 섞이면 넣지 않고 다음 사진을 기다린다)
        List<double[]> last = tr.hits.subList(tr.hits.size() - need, tr.hits.size());
        double mx = last.stream().mapToDouble(h -> h[0]).average().orElse(0);
        double my = last.stream().mapToDouble(h -> h[1]).average().orElse(0);
        if (last.stream().anyMatch(h -> Math.hypot(h[0] - mx, h[1] - my) > AGREE_M)) {
            log.info("순찰 감시: 작업 #{} {} 자리가 모이지 않음 {}", taskId, grade,
                    last.stream().map(h -> String.format("(%.2f, %.2f)", h[0], h[1])).toList());
            return;
        }
        tr.fired = true;
        double x = Math.round(mx * 100) / 100.0;
        double y = Math.round(my * 100) / 100.0;
        if ("NORMAL".equals(grade)) {
            int k = incidents.resolveHeatNear(x, y, "순찰 감시: 다음 순찰에서 정상 확인 (작업 #" + taskId + ")");
            if (k > 0) {
                log.info("순찰 감시: ({}, {}) 정상 → 열원 경고 {}건 풂", x, y, k);
            }
            return;
        }
        Double value = res.path("value").isNumber() ? res.path("value").asDouble() : null;
        Double conf = res.path("confidence").isNumber() ? res.path("confidence").asDouble() : null;
        var out = incidents.watchDetected(robotId, grade, x, y, value, conf, img);
        log.info("순찰 감시: 작업 #{} 에서 {} ({}, {}) → {}", taskId, grade, x, y, out);
    }
}
