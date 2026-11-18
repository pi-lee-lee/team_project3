"""주행 품질 측정: 목표 하나로 보내고 벽과의 최소 거리, 좌우 흔들림(각속도 부호 바뀜), 걸린 시간을 잰다.
docker compose exec sim bash -c 'source /opt/ros/humble/setup.bash; python3 /sim/tools/drive_probe.py 7.65 6.1 90'
"""
import math
import sys
import time

import rclpy
from geometry_msgs.msg import PoseStamped, Twist
from nav2_msgs.action import NavigateToPose
from rclpy.action import ActionClient
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import LaserScan
from tf2_ros import Buffer, TransformListener

sys.path.insert(0, '/sim/worlds')
import world_spec as W  # noqa: E402


def main():
    x, y, yaw = float(sys.argv[1]), float(sys.argv[2]), math.radians(float(sys.argv[3]) if len(sys.argv) > 3 else 0)
    rclpy.init()
    n = rclpy.create_node('drive_probe')
    st = {'min': 9.0, 'flips': 0, 'last': 0, 'samples': 0}

    def on_scan(m):
        r = [v for v in m.ranges if m.range_min < v < m.range_max]
        if r:
            st['min'] = min(st['min'], min(r))

    def on_cmd(m):
        s = (m.angular.z > 0.15) - (m.angular.z < -0.15)
        if s and st['last'] and s != st['last']:
            st['flips'] += 1
        if s:
            st['last'] = s
        st['samples'] += 1

    n.create_subscription(LaserScan, '/scan', on_scan, qos_profile_sensor_data)
    tfb = Buffer()
    TransformListener(tfb, n)
    rects = W.rects()
    st['clear'] = []

    def on_tick():
        try:
            t = tfb.lookup_transform('map', 'base_footprint', rclpy.time.Time()).transform.translation
        except Exception:
            return
        st['clear'].append(min(math.hypot(max(abs(t.x - rx) - sx / 2, 0), max(abs(t.y - ry) - sy / 2, 0)) for rx, ry, sx, sy in rects))

    n.create_timer(0.2, on_tick)
    n.create_subscription(Twist, '/cmd_vel', on_cmd, 10)
    ac = ActionClient(n, NavigateToPose, 'navigate_to_pose')
    ac.wait_for_server()
    p = PoseStamped()
    p.header.frame_id = 'map'
    p.pose.position.x, p.pose.position.y = x, y
    p.pose.orientation.z, p.pose.orientation.w = math.sin(yaw / 2), math.cos(yaw / 2)
    t0 = time.time()
    f = ac.send_goal_async(NavigateToPose.Goal(pose=p))
    rclpy.spin_until_future_complete(n, f)
    r = f.result().get_result_async()
    rclpy.spin_until_future_complete(n, r, timeout_sec=300)
    st['min'] = 9.0 if st['min'] == 9.0 else st['min']
    print(f'status={r.result().status if r.done() else "timeout"} time={time.time() - t0:.0f}s '
          f'벽까지(로봇 중심) 최소={min(st["clear"]):.2f}m 하위10%={sorted(st["clear"])[len(st["clear"]) // 10]:.2f}m 좌우 흔들림={st["flips"]}회', flush=True)
    rclpy.shutdown()


if __name__ == '__main__':
    main()
