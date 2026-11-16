package tp3.robot.adapter;

import javax.imageio.ImageIO;
import java.awt.Color;
import java.awt.Font;
import java.awt.Graphics2D;
import java.awt.image.BufferedImage;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.PipedInputStream;
import java.io.PipedOutputStream;
import java.nio.charset.StandardCharsets;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.CopyOnWriteArrayList;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;
import java.util.function.Consumer;

/** ROS 없이 동작하는 가짜 로봇. 화면 개발과 서비스 시험용. 목표로 일정 속도로 이동하고 그림을 사진으로 만든다. */
public class MockRobotAdapter implements RobotAdapter {

    private final String code;
    private final ScheduledExecutorService sched = Executors.newSingleThreadScheduledExecutor(r -> {
        Thread t = new Thread(r, "mock-robot");
        t.setDaemon(true);
        return t;
    });
    private final List<Consumer<GoalStatus>> listeners = new CopyOnWriteArrayList<>();
    private volatile double x;
    private volatile double y;
    private volatile double yaw;
    private volatile double[] goal;   // x, y, yaw
    private volatile String goalId;
    private volatile double lin;
    private volatile double ang;
    private volatile long lastTeleop;

    public MockRobotAdapter(String code) {
        this.code = code;
    }

    @Override
    public void start() {
        sched.scheduleAtFixedRate(this::tick, 0, 100, TimeUnit.MILLISECONDS);
    }

    private void tick() {
        double dt = 0.1;
        double[] g = goal;
        if (g != null) {
            double dx = g[0] - x;
            double dy = g[1] - y;
            double d = Math.hypot(dx, dy);
            if (d < 0.05) {
                x = g[0];
                y = g[1];
                yaw = g[2];
                String id = goalId;
                goal = null;
                emit(id, "SUCCEEDED", "");
            } else {
                yaw = Math.atan2(dy, dx);
                double step = Math.min(0.2 * dt, d);
                x += step * Math.cos(yaw);
                y += step * Math.sin(yaw);
            }
        } else if (System.currentTimeMillis() - lastTeleop < 500) {
            yaw += ang * dt;
            x += lin * dt * Math.cos(yaw);
            y += lin * dt * Math.sin(yaw);
        }
    }

    private void emit(String id, String state, String reason) {
        GoalStatus s = new GoalStatus(id, state, reason);
        listeners.forEach(l -> l.accept(s));
    }

    @Override
    public State state() {
        Map<String, Long> ages = new LinkedHashMap<>();
        ages.put("odom", 100L);
        ages.put("scan", null);
        ages.put("camera", 200L);
        ages.put("battery", 1000L);
        ages.put("nav", 500L);
        return new State(true, new Pose(x, y, yaw), 87.0, null, ages, true, true);
    }

    @Override
    public Map<String, String> capabilities() {
        Map<String, String> caps = new LinkedHashMap<>();
        caps.put("odom", "VERIFIED");
        caps.put("scan", "UNSUPPORTED");
        caps.put("camera", "VERIFIED");
        caps.put("battery", "VERIFIED");
        caps.put("nav", "VERIFIED");
        return caps;
    }

    @Override
    public void sendGoal(String id, double gx, double gy, double gyaw) {
        if (id.equals(goalId) && goal != null) {
            emit(id, "ACTIVE", "");
            return;
        }
        goalId = id;
        goal = new double[]{gx, gy, gyaw};
        emit(id, "ACTIVE", "");
    }

    @Override
    public void cancelGoal(String id) {
        String cur = goalId;
        if (goal != null && ("*".equals(id) || id.equals(cur))) {
            goal = null;
            emit(cur, "CANCELED", "cancel requested");
        }
    }

    @Override
    public void onGoalStatus(Consumer<GoalStatus> listener) {
        listeners.add(listener);
    }

    @Override
    public void teleop(double linear, double angular) {
        lin = linear;
        ang = angular;
        lastTeleop = System.currentTimeMillis();
    }

    @Override
    public void stop() {
        cancelGoal("*");
        teleop(0, 0);
    }

    @Override
    public byte[] snapshot() throws IOException {
        BufferedImage img = new BufferedImage(640, 480, BufferedImage.TYPE_INT_RGB);
        Graphics2D g = img.createGraphics();
        g.setColor(new Color(200, 210, 225));
        g.fillRect(0, 0, 640, 240);
        g.setColor(new Color(160, 160, 160));
        g.fillRect(0, 240, 640, 240);
        g.setColor(new Color(180, 30, 30));
        g.fillRect(280, 150, 80, 120);
        g.setColor(Color.BLACK);
        g.setFont(new Font(Font.SANS_SERIF, Font.BOLD, 18));
        g.drawString(String.format("%s  x=%.2f y=%.2f  %tT", code, x, y, System.currentTimeMillis()), 20, 30);
        g.dispose();
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        ImageIO.write(img, "jpg", out);
        return out.toByteArray();
    }

    @Override
    public MjpegStream openStream() throws IOException {
        PipedInputStream in = new PipedInputStream(1 << 20);
        PipedOutputStream out = new PipedOutputStream(in);
        Thread t = new Thread(() -> {
            try (out) {
                while (!Thread.currentThread().isInterrupted()) {
                    byte[] jpg = snapshot();
                    out.write(("--frame\r\nContent-Type: image/jpeg\r\nContent-Length: " + jpg.length + "\r\n\r\n")
                            .getBytes(StandardCharsets.US_ASCII));
                    out.write(jpg);
                    out.write("\r\n".getBytes(StandardCharsets.US_ASCII));
                    out.flush();
                    Thread.sleep(200);
                }
            } catch (IOException | InterruptedException ignored) {
                // 읽는 쪽이 닫히면 끝낸다
            }
        }, "mock-stream");
        t.setDaemon(true);
        t.start();
        return new MjpegStream("multipart/x-mixed-replace;boundary=frame", in);
    }

    @Override
    public void close() {
        sched.shutdownNow();
    }
}
