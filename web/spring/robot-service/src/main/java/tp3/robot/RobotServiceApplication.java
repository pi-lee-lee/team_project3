package tp3.robot;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.context.annotation.Configuration;
import org.springframework.scheduling.annotation.EnableScheduling;
import org.springframework.web.socket.config.annotation.EnableWebSocket;
import org.springframework.web.socket.config.annotation.WebSocketConfigurer;
import org.springframework.web.socket.config.annotation.WebSocketHandlerRegistry;

@SpringBootApplication
@EnableScheduling
public class RobotServiceApplication {

    public static void main(String[] args) {
        System.setProperty("java.awt.headless", "true");
        SpringApplication.run(RobotServiceApplication.class, args);
    }

    @Configuration
    @EnableWebSocket
    static class WsConfig implements WebSocketConfigurer {
        private final TeleopHandler teleop;

        WsConfig(TeleopHandler teleop) {
            this.teleop = teleop;
        }

        @Override
        public void registerWebSocketHandlers(WebSocketHandlerRegistry registry) {
            // 게이트웨이를 거쳐서만 들어오므로 Origin 검사는 게이트웨이·nginx 단에서 같은 출처로 보장된다
            registry.addHandler(teleop, "/ws/robots/*/teleop").setAllowedOriginPatterns("*");
        }
    }
}
