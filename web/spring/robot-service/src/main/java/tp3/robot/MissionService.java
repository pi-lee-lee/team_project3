package tp3.robot;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.EventListener;
import org.springframework.core.annotation.Order;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;
import tp3.robot.adapter.RobotAdapter;

import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.TimeoutException;

/**
 * 미션 실행: 출발 전 검사 → 지점마다 (이동 → 도착 → 촬영) → 완료.
 * 각 단계의 사실은 report_outbox 에 먼저 저장하고 OutboxSender 가 inspection-service 로 보낸다.
 * 같은 mission_id 로 다시 요청하면 새로 실행하지 않고 현재 상태를 돌려준다(중복 명령 처리).
 */
@Service
public class MissionService {

    private static final Logger log = LoggerFactory.getLogger(MissionService.class);
    private static final long GOAL_TIMEOUT_MS = 300_000;

    public record Waypoint(long pointId, String code, double x, double y, double yaw) {
    }

    private static final class Running {
        final long missionId;
        final long robotId;
        volatile boolean cancelRequested;
        volatile String cancelReason;
        volatile String currentGoal;
        volatile Long currentPoint;
        final Map<String, CompletableFuture<RobotAdapter.GoalStatus>> waits = new ConcurrentHashMap<>();
        final Map<String, Boolean> activeSeen = new ConcurrentHashMap<>();

        Running(long missionId, long robotId) {
            this.missionId = missionId;
            this.robotId = robotId;
        }
    }

    private final RobotRepository repo;
    private final RobotRegistry registry;
    private final ControlService control;
    private final ObjectMapper om = new ObjectMapper();
    private final Map<Long, Running> runningByRobot = new ConcurrentHashMap<>();
    /** 관제 화면 지도 모드에서 사용자가 찍은 목적지(점검 작업과 별개). 로봇별 최근 상태. */
    private final Map<Long, Map<String, Object>> manualGoals = new ConcurrentHashMap<>();
    private final ExecutorService pool = Executors.newCachedThreadPool();

    public MissionService(RobotRepository repo, RobotRegistry registry, ControlService control) {
        this.repo = repo;
        this.registry = registry;
        this.control = control;
        registry.setGoalListener(this::onGoalStatus);
    }

    /** 서비스가 재시작되면 실행 중이던 미션의 실제 결과를 알 수 없다. 그 사실을 기록한다. */
    @EventListener(ApplicationReadyEvent.class)
    @Order(2)
    public void recover() {
        for (var m : repo.unfinishedMissions()) {
            repo.missionState(m.missionId(), "INTERRUPTED", "robot-service restarted");
            event(m.missionId(), "MISSION_INTERRUPTED",
                    Map.of("reason", "로봇 서비스가 재시작되어 실행 결과를 알 수 없습니다. 로봇 상태를 확인하세요"));
            try {
                var a = registry.adapterOrNull(m.robotId());
                if (a != null) {
                    a.stop();
                }
            } catch (Exception ignored) {
                // 연결 전이면 로봇 측 워치독에 맡긴다
            }
        }
    }

    // ------------------------------------------------------------- 요청
    public synchronized Map<String, Object> submit(long missionId, long robotId, List<Waypoint> waypoints) {
        var existing = repo.mission(missionId);
        if (existing.isPresent()) {
            return Map.of("missionId", missionId, "state", existing.get().state(), "duplicate", true);
        }
        repo.robot(robotId).orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "로봇이 없습니다"));
        RobotAdapter adapter = registry.adapter(robotId);
        if (runningByRobot.containsKey(robotId)) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, "로봇이 다른 점검 작업을 수행 중입니다");
        }
        if (!adapter.state().connected()) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, "로봇과 연결되어 있지 않습니다");
        }
        if (!control.takeForMission(robotId)) {
            var h = control.holder(robotId);
            throw new ResponseStatusException(HttpStatus.CONFLICT, (h == null ? "다른 사용자" : h.login()) + " 님이 조종 중입니다");
        }
        try {
            repo.insertMission(missionId, robotId, om.writeValueAsString(waypoints));
        } catch (Exception e) {
            control.releaseMission(robotId);
            throw new IllegalStateException(e);
        }
        Running run = new Running(missionId, robotId);
        runningByRobot.put(robotId, run);
        event(missionId, "ACCEPTED", Map.of("robotId", robotId, "points", waypoints.size()));
        pool.submit(() -> execute(run, adapter, waypoints));
        return Map.of("missionId", missionId, "state", "ACCEPTED", "duplicate", false);
    }

    public synchronized Map<String, Object> cancel(long missionId, String reason) {
        var m = repo.mission(missionId).orElse(null);
        if (m == null) {
            return Map.of("applied", false, "state", "UNKNOWN");
        }
        Running run = runningByRobot.get(m.robotId());
        if (run == null || run.missionId != missionId) {
            return Map.of("applied", false, "state", m.state());
        }
        run.cancelRequested = true;
        run.cancelReason = reason;
        String g = run.currentGoal;
        try {
            registry.adapter(m.robotId()).cancelGoal(g == null ? "*" : g);
        } catch (Exception e) {
            log.warn("cancel send failed: {}", e.toString());
        }
        run.waits.values().forEach(f -> f.complete(new RobotAdapter.GoalStatus(g, "CANCELED", reason)));
        return Map.of("applied", true, "state", "CANCELLING");
    }

    /** 비상 정지: 진행 중 미션 취소 + 사용자 제어권 회수 + 정지 명령. */
    public Map<String, Object> emergencyStop(long robotId, String by) {
        Running run = runningByRobot.get(robotId);
        if (run != null) {
            cancel(run.missionId, "비상 정지 (" + by + ")");
            event(run.missionId, "EMERGENCY_STOP", Map.of("by", by));
        }
        control.revoke(robotId);
        registry.adapter(robotId).stop();
        return Map.of("stopped", true, "missionCancelled", run != null);
    }

    public Map<String, Object> active(long robotId) {
        Running run = runningByRobot.get(robotId);
        if (run == null) {
            return null;
        }
        Map<String, Object> m = new java.util.HashMap<>();
        m.put("missionId", run.missionId);
        m.put("currentPointId", run.currentPoint);
        m.put("cancelRequested", run.cancelRequested);
        return m;
    }

    // ------------------------------------------------------------- 실행
    private void execute(Running run, RobotAdapter a, List<Waypoint> wps) {
        long id = run.missionId;
        String finalState = "COMPLETED";
        String finalReason = null;
        try {
            repo.missionState(id, "RUNNING", null);
            List<String> problems = preflight(a);
            if (!problems.isEmpty()) {
                event(id, "PREFLIGHT_FAILED", Map.of("reasons", problems));
                for (int i = 0; i < wps.size(); i++) {
                    observation(id, wps.get(i), i, "UNABLE", "PREFLIGHT_FAILED",
                            "출발 전 검사 실패: " + String.join(", ", problems), null, null);
                }
                finalState = "FAILED";
                finalReason = String.join(", ", problems);
                return;
            }
            event(id, "PREFLIGHT_OK", Map.of());
            event(id, "STARTED", Map.of());
            int captured = 0;
            int unable = 0;
            for (int i = 0; i < wps.size(); i++) {
                Waypoint wp = wps.get(i);
                if (run.cancelRequested) {
                    break;
                }
                run.currentPoint = wp.pointId();
                event(id, "MOVING", Map.of("pointId", wp.pointId(), "code", wp.code(), "seq", i + 1));
                RobotAdapter.GoalStatus result = goTo(run, a, id + "-" + (i + 1), wp);
                if (run.cancelRequested || "CANCELED".equals(result.state())) {
                    break;
                }
                if (!"SUCCEEDED".equals(result.state())) {
                    String code = result.code() == null || result.code().isBlank() ? "NAV_FAILED" : result.code();
                    boolean blocked = "BLOCKED_NO_PATH".equals(code);
                    String why = (blocked ? "진입 불가: " : "도착 실패: ")
                            + (result.reason() == null || result.reason().isBlank() ? result.state() : result.reason());
                    event(id, blocked ? "ARRIVAL_BLOCKED" : "ARRIVAL_FAILED",
                            Map.of("pointId", wp.pointId(), "code", wp.code(), "reasonCode", code, "reason", why,
                                    "recoveries", result.recoveries()));
                    observation(id, wp, i, "UNABLE", code, why, a.state().pose(), null);
                    unable++;
                    continue;
                }
                event(id, "ARRIVED", result.detoured()
                        ? Map.of("pointId", wp.pointId(), "code", wp.code(), "detoured", true,
                        "recoveries", result.recoveries(), "reason", "경로상 장애물 우회")
                        : Map.of("pointId", wp.pointId(), "code", wp.code()));
                Thread.sleep(1500);   // 정지 후 영상 안정화
                byte[] img = null;
                String err = null;
                for (int k = 0; k < 3 && img == null; k++) {
                    try {
                        img = a.snapshot();
                    } catch (Exception e) {
                        err = e.getMessage();
                        Thread.sleep(700);
                    }
                }
                if (img == null) {
                    observation(id, wp, i, "UNABLE", "CAPTURE_FAILED", "촬영 실패: " + err, a.state().pose(), null);
                    unable++;
                } else {
                    observation(id, wp, i, "CAPTURED", null, null, a.state().pose(), img);
                    captured++;
                }
            }
            if (run.cancelRequested) {
                finalState = "CANCELLED";
                finalReason = run.cancelReason;
                event(id, "CANCELLED", Map.of("reason", String.valueOf(run.cancelReason)));
            } else {
                event(id, "COMPLETED", Map.of("captured", captured, "unable", unable));
            }
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            finalState = "FAILED";
            finalReason = "interrupted";
        } catch (Exception e) {
            log.warn("mission {} failed", id, e);
            finalState = "FAILED";
            finalReason = String.valueOf(e.getMessage());
        } finally {
            if ("FAILED".equals(finalState) && finalReason != null && !finalReason.equals("interrupted")) {
                event(id, "MISSION_FAILED", Map.of("reason", finalReason));
            }
            try {
                a.teleop(0, 0);
            } catch (Exception ignored) {
                // 연결이 끊긴 경우
            }
            repo.missionState(id, finalState, finalReason);
            runningByRobot.remove(run.robotId, run);
            control.releaseMission(run.robotId);
        }
    }

    private List<String> preflight(RobotAdapter a) {
        List<String> p = new ArrayList<>();
        var s = a.state();
        if (!s.connected()) {
            p.add("로봇 연결 끊김");
            return p;
        }
        Long odom = s.ageMs().get("odom");
        if (odom == null || odom > 2000) {
            p.add("위치(odom) 수신 없음");
        }
        Long cam = s.ageMs().get("camera");
        if (cam == null || cam > 5000) {
            p.add("카메라 수신 없음");
        }
        if (Boolean.FALSE.equals(s.navReady())) {
            p.add("주행 시스템(Nav2) 준비 안 됨");
        } else if (Boolean.FALSE.equals(s.localized())) {
            p.add("위치 추정 안 됨");
        }
        return p;
    }

    private RobotAdapter.GoalStatus goTo(Running run, RobotAdapter a, String goalId, Waypoint wp) throws Exception {
        CompletableFuture<RobotAdapter.GoalStatus> done = new CompletableFuture<>();
        run.waits.put(goalId, done);
        run.currentGoal = goalId;
        long start = System.currentTimeMillis();
        try {
            a.sendGoal(goalId, wp.x(), wp.y(), wp.yaw());
            // 목표 메시지가 유실될 수 있으므로 ACTIVE 응답이 올 때까지 같은 목표를 다시 보낸다.
            // 로봇 측은 같은 goalId 를 새 목표로 취급하지 않는다.
            while (true) {
                try {
                    return done.get(3, TimeUnit.SECONDS);
                } catch (TimeoutException te) {
                    if (System.currentTimeMillis() - start > GOAL_TIMEOUT_MS) {
                        a.cancelGoal(goalId);
                        return new RobotAdapter.GoalStatus(goalId, "ABORTED", "시간 초과", "TIMEOUT", false, 0);
                    }
                    if (!run.activeSeen.containsKey(goalId)) {
                        a.sendGoal(goalId, wp.x(), wp.y(), wp.yaw());
                    }
                }
            }
        } finally {
            run.waits.remove(goalId);
            run.currentGoal = null;
        }
    }

    // ------------------------------------------------------------- 지도에서 찍은 목적지로 이동 (제어권 필요)
    public Map<String, Object> goTo(long robotId, long userId, double x, double y, double yaw) {
        if (runningByRobot.containsKey(robotId)) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, "점검 작업 중에는 지도 이동을 할 수 없습니다");
        }
        if (!control.isHolder(robotId, userId)) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, "제어권을 먼저 획득하세요");
        }
        cancelManual(robotId);
        String goalId = "manual-" + System.currentTimeMillis();
        Map<String, Object> g = new java.util.HashMap<>(Map.of("goalId", goalId, "x", x, "y", y, "yaw", yaw,
                "state", "SENT", "reason", ""));
        manualGoals.put(robotId, g);
        registry.adapter(robotId).sendGoal(goalId, x, y, yaw);
        control.touch(robotId, userId);
        return g;
    }

    public void cancelManual(long robotId) {
        Map<String, Object> g = manualGoals.get(robotId);
        if (g != null && Set.of("SENT", "ACTIVE").contains(String.valueOf(g.get("state")))) {
            try {
                registry.adapter(robotId).cancelGoal(String.valueOf(g.get("goalId")));
            } catch (Exception ignored) {
                // 연결이 끊긴 경우
            }
            g.put("state", "CANCELED");
        }
    }

    public Map<String, Object> manualGoal(long robotId) {
        return manualGoals.get(robotId);
    }

    private void onGoalStatus(long robotId, RobotAdapter.GoalStatus s) {
        if (s.goalId() != null && s.goalId().startsWith("manual-")) {
            Map<String, Object> g = manualGoals.get(robotId);
            if (g != null && s.goalId().equals(g.get("goalId"))) {
                g.put("state", s.state());
                g.put("reason", s.reason() == null ? "" : s.reason());
                g.put("code", s.code() == null ? "" : s.code());
            }
            return;
        }
        Running run = runningByRobot.get(robotId);
        if (run == null || s.goalId() == null) {
            return;
        }
        if ("ACTIVE".equals(s.state())) {
            run.activeSeen.put(s.goalId(), true);
            return;
        }
        var f = run.waits.get(s.goalId());
        if (f != null) {
            f.complete(s);
        }
    }

    // ------------------------------------------------------------- 보고
    private void event(long missionId, String type, Map<String, ?> detail) {
        ObjectNode p = om.createObjectNode().put("type", type).put("occurredAt", Instant.now().toString());
        p.set("detail", om.valueToTree(detail));
        repo.enqueue(missionId, "EVENT", p.toString(), null);
    }

    private void observation(long missionId, Waypoint wp, int seq, String status, String reasonCode, String reason,
                             RobotAdapter.Pose pose, byte[] image) {
        ObjectNode p = om.createObjectNode().put("pointId", wp.pointId()).put("seq", seq + 1).put("status", status)
                .put("capturedAt", Instant.now().toString());
        if (reason != null) {
            p.put("reason", reason);
        }
        if (reasonCode != null) {
            p.put("reasonCode", reasonCode);
        }
        if (pose != null) {
            p.put("poseX", pose.x()).put("poseY", pose.y()).put("poseYaw", pose.yaw());
        }
        repo.enqueue(missionId, "OBSERVATION", p.toString(), image);
    }

    public static List<Waypoint> parseWaypoints(JsonNode arr) {
        List<Waypoint> list = new ArrayList<>();
        arr.forEach(n -> list.add(new Waypoint(n.path("pointId").asLong(), n.path("code").asText(""),
                n.path("x").asDouble(), n.path("y").asDouble(), n.path("yaw").asDouble())));
        return list;
    }
}
