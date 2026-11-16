"""SLAM 지도 작성용 순회: 정해 둔 주행 계획을 Nav2 로 차례로 따라간다(SIM_MODE=slam 에서 실행).

실제 현장에서는 사람이 원격 조종으로 돌거나 탐사 노드를 쓴다. 시뮬레이션은 같은 결과를 반복해서 얻기 위해
경유점을 고정했다. 끝나면 save_map.sh 로 /maps/site.pgm·yaml 을 저장한다.

주행 계획 규칙(로봇이 끼지 않도록):
  - 경유점 사이는 직선 구간이고, 구간 전체에서 로봇 중심이 벽·설비와 MIN_CLEAR 이상 떨어져야 한다.
    (Nav2 가 경유점 사이를 알아서 돌아가지 않아도 되게 해서, 지도가 덜 만들어진 상태에서도 엉뚱한 틈을 시도하지 않게 한다)
  - 문은 문 가운데를 수직으로 지난다(문 앞뒤에 경유점).
  - 설비 둘레는 통로 가운데로 지나며, 각 면이 라이다에 보이도록 한다.
시작 전에 world_spec 의 벽·설비로 계획을 검사하고, 어긋나면 출발하지 않는다: python3 explore.py --check
"""
import math
import sys
import time

sys.path.insert(0, '/sim/worlds')
sys.path.insert(0, __file__.rsplit('/', 2)[0] + '/worlds')
import world_spec as W  # noqa: E402

MIN_CLEAR = 0.27     # 로봇 반경 0.22 + 지도 한 칸(0.05). 좁은 틈(예: 설비↔벽 0.65m, 양옆 여유 약 0.1m)도 지나간다
GOAL_TIMEOUT = 180   # 경유점 하나당 최대 시간(초)

# 사무실 → (북쪽 문) 전기실 → (동쪽 문) 생산동 북쪽·랙 → 서쪽 좁은 틈 → 설비 둘레 → (동쪽 문) C2 → C1 → 충전 위치
# 좁은 틈은 틈 가운데 선을 따라 직선으로 들어가고 나온다(틈 안에서 방향을 꺾지 않는다).
WAYPOINTS = [
    # 사무실
    (-0.4, 0.8), (2.35, -0.1), (2.35, 2.55), (0.95, 2.55),
    # 전기실 (사무실 북쪽 문 x=0.95) — 선반 북쪽·서쪽을 돌고, 선반과 문 모서리 사이(0.61m)로 동쪽 문을 나간다
    (0.95, 3.9), (0.3, 4.6), (-0.35, 6.55), (2.2, 6.6), (0.85, 6.6), (0.85, 4.8), (2.2, 4.8), (2.42, 4.98), (2.73, 5.38), (2.97, 5.69),
    # 생산동 북쪽: 랙 둘레
    (3.6, 5.7), (3.525, 6.775), (5.1, 6.775), (6.625, 6.775), (6.625, 4.5), (5.1, 4.2), (5.1, 6.0), (5.1, 4.1),
    # 생산동 서쪽 좁은 틈(설비 1 ↔ 벽 0.65m) → 설비 둘레
    (3.7, 4.0), (3.65, 3.3), (3.375, 2.7), (3.375, 1.125), (5.35, 1.125), (5.35, 3.0),
    # C2 (생산동 동쪽 문 y=4.1) → C1 → 사무실 동쪽 문 y=-0.1
    (6.45, 4.1), (7.65, 4.1), (7.65, 6.4), (7.65, 0.0), (4.7, -0.1), (2.0, -0.1), (0.0, 0.0),
]


def _dist_point_rect(px, py, r):
    x, y, sx, sy = r
    dx = max(abs(px - x) - sx / 2, 0.0)
    dy = max(abs(py - y) - sy / 2, 0.0)
    return math.hypot(dx, dy)


def check_plan(points=WAYPOINTS, min_clear=MIN_CLEAR, start=W.START[:2]):
    """각 직선 구간의 최소 여유 거리를 계산한다. 반환: [(구간 번호, 시작, 끝, 여유)], 문제 목록."""
    rects = W.rects()
    rows, bad = [], []
    prev = start
    for i, p in enumerate(points):
        n = max(2, int(math.dist(prev, p) / 0.02))
        clear = min(_dist_point_rect(prev[0] + (p[0] - prev[0]) * k / n, prev[1] + (p[1] - prev[1]) * k / n, r)
                    for k in range(n + 1) for r in rects)
        rows.append((i + 1, prev, p, clear))
        if clear < min_clear:
            bad.append((i + 1, prev, p, clear))
        prev = p
    return rows, bad


def main():
    rows, bad = check_plan()
    if '--check' in sys.argv:
        for i, a, b, c in rows:
            print(f'{i:2d} {a} -> {b}  여유 {c:.2f}m{"  <-- 부족" if c < MIN_CLEAR else ""}')
    if bad:
        raise SystemExit(f'주행 계획 검사 실패: {len(bad)}개 구간이 벽·설비와 {MIN_CLEAR}m 미만')
    if '--check' in sys.argv:
        return

    import rclpy
    from action_msgs.msg import GoalStatus
    from geometry_msgs.msg import PoseStamped
    from nav2_msgs.action import NavigateToPose
    from nav2_msgs.srv import ClearEntireCostmap
    from rclpy.action import ActionClient

    rclpy.init()
    node = rclpy.create_node('slam_explore')
    nav = ActionClient(node, NavigateToPose, 'navigate_to_pose')
    clears = [node.create_client(ClearEntireCostmap, f'/{c}/clear_entirely_{c}') for c in ('global_costmap', 'local_costmap')]
    if not nav.wait_for_server(timeout_sec=120):
        raise SystemExit('navigate_to_pose not available')

    def go(x, y, yaw):
        p = PoseStamped()
        p.header.frame_id = 'map'
        p.header.stamp = node.get_clock().now().to_msg()
        p.pose.position.x, p.pose.position.y = x, y
        p.pose.orientation.z, p.pose.orientation.w = math.sin(yaw / 2), math.cos(yaw / 2)
        fut = nav.send_goal_async(NavigateToPose.Goal(pose=p))
        rclpy.spin_until_future_complete(node, fut)
        h = fut.result()
        if not h.accepted:
            return False
        res = h.get_result_async()
        rclpy.spin_until_future_complete(node, res, timeout_sec=GOAL_TIMEOUT)
        if not res.done():
            h.cancel_goal_async()
            return False
        return res.result().status == GoalStatus.STATUS_SUCCEEDED

    def clear_costmaps():
        for c in clears:
            if c.wait_for_service(timeout_sec=2):
                rclpy.spin_until_future_complete(node, c.call_async(ClearEntireCostmap.Request()), timeout_sec=5)

    prev = W.START[:2]
    ok_count = 0
    for i, (x, y) in enumerate(WAYPOINTS):
        yaw = math.atan2(y - prev[1], x - prev[0])   # 도착 방향 = 진행 방향(제자리 회전을 줄인다)
        t0 = time.time()
        ok = go(x, y, yaw)
        if not ok:                                   # 잡음으로 생긴 가짜 장애물 지우고 한 번 더
            clear_costmaps()
            ok = go(x, y, yaw)
        ok_count += ok
        print(f'[{i + 1}/{len(WAYPOINTS)}] ({x}, {y}) {"ok" if ok else "FAILED"} {time.time() - t0:.0f}s', flush=True)
        prev = (x, y)
    print(f'done {ok_count}/{len(WAYPOINTS)}', flush=True)
    rclpy.shutdown()


if __name__ == '__main__':
    main()
