"""로봇 측 목표 브리지: 서버의 목표 인터페이스 ↔ Nav2.

서버와의 약속(모두 std_msgs/String, JSON):
  /inspection/goal          ← {"goalId": "...", "x": 1.0, "y": 0.0, "yaw": 0.0}   (지도 좌표, yaw 는 rad)
  /inspection/goal_cancel   ← {"goalId": "..."}  ("*" 이면 전부 취소)
  /inspection/goal_status   → {"goalId", "state": ACTIVE|SUCCEEDED|ABORTED|CANCELED, "code", "reason",
                               "detoured", "recoveries", "plannedLength", "traveled"}
  /inspection/bridge_status → {"navReady": bool, "localized": bool}  (1초마다, 출발 전 검사용)
  /inspection/map_pose      → geometry_msgs/PoseStamped (frame map, 5Hz) — 지도 위 로봇 위치(관제 화면 지도 모드)
  /inspection/map           → nav_msgs/OccupancyGrid (5초마다) — /map 은 처음 한 번만 발행(latched)되어 rosbridge 로는
                              놓치기 쉬우므로 같은 지도를 주기적으로 다시 발행한다

장애물 처리는 Nav2 가 한다: 일시 장애물은 기다리고, 돌아갈 수 있으면 경로를 다시 계획한다.
Nav2 가 결국 실패하면 비용 지도의 오래된 표시를 지우고 현재 위치에서 목표까지 경로를 다시 계산한다.
경로가 있으면 한 번 더 주행하고(오래된 표시 때문이었을 수 있음), 그래도 실패하면 원인을 나눈다.
  code = BLOCKED_NO_PATH : 경로가 없다 → 통로가 막혀 진입 불가
         NAV_FAILED      : 경로는 있으나 주행 실패(복구 동작 소진 등)
         NO_PROGRESS     : 일정 시간 목표에 가까워지지 못함
         NAV_UNAVAILABLE : Nav2 가 준비되지 않음
성공했더라도 처음 계획 경로보다 크게 돌아갔거나 복구 동작이 있었으면 detoured=true 로 알린다.
"""
import json
import math
import os
import time

import rclpy
from geometry_msgs.msg import PoseStamped, PoseWithCovarianceStamped
from tf2_ros import Buffer, TransformListener
from nav2_msgs.action import ComputePathToPose, NavigateToPose
from nav2_msgs.srv import ClearEntireCostmap
from nav_msgs.msg import OccupancyGrid, Odometry
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from rclpy.time import Time
from rclpy.action import ActionClient
from rclpy.node import Node
from std_msgs.msg import String
from action_msgs.msg import GoalStatus

NO_PROGRESS_SEC = 90.0
MODE = os.environ.get('SIM_MODE', 'nav')


def path_length(path):
    pts = [(p.pose.position.x, p.pose.position.y) for p in path.poses]
    return sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(pts, pts[1:]))


class Bridge(Node):
    def __init__(self):
        super().__init__('inspection_goal_bridge')
        self.nav = ActionClient(self, NavigateToPose, 'navigate_to_pose')
        self.planner = ActionClient(self, ComputePathToPose, 'compute_path_to_pose')
        self.clear_global = self.create_client(ClearEntireCostmap, '/global_costmap/clear_entirely_global_costmap')
        self.clear_local = self.create_client(ClearEntireCostmap, '/local_costmap/clear_entirely_local_costmap')
        self.status_pub = self.create_publisher(String, '/inspection/goal_status', 10)
        self.bridge_pub = self.create_publisher(String, '/inspection/bridge_status', 10)
        self.init_pub = self.create_publisher(PoseWithCovarianceStamped, '/initialpose', 10)
        self.create_subscription(String, '/inspection/goal', self.on_goal, 10)
        self.create_subscription(String, '/inspection/goal_cancel', self.on_cancel, 10)
        self.create_subscription(Odometry, '/odom', self.on_odom, 10)
        self.create_subscription(PoseWithCovarianceStamped, '/amcl_pose', self.on_amcl, 10)
        self.localized = MODE == 'slam'     # SLAM 모드는 slam_toolbox 가 위치를 낸다
        self.init_tries = 0
        self.goal = None                    # 현재 목표 dict (Nav2 목표 핸들은 goal['handle'])
        self.last_xy = None
        self.create_timer(1.0, self.tick)
        # 지도 좌표의 로봇 위치: TF(map → base_footprint)를 읽어 5Hz 로 발행한다
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)
        self.map_pose_pub = self.create_publisher(PoseStamped, '/inspection/map_pose', 10)
        self.create_timer(0.2, self.publish_map_pose)
        latched = QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL, reliability=ReliabilityPolicy.RELIABLE)
        self.map_msg = None
        self.create_subscription(OccupancyGrid, '/map', lambda m: setattr(self, 'map_msg', m), latched)
        self.map_pub = self.create_publisher(OccupancyGrid, '/inspection/map', 1)
        self.create_timer(5.0, lambda: self.map_msg is not None and self.map_pub.publish(self.map_msg))
        self.get_logger().info(f'goal bridge ready (mode={MODE})')

    # ------------------------------------------------------------ 상태
    def on_odom(self, msg):
        x, y = msg.pose.pose.position.x, msg.pose.pose.position.y
        if self.goal and self.last_xy:
            self.goal['traveled'] += math.hypot(x - self.last_xy[0], y - self.last_xy[1])
        self.last_xy = (x, y)

    def on_amcl(self, _msg):
        self.localized = True

    def tick(self):
        ready = self.nav.server_is_ready()
        # AMCL 은 초기 위치를 받아야 map 좌표를 낸다. Nav2 는 map 좌표가 있어야 준비되므로 기다리지 않고 보낸다.
        if MODE == 'nav' and not self.localized and self.init_tries < 120 and self.count_subscribers('/initialpose') > 0:
            # 실제 로봇에서는 사람이 초기 위치를 지정한다. 시뮬레이션은 충전 위치(0,0)에서 시작한다.
            p = PoseWithCovarianceStamped()
            p.header.frame_id = 'map'
            p.header.stamp = self.get_clock().now().to_msg()
            p.pose.pose.orientation.w = 1.0
            p.pose.covariance[0] = p.pose.covariance[7] = 0.05
            p.pose.covariance[35] = 0.05
            self.init_pub.publish(p)
            self.init_tries += 1
        self.bridge_pub.publish(String(data=json.dumps({'navReady': ready, 'localized': self.localized})))
        g = self.goal
        if g and g.get('handle') and time.monotonic() - g['progress_at'] > NO_PROGRESS_SEC:
            self.get_logger().warn('no progress → cancel')
            g['stalled'] = True
            g['handle'].cancel_goal_async()
            g['progress_at'] = time.monotonic()

    def publish_map_pose(self):
        try:
            t = self.tf_buffer.lookup_transform('map', 'base_footprint', Time())
        except Exception:   # 지도·위치 추정이 아직 없음
            return
        p = PoseStamped()
        p.header.frame_id = 'map'
        p.header.stamp = t.header.stamp
        p.pose.position.x = t.transform.translation.x
        p.pose.position.y = t.transform.translation.y
        p.pose.orientation = t.transform.rotation
        self.map_pose_pub.publish(p)

    def report(self, g, state, code='', reason='', **extra):
        body = {'goalId': g['goalId'], 'state': state, 'code': code, 'reason': reason}
        body.update(extra)
        self.status_pub.publish(String(data=json.dumps(body, ensure_ascii=False)))

    # ------------------------------------------------------------ 목표
    def pose(self, x, y, yaw):
        p = PoseStamped()
        p.header.frame_id = 'map'
        p.header.stamp = self.get_clock().now().to_msg()
        p.pose.position.x, p.pose.position.y = x, y
        p.pose.orientation.z, p.pose.orientation.w = math.sin(yaw / 2), math.cos(yaw / 2)
        return p

    def on_goal(self, msg):
        try:
            d = json.loads(msg.data)
            g = {'goalId': str(d['goalId']), 'x': float(d['x']), 'y': float(d['y']), 'yaw': float(d.get('yaw', 0.0))}
        except (ValueError, KeyError, TypeError) as e:
            self.get_logger().warn(f'invalid goal: {e}')
            return
        if self.goal and self.goal['goalId'] == g['goalId']:
            self.report(self.goal, 'ACTIVE')       # 같은 목표 재전송: 새로 시작하지 않는다
            return
        if self.goal:
            old = self.goal
            old['preempted'] = True
            if old.get('handle'):
                old['handle'].cancel_goal_async()
        if not self.nav.server_is_ready():
            self.report(g, 'ABORTED', 'NAV_UNAVAILABLE', '주행 시스템(Nav2)이 준비되지 않음')
            return
        g.update(traveled=0.0, planned=None, recoveries=0, best=None, progress_at=time.monotonic(),
                 stalled=False, user_cancel=False, preempted=False, handle=None, retried=False)
        self.goal = g
        # 처음 계획 경로 길이(우회 판단 기준)
        if self.planner.server_is_ready():
            req = ComputePathToPose.Goal(goal=self.pose(g['x'], g['y'], g['yaw']), use_start=False)
            self.planner.send_goal_async(req).add_done_callback(lambda f, g=g: self.on_plan_accepted(f, g))
        self.start_nav(g)

    def start_nav(self, g):
        target = self.pose(g['x'], g['y'], g['yaw'])
        fut = self.nav.send_goal_async(NavigateToPose.Goal(pose=target), feedback_callback=lambda fb, g=g: self.on_feedback(fb, g))
        fut.add_done_callback(lambda f, g=g: self.on_accepted(f, g))

    def on_plan_accepted(self, fut, g):
        h = fut.result()
        if h.accepted:
            h.get_result_async().add_done_callback(
                lambda r, g=g: g.__setitem__('planned', path_length(r.result().result.path)
                                             if r.result().status == GoalStatus.STATUS_SUCCEEDED else None))

    def on_accepted(self, fut, g):
        h = fut.result()
        if not h.accepted:
            self.report(g, 'ABORTED', 'NAV_FAILED', 'Nav2 가 목표를 거부함')
            self.goal = None if self.goal is g else self.goal
            return
        g['handle'] = h
        if g.get('preempted'):
            h.cancel_goal_async()
            return
        if not g['retried']:
            self.report(g, 'ACTIVE')
        h.get_result_async().add_done_callback(lambda f, g=g: self.on_result(f, g))

    def on_feedback(self, fb, g):
        f = fb.feedback
        g['recoveries'] = f.number_of_recoveries
        d = f.distance_remaining
        if d > 0 and (g['best'] is None or d < g['best'] - 0.15):
            g['best'] = d
            g['progress_at'] = time.monotonic()

    def on_result(self, fut, g):
        status = fut.result().status
        extra = {'recoveries': g['recoveries'], 'traveled': round(g['traveled'], 2),
                 'plannedLength': None if g['planned'] is None else round(g['planned'], 2)}
        if g.get('preempted'):
            self.report(g, 'CANCELED', 'PREEMPTED', '새 목표로 교체', **extra)
        elif status == GoalStatus.STATUS_SUCCEEDED:
            planned = g['planned']
            detoured = g['recoveries'] > 0 or (planned is not None and g['traveled'] > planned * 1.2 + 0.5)
            self.report(g, 'SUCCEEDED', 'DETOURED' if detoured else '', '경로상 장애물 우회' if detoured else '',
                        detoured=detoured, **extra)
        elif g['user_cancel']:
            self.report(g, 'CANCELED', 'CANCELED', '취소 요청', **extra)
        else:
            # 실패 원인 분류: 비용 지도에 남은 오래된 표시를 지우고, 새 스캔이 반영된 뒤 현재 위치에서 경로를 다시 계산한다
            self.clear_costmaps()
            self.create_timer_once(3.0, lambda: self.classify(g, extra))
            return
        if self.goal is g:
            self.goal = None

    def create_timer_once(self, sec, fn):
        holder = {}

        def run():
            holder['t'].cancel()
            fn()
        holder['t'] = self.create_timer(sec, run)

    def classify(self, g, extra):
        def done(code, reason):
            self.report(g, 'ABORTED', code, reason, **extra)
            if self.goal is g:
                self.goal = None

        base = 'NO_PROGRESS' if g['stalled'] else 'NAV_FAILED'
        base_reason = '목표에 가까워지지 못함' if g['stalled'] else f'주행 실패 (복구 동작 {g["recoveries"]}회)'
        if not self.planner.server_is_ready():
            return done(base, base_reason)
        req = ComputePathToPose.Goal(goal=self.pose(g['x'], g['y'], g['yaw']), use_start=False)

        def accepted(f):
            h = f.result()
            if not h.accepted:
                return done('BLOCKED_NO_PATH', '경로 없음: 통로가 막혀 진입할 수 없음')

            def result(r):
                res = r.result()
                if res.status != GoalStatus.STATUS_SUCCEEDED or len(res.result.path.poses) == 0:
                    done('BLOCKED_NO_PATH', '경로 없음: 통로가 막혀 진입할 수 없음')
                elif not g['retried'] and not g['user_cancel'] and self.goal is g:
                    # 지운 뒤에는 경로가 있다 → 오래된 표시 때문이었을 수 있으므로 한 번 더 주행한다
                    self.get_logger().info('path exists after costmap clear → retry once')
                    g.update(retried=True, stalled=False, best=None, progress_at=time.monotonic(), handle=None)
                    self.start_nav(g)
                else:
                    done(base, base_reason)
            h.get_result_async().add_done_callback(result)
        self.planner.send_goal_async(req).add_done_callback(accepted)

    def clear_costmaps(self):
        for cli in (self.clear_global, self.clear_local):
            if cli.service_is_ready():
                cli.call_async(ClearEntireCostmap.Request())

    def on_cancel(self, msg):
        try:
            gid = json.loads(msg.data).get('goalId', '*')
        except ValueError:
            gid = '*'
        g = self.goal
        if g and gid in ('*', g['goalId']):
            g['user_cancel'] = True
            if g.get('handle'):
                g['handle'].cancel_goal_async()
            else:
                self.report(g, 'CANCELED', 'CANCELED', '취소 요청')
                self.goal = None


def main():
    rclpy.init()
    rclpy.spin(Bridge())


if __name__ == '__main__':
    main()
