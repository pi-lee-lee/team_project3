package tp3.user;

import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

import java.util.Map;

/** 내부망 전용(게이트웨이가 /internal 경로를 외부로 열지 않는다). */
@RestController
@RequestMapping("/internal")
public class InternalController {

    public record AuditEvent(Long userId, String loginId, String role, String action, String target, Integer status) {
    }

    private final UserRepository users;

    public InternalController(UserRepository users) {
        this.users = users;
    }

    /** 게이트웨이가 토큰 검증 때 조회한다: 정지·세션 종료를 반영하기 위해. */
    @GetMapping("/users/{id}/session")
    public Map<String, Object> session(@PathVariable long id) {
        var u = users.findById(id).orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND));
        return Map.of("tokenVersion", u.tokenVersion(), "status", u.status(), "role", u.roleCode());
    }

    @PostMapping("/audit")
    @ResponseStatus(HttpStatus.ACCEPTED)
    public void audit(@RequestBody AuditEvent e) {
        users.audit(e.userId(), e.loginId(), e.role(), e.action(), e.target(), e.status(), null);
    }
}
