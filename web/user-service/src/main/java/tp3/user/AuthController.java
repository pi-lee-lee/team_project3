package tp3.user;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.convert.DurationStyle;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseCookie;
import org.springframework.http.ResponseEntity;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;
import tp3.common.AuthHeaders;
import tp3.common.CurrentUser;
import tp3.common.JwtCodec;

import java.time.Duration;
import java.util.Map;

@RestController
@RequestMapping("/api/auth")
public class AuthController {

    public record LoginRequest(@NotBlank String loginId, @NotBlank String password) {
    }

    private final UserRepository users;
    private final BCryptPasswordEncoder encoder;
    private final JwtCodec jwt;
    private final Duration ttl;
    private final boolean secureCookie;

    public AuthController(UserRepository users, BCryptPasswordEncoder encoder, JwtCodec jwt,
                          @Value("${app.token-ttl}") String ttl, @Value("${app.cookie-secure}") boolean secureCookie) {
        this.users = users;
        this.encoder = encoder;
        this.jwt = jwt;
        this.ttl = DurationStyle.detectAndParse(ttl);
        this.secureCookie = secureCookie;
    }

    @PostMapping("/login")
    public ResponseEntity<Map<String, Object>> login(@Valid @RequestBody LoginRequest req) {
        var user = users.findByLogin(req.loginId()).orElse(null);
        if (user == null || !encoder.matches(req.password(), user.passwordHash())) {
            users.audit(user == null ? null : user.userId(), req.loginId(), null, "LOGIN_FAILED", "/api/auth/login", 401, null);
            throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "아이디 또는 비밀번호가 올바르지 않습니다");
        }
        if (!"ACTIVE".equals(user.status())) {
            users.audit(user.userId(), user.loginId(), user.roleCode(), "LOGIN_FAILED", "/api/auth/login", 403, "suspended");
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "정지된 계정입니다");
        }
        users.touchLogin(user.userId());
        users.audit(user.userId(), user.loginId(), user.roleCode(), "LOGIN", "/api/auth/login", 200, null);
        String token = jwt.issue(new JwtCodec.TokenClaims(user.userId(), user.loginId(), user.roleCode(), user.tokenVersion()), ttl);
        return ResponseEntity.ok()
                .header(HttpHeaders.SET_COOKIE, cookie(token, ttl).toString())
                .body(view(user));
    }

    @PostMapping("/logout")
    public ResponseEntity<Void> logout() {
        return ResponseEntity.noContent().header(HttpHeaders.SET_COOKIE, cookie("", Duration.ZERO).toString()).build();
    }

    @GetMapping("/me")
    public Map<String, Object> me(HttpServletRequest req) {
        var cu = CurrentUser.from(req);
        return users.findById(cu.id()).map(AuthController::view)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.UNAUTHORIZED));
    }

    private ResponseCookie cookie(String value, Duration maxAge) {
        return ResponseCookie.from(AuthHeaders.COOKIE, value)
                .httpOnly(true).secure(secureCookie).sameSite("Strict").path("/").maxAge(maxAge).build();
    }

    static Map<String, Object> view(UserRepository.User u) {
        return Map.of("userId", u.userId(), "loginId", u.loginId(), "name", u.name(),
                "roleId", u.roleId(), "role", u.roleCode(), "roleName", u.roleName(), "status", u.status());
    }
}
