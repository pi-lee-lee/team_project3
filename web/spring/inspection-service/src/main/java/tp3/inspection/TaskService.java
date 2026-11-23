package tp3.inspection;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Service;
import org.springframework.web.client.HttpStatusCodeException;
import org.springframework.web.client.RestClient;
import org.springframework.web.server.ResponseStatusException;
import tp3.common.CurrentUser;

import java.time.Instant;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

/**
 * 작업 생성·로봇 전달·취소와 상태 계산.
 * 상태는 사건 기록(task_event)에서 계산한 현재 값이다. 끝난 작업(완료·실패·취소·중단)은 바뀌지 않는다.
 */
@Service
public class TaskService {

    private static final Logger log = LoggerFactory.getLogger(TaskService.class);
    static final Set<String> TERMINAL = Set.of("COMPLETED", "FAILED", "CANCELLED", "INTERRUPTED");

    private final Store store;
    private final RestClient robot;
    private final ObjectMapper om = new ObjectMapper();

    public TaskService(Store store, RestClient robotClient) {
        this.store = store;
        this.robot = robotClient;
    }

    // ------------------------------------------------------------- 생성
    public Map<String, Object> create(CurrentUser u, long robotId, List<Long> pointIds, String note, Long recheckOf) {
        return create(u, robotId, pointIds, note, recheckOf, null);
    }

    /** scheduleId: 예약 점검이 만든 작업이면 그 예약 ID. */
    public Map<String, Object> create(CurrentUser u, long robotId, List<Long> pointIds, String note, Long recheckOf,
                                      Long scheduleId) {
        if (pointIds == null || pointIds.isEmpty()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "점검 지점을 하나 이상 고르세요");
        }
        List<Map<String, Object>> points = new ArrayList<>();
        for (Long pid : pointIds) {
            var p = store.point(pid).orElseThrow(() -> new ResponseStatusException(HttpStatus.BAD_REQUEST, "없는 지점: " + pid));
            if (!(Boolean) p.get("active")) {
                throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "비활성 지점: " + p.get("code"));
            }
            points.add(p);
        }
        JsonNode r;
        try {
            r = robot.get().uri("/internal/robots/{id}", robotId).retrieve().body(JsonNode.class);
        } catch (HttpStatusCodeException e) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "없는 로봇입니다");
        } catch (Exception e) {
            throw new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE, "로봇 서비스에 연결할 수 없습니다");
        }
        long taskId = store.insertTask(robotId, r.path("code").asText(), u.id(), u.login(), note, recheckOf, scheduleId);
        for (int i = 0; i < points.size(); i++) {
            store.insertTaskPoint(taskId, i + 1, ((Number) points.get(i).get("point_id")).longValue());
        }
        Map<String, Object> d = new LinkedHashMap<>();
        d.put("points", points.stream().map(p -> p.get("code")).toList());
        if (recheckOf != null) {
            d.put("recheckOf", recheckOf);
        }
        if (scheduleId != null) {
            d.put("scheduleId", scheduleId);
        }
        userEvent(taskId, "REQUESTED", d, u.login());
        dispatch(taskId, robotId, points);
        return detail(taskId);
    }

    /** 지점의 exit_zone 글자("[x1, y1, x2, y2]")를 JSON 배열로. 없거나 모양이 틀리면 null. */
    private JsonNode exitZone(Object text) {
        if (text == null) {
            return null;
        }
        try {
            JsonNode z = om.readTree(text.toString());
            return z.isArray() && z.size() == 4 ? z : null;
        } catch (Exception e) {
            return null;
        }
    }

    private void dispatch(long taskId, long robotId, List<Map<String, Object>> points) {
        var wps = points.stream().map(p -> {
            Map<String, Object> w = new HashMap<>(Map.of(
                    "pointId", p.get("point_id"), "code", p.get("code"),
                    "x", p.get("x"), "y", p.get("y"),
                    "yaw", Math.toRadians(((Number) p.get("yaw_deg")).doubleValue())));
            JsonNode zone = exitZone(p.get("exit_zone"));
            if (zone != null) {
                w.put("exitZone", zone);   // 비상구 점검 지점: 로봇이 이 구역 안에서 막히면 복구 없이 바로 진입 불가로 보고한다
            }
            return w;
        }).toList();
        try {
            robot.post().uri("/internal/missions").contentType(MediaType.APPLICATION_JSON)
                    .body(Map.of("missionId", taskId, "robotId", robotId, "waypoints", wps))
                    .retrieve().toBodilessEntity();
        } catch (HttpStatusCodeException e) {
            String msg = message(e);
            systemEvent(taskId, "DISPATCH_FAILED", Map.of("reason", msg));
            applyStatus(taskId, "DISPATCH_FAILED", msg);
        } catch (Exception e) {
            // 응답을 못 받았다: 로봇 쪽이 접수했는지 알 수 없다. 같은 ID 로 다시 보내면 중복 실행 없이 상태를 알려 준다.
            systemEvent(taskId, "DISPATCH_UNKNOWN", Map.of("reason", String.valueOf(e.getMessage())));
            log.warn("dispatch {} unknown: {}", taskId, e.toString());
        }
    }

    // ------------------------------------------------------------- 취소
    public Map<String, Object> cancel(long taskId, CurrentUser u) {
        String st = store.taskStatus(taskId);
        if (st == null) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND);
        }
        if (TERMINAL.contains(st)) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, "이미 끝난 작업입니다 (" + st + ")");
        }
        userEvent(taskId, "CANCEL_REQUESTED", Map.of(), u.login());
        synchronized (this) {
            if (!TERMINAL.contains(store.taskStatus(taskId))) {
                store.setStatus(taskId, "CANCEL_REQUESTED", null);
            }
        }
        try {
            JsonNode res = robot.post().uri("/internal/missions/{id}/cancel", taskId)
                    .contentType(MediaType.APPLICATION_JSON).body(Map.of("reason", u.login() + " 취소 요청"))
                    .retrieve().body(JsonNode.class);
            if (res != null && !res.path("applied").asBoolean()) {
                String robotState = res.path("state").asText();
                systemEvent(taskId, "CANCEL_NOT_APPLIED", Map.of("robotState", robotState));
                if ("UNKNOWN".equals(robotState)) {
                    applyStatus(taskId, "CANCELLED", "로봇에 전달되기 전 취소");
                    systemEvent(taskId, "CANCELLED", Map.of("reason", "로봇에 전달되기 전 취소"));
                }
            }
        } catch (Exception e) {
            systemEvent(taskId, "CANCEL_SEND_FAILED", Map.of("reason", String.valueOf(e.getMessage())));
        }
        return detail(taskId);
    }

    // ------------------------------------------------------------- 로봇 보고
    public void robotEvent(long taskId, UUID reportId, JsonNode body) {
        if (store.taskStatus(taskId) == null) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, "없는 작업");
        }
        String type = body.path("type").asText();
        Instant at = body.hasNonNull("occurredAt") ? Instant.parse(body.path("occurredAt").asText()) : Instant.now();
        boolean inserted = store.insertEvent(taskId, reportId, "ROBOT", type, body.path("detail").toString(), null, at);
        if (inserted) {
            String reason = body.path("detail").path("reason").asText(null);
            applyStatus(taskId, type, reason);
        }
    }

    synchronized void applyStatus(long taskId, String eventType, String reason) {
        String cur = store.taskStatus(taskId);
        if (cur == null || TERMINAL.contains(cur)) {
            return;
        }
        boolean cancelling = "CANCEL_REQUESTED".equals(cur);
        String next = switch (eventType) {
            case "ACCEPTED" -> cancelling ? null : "DISPATCHED";
            case "PREFLIGHT_OK", "STARTED", "MOVING", "ARRIVED" -> cancelling ? null : "RUNNING";
            case "COMPLETED" -> "COMPLETED";
            case "CANCELLED" -> "CANCELLED";
            case "MISSION_FAILED", "DISPATCH_FAILED" -> "FAILED";
            case "MISSION_INTERRUPTED" -> "INTERRUPTED";
            default -> null;
        };
        if (next != null) {
            // 상태 사유는 실패·취소·중단으로 끝났을 때만 남긴다(중간 사건의 참고 문구는 사건 기록에만)
            boolean failure = Set.of("FAILED", "CANCELLED", "INTERRUPTED").contains(next);
            store.setStatus(taskId, next, failure ? reason : null);
        }
    }

    // ------------------------------------------------------------- 조회
    public Map<String, Object> detail(long taskId) {
        var task = store.task(taskId).orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND));
        Map<String, Object> m = new LinkedHashMap<>(task);
        m.put("points", store.taskPoints(taskId));
        m.put("events", store.events(taskId));
        var obs = store.observationsOfTask(taskId);
        Map<Object, List<Map<String, Object>>> reviews = new HashMap<>();
        for (var r : store.reviewsOfTask(taskId)) {
            reviews.computeIfAbsent(r.get("observation_id"), k -> new ArrayList<>()).add(r);
        }
        m.put("observations", obs.stream().map(o -> {
            Map<String, Object> x = new LinkedHashMap<>(o);
            x.put("reviews", reviews.getOrDefault(o.get("observation_id"), List.of()));
            return x;
        }).toList());
        return m;
    }

    // ------------------------------------------------------------- 사건 기록 도우미
    void userEvent(long taskId, String type, Map<String, ?> detail, String actor) {
        store.insertEvent(taskId, null, "USER", type, json(detail), actor, Instant.now());
    }

    void systemEvent(long taskId, String type, Map<String, ?> detail) {
        systemEvent(taskId, type, detail, Instant.now());
    }

    void systemEvent(long taskId, String type, Map<String, ?> detail, Instant occurredAt) {
        store.insertEvent(taskId, null, "SYSTEM", type, json(detail), null, occurredAt);
    }

    private String json(Object o) {
        try {
            return om.writeValueAsString(o);
        } catch (Exception e) {
            return "{}";
        }
    }

    private String message(HttpStatusCodeException e) {
        try {
            return om.readTree(e.getResponseBodyAsString()).path("message").asText(e.getStatusText());
        } catch (Exception ex) {
            return e.getStatusText();
        }
    }
}
