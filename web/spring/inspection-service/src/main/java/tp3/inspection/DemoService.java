package tp3.inspection;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestClient;
import org.springframework.web.server.ResponseStatusException;
import tp3.common.CurrentUser;

import java.time.Instant;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * 시연 시나리오 자동 실행(시뮬레이션 전용). 관리자 "시연" 화면의 단추와 scripts/demo.py 가 부른다.
 *
 * 시나리오 하나 = 정해진 단계를 차례로 실행하는 것이다: 시뮬레이션 대상 바꾸기(로봇 서비스를 거쳐 sim 의 도구 실행),
 * 설정 바꾸기, 점검 시작, 상태가 될 때까지 기다리기. 사람이 하던 "도구 명령 → 화면 조작"을 한 번에 돌린다.
 * 한 번에 하나만 실행하고, 진행 기록(log)은 메모리에 둔다(서비스를 다시 띄우면 사라진다).
 *
 * 새 시나리오를 더하려면 SCENARIOS 에 설명을 넣고 run() 의 switch 에 단계를 적는다.
 */
@Service
public class DemoService {

    private static final Logger log = LoggerFactory.getLogger(DemoService.class);

    /** key → [이름, 설명, 묶음] */
    private static final Map<String, String[]> SCENARIOS = new LinkedHashMap<>();

    /** 통합 시연이 차례로 돌리는 시나리오(사람 손이 필요 없는 것만). scripts/demo.py 의 all 과 같다. */
    private static final List<String> ALL = List.of("reset", "rules-abnormal", "rules-restore", "fire-false", "fire-auto");

    static {
        SCENARIOS.put("all", new String[]{"통합 시연",
                "초기화 → 소방 관제(이상 발생 → 복구) → 화재(오탐 → 자동 투척)를 사람 손 없이 이어서 실행한다. 10분 안팎.", "통합"});
        SCENARIOS.put("fire-approval", new String[]{"화재 · 사람 승인",
                "투척 모드를 사람 승인으로 두고 화재를 낸다. 터틀봇이 출동해 도착하면 투척 승인 팝업이 뜬다 — 승인은 화면에서 직접 한다.", "소화액 투척"});
        SCENARIOS.put("fire-auto", new String[]{"화재 · 자동 투척",
                "투척 모드를 자동으로 두고 화재를 낸다. 도착 → 재판독 → 자동 투척 → 현장 감시 → 30초 뒤 열원을 없애 스스로 종료되는 것까지.", "소화액 투척"});
        SCENARIOS.put("fire-false", new String[]{"화재 · 오탐",
                "열원이 없는 곳에 비상 감지 보고를 보낸다. 터틀봇이 가서 보고 쏘지 않고 오탐으로 닫는다.", "소화액 투척"});
        SCENARIOS.put("fire-preempt", new String[]{"점검 중 화재",
                "점검을 시작한 뒤 화재를 낸다. 하던 점검을 멈추고 출동한다(사람 승인 모드, 승인은 화면에서).", "소화액 투척"});
        SCENARIOS.put("rules-abnormal", new String[]{"소방 관제 · 이상 발생",
                "소화기를 치우고 표시등을 빨강, 계기판을 0.6 으로 바꾼 뒤 세 지점을 점검한다. 비상 2건 · 경고 1건이 뜬다.", "소방 관제"});
        SCENARIOS.put("rules-restore", new String[]{"소방 관제 · 복구",
                "대상을 원위치하고 다시 점검한다. 경고가 스스로 풀린다.", "소방 관제"});
        SCENARIOS.put("reset", new String[]{"초기화",
                "열화상 인쇄물을 치우고 대상을 원위치하며, 열린 사건을 닫고 투척 모드를 사람 승인으로 되돌린다.", "정리"});
    }

    /** 시연용 규칙(이름이 이 머리로 시작). 지점에 규칙이 하나도 없을 때만 만든다. 값은 scripts/e2e_scenarios.py 와 같다. */
    private static final String RULE_TAG = "[시연]";
    private static final Map<String, String> DEMO_RULES = Map.of(
            "P1", """
                    {"name": "[시연] 소화기 비치", "kind": "OBJECT", "enabled": true,
                     "params": {"label": "fire_extinguisher", "expect": "PRESENT", "detector": "color"},
                     "regions": {"INSPECTOR": [0.0, 0.0, 1.0, 0.8]},
                     "grading": {"type": "map", "default": "UNKNOWN",
                                 "map": {"IN_REGION": "NORMAL", "OUT_OF_REGION": "WARNING", "MISSING": "EMERGENCY"}}}""",
            "P2", """
                    {"name": "[시연] 상태 표시등", "kind": "LAMP", "enabled": true, "params": {},
                     "regions": {"INSPECTOR": [0.0, 0.0, 1.0, 0.33]},
                     "grading": {"type": "map", "default": "UNKNOWN",
                                 "map": {"green": "NORMAL", "yellow": "WARNING", "red": "EMERGENCY", "off": "WARNING"}}}""",
            "P3", """
                    {"name": "[시연] 압력계", "kind": "GAUGE", "enabled": true,
                     "params": {"minAngle": 225, "maxAngle": -45, "minValue": 0, "maxValue": 1, "unit": "MPa"},
                     "regions": {"INSPECTOR": [0.0, 0.0, 1.0, 0.37]},
                     "grading": {"type": "ranges", "default": "EMERGENCY",
                                 "ranges": [{"min": 0.7, "max": 0.98, "grade": "NORMAL"},
                                            {"min": 0.5, "max": 0.7, "grade": "WARNING"}]}}""");

    private static final class Run {
        final String key;
        final String name;
        final String by;
        final Instant startedAt = Instant.now();
        final List<Map<String, Object>> log = new ArrayList<>();
        volatile String state = "RUNNING";     // RUNNING · DONE · FAILED · STOPPED
        volatile Instant endedAt;
        volatile boolean stop;

        Run(String key, String name, String by) {
            this.key = key;
            this.name = name;
            this.by = by;
        }
    }

    /** 단계가 실패하거나 중지를 누르면 던진다. */
    private static final class Abort extends RuntimeException {
        Abort(String msg) {
            super(msg);
        }
    }

    private final Store store;
    private final TaskService tasks;
    private final RuleService rules;
    private final IncidentService incidents;
    private final SettingsService settings;
    private final RestClient robot;
    private final ObjectMapper om = new ObjectMapper();
    private final ExecutorService pool = Executors.newSingleThreadExecutor(r -> {
        Thread t = new Thread(r, "demo");
        t.setDaemon(true);
        return t;
    });
    private volatile Run current;

    public DemoService(Store store, TaskService tasks, RuleService rules, IncidentService incidents,
                       SettingsService settings, @Value("${app.robot-url}") String robotUrl) {
        this.store = store;
        this.tasks = tasks;
        this.rules = rules;
        this.incidents = incidents;
        this.settings = settings;
        // 시뮬레이션 도구는 모델을 지우고 다시 만드느라 수십 초가 걸린다 — 읽기 제한 시간을 넉넉히 둔다
        SimpleClientHttpRequestFactory f = new SimpleClientHttpRequestFactory();
        f.setConnectTimeout(3000);
        f.setReadTimeout(200_000);
        this.robot = RestClient.builder().baseUrl(robotUrl).requestFactory(f).build();
    }

    // ------------------------------------------------------------- 조회 · 실행 · 중지
    public Map<String, Object> status() {
        List<Map<String, Object>> list = new ArrayList<>();
        SCENARIOS.forEach((k, v) -> list.add(Map.of("key", k, "name", v[0], "description", v[1], "group", v[2])));
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("scenarios", list);
        Run r = current;
        if (r == null) {
            m.put("run", null);
        } else {
            Map<String, Object> x = new LinkedHashMap<>();
            x.put("key", r.key);
            x.put("name", r.name);
            x.put("by", r.by);
            x.put("state", r.state);
            x.put("startedAt", r.startedAt.toString());
            x.put("endedAt", r.endedAt == null ? null : r.endedAt.toString());
            synchronized (r.log) {
                x.put("log", new ArrayList<>(r.log));
            }
            m.put("run", x);
        }
        return m;
    }

    public synchronized Map<String, Object> start(String key, CurrentUser u) {
        String[] sc = SCENARIOS.get(key);
        if (sc == null) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, "없는 시나리오: " + key);
        }
        if (current != null && "RUNNING".equals(current.state)) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, "'" + current.name + "' 을 실행 중입니다. 끝나거나 중지한 뒤 다시 누르세요");
        }
        Run r = new Run(key, sc[0], u.login());
        current = r;
        pool.submit(() -> execute(r, u));
        return status();
    }

    public Map<String, Object> stop() {
        Run r = current;
        if (r != null && "RUNNING".equals(r.state)) {
            r.stop = true;
            say(r, "warn", "중지 요청 — 지금 단계가 끝나면 멈춥니다(이미 시작된 로봇 동작은 계속됩니다. 정리는 '초기화')");
        }
        return status();
    }

    private void execute(Run r, CurrentUser u) {
        try {
            run(r, u);
            r.state = "DONE";
            say(r, "ok", "끝");
        } catch (Abort e) {
            r.state = r.stop ? "STOPPED" : "FAILED";
            say(r, r.stop ? "warn" : "error", e.getMessage());
        } catch (Exception e) {
            r.state = "FAILED";
            say(r, "error", "오류: " + e.getMessage());
            log.warn("demo {} failed", r.key, e);
        } finally {
            r.endedAt = Instant.now();
        }
    }

    // ------------------------------------------------------------- 시나리오
    private void run(Run r, CurrentUser u) throws InterruptedException {
        long robotId = simRobot(r);
        if ("all".equals(r.key)) {
            int n = 0;
            for (String key : ALL) {
                check(r);
                say(r, "step", "[" + (++n) + "/" + ALL.size() + "] " + SCENARIOS.get(key)[0]);
                scenario(r, u, robotId, key);
            }
            return;
        }
        scenario(r, u, robotId, r.key);
    }

    private void scenario(Run r, CurrentUser u, long robotId, String key) throws InterruptedException {
        switch (key) {
            case "fire-approval" -> {
                mode(r, "APPROVAL", u);
                String spot = spot(r, robotId, 0);
                long base = lastIncident();
                sim(r, robotId, "fire", "place", spot, "emergency", "--detect");
                long id = waitIncident(r, base);
                waitState(r, id, 600, "AWAITING_APPROVAL");
                say(r, "ok", "터틀봇이 투척 위치에 도착했습니다. 화면의 투척 승인 팝업에서 승인하세요(사용자 화면 또는 대시보드)");
                String st = waitState(r, id, 600, "MONITORING", "RESOLVED", "DISMISSED");
                say(r, "info", "MONITORING".equals(st) ? "투척함 · 열원이 남아 현장 감시 중입니다. 끝내려면 '초기화' 또는 사건을 닫으세요" : "사건이 닫혔습니다");
            }
            case "fire-auto" -> {
                mode(r, "AUTO", u);
                String spot = spot(r, robotId, 1);
                long base = lastIncident();
                sim(r, robotId, "fire", "place", spot, "emergency", "--detect");
                long id = waitIncident(r, base);
                String st = waitState(r, id, 600, "MONITORING", "RESOLVED", "AWAITING_APPROVAL");
                if ("AWAITING_APPROVAL".equals(st)) {
                    say(r, "warn", "자동 투척 조건을 채우지 못해 승인 대기로 넘어갔습니다 — 팝업에서 승인하세요");
                    st = waitState(r, id, 600, "MONITORING", "RESOLVED");
                }
                if ("MONITORING".equals(st)) {
                    say(r, "info", "투척함 · 현장 감시 중. 30초 뒤 열원을 없앱니다");
                    pause(r, 30);
                    sim(r, robotId, "fire", "place", spot, "normal");
                    waitState(r, id, 180, "RESOLVED");
                }
                sim(r, robotId, "fire", "clear");
                mode(r, "APPROVAL", u);
            }
            case "fire-false" -> {
                String spot = spot(r, robotId, 0);
                long base = lastIncident();
                sim(r, robotId, "fire", "place", spot, "normal");
                sim(r, robotId, "fire", "detect", spot, "emergency");
                long id = waitIncident(r, base);
                waitState(r, id, 600, "DISMISSED");
                say(r, "ok", "가 보니 열원이 없어 쏘지 않고 오탐으로 닫았습니다");
                sim(r, robotId, "fire", "clear");
            }
            case "fire-preempt" -> {
                mode(r, "APPROVAL", u);
                long task = inspect(r, robotId, u, "시연: 가로채기 대상 점검");
                waitTask(r, task, 120, "RUNNING");
                pause(r, 15);
                String spot = spot(r, robotId, 2);
                long base = lastIncident();
                sim(r, robotId, "fire", "place", spot, "emergency", "--detect");
                long id = waitIncident(r, base);
                waitState(r, id, 600, "AWAITING_APPROVAL");
                say(r, "ok", "점검 작업 #" + task + " 을 멈추고 출동했습니다. 투척 승인 팝업에서 승인하세요");
            }
            case "rules-abnormal" -> {
                ensureRules(r);
                sim(r, robotId, "target", "extinguisher", "remove");
                sim(r, robotId, "target", "lamp", "red");
                sim(r, robotId, "target", "gauge", "0.6");
                long task = inspect(r, robotId, u, "시연: 소방 관제(이상)");
                waitTask(r, task, 1200, "COMPLETED", "FAILED", "CANCELLED", "INTERRUPTED");
                reportGrades(r, task);
            }
            case "rules-restore" -> {
                ensureRules(r);
                sim(r, robotId, "target", "reset");
                long task = inspect(r, robotId, u, "시연: 소방 관제(복구)");
                waitTask(r, task, 1200, "COMPLETED", "FAILED", "CANCELLED", "INTERRUPTED");
                reportGrades(r, task);
            }
            case "reset" -> {
                for (var i : incidents.list(true, 50)) {
                    long id = ((Number) i.get("incidentId")).longValue();
                    incidents.closeByUser(id, "DISMISSED", u, "시연 초기화");
                    say(r, "info", "사건 #" + id + " 닫음");
                }
                sim(r, robotId, "fire", "clear");
                sim(r, robotId, "target", "reset");
                mode(r, "APPROVAL", u);
            }
            default -> throw new Abort("없는 시나리오");
        }
    }

    // ------------------------------------------------------------- 단계
    /** 시뮬레이션 로봇(연결된 ROSBRIDGE 로봇)을 찾는다. */
    private long simRobot(Run r) {
        try {
            JsonNode list = robot.get().uri("/internal/robots").retrieve().body(JsonNode.class);
            if (list != null) {
                for (JsonNode x : list) {
                    if (x.path("enabled").asBoolean() && x.path("connected").asBoolean()
                            && "ROSBRIDGE".equals(x.path("adapterType").asText())) {
                        say(r, "info", "로봇 " + x.path("code").asText());
                        return x.path("robotId").asLong();
                    }
                }
            }
        } catch (Exception e) {
            throw new Abort("로봇 서비스에 연결할 수 없습니다: " + e.getMessage());
        }
        throw new Abort("연결된 시뮬레이션 로봇이 없습니다");
    }

    /** 시뮬레이션 도구 실행(로봇 서비스 → sim 의 sim_control 노드). */
    private JsonNode sim(Run r, long robotId, String tool, String... args) {
        check(r);
        say(r, "step", tool + " " + String.join(" ", args));
        JsonNode res;
        try {
            res = robot.post().uri("/internal/robots/{id}/sim", robotId).contentType(MediaType.APPLICATION_JSON)
                    .body(Map.of("tool", tool, "args", List.of(args))).retrieve().body(JsonNode.class);
        } catch (Exception e) {
            throw new Abort("시뮬레이션 명령 실패(" + tool + "): " + e.getMessage()
                    + " — 시뮬레이션(sim)이 떠 있고 준비됐는지 확인하세요");
        }
        if (res == null || !res.path("ok").asBoolean()) {
            throw new Abort("시뮬레이션 도구가 실패했습니다(" + tool + "): " + (res == null ? "" : res.path("output").asText()));
        }
        return res;
    }

    /** n 번째 화재 자리 이름(fire.sh list). */
    private String spot(Run r, long robotId, int n) {
        String out = sim(r, robotId, "fire", "list").path("output").asText();
        try {
            JsonNode spots = om.readTree(out.substring(out.indexOf('{'), out.lastIndexOf('}') + 1)).path("spots");
            List<String> names = new ArrayList<>();
            spots.fieldNames().forEachRemaining(names::add);
            String name = names.get(n % names.size());
            say(r, "info", "화재 자리 " + name + " (" + spots.path(name).path("x").asDouble() + ", " + spots.path(name).path("y").asDouble() + ")");
            return name;
        } catch (Exception e) {
            throw new Abort("화재 자리 목록을 읽지 못했습니다: " + out);
        }
    }

    private void mode(Run r, String mode, CurrentUser u) {
        check(r);
        settings.put("launch.mode", om.getNodeFactory().textNode(mode), u.login());
        say(r, "step", "투척 모드 = " + ("AUTO".equals(mode) ? "자동 투척" : "사람 승인"));
    }

    private long lastIncident() {
        var l = incidents.list(false, 1);
        return l.isEmpty() ? 0 : ((Number) l.get(0).get("incidentId")).longValue();
    }

    private long waitIncident(Run r, long after) throws InterruptedException {
        say(r, "wait", "감지 보고 → 사건 생성을 기다림");
        for (int i = 0; i < 60; i++) {
            check(r);
            for (var x : incidents.list(true, 5)) {
                long id = ((Number) x.get("incidentId")).longValue();
                if (id > after) {
                    say(r, "ok", "사건 #" + id + " 생성");
                    return id;
                }
            }
            Thread.sleep(2000);
        }
        throw new Abort("사건이 만들어지지 않았습니다(감지 보고가 서버에 닿지 않음)");
    }

    /** 사건이 주어진 상태 가운데 하나가 될 때까지 기다린다. 상태가 바뀔 때마다 기록한다. */
    private String waitState(Run r, long id, int timeoutSec, String... want) throws InterruptedException {
        List<String> ok = List.of(want);
        String last = "";
        long end = System.currentTimeMillis() + timeoutSec * 1000L;
        while (System.currentTimeMillis() < end) {
            check(r);
            var d = incidents.detail(id);
            String st = String.valueOf(d.get("state"));
            if (!st.equals(last)) {
                say(r, "info", "사건 #" + id + " → " + STATE_KO.getOrDefault(st, st)
                        + (d.get("closeReason") == null ? "" : " (" + d.get("closeReason") + ")"));
                last = st;
            }
            if (ok.contains(st)) {
                return st;
            }
            if (List.of("FAILED", "DISMISSED", "RESOLVED").contains(st)) {
                throw new Abort("사건 #" + id + " 이 기대와 다르게 끝났습니다: " + STATE_KO.getOrDefault(st, st));
            }
            Thread.sleep(2000);
        }
        throw new Abort("시간 안에 진행되지 않았습니다(사건 #" + id + ", 지금 " + STATE_KO.getOrDefault(last, last) + ")");
    }

    private static final Map<String, String> STATE_KO = Map.of("DETECTED", "감지", "DISPATCHED", "출동", "ARRIVED", "도착",
            "AWAITING_APPROVAL", "투척 승인 대기", "LAUNCHING", "투척 중", "MONITORING", "투척함 · 현장 감시",
            "LAUNCHED", "투척함 · 확인 필요", "RESOLVED", "해결", "DISMISSED", "오탐으로 닫음", "FAILED", "대응 실패");

    /** P1~P3 점검을 시작한다(실행한 관리자 이름으로). */
    private long inspect(Run r, long robotId, CurrentUser u, String note) {
        check(r);
        List<Long> ids = new ArrayList<>();
        for (var p : store.points(false)) {
            if (List.of("P1", "P2", "P3").contains(String.valueOf(p.get("code")))) {
                ids.add(((Number) p.get("point_id")).longValue());
            }
        }
        if (ids.isEmpty()) {
            throw new Abort("점검 지점 P1~P3 가 없습니다");
        }
        var d = tasks.create(u, robotId, ids, note, null);
        long id = ((Number) d.get("task_id")).longValue();
        say(r, "step", "점검 작업 #" + id + " 시작 (지점 " + ids.size() + "곳)");
        return id;
    }

    private String waitTask(Run r, long taskId, int timeoutSec, String... want) throws InterruptedException {
        List<String> ok = List.of(want);
        String last = "";
        long end = System.currentTimeMillis() + timeoutSec * 1000L;
        say(r, "wait", "작업 #" + taskId + " 진행을 기다림");
        while (System.currentTimeMillis() < end) {
            check(r);
            String st = store.taskStatus(taskId);
            if (st != null && !st.equals(last)) {
                last = st;
            }
            if (ok.contains(st)) {
                say(r, "info", "작업 #" + taskId + " → " + st);
                return st;
            }
            if (st != null && TaskService.TERMINAL.contains(st)) {
                throw new Abort("작업 #" + taskId + " 이 " + st + " 로 끝났습니다");
            }
            Thread.sleep(3000);
        }
        throw new Abort("시간 안에 끝나지 않았습니다(작업 #" + taskId + ")");
    }

    /** 지점에 규칙이 하나도 없으면 시연용 규칙을 만든다. 이미 있으면 그대로 쓴다. */
    private void ensureRules(Run r) {
        for (var p : store.points(false)) {
            String code = String.valueOf(p.get("code"));
            String json = DEMO_RULES.get(code);
            long pid = ((Number) p.get("point_id")).longValue();
            if (json == null || !rules.rulesOfPoint(pid, false).isEmpty()) {
                continue;
            }
            try {
                var made = rules.create(pid, om.readTree(json));
                say(r, "step", code + " 에 규칙 '" + made.get("name") + "' 만듦");
            } catch (Exception e) {
                throw new Abort(code + " 규칙을 만들지 못했습니다: " + e.getMessage());
            }
        }
    }

    /** 작업의 관측마다 규칙 판독 결과가 올 때까지 기다려 기록에 적는다. */
    private void reportGrades(Run r, long taskId) throws InterruptedException {
        say(r, "wait", "사진 판독을 기다림");
        for (var o : store.observationsOfTask(taskId)) {
            long oid = ((Number) o.get("observation_id")).longValue();
            if (!"CAPTURED".equals(o.get("status"))) {
                say(r, "warn", o.get("point_code") + ": 촬영하지 못함(" + o.get("reason") + ")");
                continue;
            }
            List<Map<String, Object>> res = List.of();
            for (int i = 0; i < 40 && res.isEmpty(); i++) {
                check(r);
                res = rules.resultsOfObservation(oid);
                if (res.isEmpty()) {
                    Thread.sleep(3000);
                }
            }
            if (res.isEmpty()) {
                say(r, "warn", o.get("point_code") + ": 판독 결과가 오지 않음");
            }
            for (var x : res) {
                String grade = String.valueOf(x.get("grade"));
                say(r, "NORMAL".equals(grade) ? "ok" : "EMERGENCY".equals(grade) ? "error" : "warn",
                        o.get("point_code") + " · " + ((JsonNode) x.get("rule")).path("name").asText().replace(RULE_TAG, "").trim()
                                + " → " + RuleService.GRADE_KO.getOrDefault(grade, grade) + " (" + x.get("value") + ")");
            }
        }
    }

    private void pause(Run r, int sec) throws InterruptedException {
        for (int i = 0; i < sec; i++) {
            check(r);
            Thread.sleep(1000);
        }
    }

    private void check(Run r) {
        if (r.stop) {
            throw new Abort("중지했습니다");
        }
    }

    /** level: step(한 일) · wait(기다림) · info · ok · warn · error */
    private void say(Run r, String level, String text) {
        synchronized (r.log) {
            r.log.add(Map.of("at", Instant.now().toString(), "level", level, "text", text));
        }
    }
}
