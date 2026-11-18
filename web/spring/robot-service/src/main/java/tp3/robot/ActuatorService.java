package tp3.robot;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;
import tp3.robot.adapter.RobotAdapter;

import java.util.LinkedHashMap;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;

/**
 * 투척 명령(INTERFACES.md 2.2 · 4.1). 쏠지 말지는 inspection-service 가 정하고, 여기서는 명령을 한 번만 전달한다.
 * - 같은 commandId 가 다시 오면 보내지 않고 지난 상태를 돌려준다(actuator_command 표).
 * - 로봇이 받았다고 답할 때까지 2초마다 다시 보낸다(로봇 쪽도 같은 ID 는 한 번만 실행한다). 20초 안에 끝나지 않으면 TIMEOUT.
 * - 결과는 그 로봇이 하고 있는 미션의 사건 기록(ACTUATED / ACTUATE_FAILED)으로 보고한다.
 */
@Service
public class ActuatorService {

    private static final Logger log = LoggerFactory.getLogger(ActuatorService.class);
    private static final long TIMEOUT_MS = 20_000;

    private record Pending(String commandId, long robotId, Long missionId, String kind, int count, String params,
                           long startedAt) {
    }

    private final RobotRepository repo;
    private final RobotRegistry registry;
    private final MissionService missions;
    private final ObjectMapper om = new ObjectMapper();
    private final Map<String, Pending> pending = new ConcurrentHashMap<>();
    private final Map<String, Boolean> accepted = new ConcurrentHashMap<>();
    private final ScheduledExecutorService sched = Executors.newSingleThreadScheduledExecutor(r -> {
        Thread t = new Thread(r, "actuator");
        t.setDaemon(true);
        return t;
    });

    public ActuatorService(RobotRepository repo, RobotRegistry registry, MissionService missions) {
        this.repo = repo;
        this.registry = registry;
        this.missions = missions;
        registry.setActuatorListener(this::onStatus);
        sched.scheduleWithFixedDelay(this::watch, 2, 2, TimeUnit.SECONDS);
    }

    public Map<String, Object> actuate(long robotId, String commandId, String kind, int count, String params) {
        if (commandId == null || commandId.isBlank()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "commandId 가 필요합니다");
        }
        var old = repo.actuatorCommand(commandId).orElse(null);
        if (old != null) {
            return Map.of("accepted", true, "duplicate", true, "state", old.get("state"));
        }
        RobotAdapter a = registry.adapter(robotId);
        RobotAdapter.ActuatorState st = a.actuatorState();
        if (st == null) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, "UNSUPPORTED: 투척 기구가 없거나 응답하지 않습니다");
        }
        if (!st.ready()) {
            throw new ResponseStatusException(HttpStatus.CONFLICT,
                    "NOT_READY: 투척 기구가 준비되지 않았습니다" + (st.fault().isBlank() ? "" : " (" + st.fault() + ")"));
        }
        Long missionId = missions.activeMissionId(robotId);
        Map<String, Object> req = new LinkedHashMap<>();
        req.put("kind", kind);
        req.put("count", count);
        req.put("params", params);
        if (!repo.insertActuatorCommand(commandId, robotId, missionId, kind, json(req))) {
            return Map.of("accepted", true, "duplicate", true);
        }
        pending.put(commandId, new Pending(commandId, robotId, missionId, kind, count, params, System.currentTimeMillis()));
        a.actuate(commandId, kind, count, params);
        return Map.of("accepted", true, "duplicate", false, "state", "SENT");
    }

    private void onStatus(long robotId, RobotAdapter.ActuatorStatus s) {
        Pending p = pending.get(s.commandId());
        if (p == null) {
            return;   // 모르는 명령이거나 이미 끝난 명령의 재전송
        }
        if ("ACCEPTED".equals(s.state())) {
            accepted.put(s.commandId(), true);
            repo.actuatorState(s.commandId(), "ACCEPTED", null);
            return;
        }
        if ("DONE".equals(s.state()) || "FAILED".equals(s.state())) {
            finish(p, "DONE".equals(s.state()), s.code(), s.reason(), s.launched());
        }
    }

    private void watch() {
        long now = System.currentTimeMillis();
        for (Pending p : pending.values()) {
            try {
                if (now - p.startedAt() > TIMEOUT_MS) {
                    finish(p, false, "TIMEOUT", "투척 기구가 시간 안에 응답하지 않았습니다", 0);
                } else if (!accepted.containsKey(p.commandId())) {
                    registry.adapter(p.robotId()).actuate(p.commandId(), p.kind(), p.count(), p.params());
                }
            } catch (Exception e) {
                log.debug("actuator watch {}: {}", p.commandId(), e.toString());
            }
        }
    }

    private void finish(Pending p, boolean ok, String code, String reason, int launched) {
        if (pending.remove(p.commandId()) == null) {
            return;
        }
        accepted.remove(p.commandId());
        Map<String, Object> d = new LinkedHashMap<>();
        d.put("commandId", p.commandId());
        d.put("launched", launched);
        d.put("code", code == null ? "" : code);
        d.put("reason", reason == null ? "" : reason);
        if (!repo.actuatorState(p.commandId(), ok ? "DONE" : "FAILED", json(d))) {
            return;
        }
        if (p.missionId() != null) {
            missions.report(p.missionId(), ok ? "ACTUATED" : "ACTUATE_FAILED", d);
        }
        log.info("투척 명령 {} → {} {}", p.commandId(), ok ? "DONE" : "FAILED", code);
    }

    private String json(Object o) {
        try {
            return om.writeValueAsString(o);
        } catch (Exception e) {
            return "{}";
        }
    }
}
