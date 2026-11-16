package tp3.gateway;

import org.springframework.stereotype.Component;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Mono;
import tp3.common.JwtCodec;

import java.time.Duration;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

/**
 * 토큰이 아직 유효한지 user-service 에 확인한다(정지·역할 변경·세션 강제 종료 반영).
 * 매 요청마다 묻지 않도록 10초간 캐시한다. user-service 가 응답하지 않으면 거부한다(fail closed).
 */
@Component
public class SessionChecker {

    private record Entry(int tokenVersion, String status, long at) {
    }

    private static final long TTL_MS = 10_000;

    private final WebClient web;
    private final ServiceUrls urls;
    private final Map<Long, Entry> cache = new ConcurrentHashMap<>();

    public SessionChecker(WebClient web, ServiceUrls urls) {
        this.web = web;
        this.urls = urls;
    }

    public Mono<Boolean> isValid(JwtCodec.TokenClaims c) {
        Entry e = cache.get(c.userId());
        if (e != null && System.currentTimeMillis() - e.at() < TTL_MS) {
            return Mono.just(matches(e, c));
        }
        return web.get().uri(urls.user() + "/internal/users/{id}/session", c.userId())
                .retrieve().bodyToMono(Map.class)
                .timeout(Duration.ofSeconds(3))
                .map(m -> {
                    Entry fresh = new Entry(((Number) m.get("tokenVersion")).intValue(), (String) m.get("status"),
                            System.currentTimeMillis());
                    cache.put(c.userId(), fresh);
                    return matches(fresh, c);
                })
                .onErrorReturn(false);
    }

    private static boolean matches(Entry e, JwtCodec.TokenClaims c) {
        return "ACTIVE".equals(e.status()) && e.tokenVersion() == c.tokenVersion();
    }
}
