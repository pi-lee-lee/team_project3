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

    public InternalController(MissionService missions, RobotController robots, RobotRepository repo,
                              RobotRegistry registry) {
        this.missions = missions;
        this.robots = robots;
        this.repo = repo;
        this.registry = registry;
    }

    /** body: {"missionId": 12, "robotId": 1, "waypoints": [{"pointId":1,"code":"P1","x":1.0,"y":0.0,"yaw":0.0}]} */
    @PostMapping("/missions")
    public Map<String, Object> submit(@RequestBody JsonNode body) {
        return missions.submit(body.path("missionId").asLong(), body.path("robotId").asLong(),
                MissionService.parseWaypoints(body.path("waypoints")));
    }

    @PostMapping("/missions/{id}/cancel")
    public Map<String, Object> cancel(@PathVariable long id, @RequestBody(required = false) Map<String, String> body) {
        return missions.cancel(id, body == null ? "사용자 취소" : body.getOrDefault("reason", "사용자 취소"));
    }

    @GetMapping("/robots/{id}")
    public Map<String, Object> robot(@PathVariable long id) {
        return robots.status(id);
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
