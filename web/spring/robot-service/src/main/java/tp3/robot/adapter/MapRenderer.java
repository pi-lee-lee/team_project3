package tp3.robot.adapter;

import javax.imageio.ImageIO;
import java.awt.BasicStroke;
import java.awt.Color;
import java.awt.Graphics2D;
import java.awt.RenderingHints;
import java.awt.image.BufferedImage;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.util.ArrayList;
import java.util.List;

/**
 * 관제 화면용 지도 그림 — 설계도처럼 보이게 만든다.
 * 실제 지도(ros/maps/site.pgm, 로봇의 map_server·AMCL·Nav2 가 사용)와 별개로, 웹에 보낼 PNG 만 메모리에서 새로 그린다.
 * 그래서 아래 정리는 모두 표시용이며 주행·위치 추정에는 영향이 없다.
 *
 * SLAM 지도는 라이다 스캔이 쌓인 것이라 벽이 점선처럼 끊기고 잡음이 많다. 그래서 벽을 직접 그리지 않고
 * "로봇이 실제로 다닐 수 있는 바닥"을 먼저 구한 뒤, 그 경계를 직선 벽으로 그린다.
 *  1) 잡음 정리: 미지 영역(라이다가 못 본 설비 안쪽 등)은 막힌 곳으로 본다. 방 안의 작은 미지 점과 벽에 닿지 않은
 *     미지 영역(덜 훑은 바닥)만 빈 곳으로,
 *     작은 점유 점은 빈 곳으로(단 미지 영역에 붙은 조각은 막힌 쪽으로 남겨 설비 윤곽의 틈을 메운다)
 *  2) 바닥 계산: 빈 곳을 로봇 반경만큼 깎고(이 단계에서 로봇이 지날 수 없는 틈·좁은 공간이 막힌다)
 *     이어진 큰 영역만 남긴 뒤 같은 만큼 다시 넓힌다 → 로봇 너비로 지날 수 없는 열린 공간은 닫힌 공간이 된다
 *  3) 정돈: 바닥 경계의 1~2칸짜리 들쭉날쭉함을 없앤다
 *  4) 바닥 안에 떠 있는 장애물(설비·랙·책상 등, 건물 바깥과 이어지지 않은 덩어리)은 감싸는 직사각형 하나로 바꾼다.
 *     한쪽이 열린 상자도 닫히고, 윤곽의 작은 요철이 사라진다(운영에는 영향 없음: 표시용)
 *     이어서 1칸 폭의 벽 돌기·바닥 홈을 없애 벽을 곧게 편다(두께 2칸 이상인 실제 벽 끝은 그대로)
 *     SLAM 이 긴 벽을 따라가며 조금 기울어 생긴 1~2칸 계단도, 짧은 구간을 이웃한 긴 구간 높이에 맞춰 편다
 *  5) 그리기: 바닥 흰색, 다닐 수 없는 곳(설비 안쪽·벽 너머) 회색, 바닥 경계는 가로·세로 직선 구간으로 합쳐
 *     정해진 굵기의 벽선으로 그린다
 * 출력은 SCALE 배 해상도 PNG(위쪽이 지도의 +y).
 */
public final class MapRenderer {

    private static final int SCALE = 4;
    private static final float WALL_PX = 3.2f;          // SCALE 배 이미지 기준 벽선 굵기(px)
    private static final int ROBOT_RADIUS_CELLS = 4;    // 0.05m × 4 = 0.2m: Waffle 반폭 0.155m + 여유. 폭 0.4m 미만 틈은 닫힌 공간
    private static final int MIN_NOISE_BLOB = 6;
    private static final int MAX_UNKNOWN_SPECK = 40;
    private static final double MAX_BOX_SIDE_M = 2.5;   // 이보다 긴 덩어리는 벽으로 보고 직사각형으로 바꾸지 않는다
    private static final int FREE = 0;
    private static final int UNKNOWN = 1;
    private static final int OCC = 2;
    private static final Color FLOOR = new Color(0xFFFFFF);
    private static final Color BLOCKED = new Color(0xD1D1D6);
    private static final Color WALL = new Color(0x2C2C2E);

    private MapRenderer() {
    }

    /** data: OccupancyGrid 값(-1 미지, 0~100 점유 확률), 행 0 이 지도의 아래쪽. */
    public static byte[] render(int w, int h, int[] data) throws IOException {
        return render(w, h, 0.05, data);
    }

    public static byte[] render(int w, int h, double resolution, int[] data) throws IOException {
        int n = w * h;
        int[] cls = new int[n];
        for (int i = 0; i < n; i++) {
            int v = data[i];
            cls[i] = v < 0 ? UNKNOWN : v >= 50 ? OCC : FREE;
        }
        // 1) 잡음 정리
        cls = cleanNoise(cls, w, h);
        boolean[] free = new boolean[n];
        for (int i = 0; i < n; i++) {
            free[i] = cls[i] == FREE;
        }
        // 2) 바닥: 로봇 반경만큼 깎기 → 큰 영역만 → 다시 넓히기
        boolean[] core = free;
        for (int k = 0; k < ROBOT_RADIUS_CELLS; k++) {
            core = erode(core, w, h);
        }
        core = keepLargeRegions(core, w, h);
        boolean[] floor = core;
        for (int k = 0; k < ROBOT_RADIUS_CELLS; k++) {
            floor = dilate(floor, w, h);
        }
        floor = and(floor, free);
        // 3) 정돈: 작은 홈 메우기(닫기, 단 실제 벽은 지우지 않도록 빈 곳 안에서만) → 작은 돌기 깎기(열기)
        floor = and(erode(dilate(floor, w, h), w, h), free);
        floor = dilate(erode(floor, w, h), w, h);
        // 4) 떠 있는 장애물 → 직사각형
        int boxSide = (int) Math.round(MAX_BOX_SIDE_M / resolution);
        floor = boxIslands(floor, w, h, boxSide);   // 먼저 상자를 반듯하게(들쭉날쭉한 면이 좁은 틈을 메우지 않도록)
        floor = straighten(floor, w, h);
        floor = removeJogs(floor, w, h);                                   // 가로 벽 계단
        floor = transpose(removeJogs(transpose(floor, w, h), h, w), h, w);  // 세로 벽 계단
        floor = boxIslands(floor, w, h, boxSide);                          // 상자를 다시 반듯하게

        // 5) 그리기
        BufferedImage img = new BufferedImage(w * SCALE, h * SCALE, BufferedImage.TYPE_INT_RGB);
        Graphics2D g = img.createGraphics();
        g.setColor(BLOCKED);
        g.fillRect(0, 0, w * SCALE, h * SCALE);
        g.setColor(FLOOR);
        for (int r = 0; r < h; r++) {           // 바닥은 가로 구간 단위로 채운다
            int c = 0;
            while (c < w) {
                if (!floor[r * w + c]) {
                    c++;
                    continue;
                }
                int c0 = c;
                while (c < w && floor[r * w + c]) {
                    c++;
                }
                g.fillRect(c0 * SCALE, (h - 1 - r) * SCALE, (c - c0) * SCALE, SCALE);
            }
        }
        g.setRenderingHint(RenderingHints.KEY_ANTIALIASING, RenderingHints.VALUE_ANTIALIAS_ON);
        g.setRenderingHint(RenderingHints.KEY_STROKE_CONTROL, RenderingHints.VALUE_STROKE_PURE);
        g.setColor(WALL);
        g.setStroke(new BasicStroke(WALL_PX, BasicStroke.CAP_SQUARE, BasicStroke.JOIN_MITER));
        for (int[] s : boundarySegments(floor, w, h)) {
            g.drawLine(s[0], s[1], s[2], s[3]);
        }
        g.dispose();
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        ImageIO.write(img, "png", out);
        return out.toByteArray();
    }

    /** 바닥/비바닥 경계를 가로·세로로 길게 이은 선분(이미지 좌표 x0,y0,x1,y1). */
    private static List<int[]> boundarySegments(boolean[] f, int w, int h) {
        List<int[]> segs = new ArrayList<>();
        // 가로 경계: 칸 (r,c) 와 위 칸 (r+1,c) 사이. r = -1 은 지도 아래 가장자리
        for (int r = -1; r < h; r++) {
            int c = 0;
            while (c < w) {
                if (!edgeH(f, w, h, r, c)) {
                    c++;
                    continue;
                }
                int c0 = c;
                while (c < w && edgeH(f, w, h, r, c)) {
                    c++;
                }
                int y = (h - 1 - r) * SCALE;
                segs.add(new int[]{c0 * SCALE, y, c * SCALE, y});
            }
        }
        // 세로 경계: 칸 (r,c) 와 오른쪽 칸 (r,c+1) 사이
        for (int c = -1; c < w; c++) {
            int r = 0;
            while (r < h) {
                if (!edgeV(f, w, h, r, c)) {
                    r++;
                    continue;
                }
                int r0 = r;
                while (r < h && edgeV(f, w, h, r, c)) {
                    r++;
                }
                int x = (c + 1) * SCALE;
                segs.add(new int[]{x, (h - r) * SCALE, x, (h - r0) * SCALE});
            }
        }
        return segs;
    }

    /** 바닥이 아닌 영역 중 지도 가장자리에 닿지 않고 상자 크기(긴 변 maxSide 칸 이하)인 덩어리를 감싸는 직사각형으로 채운다. */
    private static boolean[] boxIslands(boolean[] floor, int w, int h, int maxSide) {
        boolean[] out = floor.clone();
        boolean[] seen = new boolean[floor.length];
        int[] stack = new int[floor.length];
        int[][] nb = {{1, 0}, {-1, 0}, {0, 1}, {0, -1}};
        for (int s = 0; s < floor.length; s++) {
            if (floor[s] || seen[s]) {
                continue;
            }
            int top = 0, rMin = h, rMax = -1, cMin = w, cMax = -1;
            boolean border = false;
            stack[top++] = s;
            seen[s] = true;
            while (top > 0) {
                int i = stack[--top];
                int r = i / w, c = i % w;
                rMin = Math.min(rMin, r); rMax = Math.max(rMax, r);
                cMin = Math.min(cMin, c); cMax = Math.max(cMax, c);
                border |= r == 0 || c == 0 || r == h - 1 || c == w - 1;
                for (int[] d : nb) {
                    int rr = r + d[0], cc = c + d[1];
                    if (rr >= 0 && cc >= 0 && rr < h && cc < w && !floor[rr * w + cc] && !seen[rr * w + cc]) {
                        seen[rr * w + cc] = true;
                        stack[top++] = rr * w + cc;
                    }
                }
            }
            if (border || Math.max(rMax - rMin, cMax - cMin) + 1 > maxSide) {
                continue;   // 건물 벽·바깥, 또는 긴 내부 벽
            }
            for (int r = rMin; r <= rMax; r++) {
                for (int c = cMin; c <= cMax; c++) {
                    out[r * w + c] = false;
                }
            }
        }
        return out;
    }

    /** 세 면 이상이 바닥인 비바닥 칸(1칸 폭 돌기)과 세 면 이상이 비바닥인 바닥 칸(1칸 폭 홈)을 뒤집는다. */
    private static boolean[] straighten(boolean[] floor, int w, int h) {
        boolean[] f = floor.clone();
        for (int pass = 0; pass < 3; pass++) {
            boolean[] next = f.clone();
            boolean changed = false;
            for (int r = 1; r < h - 1; r++) {
                for (int c = 1; c < w - 1; c++) {
                    int i = r * w + c;
                    int around = (f[i - w] ? 1 : 0) + (f[i + w] ? 1 : 0) + (f[i - 1] ? 1 : 0) + (f[i + 1] ? 1 : 0);
                    if (!f[i] && around >= 3) {
                        next[i] = true;
                        changed = true;
                    } else if (f[i] && around <= 1) {
                        next[i] = false;
                        changed = true;
                    }
                }
            }
            f = next;
            if (!changed) {
                break;
            }
        }
        return f;
    }

    private static final int MAX_JOG = 2;          // 이 칸 수 이하로 어긋난 이웃 구간은 한 직선으로 맞춘다
    private static final int MAX_JOG_RUN = 200;    // 옮길 수 있는 구간 길이(칸) 상한

    /** 가로 경계 구간: line p 는 칸 행 p 와 p+1 사이, 칸 열 [c0, c1), above = 바닥이 위쪽. */
    private record Run(int p, int c0, int c1, boolean above) {
        int len() {
            return c1 - c0;
        }
    }

    /**
     * 바로 이어진 두 가로 경계 구간의 높이가 1~2칸 다르면 한쪽을 다른 쪽 높이로 옮긴다.
     * 바닥을 넓히는 쪽으로만 옮겨 통로가 막히지 않게 한다(벽은 최소 1칸 남도록 moveRun 이 확인).
     */
    private static boolean[] removeJogs(boolean[] src, int w, int h) {
        boolean[] f = src.clone();
        for (int pass = 0; pass < 40; pass++) {
            List<Run> runs = new ArrayList<>();
            for (int p = 0; p < h - 1; p++) {
                int c = 0;
                while (c < w) {
                    boolean lo = f[p * w + c], hi = f[(p + 1) * w + c];
                    if (lo == hi) {
                        c++;
                        continue;
                    }
                    int c0 = c;
                    while (c < w && f[p * w + c] == lo && f[(p + 1) * w + c] == hi) {
                        c++;
                    }
                    runs.add(new Run(p, c0, c, hi));
                }
            }
            boolean changed = false;
            outer:
            for (Run a : runs) {
                for (Run b : runs) {
                    int d = Math.abs(b.p() - a.p());
                    boolean touching = b.c0() == a.c1() || b.c1() == a.c0();
                    if (b == a || d < 1 || d > MAX_JOG || b.above() != a.above() || !touching) {
                        continue;
                    }
                    // 바닥이 위쪽이면 경계를 내릴 때, 아래쪽이면 올릴 때 바닥이 넓어진다
                    boolean expands = a.above() ? b.p() < a.p() : b.p() > a.p();
                    if (expands && a.len() <= MAX_JOG_RUN && moveRun(f, w, h, a, b.p())) {
                        changed = true;
                        break outer;    // 마스크가 바뀌었으니 구간을 다시 구한다
                    }
                }
            }
            if (!changed) {
                break;
            }
        }
        return f;
    }

    /** 구간 a 의 경계를 line q 로 옮긴다. 옮긴 뒤에도 경계가 성립할 때만(바깥 칸 확인). */
    private static boolean moveRun(boolean[] f, int w, int h, Run a, int q) {
        int p = a.p();
        boolean floorAbove = a.above();
        int lo = Math.min(p, q) + 1, hi = Math.max(p, q);      // 바뀌는 칸 행 [lo, hi]
        int outside = q < p ? q : q + 1;                       // 새 경계 바깥쪽 행
        if (outside < 0 || outside >= h) {
            return false;
        }
        // 새 경계 아래(q 행)는 경계 아래쪽 상태, 위(q+1 행)는 경계 위쪽 상태여야 한다
        boolean value = q < p ? floorAbove : !floorAbove;      // 바뀌는 칸에 넣을 값
        boolean need = q < p ? !floorAbove : floorAbove;       // 바깥 행이 이미 가져야 할 값
        for (int c = a.c0(); c < a.c1(); c++) {
            if (f[outside * w + c] != need) {
                return false;
            }
        }
        for (int r = lo; r <= hi; r++) {
            for (int c = a.c0(); c < a.c1(); c++) {
                f[r * w + c] = value;
            }
        }
        return true;
    }

    private static boolean[] transpose(boolean[] g, int w, int h) {
        boolean[] t = new boolean[g.length];
        for (int r = 0; r < h; r++) {
            for (int c = 0; c < w; c++) {
                t[c * h + r] = g[r * w + c];
            }
        }
        return t;
    }

    private static boolean at(boolean[] f, int w, int h, int r, int c) {
        return r >= 0 && c >= 0 && r < h && c < w && f[r * w + c];
    }

    private static boolean edgeH(boolean[] f, int w, int h, int r, int c) {
        return at(f, w, h, r, c) != at(f, w, h, r + 1, c);
    }

    private static boolean edgeV(boolean[] f, int w, int h, int r, int c) {
        return at(f, w, h, r, c) != at(f, w, h, r, c + 1);
    }

    /**
     * 작은 점유 덩어리: 미지 칸에 붙어 있으면 미지(막힘)로, 아니면 빈 곳으로.
     * 작은 미지 덩어리(지도 가장자리에 닿지 않음): 빈 곳으로.
     */
    private static int[] cleanNoise(int[] cls, int w, int h) {
        int[] out = cls.clone();
        for (List<Integer> blob : blobs(cls, w, h, OCC, true)) {
            if (blob.size() >= MIN_NOISE_BLOB) {
                continue;
            }
            boolean touchesUnknown = blob.stream().anyMatch(i -> neighbors(cls, w, h, i, UNKNOWN));
            for (int i : blob) {
                out[i] = touchesUnknown ? UNKNOWN : FREE;
            }
        }
        int[] snapshot = out.clone();
        for (List<Integer> blob : blobs(snapshot, w, h, UNKNOWN, false)) {   // 4방향: 대각선으로 흩어진 점은 따로 센다
            boolean border = blob.stream().anyMatch(i -> i / w == 0 || i / w == h - 1 || i % w == 0 || i % w == w - 1);
            // 작은 미지 점, 또는 벽에 닿지 않고 빈 곳에 둘러싸인 미지 영역(라이다가 덜 훑은 바닥)은 빈 곳
            boolean touchesWall = blob.stream().anyMatch(i -> neighbors(snapshot, w, h, i, OCC));
            if (!border && (blob.size() < MAX_UNKNOWN_SPECK || !touchesWall)) {
                for (int i : blob) {
                    out[i] = FREE;
                }
            }
        }
        return out;
    }

    private static boolean neighbors(int[] cls, int w, int h, int i, int kind) {
        int r = i / w, c = i % w;
        for (int dr = -1; dr <= 1; dr++) {
            for (int dc = -1; dc <= 1; dc++) {
                int rr = r + dr, cc = c + dc;
                if (rr >= 0 && cc >= 0 && rr < h && cc < w && cls[rr * w + cc] == kind) {
                    return true;
                }
            }
        }
        return false;
    }

    /** kind 칸들의 연결 덩어리 목록(eight: 8방향, 아니면 4방향). */
    private static List<List<Integer>> blobs(int[] cls, int w, int h, int kind, boolean eight) {
        List<List<Integer>> all = new ArrayList<>();
        boolean[] seen = new boolean[cls.length];
        int[] stack = new int[cls.length];
        for (int s = 0; s < cls.length; s++) {
            if (cls[s] != kind || seen[s]) {
                continue;
            }
            List<Integer> cells = new ArrayList<>();
            int top = 0;
            stack[top++] = s;
            seen[s] = true;
            while (top > 0) {
                int i = stack[--top];
                cells.add(i);
                int r = i / w, c = i % w;
                for (int dr = -1; dr <= 1; dr++) {
                    for (int dc = -1; dc <= 1; dc++) {
                        if (!eight && dr != 0 && dc != 0) {
                            continue;
                        }
                        int rr = r + dr, cc = c + dc;
                        if (rr >= 0 && cc >= 0 && rr < h && cc < w && cls[rr * w + cc] == kind && !seen[rr * w + cc]) {
                            seen[rr * w + cc] = true;
                            stack[top++] = rr * w + cc;
                        }
                    }
                }
            }
            all.add(cells);
        }
        return all;
    }

    /** 가장 큰 영역의 5% 이상인 영역만 남긴다(벽 너머·설비 안쪽의 작은 빈 곳 제거). 4방향 연결. */
    private static boolean[] keepLargeRegions(boolean[] g, int w, int h) {
        int[] label = new int[g.length];
        List<Integer> sizes = new ArrayList<>();
        sizes.add(0);
        int[] stack = new int[g.length];
        int[][] nb = {{1, 0}, {-1, 0}, {0, 1}, {0, -1}};
        for (int s = 0; s < g.length; s++) {
            if (!g[s] || label[s] != 0) {
                continue;
            }
            int id = sizes.size(), top = 0, size = 0;
            stack[top++] = s;
            label[s] = id;
            while (top > 0) {
                int i = stack[--top];
                size++;
                int r = i / w, c = i % w;
                for (int[] d : nb) {
                    int rr = r + d[0], cc = c + d[1];
                    if (rr >= 0 && cc >= 0 && rr < h && cc < w && g[rr * w + cc] && label[rr * w + cc] == 0) {
                        label[rr * w + cc] = id;
                        stack[top++] = rr * w + cc;
                    }
                }
            }
            sizes.add(size);
        }
        int largest = sizes.stream().mapToInt(Integer::intValue).max().orElse(0);
        boolean[] out = new boolean[g.length];
        for (int i = 0; i < g.length; i++) {
            out[i] = label[i] != 0 && sizes.get(label[i]) * 20 >= largest;
        }
        return out;
    }

    private static boolean[] and(boolean[] a, boolean[] b) {
        boolean[] o = new boolean[a.length];
        for (int i = 0; i < a.length; i++) {
            o[i] = a[i] && b[i];
        }
        return o;
    }

    /** 3x3 팽창. */
    private static boolean[] dilate(boolean[] g, int w, int h) {
        boolean[] o = new boolean[g.length];
        for (int r = 0; r < h; r++) {
            for (int c = 0; c < w; c++) {
                boolean any = false;
                for (int dr = -1; dr <= 1 && !any; dr++) {
                    for (int dc = -1; dc <= 1 && !any; dc++) {
                        any = at(g, w, h, r + dr, c + dc);
                    }
                }
                o[r * w + c] = any;
            }
        }
        return o;
    }

    /** 3x3 침식(지도 밖은 비어 있는 것으로 본다). */
    private static boolean[] erode(boolean[] g, int w, int h) {
        boolean[] o = new boolean[g.length];
        for (int r = 0; r < h; r++) {
            for (int c = 0; c < w; c++) {
                boolean all = true;
                for (int dr = -1; dr <= 1 && all; dr++) {
                    for (int dc = -1; dc <= 1 && all; dc++) {
                        all = at(g, w, h, r + dr, c + dc);
                    }
                }
                o[r * w + c] = all;
            }
        }
        return o;
    }
}
