package tp3.inspection;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;
import org.springframework.web.client.HttpStatusCodeException;
import org.springframework.web.client.RestClient;
import org.springframework.web.server.ResponseStatusException;
import tp3.common.CurrentUser;

import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * 사건(화재 대응)의 흐름을 끌고 간다. 상태 흐름은 docs/design/INTERFACES.md 7장 F1.
 *
 *   DETECTED → DISPATCHED → ARRIVED → (재판독) → AWAITING_APPROVAL → LAUNCHING → (투척 후 판독) → RESOLVED
 *                                                                                └ 열원이 남음 → MONITORING(현장 감시) ┘
 *                                               └ 자동 모드 · 비상 확인 ┘                 (또는 DISMISSED / FAILED)
 *
 * 열원(경고, 종류 HEAT)도 같은 흐름을 탄다: DETECTED → DISPATCHED(열원 앞 heat.check_distance_m) → ARRIVED → 몇 번 찍어 확인
 *   → 과열이면 사진과 함께 열원 경고(HEAT_WARNING)를 열고 해결로 닫는다 / 정상이면 기록만 남기고 닫는다 / 화재면 화재(FIRE)로 올려
 *   재판독 · 투척 흐름을 이어 간다. 투척은 화재만 한다.
 * 점검(순찰) 중에 출동하면 그 작업을 멈추고, 사건이 끝나면 남은 지점으로 순찰을 이어 간다(resumePatrols, 설정 patrol.resume).
 * 판단은 모두 여기(서버)서 한다: 누구를 보낼지, 재판독 결과가 무엇인지, 쏠지 말지.
 * 로봇은 이동(출동 미션)과 투척 명령을 실행하고 결과를 사건 기록으로 알린다.
 * 2초마다 열린 사건을 보고 상태에 맞는 다음 일을 한다 — 서비스가 재시작되어도 DB 의 상태에서 이어진다.
 */
@Service
public class IncidentService {

    private static final Logger log = LoggerFactory.getLogger(IncidentService.class);
    /** 사람이 닫을 때까지 열려 있는 상태(FAILED 도 사람이 확인해 닫는다). */
    private static final Set<String> CLOSED = Set.of("RESOLVED", "DISMISSED");
    private static final CurrentUser SYSTEM = new CurrentUser(0, "system", "SYSTEM");
    private static final Duration DISPATCH_TIMEOUT = Duration.ofSeconds(120);

    private final JdbcClient jdbc;
    private final Store store;
    private final TaskService tasks;
    private final AlertService alerts;
    private final RuleService rules;
    private final SettingsService settings;
    private final RestClient robot;
    private final Path photoDir;
    private final ObjectMapper om = new ObjectMapper();

    public IncidentService(JdbcClient jdbc, Store store, TaskService tasks, AlertService alerts, RuleService rules,
                           SettingsService settings, RestClient robotClient,
                           @Value("${app.photo-dir}") String photoDir) {
        this.jdbc = jdbc;
        this.store = store;
        this.tasks = tasks;
        this.alerts = alerts;
        this.rules = rules;
        this.settings = settings;
        this.robot = robotClient;
        this.photoDir = Path.of(photoDir);
    }

    // ------------------------------------------------------------- 감지 보고 받기
    /**
     * 로봇의 감지 보고(S3). 비상이면 사건을 만들고(가까운 열린 사건이 있으면 거기에 붙인다), 경고면 경고만 연다.
     * 돌려주는 값: alertId, incidentId(없으면 null), duplicate.
     */
    public synchronized Map<String, Object> detect(JsonNode meta, byte[] image) {
        String detId = meta.path("detId").asText("");
        String grade = meta.path("grade").asText("");
        double x = meta.path("x").asDouble();
        double y = meta.path("y").asDouble();
        long robotId = meta.path("robotId").asLong();
        Map<String, Object> out = new LinkedHashMap<>();
        Map<String, Object> ev = new LinkedHashMap<>();
        ev.put("detId", detId);
        ev.put("kind", meta.path("kind").asText("THERMAL"));
        ev.put("value", meta.hasNonNull("value") ? meta.path("value").asDouble() : null);
        ev.put("confidence", meta.hasNonNull("confidence") ? meta.path("confidence").asDouble() : null);
        ev.put("robotId", robotId);

        if (!"EMERGENCY".equals(grade)) {
            if (!"WARNING".equals(grade)) {
                out.put("alertId", null);
                out.put("incidentId", null);
                out.put("duplicate", false);
                return out;            // 정상 · 판독 불가는 기록하지 않는다
            }
            return heatDetected(meta, image, detId, x, y, robotId, ev, out);
        }

        // 같은 감지(detId)로 만든 사건이 있는가. 로봇은 같은 것을 보는 동안 같은 ID 로 계속 보고한다.
        Long existing = null;
        Long reopenOf = null;
        var same = detId.isBlank() ? null : jdbc.sql("SELECT incident_id, state, closed_at FROM incident WHERE det_id = ?")
                .param(detId).query().listOfRows().stream().findFirst().orElse(null);
        if (same != null) {
            long sameId = num(same.get("incident_id"));
            if (!CLOSED.contains(String.valueOf(same.get("state")))) {
                out.put("alertId", null);
                out.put("incidentId", sameId);
                out.put("duplicate", true);
                return out;                       // 열려 있는 그 사건이 처리 중이다
            }
            // 사람(또는 시스템)이 닫았는데 감지가 계속된다. 닫은 직후 잠깐은 넘어가고, 그 뒤에도 오면 새 사건으로 다시 연다.
            // 닫는 것은 기록을 닫는 것이지 실제 상황이 끝났다는 확인이 아니기 때문이다.
            long since = same.get("closed_at") == null ? Long.MAX_VALUE
                    : Duration.between(((java.sql.Timestamp) same.get("closed_at")).toInstant(), Instant.now()).toSeconds();
            if (since < settings.integer("incident.reopen_grace_sec")) {
                out.put("alertId", null);
                out.put("incidentId", sameId);
                out.put("duplicate", true);
                return out;
            }
            jdbc.sql("UPDATE incident SET det_id = det_id || ':closed:' || incident_id WHERE incident_id = ?").param(sameId).update();
            reopenOf = sameId;
            ev.put("reopenOf", sameId);
        }
        if (existing == null && reopenOf == null) {
            double r = settings.number("incident.merge_radius_m");
            existing = jdbc.sql("""
                            SELECT incident_id FROM incident
                            WHERE state NOT IN ('RESOLVED', 'DISMISSED') AND sqrt(power(x - ?, 2) + power(y - ?, 2)) <= ?
                            ORDER BY incident_id DESC LIMIT 1""").params(x, y, r).query(Long.class).optional().orElse(null);
            if (existing != null) {
                event(existing, "ROBOT", "DETECTION_REPEATED", ev, null);
            }
        }
        if (existing != null) {
            out.put("alertId", null);
            out.put("incidentId", existing);
            out.put("duplicate", true);
            return out;
        }

        String mode = "AUTO".equals(settings.text("launch.mode")) ? "AUTO" : "APPROVAL";
        long id = jdbc.sql("""
                        INSERT INTO incident (state, grade, x, y, pose_quality, detected_by, det_id, launch_mode)
                        VALUES ('DETECTED', ?, ?, ?, ?, ?, ?, ?) RETURNING incident_id""")
                .params(grade, x, y, meta.hasNonNull("poseQuality") ? meta.path("poseQuality").asDouble() : null, robotId,
                        detId.isBlank() ? null : detId, mode).query(Long.class).single();
        if (image != null && image.length > 0) {
            saveImage(id, "detection", image);
        }
        event(id, "ROBOT", "DETECTED", ev, null);
        if (reopenOf != null) {
            event(id, "SYSTEM", "REOPENED", Map.of("previous", reopenOf,
                    "reason", "사건 #" + reopenOf + " 을 닫은 뒤에도 같은 감지가 계속되어 다시 엶"), null);
            event(reopenOf, "SYSTEM", "REOPENED_AS", Map.of("next", id), null);
        }
        long alertId = fireAlert(id, x, y, mode, reopenOf != null ? "닫은 뒤에도 감지가 계속됨(이전 사건 #" + reopenOf + ") · " : "", ev);
        log.info("사건 #{} 생성: ({}, {}) 모드 {}", id, x, y, mode);
        out.put("alertId", alertId);
        out.put("incidentId", id);
        out.put("duplicate", false);
        return out;
    }

    private long fireAlert(long id, double x, double y, String mode, String prefix, Map<String, ?> ev) {
        return alerts.open(new AlertService.Draft("FIRE_DETECTED", "EMERGENCY", "incident:" + id,
                "화재 감지 · 사건 #" + id, prefix + String.format("위치 (%.1f, %.1f) · 투척 %s", x, y, "AUTO".equals(mode) ? "자동" : "승인 후"),
                null, x, y, "incident", id, null, ev));
    }

    /**
     * 열원(경고) 감지: 그 자리에 열린 열원 경고가 있으면 이미 확인한 열원이라 다시 가지 않는다(경고는 다음 순찰에서 정상이면 풀린다).
     * 근처에 열린 사건이 있으면 그 사건에 붙인다. 아니면 열원 확인 사건(HEAT)을 만들어 로봇을 그 앞으로 보낸다.
     */
    private Map<String, Object> heatDetected(JsonNode meta, byte[] image, String detId, double x, double y, long robotId,
                                             Map<String, Object> ev, Map<String, Object> out) {
        double r = settings.number("incident.merge_radius_m");
        Long open = openHeatAlertNear(x, y);
        if (open != null) {
            out.put("alertId", open);
            out.put("incidentId", null);
            out.put("duplicate", true);
            return out;
        }
        Long near = jdbc.sql("""
                        SELECT incident_id FROM incident
                        WHERE state NOT IN ('RESOLVED', 'DISMISSED') AND sqrt(power(x - ?, 2) + power(y - ?, 2)) <= ?
                        ORDER BY incident_id DESC LIMIT 1""").params(x, y, r).query(Long.class).optional().orElse(null);
        if (near != null) {
            out.put("alertId", null);
            out.put("incidentId", near);
            out.put("duplicate", true);
            return out;
        }
        if (!detId.isBlank()) {      // 같은 감지 ID 의 닫힌 사건이 있으면 그 ID 를 비켜 둔다(det_id 는 하나만)
            jdbc.sql("UPDATE incident SET det_id = det_id || ':closed:' || incident_id WHERE det_id = ? AND state IN ('RESOLVED', 'DISMISSED')")
                    .param(detId).update();
        }
        String mode = "AUTO".equals(settings.text("launch.mode")) ? "AUTO" : "APPROVAL";
        long id = jdbc.sql("""
                        INSERT INTO incident (type, state, grade, x, y, pose_quality, detected_by, det_id, launch_mode)
                        VALUES ('HEAT', 'DETECTED', 'WARNING', ?, ?, ?, ?, ?, ?) RETURNING incident_id""")
                .params(x, y, meta.hasNonNull("poseQuality") ? meta.path("poseQuality").asDouble() : null, robotId,
                        detId.isBlank() ? null : detId, mode).query(Long.class).single();
        if (image != null && image.length > 0) {
            saveImage(id, "detection", image);
        }
        event(id, "ROBOT", "DETECTED", ev, null);
        log.info("열원 확인 사건 #{} 생성: ({}, {})", id, x, y);
        out.put("alertId", null);
        out.put("incidentId", id);
        out.put("duplicate", false);
        return out;
    }

    /** (x, y) 가까이(incident.merge_radius_m)에 열린 열원 경고가 있으면 그 ID. */
    public Long openHeatAlertNear(double x, double y) {
        return jdbc.sql("""
                        SELECT alert_id FROM alert WHERE type = 'HEAT_WARNING' AND state <> 'RESOLVED'
                        AND sqrt(power(x - ?, 2) + power(y - ?, 2)) <= ? ORDER BY alert_id DESC LIMIT 1""")
                .params(x, y, settings.number("incident.merge_radius_m")).query(Long.class).optional().orElse(null);
    }

    /** 순찰 감시가 그 자리를 정상으로 봤다: 가까운 열린 열원 경고를 푼다. 푼 개수. */
    public int resolveHeatNear(double x, double y, String reason) {
        return jdbc.sql("""
                        UPDATE alert SET state = 'RESOLVED', resolved_by = 'SYSTEM', resolved_at = now(), updated_at = now(),
                                         comment = ?
                        WHERE type = 'HEAT_WARNING' AND state <> 'RESOLVED' AND sqrt(power(x - ?, 2) + power(y - ?, 2)) <= ?""")
                .params(reason, x, y, settings.number("incident.merge_radius_m")).update();
    }

    /** 순찰 감시(PatrolWatchService)가 연속으로 본 열원을 감지 보고로 넣는다. 로봇의 감지 보고와 같은 길로 간다. */
    public Map<String, Object> watchDetected(long robotId, String grade, double x, double y, Double value, Double confidence,
                                             byte[] image) {
        var meta = om.createObjectNode();
        // 같은 자리(0.5m 격자) · 같은 등급이면 같은 감지 ID — 계속 보이는 동안 사건이 하나만 생긴다
        meta.put("detId", "watch-" + robotId + "-" + grade.toLowerCase() + "-" + Math.round(x * 2) + ":" + Math.round(y * 2))
                .put("kind", "THERMAL").put("grade", grade).put("x", x).put("y", y).put("robotId", robotId).put("poseQuality", 1.0);
        if (value != null) {
            meta.put("value", value);
        }
        if (confidence != null) {
            meta.put("confidence", confidence);
        }
        return detect(meta, image);
    }

    // ------------------------------------------------------------- 흐름(2초마다)
    @Scheduled(fixedDelay = 2000, initialDelay = 8000)
    public void tick() {
        for (Map<String, Object> inc : jdbc.sql("""
                SELECT * FROM incident WHERE state IN ('DETECTED', 'DISPATCHED', 'ARRIVED', 'AWAITING_APPROVAL',
                                                       'LAUNCHING', 'MONITORING') ORDER BY incident_id""").query().listOfRows()) {
            try {
                step(inc);
            } catch (Exception e) {
                log.warn("사건 #{} 처리 중 오류: {}", inc.get("incident_id"), e.toString());
            }
        }
        try {
            resumePatrols();
        } catch (Exception e) {
            log.warn("순찰 이어가기 오류: {}", e.toString());
        }
    }

    /**
     * 화재 · 열원 확인으로 멈췄던 순찰(점검 작업)을 사건이 끝나면(해결 · 오탐 · 실패) 남은 지점으로 다시 시작한다.
     * 남은 지점 = 그 작업의 지점 가운데 관측(사진 또는 촬영 불가)이 남지 않은 것. 로봇이 출동을 마치고 한가해질 때까지 기다린다.
     * 한 사건에 한 번만(PATROL_RESUMED · PATROL_RESUME_SKIPPED 기록).
     */
    private void resumePatrols() {
        for (var r : jdbc.sql("""
                SELECT i.incident_id, i.responder_id, (e.detail->>'taskId')::bigint AS task_id FROM incident i
                JOIN incident_event e ON e.incident_id = i.incident_id AND e.type = 'PREEMPTED'
                WHERE i.state IN ('RESOLVED', 'DISMISSED', 'FAILED') AND i.updated_at > now() - interval '30 minutes'
                  AND i.responder_id IS NOT NULL
                  AND NOT EXISTS (SELECT 1 FROM incident_event x WHERE x.incident_id = i.incident_id
                                  AND x.type IN ('PATROL_RESUMED', 'PATROL_RESUME_SKIPPED'))
                ORDER BY i.incident_id""").query().listOfRows()) {
            long id = num(r.get("incident_id"));
            long taskId = num(r.get("task_id"));
            if (!settings.get("patrol.resume").asBoolean(true)) {
                event(id, "SYSTEM", "PATROL_RESUME_SKIPPED", Map.of("reason", "설정(patrol.resume)이 꺼져 있음"), null);
                continue;
            }
            long robotId = num(r.get("responder_id"));
            if (!TaskService.TERMINAL.contains(String.valueOf(store.taskStatus(taskId)))) {
                continue;                       // 멈춘 작업이 아직 정리 중
            }
            boolean busy = jdbc.sql("""
                            SELECT count(*) FROM incident WHERE responder_id = ? AND state NOT IN ('RESOLVED', 'DISMISSED', 'FAILED')""")
                    .param(robotId).query(Long.class).single() > 0;
            if (busy) {
                continue;                       // 그 로봇이 다른 사건을 처리 중
            }
            try {
                JsonNode rb = robot.get().uri("/internal/robots/{id}", robotId).retrieve().body(JsonNode.class);
                if (rb == null || !rb.path("connected").asBoolean() || (rb.hasNonNull("mission") && !rb.path("mission").isEmpty())) {
                    continue;                   // 출동을 마무리하는 중(또는 연결 끊김) — 다음 틱에
                }
            } catch (Exception e) {
                continue;
            }
            List<Long> done = jdbc.sql("SELECT DISTINCT point_id FROM observation WHERE task_id = ?").param(taskId)
                    .query(Long.class).list();
            List<Long> left = new ArrayList<>();
            for (var p : store.taskPoints(taskId)) {
                long pid = num(p.get("point_id"));
                if (!done.contains(pid)) {
                    left.add(pid);
                }
            }
            if (left.isEmpty()) {
                event(id, "SYSTEM", "PATROL_RESUME_SKIPPED", Map.of("taskId", taskId, "reason", "남은 점검 지점이 없음"), null);
                continue;
            }
            try {
                var t = tasks.create(SYSTEM, robotId, left, "순찰 이어서 (사건 #" + id + " 뒤, 작업 #" + taskId + " 의 남은 지점)", null);
                long next = num(t.get("task_id"));
                event(id, "SYSTEM", "PATROL_RESUMED", Map.of("taskId", taskId, "nextTaskId", next, "points", left.size()), null);
                tasks.systemEvent(next, "RESUMED", Map.of("reason", "사건 #" + id + " 이 끝나 작업 #" + taskId + " 의 남은 지점을 이어서 점검"));
                log.info("사건 #{} 뒤 순찰 이어감: 작업 #{} → #{} ({}곳)", id, taskId, next, left.size());
            } catch (Exception e) {
                log.info("사건 #{} 뒤 순찰 이어가기 실패(다음 틱에 다시): {}", id, message(e));
            }
        }
    }

    private synchronized void step(Map<String, Object> stale) {
        long id = num(stale.get("incident_id"));
        Map<String, Object> inc = row(id);                 // 그 사이 사람이 닫았을 수 있다
        switch (String.valueOf(inc.get("state"))) {
            case "DETECTED" -> dispatch(id, inc);
            case "DISPATCHED" -> awaitArrival(id, inc);
            case "ARRIVED" -> recheck(id, inc);
            case "AWAITING_APPROVAL" -> remind(id, inc);
            case "LAUNCHING" -> awaitLaunch(id, inc);
            case "MONITORING" -> monitor(id, inc);
            default -> {
            }
        }
    }

    /** DETECTED: 대응 로봇을 골라(점검 중이면 그 작업을 멈추고) 투척 위치로 보낸다. */
    private void dispatch(long id, Map<String, Object> inc) {
        Long robotId = inc.get("responder_id") == null ? chooseResponder(inc) : (Long) num(inc.get("responder_id"));
        if (robotId == null) {
            if (age(inc) > DISPATCH_TIMEOUT.toSeconds()) {
                fail(id, "출동시킬 로봇이 없습니다(연결된 로봇 없음)");
            }
            return;
        }
        if (inc.get("responder_id") == null) {
            jdbc.sql("UPDATE incident SET responder_id = ?, updated_at = now() WHERE incident_id = ?").params(robotId, id).update();
        }
        JsonNode r;
        try {
            r = robot.get().uri("/internal/robots/{id}", robotId).retrieve().body(JsonNode.class);
        } catch (Exception e) {
            return;      // 다음 틱에 다시
        }
        if (r == null || !r.path("connected").asBoolean()) {
            if (age(inc) > DISPATCH_TIMEOUT.toSeconds()) {
                fail(id, "대응 로봇과 연결되어 있지 않습니다");
            }
            return;
        }
        if (r.hasNonNull("mission") && !r.path("mission").isEmpty()) {
            long busyTask = r.path("mission").path("missionId").asLong();
            if (!hasEvent(id, "PREEMPTED")) {
                String what = heat(inc) ? "열원 확인" : "화재 출동";
                event(id, "SYSTEM", "PREEMPTED", Map.of("taskId", busyTask, "reason", what + "을 위해 점검 작업을 멈춤"), null);
                try {
                    tasks.systemEvent(busyTask, "PREEMPTED", Map.of("reason", what + "(사건 #" + id + ")으로 중단"));
                    tasks.cancel(busyTask, SYSTEM);
                } catch (Exception e) {
                    log.info("사건 #{}: 작업 #{} 취소 요청 실패 {}", id, busyTask, e.toString());
                }
            }
            return;      // 멈출 때까지 기다린다
        }
        JsonNode cands;
        try {
            cands = robot.post().uri("/internal/robots/{id}/standoff", robotId).contentType(MediaType.APPLICATION_JSON)
                    .body(Map.of("targetX", inc.get("x"), "targetY", inc.get("y"),
                            "rangeM", heat(inc) ? settings.number("heat.check_distance_m") : settings.number("launch.range_m"),
                            "toleranceM", settings.number("launch.range_tolerance_m"), "max", 6))
                    .retrieve().body(JsonNode.class);
        } catch (Exception e) {
            if (age(inc) > DISPATCH_TIMEOUT.toSeconds()) {
                fail(id, "투척 위치를 계산할 수 없습니다: " + message(e));
            }
            return;
        }
        JsonNode list = cands == null ? null : cands.path("candidates");
        if (list == null || !list.isArray() || list.isEmpty()) {
            fail(id, "투척 위치 후보가 없습니다(사거리 안에 설 자리가 없음)");
            return;
        }
        List<Map<String, Object>> wps = new ArrayList<>();
        int n = 0;
        for (JsonNode c : list) {
            wps.add(Map.of("pointId", 0, "code", "S" + (++n), "x", c.path("x").asDouble(), "y", c.path("y").asDouble(),
                    "yaw", c.path("yaw").asDouble(), "action", "HOLD"));
        }
        Long taskId = inc.get("task_id") == null ? null : (Long) num(inc.get("task_id"));
        if (taskId == null) {
            String what = heat(inc) ? "열원 확인" : "화재 출동";
            taskId = store.insertTask(robotId, r.path("code").asText(), 0, "system", what + " (사건 #" + id + ")", null, null);
            jdbc.sql("UPDATE inspection_task SET kind = 'RESPONSE', incident_id = ? WHERE task_id = ?").params(id, taskId).update();
            jdbc.sql("UPDATE incident SET task_id = ?, standoff = CAST(? AS jsonb), updated_at = now() WHERE incident_id = ?")
                    .params(taskId, list.toString(), id).update();
            tasks.systemEvent(taskId, "REQUESTED", Map.of("reason", what + " (사건 #" + id + ")"));
        }
        try {
            robot.post().uri("/internal/missions").contentType(MediaType.APPLICATION_JSON)
                    .body(Map.of("missionId", taskId, "robotId", robotId, "kind", "RESPONSE", "waypoints", wps))
                    .retrieve().toBodilessEntity();
        } catch (Exception e) {
            if (age(inc) > DISPATCH_TIMEOUT.toSeconds()) {
                tasks.systemEvent(taskId, "DISPATCH_FAILED", Map.of("reason", message(e)));
                tasks.applyStatus(taskId, "DISPATCH_FAILED", message(e));
                fail(id, "로봇에 출동을 전달하지 못했습니다: " + message(e));
            }
            return;      // 로봇이 아직 바쁘다(직전 작업 정리 중 등) — 다음 틱에 같은 ID 로 다시 보낸다
        }
        state(id, "DISPATCHED");
        event(id, "SYSTEM", "DISPATCHED", Map.of("robotId", robotId, "robotCode", r.path("code").asText(), "taskId", taskId,
                "candidates", wps.size()), null);
    }

    /** 설정된 로봇 → 없으면 연결된 로봇 가운데 한가한 것 → 그것도 없으면 연결된 아무 로봇(점검을 멈추고 보낸다). */
    private Long chooseResponder(Map<String, Object> inc) {
        JsonNode set = settings.get("incident.responder_robot_id");
        if (set != null && set.isNumber()) {
            return set.asLong();
        }
        try {
            JsonNode list = robot.get().uri("/internal/robots").retrieve().body(JsonNode.class);
            Long busy = null;
            if (list != null) {
                for (JsonNode r : list) {
                    if (!r.path("enabled").asBoolean() || !r.path("connected").asBoolean()
                            || !"ROSBRIDGE".equals(r.path("adapterType").asText())) {
                        continue;
                    }
                    if (!r.hasNonNull("mission") || r.path("mission").isEmpty()) {
                        return r.path("robotId").asLong();
                    }
                    busy = busy == null ? r.path("robotId").asLong() : busy;
                }
            }
            return busy;
        } catch (Exception e) {
            return null;
        }
    }

    /** DISPATCHED: 로봇이 투척 위치에 도착해 기다린다고(HOLDING) 알릴 때까지. */
    private void awaitArrival(long id, Map<String, Object> inc) {
        long taskId = num(inc.get("task_id"));
        if (taskHasEvent(taskId, "HOLDING")) {
            state(id, "ARRIVED");
            event(id, "ROBOT", "ARRIVED", Map.of("taskId", taskId), null);
            return;
        }
        String st = store.taskStatus(taskId);
        if (st != null && TaskService.TERMINAL.contains(st)) {
            var t = store.task(taskId).orElse(Map.of());
            fail(id, "출동 실패: " + (t.get("status_reason") == null ? st : t.get("status_reason")));
        }
    }

    /** ARRIVED: 로봇 카메라로 다시 본다. 결과와 투척 모드로 다음을 정한다. */
    private void recheck(long id, Map<String, Object> inc) {
        if (heat(inc)) {
            heatCheck(id, inc);
            return;
        }
        long robotId = num(inc.get("responder_id"));
        JsonNode prev = json(inc.get("recheck"));
        int attempt = prev.path("attempt").asInt(0) + 1;
        Map<String, Object> res = look(id, robotId, "recheck");
        res.put("attempt", attempt);
        int aimTries = prev.path("aimTries").asInt(0);
        res.put("aimTries", aimTries);
        jdbc.sql("UPDATE incident SET recheck = CAST(? AS jsonb), updated_at = now() WHERE incident_id = ?")
                .params(text(res), id).update();
        String grade = String.valueOf(res.get("grade"));
        int max = Math.max(1, settings.integer("launch.search_steps"));
        // 조준 보정: 열원은 보이는데 정면에서 벗어나 있으면(도착 방향 오차) 제자리에서 그만큼 돌리고 다시 본다. 최대 3번.
        // 판이 사진 끝에 잘려 보이면(감지 자리가 조금 어긋나 다른 쪽을 보고 섰다) 정상으로 읽혀도 그쪽으로 돌려 다시 본다
        boolean hot = "EMERGENCY".equals(grade) || "WARNING".equals(grade);
        if (aimTries < 3 && (hot || Boolean.TRUE.equals(res.get("cut"))) && aim(id, inc, res, aimTries)) {
            return;          // 다음 틱에 다시 본다
        }
        if (!hot && attempt < max) {
            return;          // 아직 안 보인다 — 다음 틱에 다시 본다
        }
        event(id, "SYSTEM", "RECHECKED", res, null);
        if ("NORMAL".equals(grade)) {
            close(id, "DISMISSED", "SYSTEM", "도착 후 재판독이 정상(열원 없음) — 오탐으로 닫음");
            return;
        }
        boolean auto = "AUTO".equals(inc.get("launch_mode"));
        boolean aimed = Boolean.TRUE.equals(res.get("aimed"));
        if (auto && "EMERGENCY".equals(grade) && aimed) {
            launch(id, "SYSTEM", "자동 투척: 재판독 비상 확인");
            return;
        }
        String why = !auto ? "승인 모드"
                : !"EMERGENCY".equals(grade) ? "자동 투척 조건 미달: 재판독이 비상이 아님(" + RuleService.GRADE_KO.getOrDefault(grade, grade) + ")"
                : "자동 투척 조건 미달: 대상이 조준 범위 밖";
        state(id, "AWAITING_APPROVAL");
        event(id, "SYSTEM", "APPROVAL_REQUESTED", Map.of("reason", why), null);
        jdbc.sql("UPDATE alert SET detail = ?, state = 'OPEN', updated_at = now() WHERE dedup_key = ? AND state <> 'RESOLVED'")
                .params("투척 승인 대기 · " + why, "incident:" + id).update();
    }

    /**
     * ARRIVED(열원 확인): 열원 앞에서 heat.check_looks 번(틱마다, 약 2초 간격) 찍어 본다. 가장 많이 나온 등급(같으면 높은 쪽)으로 정한다.
     * 화재가 두 번 보이면 바로 화재로 올린다. 판을 찾지 못한 사진(판독 불가)은 세지 않는다.
     */
    private void heatCheck(long id, Map<String, Object> inc) {
        long robotId = num(inc.get("responder_id"));
        JsonNode prev = json(inc.get("recheck"));
        List<String> looks = new ArrayList<>();
        prev.path("looks").forEach(g -> looks.add(g.asText()));
        Map<String, Object> res = look(id, robotId, "recheck");
        int aimTries = prev.path("aimTries").asInt(0);
        res.put("aimTries", aimTries);
        res.put("looks", looks);
        // 판이 정면에서 벗어나 있으면 먼저 돌려서 본다(이 사진은 세지 않는다). 최대 2번
        if (aimTries < 2 && aim(id, inc, res, aimTries)) {
            return;
        }
        String grade = String.valueOf(res.get("grade"));
        looks.add(grade);
        res.put("looks", looks);
        res.put("attempt", looks.size());
        jdbc.sql("UPDATE incident SET recheck = CAST(? AS jsonb), updated_at = now() WHERE incident_id = ?")
                .params(text(res), id).update();
        long fire = looks.stream().filter("EMERGENCY"::equals).count();
        long warn = looks.stream().filter("WARNING"::equals).count();
        long normal = looks.stream().filter("NORMAL"::equals).count();
        if (fire < 2 && looks.size() < Math.max(1, settings.integer("heat.check_looks"))) {
            return;                              // 다음 틱에 한 번 더 찍는다
        }
        String result = fire >= 2 || (fire > 0 && fire >= warn && fire >= normal) ? "EMERGENCY"
                : warn > 0 && warn >= normal ? "WARNING" : normal > 0 ? "NORMAL" : "UNKNOWN";
        Map<String, Object> summary = new LinkedHashMap<>(res);
        summary.put("result", result);
        event(id, "SYSTEM", "HEAT_CHECKED", summary, null);
        double x = ((Number) inc.get("x")).doubleValue();
        double y = ((Number) inc.get("y")).doubleValue();
        switch (result) {
            case "EMERGENCY" -> {
                // 화재로 커졌다: 화재 사건으로 올리고(투척 위치에 이미 서 있다) 재판독 · 투척 흐름을 이어 간다
                jdbc.sql("UPDATE incident SET type = 'FIRE', grade = 'EMERGENCY', recheck = NULL, updated_at = now() WHERE incident_id = ?")
                        .param(id).update();
                event(id, "SYSTEM", "ESCALATED", Map.of("reason", "열원 확인 중 화재(비상)로 보임 — 화재 대응으로 넘김"), null);
                fireAlert(id, x, y, String.valueOf(inc.get("launch_mode")), "열원 확인 중 화재로 커짐 · ", Map.of("incidentId", id));
            }
            case "WARNING" -> {
                alerts.open(new AlertService.Draft("HEAT_WARNING", "WARNING", "heat:" + Math.round(x * 2) + ":" + Math.round(y * 2),
                        "열원 감지 (경고)", "열원 확인 · " + res.getOrDefault("reason", "") + String.format(" · 위치 (%.1f, %.1f)", x, y),
                        null, x, y, "incident", id, null, summary));
                close(id, "RESOLVED", "SYSTEM", "열원 확인: 과열(경고) — 사진과 함께 경고를 엶");
            }
            case "NORMAL" -> close(id, "DISMISSED", "SYSTEM", "열원 확인: 가 보니 정상 — 기록만 남김");
            default -> close(id, "DISMISSED", "SYSTEM", "열원 확인: 사진에서 열화상 판을 찾지 못함 — 기록만 남김");
        }
    }

    /** 사진 속 판이 정면에서 벗어나 있으면 그만큼 제자리에서 돌린다(S2 aim). 돌렸으면 true(다음 틱에 다시 본다). */
    private boolean aim(long id, Map<String, Object> inc, Map<String, Object> res, int aimTries) {
        if (res.get("bearingDeg") == null || Boolean.TRUE.equals(res.get("aimed"))) {
            return false;
        }
        double bearing = ((Number) res.get("bearingDeg")).doubleValue();
        try {
            JsonNode turned = robot.post().uri("/internal/missions/{id}/aim", num(inc.get("task_id")))
                    .contentType(MediaType.APPLICATION_JSON).body(Map.of("deltaDeg", bearing)).retrieve().body(JsonNode.class);
            res.put("aimTries", aimTries + 1);
            jdbc.sql("UPDATE incident SET recheck = CAST(? AS jsonb) WHERE incident_id = ?").params(text(res), id).update();
            event(id, "SYSTEM", "AIM_CORRECTED", Map.of("bearingDeg", bearing,
                    "turnedDeg", Math.round(Math.toDegrees(turned == null ? 0 : turned.path("turnedRad").asDouble()) * 10) / 10.0), null);
            return true;
        } catch (Exception e) {
            event(id, "SYSTEM", "AIM_FAILED", Map.of("reason", message(e)), null);
            return false;
        }
    }

    private static boolean heat(Map<String, Object> inc) {
        return "HEAT".equals(String.valueOf(inc.get("type")));
    }

    /** 로봇의 지금 사진을 받아 열화상 판독(C2)한다. 돌려주는 값: grade, value, bearingDeg, aimed, reason. */
    private Map<String, Object> look(long id, long robotId, String imageKind) {
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("grade", "UNKNOWN");
        out.put("at", Instant.now().toString());
        try {
            ResponseEntity<byte[]> snap = robot.get().uri("/internal/robots/{id}/snapshot", robotId).retrieve().toEntity(byte[].class);
            byte[] img = snap.getBody();
            if (img == null || img.length == 0) {
                out.put("reason", "사진을 받지 못함");
                return out;
            }
            saveImage(id, imageKind, img);
            JsonNode cfg = settings.get("detect.thermal");
            Map<String, Object> rule = new LinkedHashMap<>();
            rule.put("ruleId", 0);
            rule.put("name", "화재 재판독");
            rule.put("kind", "THERMAL");
            rule.put("params", cfg.path("params"));
            rule.put("regions", Map.of());
            rule.put("grading", cfg.path("grading"));
            JsonNode res = rules.check(img, List.of(rule), "INSPECTOR").path("results").path(0);
            out.put("grade", res.path("grade").asText("UNKNOWN"));
            if (res.path("value").isNumber()) {
                out.put("value", res.path("value").asDouble());
            }
            out.put("reason", res.path("reason").asText(""));
            JsonNode bbox = res.path("located").path("bbox");
            if (bbox.isArray() && bbox.size() == 4) {
                out.put("bbox", bbox);
                // 화면 가운데에서 벗어난 정도 → 각도. 왼쪽이 +
                double cx = (bbox.get(0).asDouble() + bbox.get(2).asDouble()) / 2;
                double bearing = (0.5 - cx) * settings.number("camera.hfov_deg");
                out.put("bearingDeg", Math.round(bearing * 10) / 10.0);
                out.put("aimed", Math.abs(bearing) <= settings.number("launch.aim_tolerance_deg"));
                out.put("cut", bbox.get(0).asDouble() < 0.02 || bbox.get(2).asDouble() > 0.98);   // 판이 사진 끝에 잘림
            } else {
                out.put("aimed", false);
            }
        } catch (Exception e) {
            out.put("reason", "재판독 실패: " + message(e));
        }
        return out;
    }

    /** AWAITING_APPROVAL: 정한 간격마다 다시 알린다. */
    private void remind(long id, Map<String, Object> inc) {
        int every = settings.integer("launch.approval_remind_sec");
        if (every <= 0) {
            return;
        }
        Instant last = jdbc.sql("""
                        SELECT max(occurred_at) FROM incident_event
                        WHERE incident_id = ? AND type IN ('APPROVAL_REQUESTED', 'APPROVAL_REMINDER')""")
                .param(id).query(java.sql.Timestamp.class).optional().map(java.sql.Timestamp::toInstant).orElse(Instant.EPOCH);
        if (Duration.between(last, Instant.now()).toSeconds() >= every) {
            event(id, "SYSTEM", "APPROVAL_REMINDER", Map.of(), null);
            jdbc.sql("UPDATE alert SET state = 'OPEN', updated_at = now() WHERE dedup_key = ? AND state <> 'RESOLVED'")
                    .param("incident:" + id).update();
        }
    }

    /** 투척 명령을 보낸다(S2). 쏠 수 없으면 사건을 실패로 돌린다. */
    private void launch(long id, String by, String why) {
        Map<String, Object> inc = row(id);
        long robotId = num(inc.get("responder_id"));
        int seq = jdbc.sql("UPDATE incident SET command_seq = command_seq + 1 WHERE incident_id = ? RETURNING command_seq")
                .param(id).query(Integer.class).single();
        String commandId = "inc-" + id + "-" + seq;
        try {
            robot.post().uri("/internal/robots/{id}/actuate", robotId).contentType(MediaType.APPLICATION_JSON)
                    .body(Map.of("commandId", commandId, "kind", "LAUNCH", "count", Math.max(1, settings.integer("launch.count")),
                            "params", settings.get("launch.params")))
                    .retrieve().toBodilessEntity();
        } catch (Exception e) {
            event(id, "SYSTEM", "LAUNCH_REJECTED", Map.of("commandId", commandId, "reason", message(e)), by);
            fail(id, "투척 명령을 보낼 수 없습니다: " + message(e));
            return;
        }
        state(id, "LAUNCHING");
        event(id, "SYSTEM".equals(by) ? "SYSTEM" : "USER", "LAUNCH_ORDERED", Map.of("commandId", commandId, "reason", why),
                "SYSTEM".equals(by) ? null : by);
    }

    /** LAUNCHING: 로봇이 투척 결과를 알릴 때까지. 쏜 뒤에는 한 번 더 본다. */
    private void awaitLaunch(long id, Map<String, Object> inc) {
        long taskId = num(inc.get("task_id"));
        String commandId = "inc-" + id + "-" + inc.get("command_seq");
        JsonNode done = taskEvent(taskId, "ACTUATED", commandId);
        JsonNode failed = taskEvent(taskId, "ACTUATE_FAILED", commandId);
        if (done != null) {
            state(id, "LAUNCHED");
            event(id, "ROBOT", "LAUNCHED", Map.of("commandId", commandId, "launched", done.path("launched").asInt()), null);
            Map<String, Object> after = look(id, num(inc.get("responder_id")), "after");
            jdbc.sql("UPDATE incident SET after_check = CAST(? AS jsonb), updated_at = now() WHERE incident_id = ?")
                    .params(text(after), id).update();
            event(id, "SYSTEM", "AFTER_CHECKED", after, null);
            if ("NORMAL".equals(after.get("grade"))) {
                close(id, "RESOLVED", "SYSTEM", "투척 후 재판독이 정상");
            } else {
                // 열원이 남아 있다: 로봇은 그 자리에서 계속 감시한다
                state(id, "MONITORING");
                event(id, "SYSTEM", "MONITORING", Map.of("reason", "투척 후에도 열원이 보임 — 현장에 머물며 감시"), null);
                jdbc.sql("UPDATE alert SET detail = ?, updated_at = now() WHERE dedup_key = ? AND state <> 'RESOLVED'")
                        .params("투척함 · 투척 후에도 열원이 보임 — 현장 감시 중", "incident:" + id).update();
            }
        } else if (failed != null) {
            fail(id, "투척 실패: " + failed.path("code").asText() + " " + failed.path("reason").asText());
        } else if (TaskService.TERMINAL.contains(String.valueOf(store.taskStatus(taskId)))) {
            fail(id, "투척 결과를 받기 전에 출동 작업이 끝났습니다");
        }
    }

    /**
     * MONITORING: 투척 뒤에도 열원이 남아 있다. 터틀봇은 그 자리에 머물며 계속 찍어 본다(현장 감시).
     * - 정한 간격마다 다시 판독해 가장 최근 사진과 결과를 남긴다. 등급이 바뀌면 사건 기록에 남긴다.
     * - 연속으로 정상이 나오면 열원이 사라진 것으로 보고 해결로 닫는다.
     * - 그 밖에는 사람이 닫을 때까지 계속한다(다시 쏘려면 수동 투척). 로봇은 풀어 주지 않는다.
     * (젯봇이 붙으면 젯봇은 다른 구역의 순찰을 계속한다 — 이 사건에 묶이는 것은 대응 로봇뿐이다.)
     */
    private void monitor(long id, Map<String, Object> inc) {
        long taskId = num(inc.get("task_id"));
        if (TaskService.TERMINAL.contains(String.valueOf(store.taskStatus(taskId)))) {
            // 로봇이 자리를 떠났다(비상 정지 · 취소 등). 감시를 이어갈 수 없으니 사람이 보게 한다
            state(id, "LAUNCHED");
            event(id, "SYSTEM", "MONITOR_STOPPED", Map.of("reason", "대응 로봇이 자리를 떠나 현장 감시가 끊김"), null);
            jdbc.sql("UPDATE alert SET detail = ?, state = 'OPEN', updated_at = now() WHERE dedup_key = ? AND state <> 'RESOLVED'")
                    .params("현장 감시가 끊김 — 대응 로봇이 자리를 떠남. 확인 필요", "incident:" + id).update();
            return;
        }
        JsonNode prev = json(inc.get("after_check"));
        Instant last = prev.hasNonNull("at") ? Instant.parse(prev.path("at").asText()) : Instant.EPOCH;
        if (Duration.between(last, Instant.now()).toSeconds() < Math.max(3, settings.integer("incident.monitor_interval_sec"))) {
            return;
        }
        Map<String, Object> now = look(id, num(inc.get("responder_id")), "after");
        String grade = String.valueOf(now.get("grade"));
        int streak = "NORMAL".equals(grade) ? prev.path("normalStreak").asInt(0) + 1 : 0;
        now.put("normalStreak", streak);
        now.put("checks", prev.path("checks").asInt(1) + 1);
        jdbc.sql("UPDATE incident SET after_check = CAST(? AS jsonb), updated_at = now() WHERE incident_id = ?")
                .params(text(now), id).update();
        if (!grade.equals(prev.path("grade").asText())) {
            event(id, "SYSTEM", "MONITOR_CHECKED", now, null);
            jdbc.sql("UPDATE alert SET detail = ?, updated_at = now() WHERE dedup_key = ? AND state <> 'RESOLVED'")
                    .params("투척함 · 현장 감시 중 — 지금 " + RuleService.GRADE_KO.getOrDefault(grade, grade), "incident:" + id).update();
        }
        if (streak >= Math.max(1, settings.integer("incident.monitor_clear_count"))) {
            close(id, "RESOLVED", "SYSTEM", "현장 감시 중 열원이 사라짐(연속 " + streak + "회 정상)");
        }
    }

    // ------------------------------------------------------------- 사람이 하는 일(A3)
    public synchronized Map<String, Object> approve(long id, CurrentUser u) {
        Map<String, Object> inc = row(id);
        if (!"AWAITING_APPROVAL".equals(inc.get("state"))) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, "승인 대기 중인 사건이 아닙니다 (" + inc.get("state") + ")");
        }
        jdbc.sql("UPDATE incident SET approved_by = ?, approved_at = now() WHERE incident_id = ?").params(u.login(), id).update();
        event(id, "USER", "APPROVED", Map.of(), u.login());
        launch(id, u.login(), "사용자 승인");
        return detail(id);
    }

    /** 수동 투척: 로봇이 투척 위치에 서 있으면(도착 · 승인 대기 · 투척함) 모드와 무관하게 쏜다. */
    public synchronized Map<String, Object> manualLaunch(long id, CurrentUser u) {
        Map<String, Object> inc = row(id);
        if (!Set.of("ARRIVED", "AWAITING_APPROVAL", "LAUNCHED", "MONITORING").contains(String.valueOf(inc.get("state")))) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, "로봇이 투척 위치에 있을 때만 쏠 수 있습니다 (" + inc.get("state") + ")");
        }
        if (TaskService.TERMINAL.contains(String.valueOf(store.taskStatus(num(inc.get("task_id")))))) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, "로봇이 이미 자리를 떠났습니다");
        }
        launch(id, u.login(), "수동 투척");
        return detail(id);
    }

    public synchronized Map<String, Object> closeByUser(long id, String state, CurrentUser u, String comment) {
        Map<String, Object> inc = row(id);
        if (CLOSED.contains(String.valueOf(inc.get("state")))) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, "이미 닫힌 사건입니다");
        }
        close(id, state, u.login(), comment == null || comment.isBlank()
                ? ("DISMISSED".equals(state) ? "오탐으로 닫음" : "조치 완료") : comment.trim());
        return detail(id);
    }

    // ------------------------------------------------------------- 닫기 · 실패
    private void close(long id, String state, String by, String reason) {
        Map<String, Object> inc = row(id);
        jdbc.sql("""
                        UPDATE incident SET state = ?, closed_by = ?, closed_at = now(), close_reason = ?, updated_at = now()
                        WHERE incident_id = ?""").params(state, by, reason, id).update();
        event(id, "SYSTEM".equals(by) ? "SYSTEM" : "USER", state, Map.of("reason", reason), "SYSTEM".equals(by) ? null : by);
        alerts.resolveByKey("incident:" + id, by, reason);
        if (inc.get("task_id") != null) {
            finishMission(num(inc.get("task_id")), "COMPLETED", reason);
        }
    }

    /** 실패: 로봇은 풀어 주고, 사건과 경고는 사람이 확인해 닫을 때까지 열어 둔다. */
    private void fail(long id, String reason) {
        Map<String, Object> inc = row(id);
        jdbc.sql("UPDATE incident SET state = 'FAILED', close_reason = ?, updated_at = now() WHERE incident_id = ?")
                .params(reason, id).update();
        event(id, "SYSTEM", "FAILED", Map.of("reason", reason), null);
        jdbc.sql("UPDATE alert SET detail = ?, state = 'OPEN', updated_at = now() WHERE dedup_key = ? AND state <> 'RESOLVED'")
                .params("대응 실패 · " + reason, "incident:" + id).update();
        if (inc.get("task_id") != null) {
            finishMission(num(inc.get("task_id")), "FAILED", reason);
        }
        log.info("사건 #{} 실패: {}", id, reason);
    }

    /** 출동 미션을 끝낸다(로봇의 제어권이 풀리고 밀린 예약이 이어진다). 이미 끝났으면 아무 일도 없다. */
    private void finishMission(long taskId, String result, String reason) {
        String st = store.taskStatus(taskId);
        if (st == null || TaskService.TERMINAL.contains(st)) {
            return;
        }
        try {
            JsonNode res = robot.post().uri("/internal/missions/{id}/finish", taskId).contentType(MediaType.APPLICATION_JSON)
                    .body(Map.of("result", result, "reason", reason)).retrieve().body(JsonNode.class);
            if (res != null && !res.path("applied").asBoolean()) {
                // 로봇 쪽에 그 미션이 없다(전달 전이거나 이미 끝남): 작업만 정리한다
                robot.post().uri("/internal/missions/{id}/cancel", taskId).contentType(MediaType.APPLICATION_JSON)
                        .body(Map.of("reason", reason)).retrieve().toBodilessEntity();
                if (!TaskService.TERMINAL.contains(String.valueOf(store.taskStatus(taskId)))
                        && "UNKNOWN".equals(res.path("state").asText())) {
                    tasks.systemEvent(taskId, "CANCELLED", Map.of("reason", reason));
                    tasks.applyStatus(taskId, "CANCELLED", reason);
                }
            }
        } catch (Exception e) {
            log.info("출동 미션 #{} 종료 전달 실패: {}", taskId, e.toString());
        }
    }

    // ------------------------------------------------------------- 조회
    public List<Map<String, Object>> list(boolean openOnly, int limit) {
        return jdbc.sql("SELECT * FROM incident" + (openOnly ? " WHERE state NOT IN ('RESOLVED', 'DISMISSED')" : "")
                        + " ORDER BY incident_id DESC LIMIT ?").param(Math.max(1, Math.min(limit, 200))).query().listOfRows()
                .stream().map(this::view).toList();
    }

    public Map<String, Object> detail(long id) {
        Map<String, Object> m = view(row(id));
        List<Map<String, Object>> events = new ArrayList<>();
        for (var e : jdbc.sql("""
                SELECT event_id, source, type, detail::text AS detail, actor, occurred_at FROM incident_event
                WHERE incident_id = ? ORDER BY event_id""").param(id).query().listOfRows()) {
            Map<String, Object> x = new LinkedHashMap<>(e);
            x.put("detail", json(e.get("detail")));
            events.add(x);
        }
        m.put("events", events);
        return m;
    }

    public byte[] image(long id, String kind) {
        String col = switch (kind) {
            case "recheck" -> "recheck_image";
            case "after" -> "after_image";
            default -> "detection_image";
        };
        String p = jdbc.sql("SELECT " + col + " FROM incident WHERE incident_id = ?").param(id).query(String.class)
                .optional().orElse(null);
        if (p == null) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND);
        }
        try {
            return Files.readAllBytes(Path.of(p));
        } catch (Exception e) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND);
        }
    }

    private Map<String, Object> view(Map<String, Object> r) {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("incidentId", r.get("incident_id"));
        m.put("type", r.get("type"));
        m.put("state", r.get("state"));
        m.put("grade", r.get("grade"));
        m.put("x", r.get("x"));
        m.put("y", r.get("y"));
        m.put("poseQuality", r.get("pose_quality"));
        m.put("detectedBy", r.get("detected_by"));
        m.put("launchMode", r.get("launch_mode"));
        m.put("responderId", r.get("responder_id"));
        m.put("taskId", r.get("task_id"));
        m.put("standoff", json(r.get("standoff")));
        m.put("recheck", json(r.get("recheck")));
        m.put("afterCheck", json(r.get("after_check")));
        m.put("images", Map.of("detection", r.get("detection_image") != null, "recheck", r.get("recheck_image") != null,
                "after", r.get("after_image") != null));
        m.put("approvedBy", r.get("approved_by"));
        m.put("approvedAt", r.get("approved_at"));
        m.put("closedBy", r.get("closed_by"));
        m.put("closedAt", r.get("closed_at"));
        m.put("closeReason", r.get("close_reason"));
        m.put("createdAt", r.get("created_at"));
        m.put("updatedAt", r.get("updated_at"));
        return m;
    }

    // ------------------------------------------------------------- 도우미
    private Map<String, Object> row(long id) {
        return jdbc.sql("SELECT * FROM incident WHERE incident_id = ?").param(id).query().listOfRows().stream().findFirst()
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "없는 사건"));
    }

    private void state(long id, String state) {
        jdbc.sql("UPDATE incident SET state = ?, updated_at = now() WHERE incident_id = ?").params(state, id).update();
    }

    private void event(long id, String source, String type, Map<String, ?> detail, String actor) {
        jdbc.sql("INSERT INTO incident_event (incident_id, source, type, detail, actor) VALUES (?, ?, ?, CAST(? AS jsonb), ?)")
                .params(id, source, type, text(detail), actor).update();
    }

    private boolean hasEvent(long id, String type) {
        return jdbc.sql("SELECT count(*) FROM incident_event WHERE incident_id = ? AND type = ?").params(id, type)
                .query(Long.class).single() > 0;
    }

    private boolean taskHasEvent(long taskId, String type) {
        return jdbc.sql("SELECT count(*) FROM task_event WHERE task_id = ? AND type = ?").params(taskId, type)
                .query(Long.class).single() > 0;
    }

    /** 출동 작업의 사건 기록에서 그 투척 명령의 결과를 찾는다. 없으면 null. */
    private JsonNode taskEvent(long taskId, String type, String commandId) {
        return jdbc.sql("""
                        SELECT detail::text FROM task_event
                        WHERE task_id = ? AND type = ? AND detail->>'commandId' = ? ORDER BY event_id DESC LIMIT 1""")
                .params(taskId, type, commandId).query(String.class).optional().map(this::json).orElse(null);
    }

    private void saveImage(long id, String kind, byte[] img) {
        try {
            Path f = photoDir.resolve("incident-" + id + "-" + kind + ".jpg");
            Files.write(f, img);
            jdbc.sql("UPDATE incident SET " + (switch (kind) {
                case "recheck" -> "recheck_image";
                case "after" -> "after_image";
                default -> "detection_image";
            }) + " = ? WHERE incident_id = ?").params(f.toString(), id).update();
        } catch (Exception e) {
            log.info("사건 #{} 사진 저장 실패: {}", id, e.toString());
        }
    }

    private static long age(Map<String, Object> inc) {
        return Duration.between(((java.sql.Timestamp) inc.get("created_at")).toInstant(), Instant.now()).toSeconds();
    }

    private static Long num(Object o) {
        return o == null ? null : ((Number) o).longValue();
    }

    private JsonNode json(Object text) {
        try {
            return text == null ? om.nullNode() : om.readTree(String.valueOf(text));
        } catch (Exception e) {
            return om.nullNode();
        }
    }

    private String text(Object o) {
        try {
            return om.writeValueAsString(o == null ? Map.of() : o);
        } catch (Exception e) {
            return "{}";
        }
    }

    private String message(Exception e) {
        if (e instanceof HttpStatusCodeException h) {
            try {
                return om.readTree(h.getResponseBodyAsString()).path("message").asText(h.getStatusText());
            } catch (Exception ignored) {
                return h.getStatusText();
            }
        }
        return String.valueOf(e.getMessage());
    }
}
