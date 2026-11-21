package tp3.inspection;

import jakarta.servlet.http.HttpServletRequest;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;
import tp3.common.CurrentUser;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Random;

/**
 * 포격전(이스터 에그): 픽셀 모드에서 대시보드를 열면 나오는 2인 대전. 두 전차가 번갈아 각도 · 세기를 정해 쏜다.
 *
 * - 자리: 왼쪽 전차 = 계정 sup1, 오른쪽 전차 = ADMIN 역할(또는 계정 admin1). 나머지 계정은 구경만 한다.
 * - 판정은 서버가 한다: 발사를 받으면 포탄 궤적 · 맞은 자리 · 구덩이 · 피해를 계산해 상태에 담고,
 *   두 화면은 0.4초마다 상태를 받아 같은 궤적을 그리기만 한다(화면마다 결과가 달라질 일이 없다).
 * - 상태는 메모리에만 둔다(DB 없음). 서비스를 다시 띄우면 새 판이 된다.
 * - 경로가 /api/dashboard/** 라 게이트웨이 규칙을 따로 더하지 않았다(조회는 모두, 변경은 대시보드 계정 제외).
 */
@RestController
public class DuelController {

    static final int W = 640, H = 360;          // 경기장 크기(픽셀)
    static final double G = 240;                // 중력(px/s²)
    static final double SPEED = 4.4;            // 세기 1 당 초속(px/s)
    static final double WIND_MAX = 30;          // 바람(px/s²)
    static final int BLAST = 24;                // 폭발 반지름
    static final int TANK_HALF = 8, TANK_H = 8; // 전차 반폭 · 높이
    static final int MAX_DAMAGE = 60;           // 직격 피해(체력 100)
    static final double DT = 1.0 / 60;

    private final Random rnd = new Random();
    private long gameId;
    private int[] ground = new int[W];          // 칸마다 땅 윗면의 y(위가 0)
    private final int[] tankX = new int[2];
    private final int[] hp = new int[2];
    private final double[] angle = new double[2];   // 도. 0 = 오른쪽, 90 = 위, 180 = 왼쪽
    private final double[] power = new double[2];   // 5~100
    private final String[] login = new String[2];
    private final long[] seen = new long[2];
    private int turn;
    private int winner;                         // -1 진행 중, 0·1 이긴 쪽, 2 비김
    private int seq;                            // 지금까지 쏜 횟수
    private double wind;
    private Map<String, Object> shot;           // 마지막 발사(화면이 그릴 궤적)

    public DuelController() {
        reset();
    }

    @GetMapping("/api/dashboard/duel")
    public synchronized Map<String, Object> state(HttpServletRequest req) {
        CurrentUser u = CurrentUser.from(req);
        int seat = seatOf(u);
        if (seat >= 0) {
            login[seat] = u.login();
            seen[seat] = System.currentTimeMillis();
        }
        return view(seat);
    }

    /** 조준 중인 값을 상대 화면에도 보이게 알린다(판정에는 쓰지 않는다) */
    @PostMapping("/api/dashboard/duel/aim")
    public synchronized Map<String, Object> aim(@RequestBody Map<String, Object> body, HttpServletRequest req) {
        int seat = requireSeat(req);
        angle[seat] = clamp(num(body.get("angle"), angle[seat]), 0, 180);
        power[seat] = clamp(num(body.get("power"), power[seat]), 5, 100);
        return Map.of("ok", true);
    }

    @PostMapping("/api/dashboard/duel/fire")
    public synchronized Map<String, Object> fire(@RequestBody Map<String, Object> body, HttpServletRequest req) {
        int seat = requireSeat(req);
        if (winner >= 0) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, "끝난 판입니다. 새 판을 시작하세요");
        }
        if (seat != turn) {
            throw new ResponseStatusException(HttpStatus.CONFLICT, "상대 차례입니다");
        }
        angle[seat] = clamp(num(body.get("angle"), angle[seat]), 0, 180);
        power[seat] = clamp(num(body.get("power"), power[seat]), 5, 100);
        shoot(seat);
        return view(seat);
    }

    @PostMapping("/api/dashboard/duel/reset")
    public synchronized Map<String, Object> restart(HttpServletRequest req) {
        int seat = requireSeat(req);
        reset();
        return view(seat);
    }

    // ── 자리 ──

    private static int seatOf(CurrentUser u) {
        if ("sup1".equals(u.login())) {
            return 0;
        }
        if (u.isAdmin() || "admin1".equals(u.login())) {
            return 1;
        }
        return -1;
    }

    private int requireSeat(HttpServletRequest req) {
        CurrentUser u = CurrentUser.from(req);
        int seat = seatOf(u);
        if (seat < 0) {
            throw new ResponseStatusException(HttpStatus.FORBIDDEN, "전차를 모는 계정이 아닙니다");
        }
        login[seat] = u.login();
        seen[seat] = System.currentTimeMillis();
        return seat;
    }

    // ── 판 ──

    private void reset() {
        gameId = System.currentTimeMillis();
        // 땅: 물결 몇 개를 겹친 언덕
        double p1 = rnd.nextDouble() * 6.28, p2 = rnd.nextDouble() * 6.28, p3 = rnd.nextDouble() * 6.28;
        double a1 = 30 + rnd.nextDouble() * 25, a2 = 12 + rnd.nextDouble() * 14;
        for (int x = 0; x < W; x++) {
            double y = 250 + a1 * Math.sin(x * 0.011 + p1) + a2 * Math.sin(x * 0.031 + p2) + 5 * Math.sin(x * 0.09 + p3);
            ground[x] = (int) clamp(Math.round(y), 170, 330);
        }
        tankX[0] = 60 + rnd.nextInt(90);
        tankX[1] = W - 60 - rnd.nextInt(90);
        for (int i = 0; i < 2; i++) {
            // 전차 밑은 평평하게 고른다
            int y = ground[tankX[i]];
            for (int x = tankX[i] - TANK_HALF - 2; x <= tankX[i] + TANK_HALF + 2; x++) {
                ground[x] = y;
            }
            hp[i] = 100;
            power[i] = 55;
        }
        angle[0] = 60;
        angle[1] = 120;
        turn = rnd.nextInt(2);
        winner = -1;
        seq = 0;
        shot = null;
        wind = newWind();
    }

    private double newWind() {
        return Math.round((rnd.nextDouble() * 2 - 1) * WIND_MAX);
    }

    private void shoot(int by) {
        double rad = Math.toRadians(angle[by]);
        double v = power[by] * SPEED;
        double x = tankX[by] + Math.cos(rad) * 13, y = ground[tankX[by]] - TANK_H - Math.sin(rad) * 13;
        double vx = Math.cos(rad) * v, vy = -Math.sin(rad) * v;
        List<Integer> path = new ArrayList<>();
        path.add((int) Math.round(x));
        path.add((int) Math.round(y));
        boolean hit = false;
        for (int step = 1; step <= 60 * 20; step++) {
            vx += wind * DT;
            vy += G * DT;
            x += vx * DT;
            y += vy * DT;
            if (step % 2 == 0) {
                path.add((int) Math.round(x));
                path.add((int) Math.round(y));
            }
            if (x < -200 || x > W + 200 || y > H + 40) {
                break;   // 화면 밖으로 나갔다
            }
            int xi = (int) Math.round(x);
            if (xi < 0 || xi >= W) {
                continue;   // 옆으로 벗어났지만 바람에 돌아올 수 있다
            }
            if (y >= ground[xi]) {
                hit = true;
            }
            for (int i = 0; i < 2 && !hit; i++) {
                if (i == by && step < 12) {
                    continue;   // 막 쏜 포탄이 제 전차에 걸리지 않게
                }
                int top = ground[tankX[i]] - TANK_H;
                if (hp[i] > 0 && Math.abs(x - tankX[i]) <= TANK_HALF && y >= top) {
                    hit = true;
                }
            }
            if (hit) {
                break;
            }
        }
        int hx = (int) Math.round(x), hy = (int) Math.round(y);
        path.add(hx);
        path.add(hy);
        int[] damage = new int[2];
        if (hit) {
            for (int i = 0; i < 2; i++) {
                double d = Math.hypot(hx - tankX[i], hy - (ground[tankX[i]] - TANK_H / 2.0));
                double reach = BLAST + TANK_HALF;
                if (hp[i] > 0 && d < reach) {
                    damage[i] = (int) Math.max(1, Math.round(MAX_DAMAGE * (1 - d / reach)));
                    hp[i] = Math.max(0, hp[i] - damage[i]);
                }
            }
            crater(hx, hy);
        }
        seq++;
        Map<String, Object> s = new LinkedHashMap<>();
        s.put("seq", seq);
        s.put("by", by);
        s.put("path", path);
        s.put("hit", hit);
        s.put("x", hx);
        s.put("y", hy);
        s.put("damage", damage);
        shot = s;
        if (hp[0] <= 0 && hp[1] <= 0) {
            winner = 2;
        } else if (hp[0] <= 0) {
            winner = 1;
        } else if (hp[1] <= 0) {
            winner = 0;
        } else {
            turn = 1 - by;
            wind = newWind();
        }
    }

    /** 원 모양으로 흙을 덜어 낸다. 위에 남은 흙은 그만큼 내려앉는다(땅은 칸마다 높이 하나) */
    private void crater(int cx, int cy) {
        for (int dx = -BLAST; dx <= BLAST; dx++) {
            int x = cx + dx;
            if (x < 0 || x >= W) {
                continue;
            }
            int dy = (int) Math.round(Math.sqrt(BLAST * BLAST - dx * dx));
            int bottom = cy + dy;
            if (ground[x] < bottom) {
                int removed = bottom - Math.max(ground[x], cy - dy);
                ground[x] = Math.min(H - 6, ground[x] + removed);
            }
        }
    }

    private Map<String, Object> view(int seat) {
        long now = System.currentTimeMillis();
        List<Map<String, Object>> tanks = new ArrayList<>();
        for (int i = 0; i < 2; i++) {
            Map<String, Object> t = new LinkedHashMap<>();
            t.put("x", tankX[i]);
            t.put("hp", hp[i]);
            t.put("angle", angle[i]);
            t.put("power", power[i]);
            t.put("login", login[i]);
            t.put("online", now - seen[i] < 5000);
            tanks.add(t);
        }
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("gameId", gameId);
        out.put("seat", seat);
        out.put("w", W);
        out.put("h", H);
        out.put("seq", seq);
        out.put("turn", turn);
        out.put("winner", winner);
        out.put("wind", wind);
        out.put("windMax", WIND_MAX);
        out.put("ground", ground.clone());
        out.put("tanks", tanks);
        out.put("shot", shot);
        return out;
    }

    private static double num(Object v, double fallback) {
        return v instanceof Number n ? n.doubleValue() : fallback;
    }

    private static double clamp(double v, double lo, double hi) {
        return Math.max(lo, Math.min(hi, v));
    }
}
