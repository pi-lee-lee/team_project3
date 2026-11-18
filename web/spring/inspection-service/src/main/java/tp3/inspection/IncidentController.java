package tp3.inspection;

import com.fasterxml.jackson.databind.JsonNode;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import tp3.common.CurrentUser;

import java.util.List;
import java.util.Map;

/** 화면이 부르는 사건 API(A3). 역할 제한(수동 투척 · 조치 완료는 1 관리자 · 2 매니저)은 게이트웨이 규칙이 한다. */
@RestController
public class IncidentController {

    private final IncidentService incidents;

    public IncidentController(IncidentService incidents) {
        this.incidents = incidents;
    }

    @GetMapping("/api/incidents")
    public List<Map<String, Object>> list(@RequestParam(defaultValue = "all") String state,
                                          @RequestParam(defaultValue = "50") int limit) {
        return incidents.list("open".equalsIgnoreCase(state), limit);
    }

    @GetMapping("/api/incidents/{id}")
    public Map<String, Object> detail(@PathVariable long id) {
        return incidents.detail(id);
    }

    /** kind: detection(감지 사진) | recheck(도착 후) | after(투척 후) */
    @GetMapping("/api/incidents/{id}/image")
    public ResponseEntity<byte[]> image(@PathVariable long id, @RequestParam(defaultValue = "detection") String kind) {
        return ResponseEntity.ok().contentType(MediaType.IMAGE_JPEG).header("Cache-Control", "no-cache")
                .body(incidents.image(id, kind));
    }

    @PostMapping("/api/incidents/{id}/approve")
    public Map<String, Object> approve(@PathVariable long id, HttpServletRequest req) {
        return incidents.approve(id, CurrentUser.from(req));
    }

    @PostMapping("/api/incidents/{id}/launch")
    public Map<String, Object> launch(@PathVariable long id, HttpServletRequest req) {
        return incidents.manualLaunch(id, CurrentUser.from(req));
    }

    @PostMapping("/api/incidents/{id}/dismiss")
    public Map<String, Object> dismiss(@PathVariable long id, @RequestBody(required = false) JsonNode b,
                                       HttpServletRequest req) {
        return incidents.closeByUser(id, "DISMISSED", CurrentUser.from(req), b == null ? null : b.path("comment").asText(null));
    }

    @PostMapping("/api/incidents/{id}/resolve")
    public Map<String, Object> resolve(@PathVariable long id, @RequestBody(required = false) JsonNode b,
                                       HttpServletRequest req) {
        return incidents.closeByUser(id, "RESOLVED", CurrentUser.from(req), b == null ? null : b.path("comment").asText(null));
    }
}
