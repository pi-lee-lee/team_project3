package tp3.robot;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;
import tp3.robot.adapter.RobotAdapter;

import java.util.List;
import java.util.Map;

/**
 * 금지구역: 관리자가 지도에 그려 둔 직사각형(공사 중인 구역 등). 실제 장애물이 없어도 로봇이 그 안으로 가지 않는다.
 *
 * 구역은 DB 에 두고, 목록 전체를 로봇에 보낸다(토픽 /inspection/keepout). 로봇 쪽 목표 브리지가 그 목록을
 * 계획 맵(전역 비용 지도)과 제어 맵(지역 비용 지도)에 막힌 칸으로 넣는다 — 그래서 달리는 도중에 그려도
 * 1 ~ 2초 안에 경로 검사가 "막힘"을 보고 다시 계획한다.
 * 목록은 바뀔 때마다, 그리고 5초마다 다시 보낸다(로봇 · 시뮬레이션이 다시 떠도 따로 할 일이 없다).
 */
@Service
public class KeepoutService {

    private static final Logger log = LoggerFactory.getLogger(KeepoutService.class);
    /** 구역 한 변의 최소 길이(m): 실수로 누른 점 하나가 구역이 되지 않게 */
    private static final double MIN_SIDE = 0.2;
    /** 로봇이 서 있는 자리 둘레 이만큼은 구역으로 덮을 수 없다(m): 덮으면 그 자리에서 계획이 거부돼 갇힌다 */
    private static final double ROBOT_CLEAR = 0.35;

    private final JdbcClient jdbc;
    private final RobotRegistry registry;
    private final RobotRepository repo;
    private final ObjectMapper om = new ObjectMapper();

    public KeepoutService(JdbcClient jdbc, RobotRegistry registry, RobotRepository repo) {
        this.jdbc = jdbc;
        this.registry = registry;
        this.repo = repo;
    }

    public List<Map<String, Object>> list(long robotId) {
        return jdbc.sql("""
                        SELECT zone_id AS "zoneId", name, x_min AS "xMin", y_min AS "yMin", x_max AS "xMax", y_max AS "yMax",
                               created_by AS "createdBy", created_at AS "createdAt"
                        FROM keepout_zone WHERE robot_id = ? ORDER BY zone_id""")
                .param(robotId).query().listOfRows();
    }

    public List<Map<String, Object>> create(long robotId, String name, double x1, double y1, double x2, double y2, String by) {
        repo.robot(robotId).orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND));
        double xMin = Math.min(x1, x2), xMax = Math.max(x1, x2), yMin = Math.min(y1, y2), yMax = Math.max(y1, y2);
        if (!(xMax - xMin >= MIN_SIDE && yMax - yMin >= MIN_SIDE)) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "구역이 너무 작습니다. 한 변이 " + MIN_SIDE + "m 이상이 되게 끌어 주세요");
        }
        RobotAdapter a = registry.adapterOrNull(robotId);
        RobotAdapter.Pose p = a == null ? null : a.mapView().pose();
        if (p != null && p.x() > xMin - ROBOT_CLEAR && p.x() < xMax + ROBOT_CLEAR
                && p.y() > yMin - ROBOT_CLEAR && p.y() < yMax + ROBOT_CLEAR) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, "로봇이 그 구역 안(또는 바로 옆)에 있습니다. 로봇이 나간 뒤에 설정하세요");
        }
        String n = name == null ? "" : name.strip();
        jdbc.sql("INSERT INTO keepout_zone (robot_id, name, x_min, y_min, x_max, y_max, created_by) VALUES (?, ?, ?, ?, ?, ?, ?)")
                .params(robotId, n.length() > 60 ? n.substring(0, 60) : n, xMin, yMin, xMax, yMax, by).update();
        push(robotId);
        return list(robotId);
    }

    public List<Map<String, Object>> delete(long robotId, long zoneId) {
        int n = jdbc.sql("DELETE FROM keepout_zone WHERE zone_id = ? AND robot_id = ?").params(zoneId, robotId).update();
        if (n == 0) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, "없는 구역입니다");
        }
        push(robotId);
        return list(robotId);
    }

    /** 구역 목록을 로봇에 보낸다. 연결되지 않은 로봇은 건너뛴다(다음 주기에 다시 보낸다). */
    private void push(long robotId) {
        RobotAdapter a = registry.adapterOrNull(robotId);
        if (a == null) {
            return;
        }
        ObjectNode msg = om.createObjectNode();
        ArrayNode zones = msg.putArray("zones");
        for (Map<String, Object> z : list(robotId)) {
            ObjectNode o = zones.addObject();
            o.put("id", ((Number) z.get("zoneId")).longValue());
            o.put("x1", ((Number) z.get("xMin")).doubleValue());
            o.put("y1", ((Number) z.get("yMin")).doubleValue());
            o.put("x2", ((Number) z.get("xMax")).doubleValue());
            o.put("y2", ((Number) z.get("yMax")).doubleValue());
        }
        try {
            a.keepout(msg.toString());
        } catch (Exception e) {
            log.debug("keepout push to robot {} failed: {}", robotId, e.toString());
        }
    }

    @Scheduled(fixedDelay = 5000)
    void resend() {
        for (RobotRepository.Robot r : repo.robots()) {
            if (r.enabled()) {
                push(r.robotId());
            }
        }
    }
}
