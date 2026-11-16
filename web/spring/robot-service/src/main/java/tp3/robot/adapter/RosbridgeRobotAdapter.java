package tp3.robot.adapter;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.IOException;
import java.io.InputStream;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.net.http.WebSocket;
import java.time.Duration;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.CompletionStage;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.CopyOnWriteArrayList;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;
import java.util.function.Consumer;

/**
 * rosbridge(WebSocket JSON) 기반 어댑터. 시뮬레이션과 실제 TurtleBot3 가 같은 구현을 쓰고,
 * 주소와 토픽 이름만 config 로 다르게 준다.
 *
 * config 예:
 * 카메라 영상은 압축 토픽(<image>/compressed, JPEG)으로 받는다(imageTransport: "compressed", 기본값).
 * web_video_server 가 압축 프레임을 다시 인코딩하지 않고 그대로 전달한다. "raw" 로 두면 원본 토픽을 받는다.
 *
 * {"rosbridgeUrl":"ws://sim:9090","videoUrl":"http://sim:8080","imageTransport":"compressed",
 *  "topics":{"odom":"/odom","scan":"/scan","camera":"/camera/camera_info","image":"/camera/image_raw",
 *            "battery":"/battery_state","teleop":"/cmd_vel_teleop","goal":"/inspection/goal",
 *            "goalCancel":"/inspection/goal_cancel","goalStatus":"/inspection/goal_status"}}
 */
public class RosbridgeRobotAdapter implements RobotAdapter, WebSocket.Listener {

    private static final Logger log = LoggerFactory.getLogger(RosbridgeRobotAdapter.class);
    private static final List<String> DATA_KEYS = List.of("odom", "scan", "camera", "battery", "goalStatus", "bridge");

    private final ObjectMapper om = new ObjectMapper();
    private final String code;
    private final String url;
    private final String videoUrl;
    private final boolean compressed;
    private final Map<String, String> topics = new HashMap<>();
    private final HttpClient http = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(3)).build();
    private final ScheduledExecutorService sched = Executors.newSingleThreadScheduledExecutor(r -> {
        Thread t = new Thread(r, "rosbridge-" + Thread.currentThread().getId());
        t.setDaemon(true);
        return t;
    });
    private final Object sendLock = new Object();
    private final StringBuilder buf = new StringBuilder();
    private final Map<String, Long> lastMsg = new ConcurrentHashMap<>();
    private final List<Consumer<GoalStatus>> goalListeners = new CopyOnWriteArrayList<>();

    private volatile WebSocket ws;
    private volatile boolean closed;
    private volatile Pose pose;
    private volatile Double battery;
    private volatile Double front;
    private volatile Set<String> topicList;
    private volatile Boolean navReady;
    private volatile Pose mapPose;
    private volatile long mapPoseAt;
    private volatile double[] scanRanges;
    private volatile double scanAngleMin;
    private volatile double scanAngleInc;
    private volatile java.util.List<double[]> plan = java.util.List.of();
    private volatile long planAt;
    private volatile MapInfo mapInfo;
    private volatile byte[] mapPng;
    private long mapVersion;
    private volatile Boolean localized;

    public RosbridgeRobotAdapter(String code, JsonNode config) {
        this.code = code;
        this.url = config.path("rosbridgeUrl").asText();
        this.videoUrl = config.path("videoUrl").asText("");
        this.compressed = !"raw".equalsIgnoreCase(config.path("imageTransport").asText("compressed"));
        // 기본 토픽 이름. config 의 "topics" 로 로봇마다 바꿀 수 있다.
        Map<String, String> defaults = new HashMap<>();
        defaults.put("odom", "/odom");
        defaults.put("scan", "/scan");
        defaults.put("camera", "/camera/camera_info");
        defaults.put("image", "/camera/image_raw");
        defaults.put("battery", "/battery_state");
        defaults.put("teleop", "/cmd_vel_teleop");
        defaults.put("goal", "/inspection/goal");
        defaults.put("goalCancel", "/inspection/goal_cancel");
        defaults.put("goalStatus", "/inspection/goal_status");
        defaults.put("bridge", "/inspection/bridge_status");
        defaults.put("map", "/inspection/map");       // 로봇 측 브리지가 /map 을 주기적으로 다시 발행
        defaults.put("plan", "/plan");
        defaults.put("mapPose", "/inspection/map_pose");
        topics.putAll(defaults);
        config.path("topics").fields().forEachRemaining(e -> topics.put(e.getKey(), e.getValue().asText()));
    }

    // ------------------------------------------------------------- 연결
    @Override
    public void start() {
        connect();
        sched.scheduleWithFixedDelay(this::refreshTopicList, 5, 30, TimeUnit.SECONDS);
        // 지도는 처음 한 번만 발행(latched)되므로, 받지 못했으면 다시 구독한다
        sched.scheduleWithFixedDelay(this::resubscribeMapIfMissing, 15, 15, TimeUnit.SECONDS);
    }

    private void connect() {
        if (closed) {
            return;
        }
        http.newWebSocketBuilder().connectTimeout(Duration.ofSeconds(3))
                .buildAsync(URI.create(url), this)
                .whenComplete((w, e) -> {
                    if (e != null) {
                        log.debug("[{}] rosbridge connect failed: {}", code, e.toString());
                        reconnectLater();
                    }
                });
    }

    private void reconnectLater() {
        ws = null;
        if (!closed) {
            sched.schedule(this::connect, 2, TimeUnit.SECONDS);
        }
    }

    @Override
    public void onOpen(WebSocket webSocket) {
        this.ws = webSocket;
        log.info("[{}] rosbridge connected {}", code, url);
        webSocket.request(1);
        sched.execute(this::setup);
    }

    private void setup() {
        try {
            subscribe("odom", "nav_msgs/msg/Odometry", 200);
            subscribe("scan", "sensor_msgs/msg/LaserScan", 500);
            subscribe("camera", "sensor_msgs/msg/CameraInfo", 1000);
            subscribe("battery", "sensor_msgs/msg/BatteryState", 1000);
            subscribe("goalStatus", "std_msgs/msg/String", 0);
            subscribe("bridge", "std_msgs/msg/String", 1000);
            subscribe("mapPose", "geometry_msgs/msg/PoseStamped", 200);
            subscribe("plan", "nav_msgs/msg/Path", 1000);
            subscribe("map", "nav_msgs/msg/OccupancyGrid", 0);
            advertise("teleop", "geometry_msgs/msg/Twist");
            advertise("goal", "std_msgs/msg/String");
            advertise("goalCancel", "std_msgs/msg/String");
            refreshTopicList();
        } catch (Exception e) {
            log.warn("[{}] setup failed: {}", code, e.toString());
        }
    }

    private void subscribe(String key, String type, int throttleMs) {
        ObjectNode m = om.createObjectNode().put("op", "subscribe").put("topic", topics.get(key)).put("type", type)
                .put("queue_length", 1);
        if (throttleMs > 0) {
            m.put("throttle_rate", throttleMs);
        }
        send(m);
    }

    private void advertise(String key, String type) {
        send(om.createObjectNode().put("op", "advertise").put("topic", topics.get(key)).put("type", type));
    }

    private void resubscribeMapIfMissing() {
        if (ws != null && mapPng == null) {
            try {
                send(om.createObjectNode().put("op", "unsubscribe").put("topic", topics.get("map")));
                subscribe("map", "nav_msgs/msg/OccupancyGrid", 0);
            } catch (Exception ignored) {
                // 다음 주기에 다시 시도
            }
        }
    }

    private void refreshTopicList() {
        if (ws != null) {
            try {
                send(om.createObjectNode().put("op", "call_service").put("service", "/rosapi/topics")
                        .put("id", "topics"));
            } catch (Exception ignored) {
                // 연결이 끊긴 경우 다음 주기에 다시 시도
            }
        }
    }

    private void send(JsonNode msg) {
        WebSocket w = ws;
        if (w == null) {
            throw new IllegalStateException("rosbridge not connected");
        }
        synchronized (sendLock) {
            try {
                w.sendText(om.writeValueAsString(msg), true).get(3, TimeUnit.SECONDS);
            } catch (Exception e) {
                throw new IllegalStateException("rosbridge send failed: " + e, e);
            }
        }
    }

    @Override
    public CompletionStage<?> onText(WebSocket webSocket, CharSequence data, boolean last) {
        buf.append(data);
        if (last) {
            String text = buf.toString();
            buf.setLength(0);
            try {
                handle(om.readTree(text));
            } catch (Exception e) {
                log.debug("[{}] bad message: {}", code, e.toString());
            }
        }
        webSocket.request(1);
        return null;
    }

    @Override
    public CompletionStage<?> onClose(WebSocket webSocket, int statusCode, String reason) {
        log.info("[{}] rosbridge closed {}", code, statusCode);
        reconnectLater();
        return null;
    }

    @Override
    public void onError(WebSocket webSocket, Throwable error) {
        log.info("[{}] rosbridge error {}", code, error.toString());
        reconnectLater();
    }

    // ------------------------------------------------------------- 수신 처리
    private void handle(JsonNode n) {
        String op = n.path("op").asText();
        if ("service_response".equals(op) && "topics".equals(n.path("id").asText())) {
            Set<String> s = ConcurrentHashMap.newKeySet();
            n.path("values").path("topics").forEach(t -> s.add(t.asText()));
            topicList = s;
            return;
        }
        if (!"publish".equals(op)) {
            return;
        }
        String topic = n.path("topic").asText();
        JsonNode msg = n.path("msg");
        if (topic.equals(topics.get("map"))) {
            onMap(msg);
            return;
        }
        if (topic.equals(topics.get("mapPose"))) {
            JsonNode p = msg.path("pose");
            mapPose = new Pose(p.path("position").path("x").asDouble(), p.path("position").path("y").asDouble(),
                    yawOf(p.path("orientation")));
            mapPoseAt = System.currentTimeMillis();
            return;
        }
        if (topic.equals(topics.get("plan"))) {
            java.util.List<double[]> pts = new java.util.ArrayList<>();
            JsonNode poses = msg.path("poses");
            int step = Math.max(1, poses.size() / 300);
            for (int i = 0; i < poses.size(); i += step) {
                JsonNode q = poses.get(i).path("pose").path("position");
                pts.add(new double[]{q.path("x").asDouble(), q.path("y").asDouble()});
            }
            plan = pts;
            planAt = System.currentTimeMillis();
            return;
        }
        String key = topics.entrySet().stream().filter(e -> e.getValue().equals(topic)).map(Map.Entry::getKey)
                .filter(DATA_KEYS::contains).findFirst().orElse(null);
        if (key == null) {
            return;
        }
        lastMsg.put(key, System.currentTimeMillis());
        switch (key) {
            case "odom" -> {
                JsonNode p = msg.path("pose").path("pose");
                JsonNode q = p.path("orientation");
                double yaw = Math.atan2(2 * (q.path("w").asDouble() * q.path("z").asDouble()
                                + q.path("x").asDouble() * q.path("y").asDouble()),
                        1 - 2 * (Math.pow(q.path("y").asDouble(), 2) + Math.pow(q.path("z").asDouble(), 2)));
                pose = new Pose(p.path("position").path("x").asDouble(), p.path("position").path("y").asDouble(), yaw);
            }
            case "scan" -> {
                front = frontMin(msg);
                JsonNode rs = msg.path("ranges");
                double[] arr = new double[rs.size()];
                for (int i = 0; i < arr.length; i++) {
                    JsonNode r = rs.get(i);
                    arr[i] = r == null || !r.isNumber() ? Double.NaN : r.asDouble();
                }
                scanAngleMin = msg.path("angle_min").asDouble();
                scanAngleInc = msg.path("angle_increment").asDouble();
                scanRanges = arr;
            }
            case "battery" -> {
                double pct = msg.path("percentage").asDouble(Double.NaN);
                battery = Double.isNaN(pct) ? null : (pct <= 1.0 ? pct * 100 : pct);
            }
            case "goalStatus" -> {
                try {
                    JsonNode s = om.readTree(msg.path("data").asText());
                    GoalStatus gs = new GoalStatus(s.path("goalId").asText(), s.path("state").asText(),
                            s.path("reason").asText(""), s.path("code").asText(""), s.path("detoured").asBoolean(false),
                            s.path("recoveries").asInt(0));
                    goalListeners.forEach(l -> l.accept(gs));
                } catch (Exception e) {
                    log.debug("[{}] bad goal status", code);
                }
            }
            case "bridge" -> {
                try {
                    JsonNode s = om.readTree(msg.path("data").asText());
                    navReady = s.path("navReady").asBoolean(false);
                    localized = s.path("localized").asBoolean(false);
                } catch (Exception e) {
                    log.debug("[{}] bad bridge status", code);
                }
            }
            default -> {
            }
        }
    }

    private static double yawOf(JsonNode q) {
        return Math.atan2(2 * (q.path("w").asDouble() * q.path("z").asDouble() + q.path("x").asDouble() * q.path("y").asDouble()),
                1 - 2 * (Math.pow(q.path("y").asDouble(), 2) + Math.pow(q.path("z").asDouble(), 2)));
    }

    /** OccupancyGrid → 다듬은 지도 그림(MapRenderer). 이미지 위쪽이 지도의 +y. */
    private void onMap(JsonNode msg) {
        try {
            JsonNode info = msg.path("info");
            int w = info.path("width").asInt();
            int h = info.path("height").asInt();
            JsonNode data = msg.path("data");
            if (w <= 0 || h <= 0 || data.size() < w * h) {
                return;
            }
            int[] cells = new int[w * h];
            for (int i = 0; i < cells.length; i++) {
                cells[i] = data.get(i).asInt();
            }
            byte[] png = MapRenderer.render(w, h, info.path("resolution").asDouble(0.05), cells);   // 화면 표시용으로 다듬은 그림
            JsonNode o = info.path("origin").path("position");
            synchronized (this) {
                mapVersion++;
                mapPng = png;
                mapInfo = new MapInfo(w, h, info.path("resolution").asDouble(), o.path("x").asDouble(),
                        o.path("y").asDouble(), mapVersion);
            }
        } catch (Exception e) {
            log.debug("[{}] bad map: {}", code, e.toString());
        }
    }

    @Override
    public MapInfo mapInfo() {
        return mapInfo;
    }

    @Override
    public byte[] mapPng() {
        return mapPng;
    }

    @Override
    public MapView mapView() {
        long now = System.currentTimeMillis();
        Pose p = now - mapPoseAt < 3000 ? mapPose : null;
        java.util.List<double[]> scanPts = new java.util.ArrayList<>();
        double[] rs = scanRanges;
        if (p != null && rs != null) {
            for (int i = 0; i < rs.length; i += 2) {
                double r = rs[i];
                if (Double.isNaN(r) || Double.isInfinite(r) || r < 0.12 || r > 3.5) {
                    continue;
                }
                double a = p.yaw() + scanAngleMin + i * scanAngleInc;
                scanPts.add(new double[]{Math.round((p.x() + r * Math.cos(a)) * 100) / 100.0,
                        Math.round((p.y() + r * Math.sin(a)) * 100) / 100.0});
            }
        }
        return new MapView(p, scanPts, now - planAt < 3000 ? plan : java.util.List.of());
    }

    private static Double frontMin(JsonNode scan) {
        double min = Double.POSITIVE_INFINITY;
        double a0 = scan.path("angle_min").asDouble();
        double inc = scan.path("angle_increment").asDouble();
        double rmin = scan.path("range_min").asDouble();
        double rmax = scan.path("range_max").asDouble();
        JsonNode ranges = scan.path("ranges");
        for (int i = 0; i < ranges.size(); i++) {
            JsonNode r = ranges.get(i);
            if (r == null || r.isNull() || !r.isNumber()) {
                continue;
            }
            double ang = Math.atan2(Math.sin(a0 + i * inc), Math.cos(a0 + i * inc));
            double v = r.asDouble();
            if (Math.abs(ang) <= Math.toRadians(25) && v > rmin && v < rmax) {
                min = Math.min(min, v);
            }
        }
        return Double.isInfinite(min) ? null : min;
    }

    // ------------------------------------------------------------- RobotAdapter
    @Override
    public State state() {
        long now = System.currentTimeMillis();
        Map<String, Long> ages = new LinkedHashMap<>();
        for (String k : DATA_KEYS) {
            Long t = lastMsg.get(k);
            if (!k.equals("goalStatus")) {
                ages.put(k.equals("bridge") ? "nav" : k, t == null ? null : now - t);
            }
        }
        Long b = lastMsg.get("bridge");
        boolean fresh = b != null && now - b < 3000;
        return new State(ws != null, pose, battery, front, ages, fresh ? navReady : (b == null ? null : false),
                fresh ? localized : null);
    }

    @Override
    public Map<String, String> capabilities() {
        Map<String, String> caps = new LinkedHashMap<>();
        long now = System.currentTimeMillis();
        Set<String> tl = topicList;
        for (String k : List.of("odom", "scan", "camera", "battery", "nav")) {
            String topicKey = k.equals("nav") ? "bridge" : k;
            Long t = lastMsg.get(topicKey);
            if (k.equals("camera") && compressed && tl != null && !tl.contains(topics.get("image") + "/compressed")) {
                caps.put(k, "UNSUPPORTED");     // 압축 영상 토픽이 없다(로봇에 compressed_image_transport 필요)
            } else if (k.equals("nav") && t != null && now - t < 5000) {
                caps.put(k, Boolean.TRUE.equals(navReady) ? "VERIFIED" : "STALE");
            } else if (t != null && now - t < 5000) {
                caps.put(k, "VERIFIED");
            } else if (tl == null) {
                caps.put(k, "UNKNOWN");
            } else if (tl.contains(topics.get(topicKey))) {
                caps.put(k, t == null ? "SUPPORTED" : "STALE");
            } else {
                caps.put(k, "UNSUPPORTED");
            }
        }
        return caps;
    }

    @Override
    public void sendGoal(String goalId, double x, double y, double yaw) {
        ObjectNode data = om.createObjectNode().put("goalId", goalId).put("x", x).put("y", y).put("yaw", yaw);
        publishString("goal", data.toString());
    }

    @Override
    public void cancelGoal(String goalId) {
        publishString("goalCancel", om.createObjectNode().put("goalId", goalId).toString());
    }

    private void publishString(String key, String data) {
        send(om.createObjectNode().put("op", "publish").put("topic", topics.get(key))
                .set("msg", om.createObjectNode().put("data", data)));
    }

    @Override
    public void onGoalStatus(Consumer<GoalStatus> listener) {
        goalListeners.add(listener);
    }

    @Override
    public void teleop(double linear, double angular) {
        ObjectNode msg = om.createObjectNode();
        msg.putObject("linear").put("x", linear).put("y", 0.0).put("z", 0.0);
        msg.putObject("angular").put("x", 0.0).put("y", 0.0).put("z", angular);
        send(om.createObjectNode().put("op", "publish").put("topic", topics.get("teleop")).set("msg", msg));
    }

    @Override
    public void stop() {
        try {
            cancelGoal("*");
        } finally {
            teleop(0, 0);
        }
    }

    @Override
    public byte[] snapshot() throws IOException {
        HttpRequest req = HttpRequest.newBuilder(URI.create(videoUrl + "/snapshot?topic=" + enc(topics.get("image")) + (compressed ? "&type=ros_compressed" : "")))
                .timeout(Duration.ofSeconds(5)).build();
        try {
            HttpResponse<byte[]> res = http.send(req, HttpResponse.BodyHandlers.ofByteArray());
            if (res.statusCode() != 200 || res.body().length < 100) {
                throw new IOException("snapshot HTTP " + res.statusCode());
            }
            return res.body();
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new IOException("interrupted", e);
        }
    }

    @Override
    public MjpegStream openStream() throws IOException {
        HttpRequest req = HttpRequest.newBuilder(URI.create(videoUrl + "/stream?type=" + (compressed ? "ros_compressed" : "mjpeg&quality=60") + "&topic="
                + enc(topics.get("image")))).build();
        try {
            HttpResponse<InputStream> res = http.send(req, HttpResponse.BodyHandlers.ofInputStream());
            if (res.statusCode() != 200) {
                res.body().close();
                throw new IOException("stream HTTP " + res.statusCode());
            }
            return new MjpegStream(res.headers().firstValue("Content-Type")
                    .orElse("multipart/x-mixed-replace;boundary=boundarydonotcross"), res.body());
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new IOException("interrupted", e);
        }
    }

    /** web_video_server 는 토픽 이름을 URL 디코딩하지 않으므로 그대로 넣는다(ROS 토픽 이름은 '/', 영숫자, '_' 만 허용). */
    private static String enc(String s) {
        if (!s.matches("[A-Za-z0-9_/~]+")) {
            throw new IllegalArgumentException("invalid topic name: " + s);
        }
        return s;
    }

    @Override
    public void close() {
        closed = true;
        WebSocket w = ws;
        if (w != null) {
            w.sendClose(WebSocket.NORMAL_CLOSURE, "bye");
        }
        sched.shutdownNow();
    }
}
