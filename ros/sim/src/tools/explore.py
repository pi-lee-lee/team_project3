"""SLAM 지도 작성용 순회: 정해 둔 경유점을 Nav2 로 차례로 방문한다(SIM_MODE=slam 에서 실행).

실제 현장에서는 사람이 원격 조종으로 돌거나 탐사 노드를 쓴다. 시뮬레이션은 같은 결과를 반복해서 얻기 위해
경유점을 고정했다. 끝나면 save_map.sh 로 /maps/site.pgm·yaml 을 저장한다.
"""
import math
import time

import rclpy
from action_msgs.msg import GoalStatus
from geometry_msgs.msg import PoseStamped
from nav2_msgs.action import NavigateToPose
from rclpy.action import ActionClient

# 사무실 → 전기실 → 생산동 → C1 복도 → C2 복도 → 생산동(설비 동쪽·아래쪽, 랙 사이) → 충전 위치
# 설비·랙의 모든 면을 라이다가 보도록 둘레를 지나간다(못 본 면은 지도에 미지로 남는다)
WAYPOINTS = [
    (1.8, -0.3), (2.3, 2.6), (-0.3, 2.6), (0.95, 3.7), (0.3, 4.6), (0.3, 6.6), (2.4, 6.7), (2.5, 4.3),
    (3.4, 5.65), (3.5, 6.8), (5.1, 6.8), (6.6, 6.8), (6.6, 4.1), (5.1, 3.6), (3.6, 3.4), (3.6, 1.2),
    (4.7, 1.2), (4.7, -0.1), (6.5, -0.1), (7.65, -0.1), (7.65, 2.5), (7.65, 5.0), (7.65, 6.4),
    (7.65, 4.1), (6.6, 4.1), (6.75, 3.05), (6.75, 1.15), (5.2, 1.15), (5.05, 5.6), (5.1, 3.6),
    (5.1, 1.2), (4.7, -0.1), (2.0, -0.1), (0.0, 0.0),
]


def main():
    rclpy.init()
    node = rclpy.create_node('slam_explore')
    nav = ActionClient(node, NavigateToPose, 'navigate_to_pose')
    if not nav.wait_for_server(timeout_sec=120):
        raise SystemExit('navigate_to_pose not available')
    prev = None
    for i, (x, y) in enumerate(WAYPOINTS):
        yaw = math.atan2(y - prev[1], x - prev[0]) if prev else 0.0
        p = PoseStamped()
        p.header.frame_id = 'map'
        p.header.stamp = node.get_clock().now().to_msg()
        p.pose.position.x, p.pose.position.y = x, y
        p.pose.orientation.z, p.pose.orientation.w = math.sin(yaw / 2), math.cos(yaw / 2)
        t0 = time.time()
        fut = nav.send_goal_async(NavigateToPose.Goal(pose=p))
        rclpy.spin_until_future_complete(node, fut)
        h = fut.result()
        if not h.accepted:
            print(f'[{i + 1}/{len(WAYPOINTS)}] ({x}, {y}) rejected')
            continue
        res = h.get_result_async()
        rclpy.spin_until_future_complete(node, res, timeout_sec=240)
        ok = res.done() and res.result().status == GoalStatus.STATUS_SUCCEEDED
        print(f'[{i + 1}/{len(WAYPOINTS)}] ({x}, {y}) {"ok" if ok else "FAILED"} {time.time() - t0:.0f}s', flush=True)
        if not res.done():
            h.cancel_goal_async()
        prev = (x, y)
    rclpy.shutdown()


if __name__ == '__main__':
    main()
