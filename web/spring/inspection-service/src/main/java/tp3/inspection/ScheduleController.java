package tp3.inspection;

import com.fasterxml.jackson.databind.JsonNode;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;
import tp3.common.CurrentUser;

import java.sql.Timestamp;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * 예약 점검 API. 게이트웨이의 기존 /api/inspections/** 경로를 그대로 쓴다
 * (/api/inspections/{id} 보다 글자 그대로인 schedules 경로가 먼저 맞는다).
 */
@RestController
public class ScheduleController {

    private final ScheduleService service;
    private final ScheduleStore store;

    public ScheduleController(ScheduleService service, ScheduleStore store) {
        this.service = service;
        this.store = store;
    }

    @GetMapping("/api/inspections/schedules")
    public Map<String, Object> list() {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("zone", service.zone().getId());
        m.put("schedules", store.list().stream().map(this::withLocal).toList());
        return m;
    }

    /** 지연(실행 버퍼에서 대기) 중인 회차. 화면 상단 지연 안내가 주기적으로 읽는다. */
    @GetMapping("/api/inspections/schedules/pending")
    public List<Map<String, Object>> pending() {
        return service.pending();
    }

    /** 로봇별 밀린 예약: 지금 하는 작업 + 버퍼에 쌓인 회차(순서·지연). 화면 상단 안내용. */
    @GetMapping("/api/inspections/schedules/backlog")
    public Map<String, Object> backlog() {
        return service.backlog();
    }

    @DeleteMapping("/api/inspections/schedules/pending/{key}")
    public ResponseEntity<Void> cancelPending(@PathVariable long key, HttpServletRequest req) {
        service.cancelPending(key, CurrentUser.from(req));
        return ResponseEntity.noContent().build();
    }

    @GetMapping("/api/inspections/schedules/{id}")
    public Map<String, Object> get(@PathVariable long id) {
        var s = store.get(id).orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND));
        Map<String, Object> m = withLocal(s);
        m.put("runs", store.runs(id, 50));
        return m;
    }

    @PostMapping("/api/inspections/schedules")
    public ResponseEntity<Map<String, Object>> create(@RequestBody JsonNode b, HttpServletRequest req) {
        return ResponseEntity.status(HttpStatus.CREATED).body(withLocal(service.create(b, CurrentUser.from(req))));
    }

    @PutMapping("/api/inspections/schedules/{id}")
    public Map<String, Object> update(@PathVariable long id, @RequestBody JsonNode b, HttpServletRequest req) {
        return withLocal(service.update(id, b, CurrentUser.from(req)));
    }

    /** body: {"enabled": true|false} */
    @PostMapping("/api/inspections/schedules/{id}/enabled")
    public Map<String, Object> enabled(@PathVariable long id, @RequestBody JsonNode b, HttpServletRequest req) {
        return withLocal(service.setEnabled(id, b.path("enabled").asBoolean(), CurrentUser.from(req)));
    }

    @PostMapping("/api/inspections/schedules/{id}/run")
    public Map<String, Object> runNow(@PathVariable long id, HttpServletRequest req) {
        return service.runNow(id, CurrentUser.from(req));
    }

    @DeleteMapping("/api/inspections/schedules/{id}")
    public ResponseEntity<Void> delete(@PathVariable long id, HttpServletRequest req) {
        service.delete(id, CurrentUser.from(req));
        return ResponseEntity.noContent().build();
    }

    /** 일회 실행 일시를 예약 기준 시간대의 'YYYY-MM-DDTHH:mm' 로도 내보낸다(수정 화면 입력값). */
    private Map<String, Object> withLocal(Map<String, Object> s) {
        Map<String, Object> m = new LinkedHashMap<>(s);
        if (s.get("run_at") instanceof Timestamp t) {
            m.put("run_at_local", t.toInstant().atZone(service.zone()).toLocalDateTime().toString().substring(0, 16));
        } else {
            m.put("run_at_local", null);
        }
        return m;
    }
}
