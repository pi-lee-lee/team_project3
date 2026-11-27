package tp3.inspection;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.jdbc.core.simple.JdbcClient;
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
    private static final List<String> ALL = List.of("reset", "rules-abnormal", "rules-restore", "fire-false", "fire-auto", "heat-check");

    static {
        SCENARIOS.put("all", new String[]{"통합 시연",
                "초기화 → 소방 관제(이상 발생 → 복구) → 화재(오탐 → 순찰 중 자동 투척) → 열원 확인을 사람 손 없이 이어서 실행한다. 20분 안팎.", "통합"});
        SCENARIOS.put("fire-approval", new String[]{"화재 · 사람 승인",
                "C2 복도 동쪽 벽(생산동 → C2 문 맞은편)의 열화상 사진을 화재로 바꾸고 순찰을 시작한다. 지나가며 화재를 보면 순찰을 멈추고 출동하고, 도착하면 "
                        + "투척 승인 팝업이 뜬다 — 승인은 화면에서 직접 한다. 투척 뒤 불이 꺼지면(사진이 정상으로 바뀜) 해결되고 남은 지점부터 순찰을 이어 간다.", "소화액 투척"});
        SCENARIOS.put("fire-auto", new String[]{"화재 · 자동 투척",
                "투척 모드를 자동으로 두고 C2 복도 동쪽 벽의 열화상 사진을 화재로 바꾼 뒤 순찰을 시작한다. 순찰 중 발견 → 출동 → 재판독 → 자동 투척 → "
                        + "불이 꺼짐(사진이 정상으로 바뀜) → 연속 정상 확인으로 해결 → 남은 지점부터 순찰을 이어 가는 것까지.", "소화액 투척"});
        SCENARIOS.put("fire-false", new String[]{"화재 · 오탐",
                "열화상 사진은 정상인데 그 자리에서 화재 감지 보고만 보낸다. 터틀봇이 가서 보고 쏘지 않고 오탐으로 닫는다.", "소화액 투척"});
        SCENARIOS.put("heat-check", new String[]{"열원 확인",
                "전기실 문 옆 벽의 열화상 사진을 과열로 바꾸고 순찰을 시작한다. 지나가며 과열을 보면 순찰을 멈추고 그 앞에 가서 몇 초 확인한 뒤 "
                        + "사진과 함께 경고를 열고(투척은 하지 않는다) 남은 지점부터 순찰을 이어 간다. 사진을 정상으로 되돌리고 다시 순찰하면 경고가 스스로 풀린다.", "소화액 투척"});
        SCENARIOS.put("rules-abnormal", new String[]{"소방 관제 · 이상 발생",
                "소화기를 치우고, 비상구 앞에 상자를 놓고(표시등도 빨강), 압력계를 위험(빨강 구간) 사진으로 바꾼 뒤 세 지점을 점검한다. "
                        + "경고 3건(소화기 없음 · 비상구 앞 통로 막힘 · 압력계 위험 구간)이 뜬다 — 비상은 화재만이다.", "소방 관제"});
        SCENARIOS.put("rules-restore", new String[]{"소방 관제 · 복구",
                "상자를 치우고 대상을 원위치한 뒤 다시 점검한다. 경고가 스스로 풀린다.", "소방 관제"});
        SCENARIOS.put("rules-gauge", new String[]{"소방 관제 · 압력계 단계",
                "분전반(P4) 압력계를 정상 → 주의(노랑) → 위험(빨강) → 정상 사진으로 바꿔 가며 P4 만 네 번 점검한다. "
                        + "주의 · 위험은 경고 한 건(내용만 '주의 구간' → '위험 구간'으로 바뀜), 정상으로 돌아오면 스스로 풀린다. "
                        + "지난 과정은 P4 지점 이력에 회차마다 남는다.", "소방 관제"});
        SCENARIOS.put("reset", new String[]{"초기화",
                "열화상 사진을 모두 정상(꺼짐)으로, 비상구 앞 상자를 치우고 대상을 원위치하며, 열린 사건을 닫고 열원 경고를 풀고 투척 모드를 사람 승인으로 되돌린다.", "정리"});
    }

    /** 시연용 규칙(이름이 이 머리로 시작). 같은 이름의 규칙이 있으면 이 정의로 고치고, 없으면 지점에 켜진 규칙이 없을 때만
     *  만든다(관리자가 만든 규칙은 건드리지 않는다). 시험이 만든 '[e2e] …' 규칙은 시연 동안 꺼 둔다. 값은 scripts/e2e_scenarios.py 와 같다.
     *  P1 · P2 = 소화기 사진 판(인식 모델 fire_v1). P2 는 늘 받침만 있는 비교용이라 시연 점검(DEMO_POINTS)에는 넣지 않는다. */
    private static final String RULE_TAG = "[시연]";
    private static final Map<String, String> DEMO_RULES = Map.of(
            "P1", """
                    {"name": "[시연] 소화기 비치", "kind": "OBJECT", "enabled": true,
                     "params": {"label": "fire_extinguisher", "expect": "PRESENT", "detector": "model",
                                "model": "fire_v1", "className": "fire_extinguisher"},
                     "regions": {},
                     "grading": {"type": "map", "default": "UNKNOWN",
                                 "map": {"IN_REGION": "NORMAL", "OUT_OF_REGION": "WARNING", "MISSING": "WARNING"}}}""",
            "P2", """
                    {"name": "[시연] 소화기 비치", "kind": "OBJECT", "enabled": true,
                     "params": {"label": "fire_extinguisher", "expect": "PRESENT", "detector": "model",
                                "model": "fire_v1", "className": "fire_extinguisher"},
                     "regions": {},
                     "grading": {"type": "map", "default": "UNKNOWN",
                                 "map": {"IN_REGION": "NORMAL", "OUT_OF_REGION": "WARNING", "MISSING": "WARNING"}}}""",
            "P3", """
                    {"name": "[시연] 상태 표시등", "kind": "LAMP", "enabled": true, "params": {},
                     "regions": {"INSPECTOR": [0.0, 0.0, 1.0, 0.33]},
                     "grading": {"type": "map", "default": "UNKNOWN",
                                 "map": {"green": "NORMAL", "yellow": "WARNING", "red": "WARNING", "off": "WARNING"}}}""",
            // P4 = 시연 압력계 사진(초록 0~0.6 · 노랑 0.6~0.8 · 빨강 0.8~1.0). 색 띠로 계기판을 찾는다(style zone).
            // 비상은 화재만이라 노랑 · 빨강 모두 경고(판독 이유에 '주의 구간' · '위험 구간'이 붙는다)
            "P4", """
                    {"name": "[시연] 압력계", "kind": "GAUGE", "enabled": true,
                     "params": {"style": "zone", "minAngle": 225, "maxAngle": -45, "minValue": 0, "maxValue": 1, "unit": "MPa"},
                     "regions": {},
                     "grading": {"type": "ranges", "default": "WARNING",
                                 "ranges": [{"min": 0.0, "max": 0.6, "grade": "NORMAL"}]}}""");

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

    private final JdbcClient jdbc;
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

    public DemoService(JdbcClient jdbc, Store store, TaskService tasks, RuleService rules, IncidentService incidents,
                       SettingsService settings, @Value("${app.robot-url}") String robotUrl) {
        this.jdbc = jdbc;
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
                sim(r, robotId, "fire", "set", FIRE_SPOT, "emergency");
                say(r, "step", "C2 복도 동쪽 벽의 열화상 사진을 화재로 바꿈");
                long base = lastIncident();
                long task = inspect(r, robotId, u, "시연: 순찰(화재 · 사람 승인)");
                long id = waitIncident(r, base, 600);
                waitState(r, id, 600, "AWAITING_APPROVAL");
                say(r, "ok", "점검 작업 #" + task + " 을 멈추고 출동해 투척 위치에 도착했습니다. 화면의 투척 승인 팝업에서 승인하세요(사용자 화면 또는 대시보드)");
                waitState(r, id, 900, "RESOLVED");
                say(r, "ok", "불이 꺼진 것을 연속으로 확인해 사건을 닫았습니다");
                waitResumed(r, id);
                sim(r, robotId, "fire", "reset");
            }
            case "fire-auto" -> {
                mode(r, "AUTO", u);
                sim(r, robotId, "fire", "set", FIRE_SPOT, "emergency");
                say(r, "step", "C2 복도 동쪽 벽의 열화상 사진을 화재로 바꿈");
                long base = lastIncident();
                long task = inspect(r, robotId, u, "시연: 순찰(화재 · 자동 투척)");
                long id = waitIncident(r, base, 600);
                say(r, "info", "순찰 작업 #" + task + " 이 지나가며 화재를 보고 사건을 열었습니다");
                String st = waitState(r, id, 600, "MONITORING", "RESOLVED", "AWAITING_APPROVAL");
                if ("AWAITING_APPROVAL".equals(st)) {
                    say(r, "warn", "자동 투척 조건을 채우지 못해 승인 대기로 넘어갔습니다 — 팝업에서 승인하세요");
                }
                waitState(r, id, 900, "RESOLVED");
                say(r, "ok", "투척 뒤 불이 꺼진 것을 연속으로 확인해 사건을 닫았습니다");
                waitResumed(r, id);
                sim(r, robotId, "fire", "reset");
                mode(r, "APPROVAL", u);
            }
            case "fire-false" -> {
                sim(r, robotId, "fire", "set", FIRE_SPOT, "normal");
                long base = lastIncident();
                sim(r, robotId, "fire", "detect", FIRE_SPOT, "emergency");
                say(r, "step", "사진은 정상인 자리에서 화재 감지 보고만 보냄(오탐)");
                long id = waitIncident(r, base, 120);
                waitState(r, id, 600, "DISMISSED");
                say(r, "ok", "가 보니 열원이 없어 쏘지 않고 오탐으로 닫았습니다");
            }
            case "heat-check" -> {
                mode(r, "APPROVAL", u);
                sim(r, robotId, "fire", "set", HEAT_SPOT, "warning");
                say(r, "step", "전기실 문 옆 벽의 열화상 사진을 과열로 바꿈");
                long base = lastIncident();
                long task = inspect(r, robotId, u, "시연: 순찰(열원 확인)");
                long id = waitIncident(r, base, 900);
                say(r, "info", "순찰 작업 #" + task + " 이 지나가며 과열을 보고 열원 확인에 나섰습니다");
                waitState(r, id, 600, "RESOLVED");
                say(r, "ok", "열원 앞에서 확인했습니다: " + incidents.detail(id).get("closeReason"));
                waitResumed(r, id);
                sim(r, robotId, "fire", "set", HEAT_SPOT, "normal");
                say(r, "step", "열화상 사진을 정상으로 되돌리고 다시 순찰(P3 → P4 로 그 앞을 지나간다)");
                long again = inspect(r, robotId, u, "시연: 순찰(열원 정상 확인)", List.of("P3", "P4"));
                waitTask(r, again, 900, "COMPLETED", "FAILED", "CANCELLED", "INTERRUPTED");
                long open = jdbc.sql("SELECT count(*) FROM alert WHERE type = 'HEAT_WARNING' AND state <> 'RESOLVED'").query(Long.class).single();
                say(r, open == 0 ? "ok" : "warn", open == 0 ? "다음 순찰에서 정상으로 보여 열원 경고가 풀렸습니다" : "열원 경고가 아직 열려 있습니다(" + open + "건)");
            }
            case "rules-abnormal" -> {
                ensureRules(r);
                sim(r, robotId, "target", "extinguisher", "remove");
                sim(r, robotId, "obstacle", "place", "exit");
                sim(r, robotId, "target", "lamp", "red");          // 비상구 앞 상자와 함께 켜 두는 표시. 판단은 상자로 막힌 것(경고)
                sim(r, robotId, "target", "gauge", "danger");
                long task = inspect(r, robotId, u, "시연: 소방 관제(이상)");
                waitTask(r, task, 1200, "COMPLETED", "FAILED", "CANCELLED", "INTERRUPTED");
                reportGrades(r, task);
                long exit = jdbc.sql("SELECT count(*) FROM alert WHERE type = 'EXIT_BLOCKED' AND state <> 'RESOLVED'").query(Long.class).single();
                say(r, exit > 0 ? "warn" : "error", exit > 0 ? "P3 · 비상구 앞 통로 막힘 → 경고" : "비상구 앞 통로 막힘 경고가 열리지 않았습니다");
            }
            case "rules-gauge" -> {
                ensureRules(r);
                String[][] steps = {{"normal", "정상(초록)"}, {"warning", "주의(노랑)"}, {"danger", "위험(빨강)"}, {"normal", "다시 정상(초록)"}};
                for (String[] st : steps) {
                    sim(r, robotId, "target", "gauge", st[0]);
                    say(r, "step", "압력계를 " + st[1] + " 사진으로 바꿈");
                    long task = inspect(r, robotId, u, "시연: 압력계 " + st[1], List.of("P4"));
                    waitTask(r, task, 600, "COMPLETED", "FAILED", "CANCELLED", "INTERRUPTED");
                    reportGrades(r, task);
                }
            }
            case "rules-restore" -> {
                ensureRules(r);
                sim(r, robotId, "obstacle", "clear");
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
                int heat = jdbc.sql("""
                        UPDATE alert SET state = 'RESOLVED', resolved_by = ?, resolved_at = now(), updated_at = now(), comment = '시연 초기화'
                        WHERE type = 'HEAT_WARNING' AND state <> 'RESOLVED'""").param(u.login()).update();
                if (heat > 0) {
                    say(r, "info", "열원 경고 " + heat + "건 풂");
                }
                sim(r, robotId, "fire", "reset");
                sim(r, robotId, "obstacle", "clear");
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

    /** 열화상 사진 판 자리(ros/sim/src/worlds/world_spec.py THERMAL_SPOTS): 화재 시연 · 과열 시연 */
    private static final String FIRE_SPOT = "c2_east";
    private static final String HEAT_SPOT = "elec_door";

    /** 사건이 끝난 뒤 멈췄던 순찰이 남은 지점으로 다시 시작되고 끝날 때까지 기다린다. */
    private void waitResumed(Run r, long incidentId) throws InterruptedException {
        say(r, "wait", "멈췄던 순찰이 이어지기를 기다림");
        for (int i = 0; i < 60; i++) {
            check(r);
            var ev = jdbc.sql("""
                            SELECT type, detail::text FROM incident_event WHERE incident_id = ?
                            AND type IN ('PATROL_RESUMED', 'PATROL_RESUME_SKIPPED') ORDER BY event_id DESC LIMIT 1""")
                    .param(incidentId).query().listOfRows();
            if (!ev.isEmpty()) {
                JsonNode d;
                try {
                    d = om.readTree(String.valueOf(ev.get(0).get("detail")));
                } catch (Exception e) {
                    d = om.createObjectNode();
                }
                if ("PATROL_RESUME_SKIPPED".equals(ev.get(0).get("type"))) {
                    say(r, "info", "순찰을 이어 가지 않음: " + d.path("reason").asText());
                    return;
                }
                long next = d.path("nextTaskId").asLong();
                say(r, "ok", "작업 #" + d.path("taskId").asLong() + " 의 남은 지점 " + d.path("points").asInt() + "곳으로 순찰을 이어 감(작업 #" + next + ")");
                waitTask(r, next, 900, "COMPLETED", "FAILED", "CANCELLED", "INTERRUPTED");
                reportGrades(r, next);
                return;
            }
            Thread.sleep(2000);
        }
        throw new Abort("사건 #" + incidentId + " 뒤에 순찰이 이어지지 않았습니다");
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

    private long waitIncident(Run r, long after, int timeoutSec) throws InterruptedException {
        say(r, "wait", "열원 발견 → 사건 생성을 기다림");
        for (int i = 0; i < Math.max(1, timeoutSec / 2); i++) {
            check(r);
            for (var x : incidents.list(true, 5)) {
                long id = ((Number) x.get("incidentId")).longValue();
                if (id > after) {
                    say(r, "ok", "사건 #" + id + " 생성 (" + ("HEAT".equals(x.get("type")) ? "열원 확인" : "화재") + ")");
                    return id;
                }
            }
            Thread.sleep(2000);
        }
        throw new Abort("사건이 만들어지지 않았습니다(순찰 중 열원을 보지 못했거나 감지 보고가 서버에 닿지 않음)");
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

    /** 시연 점검 지점: 소화기(P1) · 표시등(P3) · 계기판(P4). */
    private static final List<String> DEMO_POINTS = List.of("P1", "P3", "P4");

    /** 시연 지점 점검을 시작한다(실행한 관리자 이름으로). */
    private long inspect(Run r, long robotId, CurrentUser u, String note) {
        return inspect(r, robotId, u, note, DEMO_POINTS);
    }

    private long inspect(Run r, long robotId, CurrentUser u, String note, List<String> codes) {
        check(r);
        List<Long> ids = new ArrayList<>();
        for (var p : store.points(false)) {
            if (codes.contains(String.valueOf(p.get("code")))) {
                ids.add(((Number) p.get("point_id")).longValue());
            }
        }
        if (ids.isEmpty()) {
            throw new Abort("점검 지점 " + codes + " 가 없습니다");
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
            if (json == null) {
                continue;
            }
            try {
                var def = om.readTree(json);
                // 시험(scripts/e2e_scenarios.py)이 만든 '[e2e] …' 규칙은 끈다 — 같은 사진을 두 규칙이 판단해 경고가 두 번 뜨지 않게.
                // 시험은 거꾸로 '[시연] …' 규칙을 끄고 돈다. 관리자가 만든 다른 규칙은 건드리지 않는다
                for (var x : rules.rulesOfPoint(pid, true)) {
                    if (String.valueOf(x.get("name")).startsWith("[e2e]")) {
                        var off = (com.fasterxml.jackson.databind.node.ObjectNode) om.valueToTree(x);
                        off.put("enabled", false);
                        rules.update(((Number) x.get("ruleId")).longValue(), off);
                        say(r, "step", code + " 의 시험 규칙 '" + x.get("name") + "' 을 끔");
                    }
                }
                var existing = rules.rulesOfPoint(pid, false);
                var same = existing.stream().filter(x -> def.path("name").asText().equals(x.get("name"))).findFirst();
                if (same.isPresent()) {
                    long id = ((Number) same.get().get("ruleId")).longValue();
                    var cur = om.valueToTree(same.get());
                    boolean changed = !def.path("params").equals(cur.path("params")) || !def.path("grading").equals(cur.path("grading"))
                            || !def.path("regions").equals(cur.path("regions")) || !cur.path("enabled").asBoolean(true);
                    if (changed) {
                        rules.update(id, def);
                        say(r, "step", code + " 규칙 '" + def.path("name").asText() + "' 을 시연 정의로 고침");
                    }
                } else if (existing.stream().noneMatch(x -> Boolean.TRUE.equals(x.get("enabled")))) {   // 켜진 규칙이 없을 때만 만든다
                    var made = rules.create(pid, def);
                    say(r, "step", code + " 에 규칙 '" + made.get("name") + "' 만듦");
                }
            } catch (Abort a) {
                throw a;
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
