package tp3.robot;

import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.annotation.PreDestroy;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.EventListener;
import org.springframework.core.annotation.Order;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Component;
import org.springframework.web.server.ResponseStatusException;
import tp3.robot.adapter.MockRobotAdapter;
import tp3.robot.adapter.RobotAdapter;
import tp3.robot.adapter.RosbridgeRobotAdapter;

import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.function.BiConsumer;

/** 등록된 로봇마다 어댑터를 하나씩 만들어 유지한다. 설정이 바뀌면 어댑터를 새로 만든다. */
@Component
public class RobotRegistry {

    private static final Logger log = LoggerFactory.getLogger(RobotRegistry.class);

    private final RobotRepository repo;
    private final ObjectMapper om = new ObjectMapper();
    private final Map<Long, RobotAdapter> adapters = new ConcurrentHashMap<>();
    private final String simRosbridge;
    private final String simVideo;
    private BiConsumer<Long, RobotAdapter.GoalStatus> goalListener = (id, s) -> {
    };

    public RobotRegistry(RobotRepository repo, @Value("${app.sim-rosbridge-url}") String simRosbridge,
                         @Value("${app.sim-video-url}") String simVideo) {
        this.repo = repo;
        this.simRosbridge = simRosbridge;
        this.simVideo = simVideo;
    }

    public void setGoalListener(BiConsumer<Long, RobotAdapter.GoalStatus> l) {
        this.goalListener = l;
    }

    @EventListener(ApplicationReadyEvent.class)
    @Order(1)
    public void init() {
        if (repo.robots().isEmpty()) {
            String cfg = om.createObjectNode().put("rosbridgeUrl", simRosbridge).put("videoUrl", simVideo).toString();
            repo.insertRobot("tb3-sim", "TurtleBot3 (시뮬레이션)", "ROSBRIDGE", cfg, true);
            repo.insertRobot("mock-1", "가짜 로봇 (ROS 없이 시험)", "MOCK", "{}", false);
            log.info("초기 로봇 등록: tb3-sim({}), mock-1(비활성)", simRosbridge);
        }
        repo.robots().forEach(this::load);
    }

    public synchronized void load(RobotRepository.Robot r) {
        RobotAdapter old = adapters.remove(r.robotId());
        if (old != null) {
            old.close();
        }
        if (!r.enabled()) {
            return;
        }
        try {
            RobotAdapter a = switch (r.adapterType()) {
                case "ROSBRIDGE" -> new RosbridgeRobotAdapter(r.code(), om.readTree(r.config()));
                case "MOCK" -> new MockRobotAdapter(r.code());
                default -> throw new IllegalArgumentException("unknown adapter " + r.adapterType());
            };
            a.onGoalStatus(s -> goalListener.accept(r.robotId(), s));
            a.start();
            adapters.put(r.robotId(), a);
        } catch (Exception e) {
            log.warn("로봇 {} 어댑터 생성 실패: {}", r.code(), e.toString());
        }
    }

    public RobotAdapter adapter(long robotId) {
        RobotAdapter a = adapters.get(robotId);
        if (a == null) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, "로봇이 비활성 상태이거나 없습니다");
        }
        return a;
    }

    public RobotAdapter adapterOrNull(long robotId) {
        return adapters.get(robotId);
    }

    @PreDestroy
    public void shutdown() {
        adapters.values().forEach(RobotAdapter::close);
    }
}
