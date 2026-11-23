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

    /** action: CAPTURE(도착해 촬영, 기본) / HOLD(출동: 도착만 알리고 기다린다)
     *  exitZone: 비상구 점검 지점의 비상구 앞 구역 [x1, y1, x2, y2](없으면 null). 로봇이 이 안에서 막히면 복구 없이 바로 진입 불가. */
    public record Waypoint(long pointId, String code, double x, double y, double yaw, String action, double[] exitZone) {
        public Waypoint(long pointId, String code, double x, double y, double yaw, String action) {
            this(pointId, code, x, y, yaw, action, null);
        }
    }

    private static final class Running {
        final long missionId;
        final long robotId;
        volatile boolean cancelRequested;
        volatile String cancelReason;
        volatile String currentGoal;
        volatile Long currentPoint;
        volatile boolean holding;
        /** 출동 미션을 끝내라는 신호: [결과(COMPLETED/FAILED), 사유] */
        final CompletableFuture<String[]> finish = new CompletableFuture<>();
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
    public synchronized Map<String, Object> submit(long missionId, long robotId, String kind, List<Waypoint> waypoints) {
        boolean response = "RESPONSE".equals(kind);
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
        if (response) {
            cancelManual(robotId);
            control.revoke(robotId);      // 화재 출동은 사용자 조종보다 먼저다
        }
        if (!control.takeForMission(robotId)) {
            var h = control.holder(robotId);
            throw new ResponseStatusException(HttpStatus.CONFLICT, (h == null ? "다른 사용자" : h.login()) + " 님이 조종 중입니다");
        }
        try {
            repo.insertMission(missionId, robotId, om.writeValueAsString(waypoints), response ? "RESPONSE" : "INSPECTION");
        } catch (Exception e) {
            control.releaseMission(robotId);
            throw new IllegalStateException(e);
        }
        Running run = new Running(missionId, robotId);
        runningByRobot.put(robotId, run);
        event(missionId, "ACCEPTED", Map.of("robotId", robotId, "points", waypoints.size()));
        if (response) {
            pool.submit(() -> executeResponse(run, adapter, waypoints));
        } else {
            pool.submit(() -> execute(run, adapter, waypoints));
        }
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
        run.finish.complete(new String[]{"CANCELLED", reason});
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
        m.put("holding", run.holding);
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
                    // 진입 불가(통로 막힘)는 로봇이 막힌 곳 가까이 가서 알게 되므로 그 자리 사진을 근거로 함께 올린다.
                    // 복구 동작(후진 · 회전) 뒤라 로봇이 아무 쪽이나 보고 멈춰 있으므로, 제자리에서 목적지 쪽으로만 돌린 뒤 찍는다
                    // (막은 물건은 로봇과 목적지 사이에 있다). 관제가 사진을 보고 판단한다.
                    byte[] evidence = null;
                    if (blocked) {
                        faceToward(a, wp.x(), wp.y());
                        Thread.sleep(1500);   // 정지 후 영상 안정화
                        evidence = snapshotOrNull(a);
                    }
                    observation(id, wp, i, "UNABLE", code, why, a.state().pose(), evidence);
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

    /**
     * 화재 출동: 투척 위치 후보(가까운 순)를 차례로 시도해 도착하면 HOLDING 으로 기다린다.
     * 기다리는 동안 inspection-service 가 사진을 받아 판독하고 투척을 명령한다. finish()·cancel() 이 오면 끝낸다.
     */
    private void executeResponse(Running run, RobotAdapter a, List<Waypoint> wps) {
        long id = run.missionId;
        String finalState = "FAILED";
        String finalReason = null;
        try {
            repo.missionState(id, "RUNNING", null);
            List<String> problems = preflight(a);
            if (!problems.isEmpty()) {
                event(id, "PREFLIGHT_FAILED", Map.of("reasons", problems));
                finalReason = "출발 전 검사 실패: " + String.join(", ", problems);
                return;
            }
            event(id, "PREFLIGHT_OK", Map.of());
            event(id, "STARTED", Map.of("kind", "RESPONSE"));
            Waypoint arrived = null;
            boolean lastWasCancel = false;
            for (int i = 0; i < wps.size() && arrived == null && !run.cancelRequested; i++) {
                Waypoint wp = wps.get(i);
                event(id, "MOVING", Map.of("code", wp.code(), "seq", i + 1, "x", wp.x(), "y", wp.y()));
                RobotAdapter.GoalStatus result = goTo(run, a, id + "-r" + (i + 1), wp);
                if (run.cancelRequested || "CANCELED".equals(result.state())) {
                    lastWasCancel = !run.cancelRequested;
                    break;
                }
                if ("SUCCEEDED".equals(result.state())) {
                    arrived = wp;
                } else {
                    String code = result.code() == null || result.code().isBlank() ? "NAV_FAILED" : result.code();
                    event(id, "BLOCKED_NO_PATH".equals(code) ? "ARRIVAL_BLOCKED" : "ARRIVAL_FAILED",
                            Map.of("code", wp.code(), "reasonCode", code,
                                    "reason", "투척 위치 " + (i + 1) + " 에 갈 수 없음: " + result.reason()));
                }
            }
            if (run.cancelRequested) {
                finalState = "CANCELLED";
                finalReason = run.cancelReason;
                event(id, "CANCELLED", Map.of("reason", String.valueOf(run.cancelReason)));
                return;
            }
            if (arrived == null) {
                finalReason = lastWasCancel ? "이동 목표가 밖에서 취소되었습니다(다른 쪽에서 로봇에 정지 · 취소를 보냄)"
                        : "투척 위치에 갈 수 없습니다(후보 " + wps.size() + "곳)";
                return;
            }
            Thread.sleep(1500);   // 정지 후 영상 안정화
            run.holding = true;
            repo.missionState(id, "HOLDING", null);
            event(id, "HOLDING", Map.of("x", arrived.x(), "y", arrived.y(), "yaw", arrived.yaw(), "code", arrived.code()));
            String[] fin = run.finish.get();     // inspection-service 가 끝내라고 할 때까지
            if ("CANCELLED".equals(fin[0])) {
                finalState = "CANCELLED";
                finalReason = fin[1];
                event(id, "CANCELLED", Map.of("reason", String.valueOf(fin[1])));
            } else if ("COMPLETED".equals(fin[0])) {
                finalState = "COMPLETED";
                event(id, "COMPLETED", Map.of("reason", String.valueOf(fin[1])));
            } else {
                finalReason = fin[1];
            }
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            finalReason = "interrupted";
        } catch (Exception e) {
            log.warn("response mission {} failed", id, e);
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

    /** HOLDING 중인 출동 미션을 끝낸다. result: COMPLETED / FAILED. */
    public Map<String, Object> finish(long missionId, String result, String reason) {
        var m = repo.mission(missionId).orElse(null);
        Running run = m == null ? null : runningByRobot.get(m.robotId());
        if (run == null || run.missionId != missionId) {
            return Map.of("applied", false, "state", m == null ? "UNKNOWN" : m.state());
        }
        if (!run.holding) {
            // 아직 투척 위치로 가는 중이다: 사건이 닫혔으므로 이동을 멈춘다(취소와 같은 경로)
            return cancel(missionId, reason);
        }
        run.finish.complete(new String[]{"COMPLETED".equals(result) ? "COMPLETED" : "FAILED", reason});
        return Map.of("applied", true);
    }

    /**
     * 조준 보정: 투척 위치에서 기다리는(HOLDING) 로봇을 제자리에서 deltaRad 만큼 돌린다(+ = 반시계).
     * Nav2 의 도착 방향 허용 오차(0.15rad)보다 작은 보정이라 목표로 보내지 않고, 회전 명령을 직접 내며
     * 오도메트리의 방향이 그만큼 바뀔 때까지 돈다(최대 8초). 실제로 돈 각도를 돌려준다.
     */
    public Map<String, Object> aim(long missionId, double deltaRad) {
        var m = repo.mission(missionId).orElse(null);
        Running run = m == null ? null : runningByRobot.get(m.robotId());
        if (run == null || run.missionId != missionId || !run.holding) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, "투척 위치에서 대기 중인 미션이 아닙니다");
        }
        RobotAdapter a = registry.adapter(run.robotId);
        var start = a.state().pose();
        if (start == null) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, "로봇 방향(odom)을 알 수 없습니다");
        }
        double target = Math.max(-0.6, Math.min(0.6, deltaRad));       // 한 번에 최대 약 34°
        double turned = 0;
        long end = System.currentTimeMillis() + 8000;
        try {
            while (System.currentTimeMillis() < end && !run.cancelRequested) {
                var p = a.state().pose();
                turned = Math.atan2(Math.sin(p.yaw() - start.yaw()), Math.cos(p.yaw() - start.yaw()));
                double left = target - turned;
                if (Math.abs(left) < 0.02) {
                    break;
                }
                a.teleop(0, Math.signum(left) * Math.max(0.12, Math.min(0.4, Math.abs(left) * 1.5)));
                Thread.sleep(100);
            }
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        } finally {
            a.teleop(0, 0);
        }
        return Map.of("requestedRad", target, "turnedRad", Math.round(turned * 1000) / 1000.0);
    }

    /** 로봇이 지금 하는 미션 ID(없으면 null). 투척 결과를 그 미션의 사건 기록으로 보낼 때 쓴다. */
    public Long activeMissionId(long robotId) {
        Running run = runningByRobot.get(robotId);
        return run == null ? null : run.missionId;
    }

    /** 미션의 사건 기록을 보고한다(outbox 경유). */
    public void report(long missionId, String type, Map<String, ?> detail) {
        event(missionId, type, detail);
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
            a.sendGoal(goalId, wp.x(), wp.y(), wp.yaw(), wp.exitZone());
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
                        a.sendGoal(goalId, wp.x(), wp.y(), wp.yaw(), wp.exitZone());
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

    /**
     * 제자리에서 (tx, ty) 쪽을 보도록 돈다(전진 없음). 원격 조종과 같은 속도 명령(/cmd_vel_teleop)을 쓰고, 끝나면 반드시 정지 명령을 보낸다.
     * 막힌 직후에는 Nav2 의 복구 동작(제자리 회전 등)이 취소와 엇갈려 몇 초 더 돌 수 있다 → 그 명령과 섞이지 않게
     * 먼저 로봇이 멈출 때까지(방향이 STILL_MS 동안 그대로) 기다린 뒤 돌고, 돈 뒤 잠깐 기다려 방향이 맞는지 다시 본다(최대 3번).
     * 위치를 모르거나 명령을 못 보내면 그대로 둔다(사진은 그 방향 그대로 찍힌다).
     */
    private static void faceToward(RobotAdapter a, double tx, double ty) throws InterruptedException {
        final long STILL_MS = 800;
        try {
            for (int round = 0; round < 3; round++) {
                waitStill(a, STILL_MS, 5000);
                if (Math.abs(headingError(a, tx, ty)) < 0.1) {
                    return;
                }
                long end = System.currentTimeMillis() + 8000;
                while (System.currentTimeMillis() < end) {
                    double err = headingError(a, tx, ty);
                    if (Double.isNaN(err)) {
                        return;
                    }
                    if (Math.abs(err) < 0.08) {
                        break;
                    }
                    a.teleop(0, Math.copySign(Math.max(0.2, Math.min(0.6, Math.abs(err))), err));
                    Thread.sleep(100);
                }
                a.teleop(0, 0);
            }
        } catch (InterruptedException e) {
            throw e;
        } catch (Exception e) {
            log.warn("목적지 쪽으로 돌지 못함: {}", e.getMessage());
        } finally {
            try {
                a.teleop(0, 0);
            } catch (Exception ignored) {
                // 연결이 끊긴 경우 로봇 측 워치독이 정지시킨다
            }
        }
    }

    /** (tx, ty) 쪽과 지금 방향의 차(rad, -π ~ π). 위치를 모르면 NaN. */
    private static double headingError(RobotAdapter a, double tx, double ty) {
        RobotAdapter.Pose p = a.state().pose();
        if (p == null) {
            return Double.NaN;
        }
        double err = Math.atan2(ty - p.y(), tx - p.x()) - p.yaw();
        return Math.atan2(Math.sin(err), Math.cos(err));
    }

    /** 로봇 방향이 stillMs 동안 0.03rad 넘게 바뀌지 않을 때까지 기다린다(최대 maxMs). */
    private static void waitStill(RobotAdapter a, long stillMs, long maxMs) throws InterruptedException {
        long end = System.currentTimeMillis() + maxMs, since = System.currentTimeMillis();
        RobotAdapter.Pose last = a.state().pose();
        while (System.currentTimeMillis() < end) {
            Thread.sleep(150);
            RobotAdapter.Pose p = a.state().pose();
            if (p == null || last == null) {
                return;
            }
            double d = Math.atan2(Math.sin(p.yaw() - last.yaw()), Math.cos(p.yaw() - last.yaw()));
            if (Math.abs(d) > 0.03 || Math.hypot(p.x() - last.x(), p.y() - last.y()) > 0.02) {
                since = System.currentTimeMillis();
                last = p;
            } else if (System.currentTimeMillis() - since >= stillMs) {
                return;
            }
        }
    }

    /** 카메라 한 장(세 번까지 다시 시도). 끝내 못 찍으면 null — 근거 사진이 없을 뿐 관측은 그대로 올린다. */
    private static byte[] snapshotOrNull(RobotAdapter a) throws InterruptedException {
        for (int k = 0; k < 3; k++) {
            try {
                return a.snapshot();
            } catch (Exception e) {
                log.warn("근거 사진 촬영 실패({}회): {}", k + 1, e.getMessage());
                Thread.sleep(700);
            }
        }
        return null;
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
        arr.forEach(n -> {
            JsonNode z = n.path("exitZone");
            double[] zone = z.isArray() && z.size() == 4
                    ? new double[]{z.get(0).asDouble(), z.get(1).asDouble(), z.get(2).asDouble(), z.get(3).asDouble()} : null;
            list.add(new Waypoint(n.path("pointId").asLong(), n.path("code").asText(""),
                    n.path("x").asDouble(), n.path("y").asDouble(), n.path("yaw").asDouble(),
                    n.path("action").asText("CAPTURE"), zone));
        });
        return list;
    }
}
