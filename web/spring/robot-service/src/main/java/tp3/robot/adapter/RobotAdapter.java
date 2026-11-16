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
}
