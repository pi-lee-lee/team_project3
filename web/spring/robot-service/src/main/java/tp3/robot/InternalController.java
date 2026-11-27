package tp3.robot;

import com.fasterxml.jackson.databind.JsonNode;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

/** 내부망 전용: inspection-service 와 gateway 가 호출한다. */
@RestController
@RequestMapping("/internal")
public class InternalController {

    private final MissionService missions;
    private final RobotController robots;
    private final RobotRepository repo;
    private final RobotRegistry registry;
    private final ActuatorService actuators;
    private final SimService sim;

    public InternalController(MissionService missions, RobotController robots, RobotRepository repo,
                              RobotRegistry registry, ActuatorService actuators, SimService sim) {
        this.actuators = actuators;
        this.sim = sim;
        this.missions = missions;
        this.robots = robots;
        this.repo = repo;
        this.registry = registry;
    }

    /** body: {"missionId": 12, "robotId": 1, "waypoints": [{"pointId":1,"code":"P1","x":1.0,"y":0.0,"yaw":0.0}]} */
    @PostMapping("/missions")
    public Map<String, Object> submit(@RequestBody JsonNode body) {
        return missions.submit(body.path("missionId").asLong(), body.path("robotId").asLong(),
                body.path("kind").asText("INSPECTION"), MissionService.parseWaypoints(body.path("waypoints")));
    }

    @PostMapping("/missions/{id}/cancel")
    public Map<String, Object> cancel(@PathVariable long id, @RequestBody(required = false) Map<String, String> body) {
        return missions.cancel(id, body == null ? "사용자 취소" : body.getOrDefault("reason", "사용자 취소"));
    }

    /** HOLDING 중인 출동 미션을 끝낸다. body: {"result": "COMPLETED"|"FAILED", "reason": "..."} */
    @PostMapping("/missions/{id}/finish")
    public Map<String, Object> finish(@PathVariable long id, @RequestBody JsonNode body) {
        return missions.finish(id, body.path("result").asText("COMPLETED"), body.path("reason").asText(""));
    }

    /**
     * 시뮬레이션 전용: 시뮬레이션 도구를 실행하고 끝날 때까지 기다린다. body: {"tool": "fire"|"target", "args": [...]}
     * → {"ok", "code", "output"}
     */
    @PostMapping("/robots/{id}/sim")
    public Map<String, Object> simCommand(@PathVariable long id, @RequestBody JsonNode body) {
        java.util.List<String> args = new java.util.ArrayList<>();
        body.path("args").forEach(a -> args.add(a.asText()));
        return sim.run(id, body.path("tool").asText(), args);
    }

    /** 조준 보정: 대기 중인 출동 로봇을 제자리에서 돌린다. body: {"deltaDeg": 9.6} (+ = 왼쪽으로) */
    @PostMapping("/missions/{id}/aim")
    public Map<String, Object> aim(@PathVariable long id, @RequestBody JsonNode body) {
        return missions.aim(id, Math.toRadians(body.path("deltaDeg").asDouble()));
    }

    /** 투척 명령. body: {"commandId", "kind": "LAUNCH", "count": 1, "params": {}} — 결과는 미션의 사건 기록으로 간다. */
    @PostMapping("/robots/{id}/actuate")
    public Map<String, Object> actuate(@PathVariable long id, @RequestBody JsonNode body) {
        return actuators.actuate(id, body.path("commandId").asText(), body.path("kind").asText("LAUNCH"),
                Math.max(1, body.path("count").asInt(1)), body.path("params").isObject() ? body.path("params").toString() : "{}");
    }

    /** 지금 사진 + 그 순간의 지도 위 위치(헤더 X-Pose: "x,y,yaw"). 위치를 모르면 헤더가 없다. */
    @GetMapping("/robots/{id}/snapshot")
    public org.springframework.http.ResponseEntity<byte[]> snapshot(@PathVariable long id) throws Exception {
        var a = registry.adapter(id);
        var pose = a.mapView().pose();
        byte[] img = a.snapshot();
        var b = org.springframework.http.ResponseEntity.ok().contentType(org.springframework.http.MediaType.IMAGE_JPEG);
        if (pose != null) {
            b.header("X-Pose", pose.x() + "," + pose.y() + "," + pose.yaw());
        }
        return b.body(img);
    }

    /** 투척 위치 후보. body: {"targetX", "targetY", "rangeM", "toleranceM", "max"} */
    @PostMapping("/robots/{id}/standoff")
    public Map<String, Object> standoff(@PathVariable long id, @RequestBody JsonNode b) {
        var a = registry.adapter(id);
        var grid = a.grid();
        if (grid == null) {
            throw new org.springframework.web.server.ResponseStatusException(org.springframework.http.HttpStatus.CONFLICT,
                    "지도를 아직 받지 못했습니다");
        }
        return Map.of("candidates", Standoff.candidates(grid, a.mapView().pose(), b.path("targetX").asDouble(),
                b.path("targetY").asDouble(), b.path("rangeM").asDouble(1.0), b.path("toleranceM").asDouble(0.2),
                Math.max(1, b.path("max").asInt(8))));
    }

    /**
     * 지도 위 한 점에서 한 방향으로 처음 만나는 벽 · 설비의 자리. body: {"x", "y", "angleRad", "maxM"}
     * → {"hit": {"x", "y", "distanceM"} 또는 null}. 순찰 감시(inspection-service PatrolWatchService)가 쓴다.
     */
    @PostMapping("/robots/{id}/raycast")
    public Map<String, Object> raycast(@PathVariable long id, @RequestBody JsonNode b) {
        var grid = registry.adapter(id).grid();
        if (grid == null) {
            throw new org.springframework.web.server.ResponseStatusException(org.springframework.http.HttpStatus.CONFLICT,
                    "지도를 아직 받지 못했습니다");
        }
        Map<String, Object> out = new HashMap<>();
        out.put("hit", Standoff.ray(grid, b.path("x").asDouble(), b.path("y").asDouble(), b.path("angleRad").asDouble(),
                b.path("maxM").asDouble(6.0)));
        return out;
    }

    @GetMapping("/robots/{id}")
    public Map<String, Object> robot(@PathVariable long id) {
        return robots.status(id);
    }

    /** 로봇 목록(연결 · 임무 상태 포함). 화재 출동에 보낼 로봇을 고를 때 쓴다. */
    @GetMapping("/robots")
    public List<Map<String, Object>> list() {
        return robots.list();
    }

    /** A6 시스템 상태용: 로봇별 연결·갱신 상태와 미전송 보고 수. */
    @GetMapping("/robots/status")
    public List<Map<String, Object>> status() {
        var stats = repo.outboxStats();
        return repo.robots().stream().map(r -> {
            Map<String, Object> m = new HashMap<>();
            m.put("code", r.code());
            m.put("enabled", r.enabled());
            var a = registry.adapterOrNull(r.robotId());
            m.put("connected", a != null && a.state().connected());
            m.put("ageMs", a == null ? Map.of() : a.state().ageMs());
            m.put("outboxPending", stats.get("pending"));
            return m;
        }).toList();
    }
}
