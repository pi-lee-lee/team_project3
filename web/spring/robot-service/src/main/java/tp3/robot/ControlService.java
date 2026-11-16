package tp3.robot;

import org.springframework.http.HttpStatus;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;
import tp3.common.CurrentUser;

import java.time.Instant;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

/**
 * 제어권: 로봇마다 한 시점에 하나의 보유자(사용자 1명 또는 미션). 조종 명령은 보유자만 보낼 수 있다.
 * 사용자 제어권은 조종이 2분간 없으면 자동 반납된다.
 */
@Service
public class ControlService {

    public record Lease(String kind, Long userId, String login, Instant since, long lastActivity) {
        public Map<String, Object> view() {
            return Map.of("kind", kind, "userId", userId == null ? 0 : userId, "login", login == null ? "" : login,
                    "since", since.toString());
        }
    }

    private static final long IDLE_MS = 120_000;
    private final Map<Long, Lease> leases = new ConcurrentHashMap<>();
    private final RobotRegistry registry;

    public ControlService(RobotRegistry registry) {
        this.registry = registry;
    }

    public Lease holder(long robotId) {
        return leases.get(robotId);
    }

    public synchronized Lease acquire(long robotId, CurrentUser u) {
        registry.adapter(robotId);
        Lease cur = leases.get(robotId);
        if (cur != null && "MISSION".equals(cur.kind())) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, "점검 작업이 진행 중이라 조종할 수 없습니다");
        }
        if (cur != null && !cur.userId().equals(u.id())) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, cur.login() + " 님이 조종 중입니다");
        }
        Lease l = new Lease("USER", u.id(), u.login(), Instant.now(), System.currentTimeMillis());
        leases.put(robotId, l);
        return l;
    }

    public synchronized void release(long robotId, CurrentUser u) {
        Lease cur = leases.get(robotId);
        if (cur != null && "USER".equals(cur.kind()) && cur.userId().equals(u.id())) {
            leases.remove(robotId);
            stopQuietly(robotId);
        }
    }

    /** 관리자 강제 회수. 미션 제어권은 회수하지 않는다(미션은 취소·비상 정지로 멈춘다). */
    public synchronized Lease revoke(long robotId) {
        Lease cur = leases.get(robotId);
        if (cur != null && "USER".equals(cur.kind())) {
            leases.remove(robotId);
            stopQuietly(robotId);
        }
        return cur;
    }

    public synchronized boolean takeForMission(long robotId) {
        Lease cur = leases.get(robotId);
        if (cur != null) {
            return false;
        }
        leases.put(robotId, new Lease("MISSION", null, "mission", Instant.now(), System.currentTimeMillis()));
        return true;
    }

    public synchronized void releaseMission(long robotId) {
        Lease cur = leases.get(robotId);
        if (cur != null && "MISSION".equals(cur.kind())) {
            leases.remove(robotId);
        }
    }

    public synchronized void clear(long robotId) {
        leases.remove(robotId);
    }

    public boolean isHolder(long robotId, long userId) {
        Lease cur = leases.get(robotId);
        return cur != null && "USER".equals(cur.kind()) && cur.userId() == userId;
    }

    public void touch(long robotId, long userId) {
        Lease cur = leases.get(robotId);
        if (cur != null && "USER".equals(cur.kind()) && cur.userId() == userId) {
            leases.put(robotId, new Lease(cur.kind(), cur.userId(), cur.login(), cur.since(), System.currentTimeMillis()));
        }
    }

    @Scheduled(fixedDelay = 10_000)
    public void expireIdle() {
        long now = System.currentTimeMillis();
        leases.forEach((robotId, l) -> {
            if ("USER".equals(l.kind()) && now - l.lastActivity() > IDLE_MS) {
                leases.remove(robotId, l);
                stopQuietly(robotId);
            }
        });
    }

    private void stopQuietly(long robotId) {
        try {
            var a = registry.adapterOrNull(robotId);
            if (a != null) {
                a.teleop(0, 0);
            }
        } catch (Exception ignored) {
            // 연결이 끊긴 경우 로봇 측 워치독이 정지시킨다
        }
    }
}
