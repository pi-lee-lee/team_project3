package tp3.gateway;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.cloud.gateway.route.RouteLocator;
import org.springframework.cloud.gateway.route.builder.RouteLocatorBuilder;
import org.springframework.context.annotation.Bean;
import org.springframework.web.reactive.function.client.WebClient;
import tp3.common.JwtCodec;

@SpringBootApplication
@EnableConfigurationProperties({AccessPolicy.class, ServiceUrls.class})
public class GatewayApplication {

    public static void main(String[] args) {
        SpringApplication.run(GatewayApplication.class, args);
    }

    @Bean
    JwtCodec jwtCodec(@Value("${app.jwt-secret}") String secret) {
        return new JwtCodec(secret);
    }

    @Bean
    WebClient webClient(WebClient.Builder builder) {
        return builder.build();
    }

    /**
     * 경로 → 서비스 라우팅. /internal/** 과 /actuator/** 는 라우팅하지 않으므로 외부에서 접근할 수 없다.
     * /api/admin/system 은 게이트웨이가 직접 처리한다(SystemController).
     */
    @Bean
    RouteLocator routes(RouteLocatorBuilder b, ServiceUrls s) {
        String robotWs = s.robot().replaceFirst("^http", "ws");
        return b.routes()
                .route("user", r -> r.path("/api/auth/**", "/api/admin/users/**", "/api/admin/roles",
                        "/api/admin/audit/**").uri(s.user()))
                .route("inspection", r -> r.path("/api/points/**", "/api/admin/points/**", "/api/inspections/**",
                        "/api/observations/**").uri(s.inspection()))
                .route("robot", r -> r.path("/api/robots/**", "/api/admin/robots/**").uri(s.robot()))
                .route("robot-ws", r -> r.path("/ws/robots/**").uri(robotWs))
                .route("analysis", r -> r.path("/api/admin/analysis/**").uri(s.analysis()))
                .build();
    }
}
