package tp3.robot;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;
import org.springframework.web.socket.CloseStatus;
import org.springframework.web.socket.TextMessage;
import org.springframework.web.socket.WebSocketSession;
import org.springframework.web.socket.handler.TextWebSocketHandler;
import tp3.common.AuthHeaders;

import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

/**
 * 원격 조종 WebSocket: /ws/robots/{id}/teleop
 * 클라이언트는 누르는 동안 100ms 마다 {"linear":0.2,"angular":0.0} 을 보낸다.
 * - 제어권 보유자만 명령할 수 있다.
 * - 속도는 서버에서 제한한다.
 * - 최신 명령만 의미가 있으므로 쌓지 않고 바로 보낸다.
 * - 명령이 0.5초 끊기면 서버가 정지 명령을 보낸다(로봇 측 워치독과 이중 보호).
 */
@Component
public class TeleopHandler extends TextWebSocketHandler {

    private static final double MAX_LINEAR = 0.22;   // TurtleBot3 최대 0.26 m/s 보다 낮게
    private static final double MAX_ANGULAR = 1.5;

    private record Ctx(long robotId, long userId, String login, long[] last, boolean[] moving) {
    }

    private final ControlService control;
    private final RobotRegistry registry;
    private final MissionService missions;
    private final ObjectMapper om = new ObjectMapper();
    private final Map<String, Ctx> sessions = new ConcurrentHashMap<>();

    public TeleopHandler(ControlService control, RobotRegistry registry, MissionService missions) {
        this.control = control;
        this.registry = registry;
        this.missions = missions;
    }

    @Override
    public void afterConnectionEstablished(WebSocketSession s) throws Exception {
        String uid = s.getHandshakeHeaders().getFirst(AuthHeaders.USER_ID);
        String path = s.getUri() == null ? "" : s.getUri().getPath();
        String[] parts = path.split("/");   // /ws/robots/{id}/teleop
        if (uid == null || parts.length < 5) {
            s.close(CloseStatus.POLICY_VIOLATION);
            return;
        }
        sessions.put(s.getId(), new Ctx(Long.parseLong(parts[3]), Long.parseLong(uid),
                s.getHandshakeHeaders().getFirst(AuthHeaders.LOGIN), new long[]{0}, new boolean[]{false}));
        s.sendMessage(new TextMessage("{\"type\":\"ready\"}"));
    }

    @Override
    protected void handleTextMessage(WebSocketSession s, TextMessage message) throws Exception {
        Ctx c = sessions.get(s.getId());
        if (c == null) {
            return;
        }
        if (!control.isHolder(c.robotId(), c.userId())) {
            s.sendMessage(new TextMessage("{\"type\":\"error\",\"message\":\"제어권이 없습니다\"}"));
            return;
        }
        JsonNode n = om.readTree(message.getPayload());
        double lin = clamp(n.path("linear").asDouble(0), MAX_LINEAR);
        double ang = clamp(n.path("angular").asDouble(0), MAX_ANGULAR);
        try {
            if (lin != 0 || ang != 0) {
                missions.cancelManual(c.robotId());   // 직접 조종하면 지도 이동 목적지는 취소
            }
            registry.adapter(c.robotId()).teleop(lin, ang);
            c.last()[0] = System.currentTimeMillis();
            c.moving()[0] = lin != 0 || ang != 0;
            control.touch(c.robotId(), c.userId());
        } catch (Exception e) {
            s.sendMessage(new TextMessage("{\"type\":\"error\",\"message\":\"로봇에 명령을 보내지 못했습니다\"}"));
        }
    }

    @Override
    public void afterConnectionClosed(WebSocketSession s, CloseStatus status) {
        Ctx c = sessions.remove(s.getId());
        if (c != null && c.moving()[0]) {
            stop(c);
        }
    }

    @Scheduled(fixedRate = 100)
    public void watchdog() {
        long now = System.currentTimeMillis();
        sessions.values().forEach(c -> {
            if (c.moving()[0] && now - c.last()[0] > 500) {
                stop(c);
            }
        });
    }

    private void stop(Ctx c) {
        c.moving()[0] = false;
        try {
            var a = registry.adapterOrNull(c.robotId());
            if (a != null) {
                a.teleop(0, 0);
            }
        } catch (Exception ignored) {
            // 연결이 끊긴 경우 로봇 측 워치독이 정지시킨다
        }
    }

    private static double clamp(double v, double max) {
        return Math.max(-max, Math.min(max, v));
    }
}
