package tp3.inspection;

import com.fasterxml.jackson.databind.JsonNode;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;
import org.springframework.web.client.HttpStatusCodeException;
import org.springframework.web.client.RestClient;
import org.springframework.web.server.ResponseStatusException;
import tp3.common.CurrentUser;

import java.sql.Timestamp;
import java.time.Duration;
import java.time.Instant;
import java.time.LocalDateTime;
import java.time.LocalTime;
import java.time.ZoneId;
import java.time.format.DateTimeParseException;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentLinkedDeque;
import java.util.concurrent.atomic.AtomicLong;

/**
 * 예약 점검: 등록·수정·켜고 끄기와 실행기.
 * 실행기는 5초마다 때가 된 예약의 회차를 로봇별 실행 버퍼(대기열)에 담고, 로봇이 비면 앞에서부터 일반 점검 요청과
 * 같은 경로(TaskService.create)로 작업을 만든다. 로봇이 작업 중·조종 중·연결 안 됨이면 건너뛰지 않고 기다렸다가 이어서
 * 실행하며, 기다리는 동안은 지연 목록(pending)으로 화면에 알린다.
 * 버퍼는 메모리에만 있어 재기동하면 비고, 꺼져 있던 동안 지나간 회차는 MISSED 로만 기록하고 실행하지 않는다.
 */
@Service
public class ScheduleService {

    private static final Logger log = LoggerFactory.getLogger(ScheduleService.class);
    static final Set<String> KINDS = Set.of("MANUAL", "ONCE", "INTERVAL", "DAILY", "WEEKLY");

    private final ScheduleStore store;
    private final Store points;
    private final TaskService tasks;
    private final RestClient robot;
    private final ZoneId zone;

    public ScheduleService(ScheduleStore store, Store points, TaskService tasks, RestClient robotClient,
                           @Value("${app.schedule-zone:Asia/Seoul}") String zone) {
        this.store = store;
        this.points = points;
        this.tasks = tasks;
        this.robot = robotClient;
        this.zone = ZoneId.of(zone);
    }

    public ZoneId zone() {
        return zone;
    }

    // ------------------------------------------------------------- 등록·수정
    public Map<String, Object> create(JsonNode b, CurrentUser u) {
        Map<String, Object> v = validate(b);
        long id = store.insert(v, u.id(), u.login(), u.role());
        return store.get(id).orElseThrow();
    }

    public Map<String, Object> update(long id, JsonNode b, CurrentUser u) {
        editable(id, u);
        Map<String, Object> v = validate(b);
        store.update(id, v);
        return store.get(id).orElseThrow();
    }

    public Map<String, Object> setEnabled(long id, boolean enabled, CurrentUser u) {
        var s = editable(id, u);
        Instant next = null;
        if (enabled && !"MANUAL".equals(s.get("kind"))) {
            next = rule(s).first(Instant.now(), zone);
            if (next == null) {
                throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "더 실행할 시각이 없습니다. 시각을 고쳐 주세요");
            }
        }
        // 다시 켤 때는 지금 기준으로 다시 계산한다(꺼져 있던 동안의 지난 시각으로 곧바로 실행하지 않게)
        store.setEnabled(id, enabled, next);
        if (!enabled) {
            dropPending(id, u.login() + " 님이 예약을 끔");
        }
        return store.get(id).orElseThrow();
    }

    public void delete(long id, CurrentUser u) {
        editable(id, u);
        store.delete(id);
        dropPending(id, u.login() + " 님이 예약을 지움");
    }

    /** 만든 사람 또는 3 사용자보다 높은 역할만 고칠 수 있다. */
    private Map<String, Object> editable(long id, CurrentUser u) {
        var s = store.get(id).orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND));
        boolean owner = ((Number) s.get("created_by")).longValue() == u.id();
        if (!owner && "USER".equals(u.role())) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "다른 사람이 만든 예약은 고칠 수 없습니다");
        }
        return s;
    }

    /** 요청 본문을 검사해 저장할 값으로 바꾼다. 다음 실행 시각도 여기서 계산한다. */
    private Map<String, Object> validate(JsonNode b) {
        String name = b.path("name").asText("").trim();
        if (name.isEmpty()) {
            throw bad("예약 이름이 필요합니다");
        }
        long robotId = b.path("robotId").asLong(0);
        if (robotId <= 0) {
            throw bad("로봇을 고르세요");
        }
        List<Long> pointIds = new ArrayList<>();
        b.path("pointIds").forEach(n -> pointIds.add(n.asLong()));
        if (pointIds.isEmpty()) {
            throw bad("점검 지점을 하나 이상 고르세요");
        }
        for (Long pid : pointIds) {
            var p = points.point(pid).orElseThrow(() -> bad("없는 지점: " + pid));
            if (!(Boolean) p.get("active")) {
                throw bad("비활성 지점: " + p.get("code"));
            }
        }
        try {
            robot.get().uri("/internal/robots/{id}", robotId).retrieve().toBodilessEntity();
        } catch (HttpStatusCodeException e) {
            throw bad("없는 로봇입니다");
        } catch (Exception e) {
            // 로봇 서비스가 잠시 안 될 때도 예약은 저장할 수 있게 한다(실행 시점에 다시 확인한다)
        }
        String kind = b.path("kind").asText("");
        if (!KINDS.contains(kind)) {
            throw bad("실행 방식은 MANUAL / ONCE / INTERVAL / DAILY / WEEKLY");
        }
        Instant runAt = localDateTime(b, "runAt");
        Integer interval = b.hasNonNull("intervalMinutes") ? b.path("intervalMinutes").asInt() : null;
        LocalTime timeOfDay = time(b, "timeOfDay");
        LocalTime ws = time(b, "windowStart");
        LocalTime we = time(b, "windowEnd");
        Set<Integer> days = new LinkedHashSet<>();
        b.path("daysOfWeek").forEach(n -> days.add(n.asInt()));
        if (days.stream().anyMatch(d -> d < 1 || d > 7)) {
            throw bad("요일은 1(월)~7(일)");
        }
        switch (kind) {
            case "MANUAL" -> {
                runAt = null; interval = null; timeOfDay = null; ws = null; we = null; days.clear();
            }
            case "ONCE" -> {
                if (runAt == null) throw bad("실행 일시를 정하세요");
                if (!runAt.isAfter(Instant.now())) throw bad("실행 일시가 이미 지났습니다");
                interval = null; timeOfDay = null; ws = null; we = null; days.clear();
            }
            case "INTERVAL" -> {
                if (interval == null || interval < 5 || interval > 7 * 24 * 60) {
                    throw bad("간격은 5분 ~ 7일(10080분) 사이로 정하세요");
                }
                if ((ws == null) != (we == null)) throw bad("시간대는 시작과 끝을 함께 정하세요");
                if (ws != null && ws.equals(we)) throw bad("시간대의 시작과 끝이 같습니다");
                timeOfDay = null;
            }
            case "DAILY" -> {
                if (timeOfDay == null) throw bad("실행 시각을 정하세요");
                runAt = null; interval = null; ws = null; we = null; days.clear();
            }
            case "WEEKLY" -> {
                if (timeOfDay == null) throw bad("실행 시각을 정하세요");
                if (days.isEmpty()) throw bad("요일을 하나 이상 고르세요");
                runAt = null; interval = null; ws = null; we = null;
            }
            default -> throw bad("반복 방식");
        }
        boolean enabled = b.path("enabled").asBoolean(true);
        ScheduleRule rule = new ScheduleRule(kind, runAt, interval, timeOfDay, days, ws, we);
        Instant next = enabled ? rule.first(Instant.now(), zone) : null;
        if (enabled && next == null && !"MANUAL".equals(kind)) {
            throw bad("조건에 맞는 실행 시각이 없습니다");
        }
        Map<String, Object> v = new HashMap<>();
        v.put("name", name);
        v.put("robotId", robotId);
        v.put("pointIds", pointIds);
        String note = b.path("note").asText("").trim();
        v.put("note", note.isEmpty() ? null : note);
        v.put("kind", kind);
        v.put("runAt", runAt);
        v.put("intervalMinutes", interval);
        v.put("timeOfDay", hhmm(timeOfDay));
        v.put("days", days.stream().sorted().toList());
        v.put("windowStart", hhmm(ws));
        v.put("windowEnd", hhmm(we));
        v.put("enabled", enabled);
        v.put("nextRunAt", next);
        return v;
    }

    // ------------------------------------------------------------- 실행기 · 실행 버퍼
    /**
     * 대기 중인 회차 하나. 버퍼는 메모리에만 있다 — 서버가 재기동하면 빈 상태로 시작하고,
     * 꺼져 있던 동안 지나간 회차는 담지 않는다(MISSED 로 기록).
     */
    static final class Pending {
        final long key;
        final long scheduleId;
        final String name;
        final String points;
        final long robotId;
        final Instant planned;
        final Instant queuedAt = Instant.now();
        final String manualBy;      // "지금 실행" 이면 누른 사람
        final CurrentUser runner;   // 손으로 실행했으면 그 사람 이름으로 작업을 요청한다(시각 회차는 계획 작성자)
        volatile String waitReason; // 아직 실행하지 못한 이유(로봇 작업 중 등)

        Pending(long key, long scheduleId, String name, String points, long robotId, Instant planned, CurrentUser runner) {
            this.key = key;
            this.scheduleId = scheduleId;
            this.name = name;
            this.points = points;
            this.robotId = robotId;
            this.planned = planned;
            this.runner = runner;
            this.manualBy = runner == null ? null : runner.login();
        }
    }

    /** 로봇이 지금 작업을 받을 수 없는 이유. fatal 이면 기다려도 소용없어 회차를 실패로 끝낸다. */
    private record Wait(String reason, boolean fatal) {
    }

    /** 서버(이 프로세스)가 뜬 시각: 이보다 앞선 예정 회차는 꺼져 있던 동안 지나간 것이다. */
    private final Instant bootTime = Instant.now();
    private final AtomicLong keys = new AtomicLong();
    /** 로봇별 대기열(예정 시각 순서). 실행(drain)은 drainLock 하나로 직렬화하고, 조회는 잠그지 않는다. */
    private final Map<Long, ConcurrentLinkedDeque<Pending>> buffer = new ConcurrentHashMap<>();
    private final Object drainLock = new Object();

    @Scheduled(fixedDelayString = "${app.schedule-poll-ms:5000}", initialDelay = 5000)
    public void tick() {
        try {
            for (var s : store.due(50)) {
                collect(s);
            }
        } catch (Exception e) {
            log.warn("schedule collect failed: {}", e.toString());
        }
        try {
            drainAll();
        } catch (Exception e) {
            log.warn("schedule drain failed: {}", e.toString());
        }
    }

    /** 때가 된 예약의 회차를 가져가 버퍼에 담는다. 재기동 전에 지나간 회차는 담지 않는다. */
    private void collect(Map<String, Object> s) {
        long id = ((Number) s.get("schedule_id")).longValue();
        Instant planned = instant(s.get("next_run_at"));
        Instant now = Instant.now();
        Instant next = rule(s).after(planned, now, zone);
        if (!store.claim(id, planned, next, next != null)) {
            return; // 그 사이 수정·끄기·다른 실행기가 가져감
        }
        if (planned.isBefore(bootTime)) {
            store.insertRun(id, planned, "MISSED", null, "서버가 꺼져 있던 동안 지나간 회차 — 재기동 후 다시 실행하지 않음", null);
            log.info("schedule {} missed {} (before boot {})", id, planned, bootTime);
            return;
        }
        enqueue(s, planned, null);
    }

    private Pending enqueue(Map<String, Object> s, Instant planned, CurrentUser runner) {
        long robotId = ((Number) s.get("robot_id")).longValue();
        var p = new Pending(keys.incrementAndGet(), ((Number) s.get("schedule_id")).longValue(), (String) s.get("name"),
                (String) s.get("points"), robotId, planned, runner);
        buffer.computeIfAbsent(robotId, k -> new ConcurrentLinkedDeque<>()).addLast(p);
        return p;
    }

    private void drainAll() {
        for (Long robotId : List.copyOf(buffer.keySet())) {
            drain(robotId);
        }
    }

    /**
     * 로봇의 대기열 앞에서부터 실행한다. 로봇이 작업 중·조종 중·연결 안 됨이면 멈추고 다음 틱에 다시 본다
     * (작업이 끝나면 이어서 실행 — 건너뛰지 않는다). 실행한 회차의 결과를 key 별로 돌려준다.
     */
    private Map<Long, Map<String, Object>> drain(long robotId) {
        Map<Long, Map<String, Object>> done = new HashMap<>();
        synchronized (drainLock) {
            var q = buffer.get(robotId);
            while (q != null && !q.isEmpty()) {
                Pending p = q.peekFirst();
                var s = store.getIncludingDeleted(p.scheduleId).orElse(null);
                if (s == null || s.get("deleted_at") != null) {
                    if (q.remove(p)) {
                        finish(p, "CANCELLED", null, "대기 중에 예약이 삭제됨", done);
                    }
                    continue;
                }
                Wait w = robotWait(robotId);
                if (w != null && !w.fatal()) {
                    q.forEach(x -> x.waitReason = w.reason());
                    break;
                }
                if (!q.remove(p)) {
                    continue; // 그 사이 사용자가 대기 취소
                }
                if (w != null) {
                    finish(p, "FAILED", null, w.reason(), done);
                    continue;
                }
                execute(s, p, done);
            }
            if (q != null && q.isEmpty()) {
                buffer.remove(robotId, q);
            }
        }
        return done;
    }

    private Wait robotWait(long robotId) {
        try {
            JsonNode r = robot.get().uri("/internal/robots/{id}", robotId).retrieve().body(JsonNode.class);
            if (r == null) return new Wait("로봇 상태를 알 수 없습니다", false);
            if (!r.path("enabled").asBoolean(true)) return new Wait("로봇이 사용 중지 상태입니다", false);
            if (!r.path("connected").asBoolean()) return new Wait("로봇과 연결되어 있지 않습니다", false);
            if (r.hasNonNull("mission") && !r.path("mission").isEmpty()) {
                return new Wait("로봇이 작업 #" + r.path("mission").path("missionId").asText() + " 를 수행 중입니다", false);
            }
            if ("USER".equals(r.path("control").path("kind").asText())) {
                return new Wait(r.path("control").path("login").asText("다른 사용자") + " 님이 조종 중입니다", false);
            }
            return null;
        } catch (HttpStatusCodeException e) {
            return new Wait("로봇을 찾을 수 없습니다", e.getStatusCode().value() == 404);
        } catch (Exception e) {
            return new Wait("로봇 서비스에 연결할 수 없습니다", false);
        }
    }

    private void execute(Map<String, Object> s, Pending p, Map<Long, Map<String, Object>> done) {
        long delay = Math.max(0, Duration.between(p.planned, Instant.now()).toSeconds());
        boolean late = delay >= 60;
        try {
            @SuppressWarnings("unchecked")
            List<Number> ids = (List<Number>) s.get("point_ids");
            String note = (p.runner != null ? "점검: " : "예약 점검: ") + s.get("name") + (s.get("note") == null ? "" : " · " + s.get("note"))
                    + (late ? " (예정 " + hhmm(p.planned.atZone(zone).toLocalTime()) + ", " + (delay / 60) + "분 지연)" : "");
            var user = p.runner != null ? p.runner
                    : new CurrentUser(((Number) s.get("created_by")).longValue(), (String) s.get("creator_login"),
                    (String) s.get("creator_role"));
            var d = tasks.create(user, p.robotId, ids.stream().map(Number::longValue).toList(), note, null, p.scheduleId);
            String reason = late ? (delay / 60) + "분 지연 실행" + (p.waitReason == null ? "" : " — " + p.waitReason) : null;
            finish(p, "CREATED", ((Number) d.get("task_id")).longValue(), reason, done);
        } catch (ResponseStatusException e) {
            finish(p, "FAILED", null, e.getReason(), done);
        } catch (Exception e) {
            finish(p, "FAILED", null, String.valueOf(e.getMessage()), done);
        }
    }

    private void finish(Pending p, String outcome, Long taskId, String reason, Map<Long, Map<String, Object>> done) {
        int delay = (int) Math.max(0, Duration.between(p.planned, Instant.now()).toSeconds());
        String r = p.manualBy == null ? reason : "실행(" + p.manualBy + ")" + (reason == null ? "" : " · " + reason);
        store.insertRun(p.scheduleId, p.planned, outcome, taskId, r, delay);
        log.info("schedule {} run: {} task={} delay={}s {}", p.scheduleId, outcome, taskId, delay, r == null ? "" : r);
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("outcome", outcome);
        m.put("taskId", taskId);
        m.put("reason", r);
        done.put(p.key, m);
    }

    /**
     * 지금 한 번 실행(다음 예정 시각은 그대로) — 예전의 "점검 요청". 로봇이 바쁘면 대기열 끝에 담고 QUEUED 를 돌려준다.
     * 실행은 누구나 할 수 있고(수정·삭제만 작성자 또는 3 사용자보다 높은 역할), 작업은 누른 사람 이름으로 요청된다.
     */
    public Map<String, Object> runNow(long id, CurrentUser u) {
        var s = store.get(id).orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND));
        Pending p = enqueue(s, Instant.now(), u);
        var done = drain(p.robotId);
        if (done.containsKey(p.key)) {
            return done.get(p.key);
        }
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("outcome", "QUEUED");
        m.put("taskId", null);
        m.put("reason", p.waitReason);
        return m;
    }

    /**
     * 로봇별 밀린 예약: 로봇이 지금 하는 작업(있으면)과 버퍼에 쌓인 회차 전부(실행 순서대로).
     * 화면 상단 지연 안내가 5초마다 읽는다. 버퍼가 빈 로봇은 넣지 않는다.
     */
    public Map<String, Object> backlog() {
        Instant now = Instant.now();
        var all = pending();
        List<Map<String, Object>> robots = new ArrayList<>();
        for (Long robotId : List.copyOf(buffer.keySet())) {
            var queue = all.stream().filter(m -> ((Number) m.get("robotId")).longValue() == robotId).toList();
            if (queue.isEmpty()) {
                continue;
            }
            Map<String, Object> r = new LinkedHashMap<>();
            r.put("robotId", robotId);
            r.put("robotCode", null);
            r.put("current", null);
            r.put("waitReason", queue.get(0).get("waitReason"));
            try {
                JsonNode st = robot.get().uri("/internal/robots/{id}", robotId).retrieve().body(JsonNode.class);
                if (st != null) {
                    r.put("robotCode", st.path("code").asText(null));
                    JsonNode mission = st.path("mission");
                    if (mission.hasNonNull("missionId")) {
                        r.put("current", currentTask(mission.path("missionId").asLong(),
                                mission.hasNonNull("currentPointId") ? mission.path("currentPointId").asLong() : null, now));
                    }
                }
            } catch (Exception e) {
                // 로봇 서비스가 안 되면 현재 작업 없이 대기열만 보여 준다
            }
            List<Map<String, Object>> items = new ArrayList<>();
            for (int i = 0; i < queue.size(); i++) {
                Map<String, Object> m = new LinkedHashMap<>(queue.get(i));
                m.put("order", i + 1);
                items.add(m);
            }
            r.put("queue", items);
            r.put("count", items.size());
            r.put("maxDelaySec", items.stream().mapToLong(m -> ((Number) m.get("delaySec")).longValue()).max().orElse(0));
            robots.add(r);
        }
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("total", robots.stream().mapToInt(r -> (Integer) r.get("count")).sum());
        m.put("robots", robots);
        return m;
    }

    /** 로봇이 지금 수행 중인 점검 작업 요약(지점 순서, 현재 지점, 요청자, 예약 작업이면 그 예약). */
    private Map<String, Object> currentTask(long taskId, Long currentPointId, Instant now) {
        var t = points.task(taskId).orElse(null);
        if (t == null) {
            return Map.of("taskId", taskId);
        }
        var tps = points.taskPoints(taskId);
        Map<String, Object> c = new LinkedHashMap<>();
        c.put("taskId", taskId);
        c.put("status", t.get("status"));
        c.put("requester", t.get("requester_login"));
        c.put("note", t.get("note"));
        c.put("scheduleId", t.get("schedule_id"));
        c.put("createdAt", t.get("created_at") instanceof Timestamp ts ? ts.toInstant().toString() : null);
        c.put("points", String.join(" → ", tps.stream().map(p -> String.valueOf(p.get("code"))).toList()));
        String cur = null;
        int seq = 0;
        for (var p : tps) {
            if (currentPointId != null && ((Number) p.get("point_id")).longValue() == currentPointId) {
                cur = String.valueOf(p.get("code"));
                seq = ((Number) p.get("seq")).intValue();
            }
        }
        c.put("currentPoint", cur);
        c.put("progress", cur == null ? null : seq + "/" + tps.size());
        c.put("elapsedSec", t.get("created_at") instanceof Timestamp ts
                ? Math.max(0, Duration.between(ts.toInstant(), now).toSeconds()) : null);
        return c;
    }

    /** 지연(대기) 중인 회차 목록: 화면의 지연 안내에 쓴다. */
    public List<Map<String, Object>> pending() {
        Instant now = Instant.now();
        List<Map<String, Object>> out = new ArrayList<>();
        buffer.values().forEach(q -> q.forEach(p -> {
            Map<String, Object> m = new LinkedHashMap<>();
            m.put("key", p.key);
            m.put("scheduleId", p.scheduleId);
            m.put("name", p.name);
            m.put("points", p.points);
            m.put("robotId", p.robotId);
            m.put("plannedAt", p.planned.toString());
            m.put("queuedAt", p.queuedAt.toString());
            m.put("delaySec", Math.max(0, Duration.between(p.planned, now).toSeconds()));
            m.put("waitReason", p.waitReason);
            m.put("manualBy", p.manualBy);
            out.add(m);
        }));
        out.sort(Comparator.comparing(m -> (String) m.get("plannedAt")));
        return out;
    }

    /** 대기 중인 회차 하나를 취소한다(실행 기록에 CANCELLED). */
    public void cancelPending(long key, CurrentUser u) {
        for (var q : buffer.values()) {
            for (Pending p : q) {
                if (p.key == key) {
                    editable(p.scheduleId, u);
                    if (q.remove(p)) {
                        finish(p, "CANCELLED", null, u.login() + " 님이 대기 취소", new HashMap<>());
                    }
                    return;
                }
            }
        }
        throw new ResponseStatusException(HttpStatus.NOT_FOUND, "이미 실행됐거나 없는 대기 항목입니다");
    }

    /** 예약을 끄거나 지우면 그 예약의 대기 회차도 치운다. */
    private void dropPending(long scheduleId, String reason) {
        for (var q : buffer.values()) {
            for (Pending p : q) {
                if (p.scheduleId == scheduleId && q.remove(p)) {
                    finish(p, "CANCELLED", null, reason, new HashMap<>());
                }
            }
        }
    }

    // ------------------------------------------------------------- 도우미
    @SuppressWarnings("unchecked")
    private ScheduleRule rule(Map<String, Object> s) {
        List<Number> days = (List<Number>) s.get("days_of_week");
        Set<Integer> ds = new LinkedHashSet<>();
        if (days != null) {
            days.forEach(d -> ds.add(d.intValue()));
        }
        return new ScheduleRule((String) s.get("kind"), instant(s.get("run_at")),
                s.get("interval_minutes") == null ? null : ((Number) s.get("interval_minutes")).intValue(),
                parseTime((String) s.get("time_of_day")), ds, parseTime((String) s.get("window_start")),
                parseTime((String) s.get("window_end")));
    }

    private static Instant instant(Object o) {
        if (o instanceof Timestamp t) return t.toInstant();
        if (o instanceof java.time.OffsetDateTime t) return t.toInstant();
        if (o instanceof Instant i) return i;
        return null;
    }

    private static LocalTime parseTime(String s) {
        return s == null ? null : LocalTime.parse(s);
    }

    private static String hhmm(LocalTime t) {
        return t == null ? null : String.format("%02d:%02d", t.getHour(), t.getMinute());
    }

    private static LocalTime time(JsonNode b, String field) {
        String s = b.path(field).asText("").trim();
        if (s.isEmpty()) return null;
        try {
            return LocalTime.parse(s.length() > 5 ? s.substring(0, 5) : s);
        } catch (DateTimeParseException e) {
            throw bad(field + " 형식은 HH:mm");
        }
    }

    /** 화면의 'YYYY-MM-DDTHH:mm' 은 예약 기준 시간대(zone)의 시각으로 해석한다. */
    private Instant localDateTime(JsonNode b, String field) {
        String s = b.path(field).asText("").trim();
        if (s.isEmpty()) return null;
        try {
            return LocalDateTime.parse(s.length() > 16 ? s.substring(0, 16) : s).atZone(zone).toInstant();
        } catch (DateTimeParseException e) {
            throw bad(field + " 형식은 YYYY-MM-DDTHH:mm");
        }
    }

    private static ResponseStatusException bad(String msg) {
        return new ResponseStatusException(HttpStatus.BAD_REQUEST, msg);
    }
}
