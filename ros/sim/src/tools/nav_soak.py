"""주행 안정성 반복 시험: P4 ↔ P1 을 장애물 종류 · 놓는 시점을 바꿔 가며 되풀이하고, 회차마다 결과를 한 줄로 낸다.
docker compose exec sim bash -c 'source /opt/ros/$ROS_DISTRO/setup.bash; python3 /sim/tools/nav_soak.py [--rounds 1] [--sets aisle,hall,hall_back] [--only aisle60,none]'

목표는 서버와 같은 길(/inspection/goal → 목표 브리지 → Nav2)로 보낸다. 브리지의 재시도 · 물러나기까지 포함해 본다.
기준(타협 없음): 길이 있으면 반드시 도착한다. 끼여서 모든 계획이 실패한 채 멈추는 일이 없어야 한다.
  결과   = 도착 / 실패(code) / 시간초과
  경로   = 직행(문 아래 골목으로) / 우회(랙 위로) / 먼길(그보다 더 돎). 장애물마다 '맞는 경로'가 정해져 있다:
           없음 · 폭 0.7 · 0.6 틈 → 직행,  폭 0.5 틈 · 완전 막힘 → 우회
  정지   = 출발한 뒤 속도 명령이 선속도 · 각속도 모두 0 에 가까웠던 시간(초). 제자리 회전은 '전진 없음'에 따로 센다.
놓는 시점: static = 출발 전에 놓음,  far = 달리는 도중 로봇 중심이 장애물에서 1.2m 일 때,  near = 0.6m 일 때(코앞. 차체와는 0.45m 로 겹치지 않는다)
장애물은 시작할 때 건물 밖에 미리 만들어 두고 /world/factory/set_pose 로 즉시 옮긴다. 그때그때 새로 만들면 서기까지 2.5~4초가
걸려 로봇 위에 겹쳐 생기곤 했다 — 차체가 튕겨 위치 추정이 깨지는, 실제로는 없는 상황이다.
"""
import json
import math
import subprocess
import sys
import time
import uuid

import rclpy
from nav2_msgs.srv import ClearEntireCostmap
from geometry_msgs.msg import TwistStamped
from ros_gz_interfaces.msg import Entity, EntityFactory
from ros_gz_interfaces.srv import SetEntityPose, SpawnEntity
from std_msgs.msg import String
from tf2_ros import Buffer, TransformListener

sys.path.insert(0, '/sim/worlds')
import world_spec as W  # noqa: E402
sys.path.insert(0, '/sim/tools')
from obstacle import sdf  # noqa: E402

P1, P3, P4 = (3.95, 3.9, math.pi), (7.65, 6.1, math.pi / 2), (0.3, 4.6, math.pi)
# 묶음: 이름 → (구간들, {장애물: (맞는 경로 이름, 주행 거리 범위 m)}).  '막힘' 은 길이 없어 BLOCKED_NO_PATH 로 끝나야 맞다.
SETS = {
    # 전기실 문 바로 아래 골목: 직행 5.1~5.5m, 랙 1 위로 우회 8.2~10.6m
    'aisle': ([('P4→P1', P4, P1), ('P1→P4', P1, P4)],
              {'none': ('직행', 0, 6.5), 'aisle70': ('직행', 0, 6.5), 'aisle60': ('직행', 0, 6.5),
               'aisle50': ('우회', 6.5, 11.5), 'aisle': ('우회', 6.5, 11.5)}),
    # 생산동: 직행 5.0m(팔레트는 옆으로 비켜 감), 문이 막히면 C1 · C2 로 돌아 14~19m, C2 위쪽이 막히면 길이 없다
    'hall': ([('P1→P3', P1, P3)],
             {'none': ('직행', 0, 6.5), 'pallet': ('직행', 0, 7.0), 'door': ('우회', 11.0, 21.0), 'block': ('막힘', 0, 99)}),
    'hall_back': ([('P3→P1', P3, P1)], {'pallet': ('직행', 0, 7.0), 'door': ('우회', 11.0, 21.0)}),
}
TIMEOUT = 300.0
TRIGGER = {'far': 1.2, 'near': 0.6}          # 로봇 중심에서 장애물(상자)까지의 거리(m)


class Soak:
    def __init__(self):
        self.n = rclpy.create_node('nav_soak')
        self.goal_pub = self.n.create_publisher(String, '/inspection/goal', 10)
        self.n.create_subscription(String, '/inspection/goal_status', self.on_status, 20)
        self.n.create_subscription(TwistStamped, '/cmd_vel', self.on_cmd, 20)   # Jazzy: 바퀴 명령은 TwistStamped
        self.tf = Buffer()
        TransformListener(self.tf, self.n)
        self.status, self.gid = None, None
        self.spawn = self.n.create_client(SpawnEntity, '/world/factory/create')      # Gazebo Harmonic 월드 서비스
        self.move = self.n.create_client(SetEntityPose, '/world/factory/set_pose')
        self.clears = [self.n.create_client(ClearEntireCostmap, f'/{c}/clear_entirely_{c}') for c in ('global_costmap', 'local_costmap')]
        self.parked = {}
        self.stop = self.noforward = 0.0
        self.cmd_at, self.moving = None, False

    def on_status(self, msg):
        s = json.loads(msg.data)
        if s.get('goalId') == self.gid and s.get('state') in ('SUCCEEDED', 'ABORTED', 'CANCELED'):
            self.status = s

    def on_cmd(self, stamped):
        m = stamped.twist
        now = time.monotonic()
        dt = min(now - self.cmd_at, 0.5) if self.cmd_at else 0.0
        self.cmd_at = now
        if abs(m.linear.x) > 0.05:
            self.moving = True
        if not self.moving:
            return
        if abs(m.linear.x) < 0.02:
            self.noforward += dt
            if abs(m.angular.z) < 0.05:
                self.stop += dt

    def xy(self):
        try:
            t = self.tf.lookup_transform('map', 'base_footprint', rclpy.time.Time()).transform.translation
            return t.x, t.y
        except Exception:
            return None

    def prepare(self, names):
        """장애물을 건물 밖에 미리 만들어 둔다."""
        self.spawn.wait_for_service(timeout_sec=20)
        self.move.wait_for_service(timeout_sec=20)
        for i, nm in enumerate(names):
            _, _, sx, sy = W.OBSTACLES[nm]
            self.parked[nm] = (-30.0 - 2 * i, -30.0)
            ef = EntityFactory(name=f'obstacle_{nm}', allow_renaming=False,
                               sdf=f'<sdf version="1.8">{sdf(f"obstacle_{nm}", sx, sy)}</sdf>')
            ef.pose.position.x, ef.pose.position.y, ef.pose.position.z = *self.parked[nm], 0.3
            f = self.spawn.call_async(SpawnEntity.Request(entity_factory=ef))
            rclpy.spin_until_future_complete(self.n, f, timeout_sec=90)

    def put(self, nm, x, y):
        req = SetEntityPose.Request(entity=Entity(name=f'obstacle_{nm}', type=Entity.MODEL))
        req.pose.position.x, req.pose.position.y, req.pose.position.z, req.pose.orientation.w = float(x), float(y), 0.3, 1.0
        f = self.move.call_async(req)
        rclpy.spin_until_future_complete(self.n, f, timeout_sec=5)

    def place(self, nm):
        self.put(nm, *W.OBSTACLES[nm][:2])

    def clear(self):
        for nm, (x, y) in self.parked.items():
            self.put(nm, x, y)
        self.spin(1.0)                       # 라이다가 치워진 것을 본 뒤
        for c in self.clears:
            if c.service_is_ready():
                c.call_async(ClearEntireCostmap.Request())
        self.spin(3.0)

    def spin(self, sec):
        end = time.monotonic() + sec
        while time.monotonic() < end:
            rclpy.spin_once(self.n, timeout_sec=0.05)

    def go(self, goal, drop=None):
        """목표로 보낸다. drop = (장애물 이름, 거리): 로봇이 그 장애물에서 거리 안으로 오면 놓는다."""
        self.gid, self.status = uuid.uuid4().hex[:8], None
        self.stop = self.noforward = 0.0
        self.moving, self.cmd_at = False, None
        start, t0, placed = self.xy(), time.monotonic(), None
        dist, last = 0.0, start
        msg = String(data=json.dumps({'goalId': self.gid, 'x': goal[0], 'y': goal[1], 'yaw': goal[2]}))
        self.goal_pub.publish(msg)
        while self.status is None and time.monotonic() - t0 < TIMEOUT:
            rclpy.spin_once(self.n, timeout_sec=0.05)
            p = self.xy()
            if p and last:
                dist += math.hypot(p[0] - last[0], p[1] - last[1])
                last = p
            if drop and placed is None and p:
                ox, oy, sx, sy = W.OBSTACLES[drop[0]]
                if math.hypot(max(abs(p[0] - ox) - sx / 2, 0), max(abs(p[1] - oy) - sy / 2, 0)) < drop[1]:
                    placed = time.monotonic()
                    self.place(drop[0])
        took = time.monotonic() - t0
        if self.status is None:
            cancel = String(data=json.dumps({'goalId': self.gid}))
            self.n.create_publisher(String, '/inspection/goal_cancel', 1).publish(cancel)
            self.spin(3)
            return {'result': '시간초과', 'time': took, 'dist': dist}
        s = self.status
        ok = s['state'] == 'SUCCEEDED'
        return {'result': '도착' if ok else f"실패({s.get('code')})", 'time': took, 'dist': dist,
                'recoveries': s.get('recoveries', 0)}


def obstacle(*a):
    subprocess.run(['/sim/tools/obstacle.sh', *a], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main():
    argv = sys.argv[1:]
    rounds = int(argv[argv.index('--rounds') + 1]) if '--rounds' in argv else 1
    sets = argv[argv.index('--sets') + 1].split(',') if '--sets' in argv else list(SETS)
    only = argv[argv.index('--only') + 1].split(',') if '--only' in argv else None
    rclpy.init()
    k = Soak()
    k.spin(3)
    obstacle('clear')
    names = sorted({o for st in sets for o in SETS[st][1] if o != 'none' and (not only or o in only)})
    k.prepare(names)
    rows = []
    for r in range(rounds):
        for st in sets:
            legs, expect = SETS[st]
            for name, (want, lo, hi) in expect.items():
                if only and name not in only:
                    continue
                for timing in (('static',) if name == 'none' else ('static', 'far', 'near')):
                    for leg, a, b in legs:
                        k.clear()
                        pre = k.go(a)                              # 출발 자리로(장애물 없이)
                        if pre['result'] != '도착':
                            print(f'  (출발 자리로 가지 못함: {pre["result"]})', flush=True)
                        drop = None
                        if name != 'none':
                            if timing == 'static':
                                k.place(name)
                                k.spin(4)
                            else:
                                drop = (name, TRIGGER[timing])
                        res = k.go(b, drop)
                        d = res['dist']
                        if want == '막힘':
                            good = res['result'] == '실패(BLOCKED_NO_PATH)'
                            route = '-'
                        else:
                            route = '직행' if d < 6.5 else '우회' if lo <= d <= hi or want == '우회' and d <= hi else '먼길'
                            if res['result'] == '도착' and not lo <= d <= hi:
                                route = '먼길' if d > hi else '직행'
                            good = res['result'] == '도착' and lo <= d <= hi
                        row = dict(leg=leg, obstacle=name, timing=timing, route=route if res['result'] == '도착' else '-',
                                   stop=k.stop, noforward=k.noforward, ok=good, **res)
                        rows.append(row)
                        print(f"{'✓' if good else '✗'} {leg} {name:8s} {timing:6s} {res['result']:22s} 경로={row['route']} "
                              f"(맞는 결과 {want}) 시간={res['time']:.0f}s 주행={d:.1f}m 정지={k.stop:.0f}s "
                              f"전진없음={k.noforward:.0f}s 복구={res.get('recoveries', '-')}", flush=True)
    k.clear()
    n = len(rows)
    arrived = sum(1 for x in rows if x['result'] == '도착')
    print(f"\n합계 {n}회: 맞는 결과 {sum(1 for x in rows if x['ok'])} · 틀린 결과 {sum(1 for x in rows if not x['ok'])} "
          f"(도착 {arrived}) · 정지 합 {sum(x['stop'] for x in rows):.0f}s · 전진 없음 합 {sum(x['noforward'] for x in rows):.0f}s",
          flush=True)
    rclpy.shutdown()


if __name__ == '__main__':
    main()
