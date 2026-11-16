package tp3.gateway;

import org.springframework.core.annotation.Order;
import org.springframework.http.HttpCookie;
import org.springframework.http.HttpMethod;
import org.springframework.http.HttpStatus;
import org.springframework.http.server.reactive.ServerHttpRequest;
import org.springframework.stereotype.Component;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.web.server.ServerWebExchange;
import org.springframework.web.server.WebFilter;
import org.springframework.web.server.WebFilterChain;
import reactor.core.publisher.Mono;
import tp3.common.AuthHeaders;
import tp3.common.JwtCodec;

import java.util.HashMap;
import java.util.Map;
import java.util.Set;

/**
 * 모든 요청의 입구.
 * 1) 클라이언트가 보낸 X-User-* 헤더를 지운다(위조 방지).
 * 2) /api, /ws 외의 경로(/internal, /actuator 등)는 막는다.
 * 3) 쿠키의 JWT를 검증하고, 세션이 유효한지 확인하고, 경로별 역할 정책을 적용한다.
 * 4) 내부 서비스로 X-User-* 헤더를 붙여 넘긴다.
 * 5) 변경 요청(POST·PUT·PATCH·DELETE)은 끝난 뒤 감사 로그로 보낸다.
 */
@Component
@Order(-200)
public class AuthWebFilter implements WebFilter {

    private static final Set<HttpMethod> MUTATING = Set.of(HttpMethod.POST, HttpMethod.PUT, HttpMethod.PATCH,
            HttpMethod.DELETE);

    private final JwtCodec jwt;
    private final AccessPolicy policy;
    private final SessionChecker sessions;
    private final WebClient web;
    private final ServiceUrls urls;

    public AuthWebFilter(JwtCodec jwt, AccessPolicy policy, SessionChecker sessions, WebClient web, ServiceUrls urls) {
        this.jwt = jwt;
        this.policy = policy;
        this.sessions = sessions;
        this.web = web;
        this.urls = urls;
    }

    @Override
    public Mono<Void> filter(ServerWebExchange exchange, WebFilterChain chain) {
        String path = exchange.getRequest().getPath().value();
        ServerHttpRequest stripped = exchange.getRequest().mutate().headers(h -> {
            h.remove(AuthHeaders.USER_ID);
            h.remove(AuthHeaders.LOGIN);
            h.remove(AuthHeaders.ROLE);
        }).build();
        ServerWebExchange ex = exchange.mutate().request(stripped).build();

        // 컨테이너 상태 검사용. nginx 는 /api·/ws 만 넘기므로 외부에서는 닿지 않는다.
        if ("/actuator/health".equals(path)) {
            return chain.filter(ex);
        }
        if (!path.startsWith("/api/") && !path.startsWith("/ws/")) {
            return reject(ex, HttpStatus.NOT_FOUND);
        }
        if (policy.isPublic(path)) {
            return chain.filter(ex);
        }
        HttpCookie cookie = ex.getRequest().getCookies().getFirst(AuthHeaders.COOKIE);
        var claims = cookie == null ? null : jwt.parse(cookie.getValue()).orElse(null);
        if (claims == null) {
            return reject(ex, HttpStatus.UNAUTHORIZED);
        }
        return sessions.isValid(claims).flatMap(valid -> {
            if (!valid) {
                return reject(ex, HttpStatus.UNAUTHORIZED);
            }
            if (!policy.allows(path, claims.role()).orElse(false)) {
                return reject(ex, HttpStatus.FORBIDDEN);
            }
            ServerHttpRequest withUser = ex.getRequest().mutate()
                    .header(AuthHeaders.USER_ID, Long.toString(claims.userId()))
                    .header(AuthHeaders.LOGIN, claims.login())
                    .header(AuthHeaders.ROLE, claims.role())
                    .build();
            ServerWebExchange authed = ex.mutate().request(withUser).build();
            HttpMethod method = ex.getRequest().getMethod();
            if (!MUTATING.contains(method)) {
                return chain.filter(authed);
            }
            return chain.filter(authed).doFinally(sig -> audit(claims, method, path, authed));
        });
    }

    private void audit(JwtCodec.TokenClaims c, HttpMethod method, String path, ServerWebExchange ex) {
        var code = ex.getResponse().getStatusCode();
        Map<String, Object> body = new HashMap<>();
        body.put("userId", c.userId());
        body.put("loginId", c.login());
        body.put("role", c.role());
        body.put("action", method.name());
        body.put("target", path);
        body.put("status", code == null ? null : code.value());
        web.post().uri(urls.user() + "/internal/audit").bodyValue(body).retrieve().toBodilessEntity()
                .onErrorResume(e -> Mono.empty()).subscribe();
    }

    private static Mono<Void> reject(ServerWebExchange ex, HttpStatus status) {
        ex.getResponse().setStatusCode(status);
        return ex.getResponse().setComplete();
    }
}
