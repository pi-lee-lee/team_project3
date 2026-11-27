package tp3.robot;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;
import tp3.robot.adapter.RobotAdapter;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.TimeoutException;

/**
 * 시뮬레이션 전용: 시뮬레이션 도구(fire · target · obstacle)를 실행한다. 관리자 "시연" 화면과 시연 스크립트가 쓴다.
 * sim 컨테이너의 sim_control.py 가 /sim/command 를 받아 실행하고 /sim/command_status 로 답한다.
 * 실제 로봇에는 그 노드가 없으므로 응답이 오지 않고 "시뮬레이션이 아닙니다"로 끝난다.
 */
@Service
public class SimService {

    private static final Set<String> TOOLS = Set.of("fire", "target", "obstacle");

    private final RobotRegistry registry;
    private final ObjectMapper om = new ObjectMapper();
    private final Map<String, CompletableFuture<JsonNode>> waits = new ConcurrentHashMap<>();

    public SimService(RobotRegistry registry) {
        this.registry = registry;
        registry.setSimListener((robotId, data) -> {
            try {
                JsonNode n = om.readTree(data);
                var f = waits.get(n.path("id").asText());
                if (f != null) {
                    f.complete(n);
                }
            } catch (Exception ignored) {
                // 모양이 틀린 응답은 버린다
            }
        });
    }

    public Map<String, Object> run(long robotId, String tool, List<String> args) {
        if (!TOOLS.contains(tool)) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "허용하지 않는 도구: " + tool);
        }
        RobotAdapter a = registry.adapter(robotId);
        String id = UUID.randomUUID().toString();
        CompletableFuture<JsonNode> f = new CompletableFuture<>();
        waits.put(id, f);
        try {
            a.simCommand(id, tool, args);
            JsonNode res = null;
            // 명령이 유실될 수 있으므로 답이 올 때까지 5초마다 다시 보낸다(받는 쪽은 같은 id 를 한 번만 실행한다)
            for (int i = 0; i < 36 && res == null; i++) {
                try {
                    res = f.get(5, TimeUnit.SECONDS);
                } catch (TimeoutException te) {
                    a.simCommand(id, tool, args);
                }
            }
            if (res == null) {
                throw new ResponseStatusException(HttpStatus.GATEWAY_TIMEOUT,
                        "시뮬레이션이 답하지 않습니다(시뮬레이션 로봇이 아니거나 sim_control 노드가 떠 있지 않음)");
            }
            Map<String, Object> m = new LinkedHashMap<>();
            m.put("ok", res.path("ok").asBoolean());
            m.put("code", res.path("code").asInt());
            m.put("output", res.path("output").asText());
            return m;
        } catch (UnsupportedOperationException e) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, e.getMessage());
        } catch (ResponseStatusException e) {
            throw e;
        } catch (Exception e) {
            throw new ResponseStatusException(HttpStatus.INTERNAL_SERVER_ERROR, String.valueOf(e.getMessage()));
        } finally {
            waits.remove(id);
        }
    }
}
