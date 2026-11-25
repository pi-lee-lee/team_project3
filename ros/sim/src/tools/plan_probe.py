"""계획 경로 품질 측정: 로봇을 움직이지 않고 계획기에 경로만 물어 길이와 굽이(출렁임)를 잰다.
docker compose exec sim bash -c 'source /opt/ros/$ROS_DISTRO/setup.bash; python3 /sim/tools/plan_probe.py [계획기 이름 ...]'
  계획기 이름을 주지 않으면 GridBased 하나. 구간은 충전 위치·점검 지점 P1 · P3 · P4 사이.
길이   = 경로 길이(m). 직선비 = 길이 / 출발~도착 직선 거리.
꺾임   = 진행 방향이 바뀐 양의 합(도). 곧은 길 + 모퉁이만 도는 경로면 모퉁이 각의 합과 같고, 출렁일수록 커진다.
되꺾임 = 좌우로 번갈아 꺾인 횟수(0.3m 창으로 본 방향 변화의 부호가 바뀐 수). 출렁임 그 자체다.
벽     = 경로가 벽·설비에 가장 가까운 거리(m, 로봇 중심 기준. 로봇 반지름 0.22 보다 커야 한다).
--dump 파일 을 주면 경로 좌표를 JSON 으로 남긴다.
"""
import json
import math
import sys

import rclpy
from geometry_msgs.msg import PoseStamped
from nav2_msgs.action import ComputePathToPose
from rclpy.action import ActionClient

sys.path.insert(0, '/sim/worlds')
import world_spec as W  # noqa: E402

SPOTS = {'충전': (0.0, 0.0), 'P1': (3.95, 3.9), 'P3': (7.65, 6.1), 'P4': (0.3, 4.6)}
LEGS = [('P4', 'P1'), ('P1', 'P4'), ('충전', 'P3'), ('P3', '충전'), ('P1', 'P3'), ('P4', 'P3'), ('충전', 'P1')]


def resample(pts, step=0.1):
    out, carry = [pts[0]], 0.0
    for (ax, ay), (bx, by) in zip(pts, pts[1:]):
        seg = math.hypot(bx - ax, by - ay)
        d = step - carry
        while d <= seg:
            out.append((ax + (bx - ax) * d / seg, ay + (by - ay) * d / seg))
            d += step
        carry = (carry + seg) % step
    return out


def measure(pts, rects):
    length = sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(pts, pts[1:]))
    r = resample(pts)
    k = 3                                    # 0.3m 앞뒤 방향 차
    turns = []
    for i in range(k, len(r) - k):
        a = math.atan2(r[i][1] - r[i - k][1], r[i][0] - r[i - k][0])
        b = math.atan2(r[i + k][1] - r[i][1], r[i + k][0] - r[i][0])
        turns.append(math.atan2(math.sin(b - a), math.cos(b - a)))
    total = math.degrees(sum(abs(t) for t in turns)) / k
    flips, last = 0, 0
    for t in turns:
        s = 1 if t > 0.05 else -1 if t < -0.05 else 0
        if s and last and s != last:
            flips += 1
        last = s or last
    wall = min(math.hypot(max(abs(x - rx) - sx / 2, 0), max(abs(y - ry) - sy / 2, 0)) for x, y in r for rx, ry, sx, sy in rects)
    return length, total, flips, wall


def main():
    argv = sys.argv[1:]
    dump = argv.pop(argv.index('--dump') + 1) if '--dump' in argv else None
    planners = [a for a in argv if a != '--dump'] or ['GridBased']
    rclpy.init()
    n = rclpy.create_node('plan_probe')
    ac = ActionClient(n, ComputePathToPose, 'compute_path_to_pose')
    ac.wait_for_server()
    rects, out = W.rects(), {}

    def pose(x, y):
        p = PoseStamped()
        p.header.frame_id = 'map'
        p.pose.position.x, p.pose.position.y, p.pose.orientation.w = float(x), float(y), 1.0
        return p

    for pl in planners:
        print(f'== {pl}')
        tot = [0.0, 0.0, 0]
        for a, b in LEGS:
            req = ComputePathToPose.Goal(start=pose(*SPOTS[a]), goal=pose(*SPOTS[b]), planner_id=pl, use_start=True)
            f = ac.send_goal_async(req)
            rclpy.spin_until_future_complete(n, f, timeout_sec=20)
            gh = f.result()
            if not gh or not gh.accepted:
                print(f'  {a}→{b}: 거부')
                continue
            rf = gh.get_result_async()
            rclpy.spin_until_future_complete(n, rf, timeout_sec=30)
            pts = [(p.pose.position.x, p.pose.position.y) for p in rf.result().result.path.poses] if rf.result() else []
            if len(pts) < 2:
                print(f'  {a}→{b}: 경로 없음')
                continue
            ln, turn, flips, wall = measure(pts, rects)
            direct = math.hypot(SPOTS[b][0] - SPOTS[a][0], SPOTS[b][1] - SPOTS[a][1])
            print(f'  {a}→{b}: 길이={ln:.2f}m 직선비={ln / direct:.2f} 꺾임={turn:.0f}도 되꺾임={flips}회 벽={wall:.2f}m 점={len(pts)}')
            tot[0] += ln; tot[1] += turn; tot[2] += flips
            out[f'{pl}:{a}>{b}'] = [[round(x, 3), round(y, 3)] for x, y in pts]
        print(f'  합계: 길이={tot[0]:.2f}m 꺾임={tot[1]:.0f}도 되꺾임={tot[2]}회', flush=True)
    if dump:
        json.dump(out, open(dump, 'w'))
    rclpy.shutdown()


if __name__ == '__main__':
    main()
