package tp3.robot.adapter;

import java.io.IOException;
import java.io.InputStream;
import java.util.Map;
import java.util.function.Consumer;

/**
 * 로봇 연결 인터페이스. 서비스 코드는 이 인터페이스만 사용한다.
 * 구현: RosbridgeRobotAdapter(시뮬레이션·실제 TurtleBot3 공통, 주소·토픽은 설정), MockRobotAdapter(ROS 없이 화면 개발용).
 * 경계는 "목표 단위"다: 서버는 목표 지점을 보내고 결과를 받는다. 주행 제어 루프는 로봇 쪽에서 돈다.
 */
public interface RobotAdapter extends AutoCloseable {

    record Pose(double x, double y, double yaw) {
    }

    /**
     * ageMs: 데이터 종류(odom, scan, camera, battery, nav) → 마지막 수신 후 경과 ms, 받은 적 없으면 없음.
     * navReady·localized: 로봇 측 주행 시스템 준비·위치 추정 여부. 알 수 없으면 null.
     */
    record State(boolean connected, Pose pose, Double batteryPercent, Double frontObstacleM, Map<String, Long> ageMs,
                 Boolean navReady, Boolean localized) {
    }

    /**
     * 목표 결과. state: ACTIVE / SUCCEEDED / ABORTED / CANCELED.
     * code: 실패·특이 사항 분류 — BLOCKED_NO_PATH(경로 없음, 진입 불가), NAV_FAILED, NO_PROGRESS, NAV_UNAVAILABLE,
     *       DETOURED(성공했지만 우회), CANCELED 등. detoured: 장애물로 우회해 도착했는지.
     */
    record GoalStatus(String goalId, String state, String reason, String code, boolean detoured, int recoveries) {
        public GoalStatus(String goalId, String state, String reason) {
            this(goalId, state, reason, "", false, 0);
        }
    }

    record MjpegStream(String contentType, InputStream body) {
    }

    /** 지도 정보(관제 화면 지도 모드). version 은 지도가 새로 들어올 때마다 증가한다. */
    record MapInfo(int width, int height, double resolution, double originX, double originY, long version) {
    }

    /** 지도 위 실시간 표시: 지도 좌표의 로봇 위치, 라이다 점, 계획 경로(주행 중일 때). */
    record MapView(Pose pose, java.util.List<double[]> scan, java.util.List<double[]> path, DrivePlan control) {
    }

    /** 제어기가 지금 내는 속도 명령(v m/s, w rad/s)과 그 명령으로 갈 예상 호(지도 좌표). 주행 중이 아니면 MapView.control 은 null. */
    record DrivePlan(double v, double w, java.util.List<double[]> traj) {
    }

    /** 투척 명령의 결과. state: ACCEPTED / DONE / FAILED. code: NOT_READY, EMPTY, JAMMED, TIMEOUT, ESTOP, UNSUPPORTED. */
    record ActuatorStatus(String commandId, String state, String code, String reason, int launched) {
    }

    /** 투척 기구 상태(1초마다 받는 값). 기구가 없으면 어댑터가 null 을 돌려준다. */
    record ActuatorState(boolean ready, Integer remaining, String fault) {
    }

    /** 원본 점유 격자(-1 모름, 0 빈 칸, 100 막힘). 투척 위치 후보 계산에 쓴다. */
    record Grid(int width, int height, double resolution, double originX, double originY, int[] cells) {
    }

    void start();

    @Override
    void close();

    State state();

    /** 데이터 종류 → VERIFIED(데이터 수신) / SUPPORTED(토픽 있음) / UNSUPPORTED(토픽 없음) / UNKNOWN. */
    Map<String, String> capabilities();

    void sendGoal(String goalId, double x, double y, double yaw);

    /** goalId 가 "*" 이면 모든 목표 취소. */
    void cancelGoal(String goalId);

    void onGoalStatus(Consumer<GoalStatus> listener);

    void teleop(double linear, double angular);

    void stop();

    byte[] snapshot() throws IOException;

    MjpegStream openStream() throws IOException;

    /** 지도가 아직 없으면 null. */
    MapInfo mapInfo();

    /** 지도 이미지(PNG, 위쪽이 +y). 없으면 null. */
    byte[] mapPng();

    MapView mapView();

    // ------------------------------------------------------------- 투척 · 감지 (없는 로봇은 기본 동작 그대로)
    /** 투척 명령을 보낸다. 같은 commandId 는 로봇 쪽에서 한 번만 실행한다. */
    default void actuate(String commandId, String kind, int count, String paramsJson) {
        throw new UnsupportedOperationException("투척 기구가 없는 로봇입니다");
    }

    default void onActuatorStatus(Consumer<ActuatorStatus> listener) {
    }

    /** 투척 기구가 없거나 상태를 받은 적이 없으면 null. */
    default ActuatorState actuatorState() {
        return null;
    }

    /** 로봇이 스스로 감지해 보낸 것(/patrol/detection 의 JSON 글자). */
    default void onDetection(Consumer<String> listener) {
    }

    /**
     * 시뮬레이션 전용: 시뮬레이션 도구(fire · target)를 실행하게 한다(sim 의 sim_control.py 가 받는다).
     * 결과는 onSimStatus 로 온다. 시뮬레이션이 아닌 로봇은 지원하지 않는다.
     */
    default void simCommand(String id, String tool, java.util.List<String> args) {
        throw new UnsupportedOperationException("시뮬레이션 로봇이 아닙니다");
    }

    /** 결과 JSON 글자: {"id", "ok", "code", "output"} */
    default void onSimStatus(Consumer<String> listener) {
    }

    /** 지도가 아직 없으면 null. */
    default Grid grid() {
        return null;
    }
}
