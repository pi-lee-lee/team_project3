package tp3.gateway;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;

import java.time.Duration;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** A6 시스템 상태: 각 서비스의 health 와 로봇 연결 상태를 모아 보여 준다. (ADMIN 전용 경로) */
@RestController
public class SystemController {

    private final WebClient web;
    private final ServiceUrls urls;

    public SystemController(WebClient web, ServiceUrls urls) {
        this.web = web;
        this.urls = urls;
    }

    @GetMapping("/api/admin/system")
    public Mono<Map<String, Object>> system() {
        Map<String, String> targets = new LinkedHashMap<>();
        targets.put("user-service", urls.user() + "/actuator/health");
        targets.put("inspection-service", urls.inspection() + "/actuator/health");
        targets.put("robot-service", urls.robot() + "/actuator/health");
        targets.put("analysis-service", urls.analysis() + "/health");

        Mono<List<Map<String, Object>>> services = Flux.fromIterable(targets.entrySet())
                .flatMapSequential(e -> web.get().uri(e.getValue()).retrieve().bodyToMono(Map.class)
                        .timeout(Duration.ofSeconds(2))
                        .map(m -> Map.<String, Object>of("name", e.getKey(), "status", String.valueOf(m.get("status"))))
                        .onErrorReturn(Map.of("name", e.getKey(), "status", "DOWN")))
                .collectList();

        Mono<Object> robots = web.get().uri(urls.robot() + "/internal/robots/status").retrieve()
                .bodyToMono(Object.class).timeout(Duration.ofSeconds(2))
                .onErrorReturn(List.of());

        return Mono.zip(services, robots).map(t -> {
            List<Map<String, Object>> all = new java.util.ArrayList<>();
            all.add(Map.of("name", "gateway", "status", "UP"));
            all.addAll(t.getT1());
            return Map.of("services", all, "robots", t.getT2());
        });
    }
}
