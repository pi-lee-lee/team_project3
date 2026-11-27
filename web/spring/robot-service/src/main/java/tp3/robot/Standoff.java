package tp3.robot;

import tp3.robot.adapter.RobotAdapter;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * 투척 위치 후보 계산: 대상에서 사거리만큼 떨어져 대상을 바라보는 자세들 가운데
 * (1) 로봇이 설 수 있고(주변이 빈 칸) (2) 대상과의 사이에 벽이 없는 것을 고른다.
 * 순서: 대상을 정면에서 보는 자세 먼저(설 수 있는 방향들의 한가운데 = 대상이 붙은 벽의 정면), 그다음 로봇에 가까운 순.
 * 갈 수 있는지(경로)는 여기서 보지 않는다 — 실제로 보내 보고 막히면 다음 후보로 넘어간다.
 */
final class Standoff {

    private static final double ROBOT_RADIUS = 0.24;   // 터틀봇3 와플 파이의 바깥 반지름 + 여유
    private static final double NEAR_TARGET = 0.15;    // 대상이 벽면에 붙어 있으므로 대상 바로 앞(벽 칸)은 막혀 있어도 된다.
                                                       // 너무 크게 잡으면 벽 반대편 방에서도 '보인다'고 판단한다

    private static final double RAY_BACK = 0.1;      // raycast: 벽 칸에서 로봇 쪽으로 당기는 거리

    private Standoff() {
    }

    static List<Map<String, Object>> candidates(RobotAdapter.Grid g, RobotAdapter.Pose robot, double tx, double ty,
                                                double range, double tolerance, int max) {
        List<Map<String, Object>> out = new ArrayList<>();
        double[] ranges = tolerance > 0 ? new double[]{range, range - tolerance, range + tolerance} : new double[]{range};
        for (double r : ranges) {
            for (int deg = 0; deg < 360; deg += 10) {
                double a = Math.toRadians(deg);
                double x = tx + r * Math.cos(a);
                double y = ty + r * Math.sin(a);
                if (!clear(g, x, y) || !lineOfSight(g, x, y, tx, ty)) {
                    continue;
                }
                Map<String, Object> c = new LinkedHashMap<>();
                c.put("x", round(x));
                c.put("y", round(y));
                c.put("yaw", round(Math.atan2(ty - y, tx - x)));
                c.put("rangeM", round(r));
                c.put("distanceFromRobot", robot == null ? 0.0 : round(Math.hypot(x - robot.x(), y - robot.y())));
                out.add(c);
            }
        }
        // 설 수 있는 방향들의 평균 = 대상이 붙은 벽의 정면 방향. 거기서 벗어난 각도가 작은 것이 정면에서 보는 자세다
        double sx = 0;
        double sy = 0;
        for (var c : out) {
            sx += (double) c.get("x") - tx;
            sy += (double) c.get("y") - ty;
        }
        double front = Math.atan2(sy, sx);
        for (var c : out) {
            double a = Math.atan2((double) c.get("y") - ty, (double) c.get("x") - tx);
            double off = Math.abs(Math.atan2(Math.sin(a - front), Math.cos(a - front)));
            c.put("offAxisDeg", (double) Math.round(Math.toDegrees(off)));
        }
        // 사거리가 정확한 것 먼저 → 정면에 가까운 것(20° 단위) → 로봇에 가까운 순
        out.sort(Comparator.<Map<String, Object>>comparingDouble(c -> Math.abs((double) c.get("rangeM") - range))
                .thenComparingDouble(c -> Math.floor((double) c.get("offAxisDeg") / 20))
                .thenComparingDouble(c -> (double) c.get("distanceFromRobot")));
        return out.size() > max ? out.subList(0, max) : out;
    }

    private static int cell(RobotAdapter.Grid g, double x, double y) {
        int cx = (int) Math.floor((x - g.originX()) / g.resolution());
        int cy = (int) Math.floor((y - g.originY()) / g.resolution());
        if (cx < 0 || cy < 0 || cx >= g.width() || cy >= g.height()) {
            return -1;
        }
        return g.cells()[cy * g.width() + cx];
    }

    /** 로봇 반지름 안이 모두 빈 칸(0)인가. 모르는 칸(-1)도 설 수 없는 곳으로 본다. */
    private static boolean clear(RobotAdapter.Grid g, double x, double y) {
        double step = g.resolution();
        for (double dx = -ROBOT_RADIUS; dx <= ROBOT_RADIUS; dx += step) {
            for (double dy = -ROBOT_RADIUS; dy <= ROBOT_RADIUS; dy += step) {
                if (dx * dx + dy * dy <= ROBOT_RADIUS * ROBOT_RADIUS && cell(g, x + dx, y + dy) != 0) {
                    return false;
                }
            }
        }
        return true;
    }

    private static boolean lineOfSight(RobotAdapter.Grid g, double x, double y, double tx, double ty) {
        double d = Math.hypot(tx - x, ty - y);
        int n = (int) Math.ceil(d / (g.resolution() / 2));
        for (int i = 0; i <= n; i++) {
            double t = (double) i / n;
            if (d * (1 - t) < NEAR_TARGET) {
                break;
            }
            if (cell(g, x + (tx - x) * t, y + (ty - y) * t) > 50) {
                return false;
            }
        }
        return true;
    }

    /**
     * (x, y) 에서 방향 angle(rad)로 나아가 처음 만나는 막힌 칸(벽 · 설비)의 자리. maxM 안에 없으면 null.
     * 순찰 감시가 사진 속 열원 방향을 지도 위 자리로 바꿀 때 쓴다(열원은 벽에 붙은 판이다). 출발점 둘레(로봇 몸통)는 건너뛴다.
     * 돌려주는 자리는 벽 칸에서 로봇 쪽으로 RAY_BACK 만큼 당긴 곳이다 — 벽 칸 위를 대상으로 잡으면 벽 반대편 방에서도
     * '보인다'고 판단해(lineOfSight 는 대상 둘레 NEAR_TARGET 을 건너뛴다) 판 뒷면 쪽으로 로봇을 보내게 된다.
     */
    static Map<String, Object> ray(RobotAdapter.Grid g, double x, double y, double angle, double maxM) {
        double step = g.resolution() / 2;
        for (double d = ROBOT_RADIUS; d <= maxM; d += step) {
            double px = x + d * Math.cos(angle);
            double py = y + d * Math.sin(angle);
            int c = cell(g, px, py);
            if (c > 50) {
                double back = Math.max(ROBOT_RADIUS, d - RAY_BACK);
                Map<String, Object> hit = new LinkedHashMap<>();
                hit.put("x", round(x + back * Math.cos(angle)));
                hit.put("y", round(y + back * Math.sin(angle)));
                hit.put("distanceM", round(d));
                return hit;
            }
        }
        return null;
    }

    private static double round(double v) {
        return Math.round(v * 1000) / 1000.0;
    }
}
