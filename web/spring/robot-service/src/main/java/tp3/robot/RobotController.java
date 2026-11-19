package tp3.robot;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;
import org.springframework.web.servlet.mvc.method.annotation.StreamingResponseBody;
import tp3.common.CurrentUser;
import tp3.robot.adapter.RobotAdapter;

import java.io.InputStream;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

@RestController
public class RobotController {

    private final RobotRepository repo;
    private final RobotRegistry registry;
    private final ControlService control;
    private final MissionService missions;
    private final ObjectMapper om = new ObjectMapper();

    public RobotController(RobotRepository repo, RobotRegistry registry, ControlService control, MissionService missions) {
        this.repo = repo;
        this.registry = registry;
        this.control = control;
        this.missions = missions;
    }

    // ------------------------------------------------------------- 사용자 (역할 1·2·3, ADMIN)
    @GetMapping("/api/robots")
    public List<Map<String, Object>> list() {
        return repo.robots().stream().map(r -> summary(r, false)).toList();
    }

    @GetMapping("/api/robots/{id}/status")
    public Map<String, Object> status(@PathVariable long id) {
        var r = repo.robot(id).orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND));
        Map<String, Object> m = summary(r, false);
        RobotAdapter a = registry.adapterOrNull(id);
        if (a != null) {
            var s = a.state();
            m.put("pose", s.pose());
            m.put("batteryPercent", s.batteryPercent());
            m.put("frontObstacleM", s.frontObstacleM());
            m.put("ageMs", s.ageMs());
            m.put("capabilities", a.capabilities());
            m.put("mapPose", a.mapView().pose());
            var ls = a.actuatorState();
            m.put("launcher", ls == null ? null : Map.of("ready", ls.ready(), "remaining", ls.remaining() == null ? -1 : ls.remaining(), "fault", ls.fault()));
        }
        return m;
    }

    @GetMapping("/api/robots/{id}/snapshot")
    public ResponseEntity<byte[]> snapshot(@PathVariable long id) throws Exception {
        return ResponseEntity.ok().contentType(MediaType.IMAGE_JPEG).body(registry.adapter(id).snapshot());
    }

    /** MJPEG 영상 중계. 브라우저는 <img src> 로 연결한다. */
    @GetMapping("/api/robots/{id}/stream")
    public ResponseEntity<StreamingResponseBody> stream(@PathVariable long id) throws Exception {
        RobotAdapter.MjpegStream s = registry.adapter(id).openStream();
        StreamingResponseBody body = out -> {
            try (InputStream in = s.body()) {
                byte[] buf = new byte[16 * 1024];
                int n;
                while ((n = in.read(buf)) >= 0) {
                    out.write(buf, 0, n);
                    out.flush();
                }
            }
        };
        return ResponseEntity.ok().header("Content-Type", s.contentType()).header("Cache-Control", "no-store")
                .body(body);
    }

    // ------------------------------------------------------------- 지도 모드
    /** 지도 정보. 지도가 아직 없으면 404. */
    @GetMapping("/api/robots/{id}/map")
    public RobotAdapter.MapInfo mapInfo(@PathVariable long id) {
        RobotAdapter.MapInfo info = registry.adapter(id).mapInfo();
        if (info == null) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, "지도를 아직 받지 못했습니다");
        }
        return info;
    }

    @GetMapping("/api/robots/{id}/map.png")
    public ResponseEntity<byte[]> mapPng(@PathVariable long id) {
        byte[] png = registry.adapter(id).mapPng();
        if (png == null) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND);
        }
        return ResponseEntity.ok().contentType(MediaType.IMAGE_PNG).header("Cache-Control", "no-cache").body(png);
    }

    /** 지도 위 실시간 표시: 로봇 위치(지도 좌표), 라이다 점, 계획 경로, 제어기 방향(control), 지도 이동 목적지 상태. */
    @GetMapping("/api/robots/{id}/mapview")
    public Map<String, Object> mapView(@PathVariable long id) {
        RobotAdapter.MapView v = registry.adapter(id).mapView();
        Map<String, Object> m = new HashMap<>();
        m.put("pose", v.pose());
        m.put("scan", v.scan());
        m.put("path", v.path());
        m.put("control", v.control());
        m.put("manualGoal", missions.manualGoal(id));
        m.put("mission", missions.active(id));
        return m;
    }

    /** body: {"x":1.0,"y":2.0,"yaw":0.0} (지도 좌표, rad). 제어권을 가진 사용자만. */
    @PostMapping("/api/robots/{id}/goto")
    public Map<String, Object> goTo(@PathVariable long id, @RequestBody JsonNode b, HttpServletRequest req) {
        return missions.goTo(id, CurrentUser.from(req).id(), b.path("x").asDouble(), b.path("y").asDouble(),
                b.path("yaw").asDouble(0));
    }

    @PostMapping("/api/robots/{id}/goto/cancel")
    public Map<String, Object> cancelGoTo(@PathVariable long id) {
        missions.cancelManual(id);
        return Map.of("cancelled", true);
    }

    @PostMapping("/api/robots/{id}/control/acquire")
    public Map<String, Object> acquire(@PathVariable long id, HttpServletRequest req) {
        return control.acquire(id, CurrentUser.from(req)).view();
    }

    @PostMapping("/api/robots/{id}/control/release")
    public Map<String, Object> release(@PathVariable long id, HttpServletRequest req) {
        missions.cancelManual(id);
        control.release(id, CurrentUser.from(req));
        return Map.of("released", true);
    }

    /** 비상 정지는 모든 로그인 사용자가 쓸 수 있다. */
    @PostMapping({"/api/robots/{id}/estop", "/api/admin/robots/{id}/estop"})
    public Map<String, Object> estop(@PathVariable long id, HttpServletRequest req) {
        return missions.emergencyStop(id, CurrentUser.from(req).login());
    }

    // ------------------------------------------------------------- 관리자
    @GetMapping("/api/admin/robots")
    public List<Map<String, Object>> adminList() {
        return repo.robots().stream().map(r -> summary(r, true)).toList();
    }

    @PostMapping("/api/admin/robots")
    public Map<String, Object> create(@RequestBody JsonNode body) throws Exception {
        String type = validType(body.path("adapterType").asText());
        String code = body.path("code").asText();
        if (code.isBlank() || body.path("name").asText().isBlank()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "코드와 이름이 필요합니다");
        }
        long id = repo.insertRobot(code, body.path("name").asText(), type, configText(body),
                body.path("enabled").asBoolean(true));
        var r = repo.robot(id).orElseThrow();
        registry.load(r);
        return summary(r, true);
    }

    /** 연결 설정 변경 = 시뮬레이션 → 실제 로봇 교체 지점. 저장하면 어댑터를 다시 만든다. */
    @PutMapping("/api/admin/robots/{id}")
    public Map<String, Object> update(@PathVariable long id, @RequestBody JsonNode body) throws Exception {
        var cur = repo.robot(id).orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND));
        if (missions.active(id) != null) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, "점검 작업 중에는 설정을 바꿀 수 없습니다");
        }
        repo.updateRobot(id, body.path("name").asText(cur.name()),
                validType(body.path("adapterType").asText(cur.adapterType())),
                body.has("config") ? configText(body) : cur.config(), body.path("enabled").asBoolean(cur.enabled()));
        control.clear(id);
        var r = repo.robot(id).orElseThrow();
        registry.load(r);
        return summary(r, true);
    }

    @PostMapping("/api/admin/robots/{id}/revoke-control")
    public Map<String, Object> revoke(@PathVariable long id) {
        missions.cancelManual(id);
        var prev = control.revoke(id);
        return Map.of("revoked", prev != null && "USER".equals(prev.kind()),
                "from", prev == null ? "" : prev.login());
    }

    private String configText(JsonNode body) throws Exception {
        JsonNode c = body.path("config");
        if (c.isTextual()) {
            c = om.readTree(c.asText());
        }
        if (!c.isObject()) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "config 는 JSON 객체여야 합니다");
        }
        return c.toString();
    }

    private static String validType(String t) {
        if (!Set.of("ROSBRIDGE", "MOCK").contains(t)) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "adapterType 은 ROSBRIDGE 또는 MOCK");
        }
        return t;
    }

    Map<String, Object> summary(RobotRepository.Robot r, boolean withConfig) {
        Map<String, Object> m = new HashMap<>();
        m.put("robotId", r.robotId());
        m.put("code", r.code());
        m.put("name", r.name());
        m.put("adapterType", r.adapterType());
        m.put("enabled", r.enabled());
        RobotAdapter a = registry.adapterOrNull(r.robotId());
        m.put("connected", a != null && a.state().connected());
        var lease = control.holder(r.robotId());
        m.put("control", lease == null ? null : lease.view());
        m.put("mission", missions.active(r.robotId()));
        if (withConfig) {
            try {
                m.put("config", om.readTree(r.config()));
            } catch (Exception e) {
                m.put("config", r.config());
            }
        }
        return m;
    }
}
