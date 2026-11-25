"""주행 품질 측정: 목표 하나로 보내고 벽과의 최소 거리, 좌우 흔들림(각속도 부호 바뀜), 걸린 시간, 주행 거리를 잰다.
docker compose exec sim bash -c 'source /opt/ros/$ROS_DISTRO/setup.bash; python3 /sim/tools/drive_probe.py 7.65 6.1 90'
좁은 통로 시험(obstacle.sh place gap 폭 을 놓은 뒤): 끝에 --gap 폭 을 붙이면 그 상자까지의 거리도 함께 잰다.
갑자기 나타난 장애물 시험: --drop 이름 거리 — 로봇이 그 장애물 자리에서 '거리'(m) 안으로 들어오면 그때 놓는다.
전진 멈춤 = 출발한 뒤 전진 속도 명령이 0.02m/s 아래였던 시간(제자리 회전 · 대기 포함).
최대속도 유지 = 출발한 뒤 도착까지 전진 속도 명령이 최대 속도(--vmax, 기본 0.22)의 90% 이상이었던 시간의 비율.
  "매끄러운 주행"의 기준이다: 감속 없이 최대 속도로 달릴수록 100% 에 가깝다. 평균 속도 = 주행 거리 / 걸린 시간.
"""
import math
import subprocess
import sys
import time

import rclpy
from geometry_msgs.msg import PoseStamped, TwistStamped
from nav2_msgs.action import NavigateToPose
from rclpy.action import ActionClient
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import LaserScan
from tf2_ros import Buffer, TransformListener

sys.path.insert(0, '/sim/worlds')
import world_spec as W  # noqa: E402


def main():
    argv = sys.argv[1:]
    gap = float(argv.pop(argv.index('--gap') + 1)) if '--gap' in argv else None
    argv = [a for a in argv if a != '--gap']
    vmax = float(argv.pop(argv.index('--vmax') + 1)) if '--vmax' in argv else 0.22
    argv = [a for a in argv if a != '--vmax']
    drop = None
    if '--drop' in argv:
        i = argv.index('--drop')
        drop = (argv[i + 1], float(argv[i + 2]))
        del argv[i:i + 3]
    x, y, yaw = float(argv[0]), float(argv[1]), math.radians(float(argv[2]) if len(argv) > 2 else 0)
    rclpy.init()
    n = rclpy.create_node('drive_probe')
    st = {'min': 9.0, 'flips': 0, 'last': 0, 'samples': 0}

    def on_scan(m):
        r = [v for v in m.ranges if m.range_min < v < m.range_max]
        if r:
            st['min'] = min(st['min'], min(r))

    def on_cmd(stamped):
        m = stamped.twist                   # Jazzy: 바퀴 명령은 TwistStamped
        s = (m.angular.z > 0.15) - (m.angular.z < -0.15)
        if s and st['last'] and s != st['last']:
            st['flips'] += 1
        if s:
            st['last'] = s
        st['samples'] += 1
        now = time.time()
        dt = now - st['cmd_at'] if st.get('moved') and st.get('cmd_at') else 0.0
        st['run'] += dt
        if abs(m.linear.x) >= 0.02:
            st['moved'] = True
        else:
            st['halt'] += dt
        if m.linear.x >= 0.9 * vmax:
            st['full'] += dt
        st['cmd_at'] = now

    n.create_subscription(LaserScan, '/scan', on_scan, qos_profile_sensor_data)
    tfb = Buffer()
    TransformListener(tfb, n)
    rects = W.rects() + (list(W.gap_boxes(gap).values()) if gap else [])
    st['clear'] = []
    st['dist'], st['xy'], st['halt'], st['run'], st['full'] = 0.0, None, 0.0, 0.0, 0.0

    def on_tick():
        try:
            t = tfb.lookup_transform('map', 'base_footprint', rclpy.time.Time()).transform.translation
        except Exception:
            return
        if st['xy']:
            st['dist'] += math.hypot(t.x - st['xy'][0], t.y - st['xy'][1])
        st['xy'] = (t.x, t.y)
        if drop and not st.get('dropped'):
            ox, oy, sx, sy = W.OBSTACLES[drop[0]]
            if math.hypot(t.x - ox, t.y - oy) < drop[1]:
                st['dropped'] = True
                rects.append((ox, oy, sx, sy))
                subprocess.Popen(['/sim/tools/obstacle.sh', 'place', drop[0]], stdout=subprocess.DEVNULL)
        st['clear'].append(min(math.hypot(max(abs(t.x - rx) - sx / 2, 0), max(abs(t.y - ry) - sy / 2, 0)) for rx, ry, sx, sy in rects))

    n.create_timer(0.2, on_tick)
    n.create_subscription(TwistStamped, '/cmd_vel', on_cmd, 10)
    ac = ActionClient(n, NavigateToPose, 'navigate_to_pose')
    ac.wait_for_server()
    p = PoseStamped()
    p.header.frame_id = 'map'
    p.pose.position.x, p.pose.position.y = x, y
    p.pose.orientation.z, p.pose.orientation.w = math.sin(yaw / 2), math.cos(yaw / 2)
    t0 = time.time()
    for _ in range(3):                     # 목표 응답을 놓치는 일이 있었다(에뮬레이션) → 기다리다 다시 보낸다
        f = ac.send_goal_async(NavigateToPose.Goal(pose=p))
        rclpy.spin_until_future_complete(n, f, timeout_sec=15)
        if f.done():
            break
    else:
        raise SystemExit('status=no-response Nav2 가 목표에 답하지 않음')
    r = f.result().get_result_async()
    rclpy.spin_until_future_complete(n, r, timeout_sec=300)
    st['min'] = 9.0 if st['min'] == 9.0 else st['min']
    if not r.done():                       # 시간 초과: 목표를 남겨 두지 않는다
        rclpy.spin_until_future_complete(n, f.result().cancel_goal_async(), timeout_sec=10)
    el = time.time() - t0
    print(f'status={r.result().status if r.done() else "timeout"} time={el:.0f}s 주행={st["dist"]:.1f}m '
          f'평균={st["dist"] / el:.2f}m/s 최대속도 유지={100 * st["full"] / max(st["run"], 0.1):.0f}% '
          f'벽까지(로봇 중심) 최소={min(st["clear"]):.2f}m 하위10%={sorted(st["clear"])[len(st["clear"]) // 10]:.2f}m 좌우 흔들림={st["flips"]}회 전진 멈춤={st["halt"]:.0f}s', flush=True)
    rclpy.shutdown()


if __name__ == '__main__':
    main()
