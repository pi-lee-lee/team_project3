package tp3.user;

import jakarta.validation.Valid;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.http.HttpStatus;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

import java.util.List;
import java.util.Map;

/** 웹사이트 admin 전용. 게이트웨이가 /api/admin/** 을 ADMIN 역할로 제한한다. */
@RestController
@RequestMapping("/api/admin")
public class AdminController {

    public record CreateUser(@NotBlank @Size(max = 50) String loginId, @NotBlank @Size(min = 8) String password,
                             @NotBlank @Size(max = 50) String name, @NotNull @Min(0) @Max(3) Integer roleId) {
    }

    public record UpdateUser(@Size(max = 50) String name, @Min(0) @Max(3) Integer roleId,
                             @Pattern(regexp = "ACTIVE|SUSPENDED") String status) {
    }

    public record PasswordReset(@NotBlank @Size(min = 8) String password) {
    }

    private final UserRepository users;
    private final BCryptPasswordEncoder encoder;

    public AdminController(UserRepository users, BCryptPasswordEncoder encoder) {
        this.users = users;
        this.encoder = encoder;
    }

    @GetMapping("/roles")
    public List<UserRepository.Role> roles() {
        return users.roles();
    }

    @GetMapping("/users")
    public List<Map<String, Object>> list() {
        return users.findAll().stream().map(u -> {
            var m = new java.util.LinkedHashMap<>(AuthController.view(u));
            m.put("createdAt", u.createdAt());
            m.put("lastLoginAt", u.lastLoginAt());
            return (Map<String, Object>) m;
        }).toList();
    }

    @PostMapping("/users")
    @ResponseStatus(HttpStatus.CREATED)
    public Map<String, Object> create(@Valid @RequestBody CreateUser req) {
        try {
            long id = users.insert(req.loginId(), encoder.encode(req.password()), req.name(), req.roleId());
            return AuthController.view(users.findById(id).orElseThrow());
        } catch (DuplicateKeyException e) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, "이미 있는 아이디입니다");
        }
    }

    /** 역할·상태가 바뀌면 토큰 버전을 올려 기존 로그인을 끊는다. */
    @PatchMapping("/users/{id}")
    public Map<String, Object> update(@PathVariable long id, @Valid @RequestBody UpdateUser req,
                                      jakarta.servlet.http.HttpServletRequest http) {
        var target = users.findById(id).orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND));
        boolean self = tp3.common.CurrentUser.from(http).id() == id;
        boolean roleChange = req.roleId() != null && req.roleId() != target.roleId();
        boolean suspend = "SUSPENDED".equals(req.status());
        if (self && (roleChange || suspend)) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "자기 계정의 역할 변경·정지는 할 수 없습니다");
        }
        users.update(id, req.name(), req.roleId(), req.status());
        return AuthController.view(users.findById(id).orElseThrow());
    }

    @PostMapping("/users/{id}/password")
    public Map<String, Object> resetPassword(@PathVariable long id, @Valid @RequestBody PasswordReset req) {
        users.findById(id).orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND));
        users.updatePassword(id, encoder.encode(req.password()));
        return Map.of("ok", true);
    }

    @PostMapping("/users/{id}/revoke-sessions")
    public Map<String, Object> revoke(@PathVariable long id) {
        users.findById(id).orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND));
        users.revokeSessions(id);
        return Map.of("ok", true);
    }

    @GetMapping("/audit")
    public List<Map<String, Object>> audit(@RequestParam(defaultValue = "200") int limit) {
        return users.auditLog(Math.min(limit, 1000));
    }
}
