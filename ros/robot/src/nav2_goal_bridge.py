"""로봇 측 목표 브리지: 서버의 목표 인터페이스 ↔ Nav2.

서버와의 약속(모두 std_msgs/String, JSON):
  /inspection/goal          ← {"goalId": "...", "x": 1.0, "y": 0.0, "yaw": 0.0}   (지도 좌표, yaw 는 rad)
  /inspection/goal_cancel   ← {"goalId": "..."}  ("*" 이면 전부 취소)
  /inspection/goal_status   → {"goalId", "state": ACTIVE|SUCCEEDED|ABORTED|CANCELED, "code", "reason",
                               "detoured", "recoveries", "plannedLength", "traveled"}
  /inspection/bridge_status → {"navReady": bool, "localized": bool}  (1초마다, 출발 전 검사용)
  /inspection/map_pose      → geometry_msgs/PoseStamped (frame map, 5Hz) — 지도 위 로봇 위치(관제 화면 지도 모드)
  /inspection/scan_map      → std_msgs/String JSON {"pts": [[x, y], ...]} — 라이다 점을 스캔이 찍힌 시각의 TF 로
                              지도 좌표로 바꾼 것(관제 지도 모드). 위치와 스캔을 따로 보내면 회전 중 시간차만큼 어긋난다
  /inspection/drive_plan    → std_msgs/String JSON {"v", "w", "traj": [[x, y], ...]} — 제어기가 지금 내는 속도 명령(v m/s, w rad/s)과
                              그 명령을 DRIVE_HORIZON 초 유지했을 때 로봇이 지나갈 호(지도 좌표). 관제 지도에서 A* 경로(/plan)와
                              겹쳐 보면 제어기가 경로를 따르는지 · 어느 쪽으로 비켜 가는지가 보인다. 주행 명령이 있을 때만 5Hz
  /inspection/map           → nav_msgs/OccupancyGrid (5초마다) — /map 은 처음 한 번만 발행(latched)되어 rosbridge 로는
                              놓치기 쉬우므로 같은 지도를 주기적으로 다시 발행한다

장애물 처리는 Nav2 가 한다: 일시 장애물은 기다리고, 돌아갈 수 있으면 경로를 다시 계획한다.
Nav2 가 결국 실패하면 비용 지도의 오래된 표시를 지우고 현재 위치에서 목표까지 경로를 다시 계산한다.
경로가 있으면 한 번 더 주행하고(오래된 표시 때문이었을 수 있음), 그래도 실패하면 원인을 나눈다.
  code = BLOCKED_NO_PATH : 경로가 없다 → 통로가 막혀 진입 불가
         NAV_FAILED      : 경로는 있으나 주행 실패(복구 동작 소진 등)
         NO_PROGRESS     : 일정 시간 목표에 가까워지지 못함
         NAV_UNAVAILABLE : Nav2 가 준비되지 않음
지나지 못하는 자리 피하기(목표를 누가 보냈든 동작한다): 제어기 주행(FollowPath)이 같은 자리(반경 STUCK_RADIUS)에서 STUCK_TRIES 번
실패하면 '막힘'이다. 처음에는 물러나 자세만 다시 잡는다(아래). 물러났다가 다시 와서 같은 자리에서 또 막히면 그 자리를
가상 장애물로 찍어 다른 길로 다시 계획하게 한다. 표시는 그 목표가 끝나면 지운다.
(처음에는 '경로 위 로봇 앞자리'를 바로 막았는데, 실패하는 동안 경로가 바뀌어 돌아가는 길이나 물러날 길을 막아 로봇을
가두는 일이 거듭됐다. 막혔던 그 자리 자체를, 로봇이 거기서 물러난 뒤에 막는 것으로 바꿨다.)
가상 장애물은 지도와 같은 크기의 격자(/inspection/virtual_map, OccupancyGrid)로 보내고, 전역 비용 지도가 별도 층(virtual_layer)으로
받는다. 보낼 때마다 층 전체가 바뀌므로 표시가 남지 않는다. (처음에는 장애물 층의 관측(PointCloud2)으로 넣었는데, 장애물 층은
한번 찍힌 칸을 라이다가 다시 볼 때까지 지우지 않아, 치운 뒤에도 표시가 남아 멀쩡한 문을 막고 경로를 바꿨다.)
물러나 자세 잡기: 로봇이 장애물에 바짝 붙어(중심이 충돌 구역 안) 멈추면 Nav2 는 그 자리에서 계획 → 실패를 되풀이한다.
제어기의 후보 궤적이 전부 충돌로 버려지고, Nav2 의 복구 동작(후진 · 회전)도 '앞에 충돌'이라며 시작하지 못하기 때문이다.
그래서 같은 자리에서 STUCK_TRIES 번 실패하면 브리지가 직접 /cmd_vel 로 로봇을 뺀다: 가까운 장애물들에서 멀어지는 쪽으로
(차체를 덜 돌려도 되게 전진 또는 후진) ESCAPE_DIST 만큼, 또는 사방이 ESCAPE_CLEAR 만큼 트일 때까지 간다. 나아가는 쪽 라이다
거리가 ESCAPE_REAR_MIN 아래면 멈춘다. Nav2 의 충돌 검사를 거치지 않는 유일한 동작이다. (처음에는 지나온 길을 되짚어
후진했는데, 뒤가 막혀 있으면 한 걸음도 못 갔다.) Nav2 목표가 끝내 실패하면 같은 동작을 한 뒤 다시 계획해 MAX_RETRIES 번까지
다시 보낸다. '경로 없음'은 장애물에서 충분히 떨어진 자리에서 계산했을 때만 믿는다.
장애물의 몸통 채우기: 라이다는 새 장애물의 앞면만 선으로 본다. 그대로 두면 계획은 그 선 바로 뒤(실제로는 장애물이 차지한 곳)를
지나갈 수 있는 곳으로 믿는다. 저장 지도에 없는 장애물(벽에서 SHADOW_WALL_TOL 넘게 떨어진 점)의 보인 면에서, 면에 수직으로
뒤쪽 SHADOW_DEPTH 까지를 가상 장애물로 찍어 몸통을 채운다(같은 격자). 폭은 보인 면 그대로다. 빔 방향이 아니라 면에 수직으로 채우므로 장애물 옆의
틈은 그대로 열려 있다. 주행 중에는 채운 칸을 기억하고(면이 안 보이게 돼도 몸통은 그대로다), 라이다 빔이 그 칸을 지나가면
(빈 곳으로 확인되면) 지운다. 목표가 끝나면 모두 지우고, 서 있을 때는 지금 보이는 면만 채운다.
몸통의 두께는 추정이다. 그래서 (1) 목표 둘레 SHADOW_GOAL_CLEAR 는 찍지 않고, (2) 그래도 계획이 실패하면 그 목표가 끝날 때까지
채우기를 끄고 실제로 본 것만으로 다시 계획하게 한다.
성공했더라도 처음 계획 경로보다 크게 돌아갔거나 복구 동작이 있었으면 detoured=true 로 알린다.
비상구 앞 구역(목표에 "exitZone": [x1, y1, x2, y2] 이 붙은 것 — 비상구 점검 지점으로 가는 목표에만 붙는다):
로봇이 그 구역에서 EXIT_NEAR_DIST 안에 있고 구역 안에 저장 지도에 없는 장애물(벽 쪽 EXIT_ZONE_MARGIN 은 빼고 EXIT_MIN_HITS 점 이상)이
보이는 채로 막히면(계획 실패 · 제어기 실패 · 목표 실패 · EXIT_STALL_SEC 동안 가까워지지 못함) 위의 복구 · 우회 · 재시도를 하지 않고
바로 BLOCKED_NO_PATH 로 끝낸다. 멀리서는 평소처럼 복구 · 우회하고, 끝내 길이 없을 때 그 구역에 물건이 보이면 같은 처리를 한다. 비상구 앞 통로는 비어 있어야 하므로 그 안의 장애물은
돌아갈 대상이 아니라 알릴 대상이다(서버가 목적지 쪽 사진을 찍어 올린다). 막은 물건이 구역 밖이면(통로로 가는 문 등) 지금까지와 똑같다.
"""
import json
import math
import os
import time

import rclpy
from geometry_msgs.msg import PoseStamped, PoseWithCovarianceStamped, Twist, TwistStamped
from tf2_ros import Buffer, TransformListener
from nav2_msgs.action import ComputePathToPose, NavigateToPose
from nav2_msgs.srv import ClearEntireCostmap
from nav_msgs.msg import OccupancyGrid, Odometry, Path
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from rclpy.time import Time
from rclpy.action import ActionClient
from rclpy.node import Node
from std_msgs.msg import String
from sensor_msgs.msg import LaserScan
from rclpy.qos import qos_profile_sensor_data
from rclpy.duration import Duration
from action_msgs.msg import GoalStatus, GoalStatusArray

NO_PROGRESS_SEC = 90.0
DRIVE_HORIZON = 3.0       # 제어기 방향 표시: 지금 속도 명령을 이만큼 유지했을 때의 호(MPPI 예측 시간과 같게)
DRIVE_STEPS = 12
STUCK_TRIES = 3           # 같은 자리에서 제어기 주행이 이만큼 실패하면 그 앞을 막힌 것으로 본다
STUCK_RADIUS = 0.4        # '같은 자리'의 범위(m): 첫 실패 위치에서 이 안
ESCAPE_DIST = 0.45        # 빠져나오는 거리(m)
ESCAPE_SPEED = 0.10       # 빠져나오는 속도(m/s)
ESCAPE_REAR_MIN = 0.22    # 나아가는 쪽(±35도) 라이다 거리가 이 아래면 멈춘다(m). 라이다에서 차체 앞 · 뒤 끝까지가 0.14m
ESCAPE_CLEAR = 0.40       # 사방 라이다 최소 거리가 이만큼 되면(충돌 구역 0.22 를 넉넉히 벗어나면) 그만 간다(m)
MAX_RETRIES = 3           # Nav2 목표가 실패했을 때 다시 보내는 횟수
# 바퀴 명령 형식: ROS 2 Jazzy(실제 터틀봇 · Jazzy 시뮬레이션)는 /cmd_vel 이 TwistStamped, Humble 은 Twist.
# 제어기 출력(/cmd_vel_nav)도 같은 형식이다(Nav2 enable_stamped_cmd_vel). CMD_VEL_STAMPED=0 이면 Twist.
STAMPED = os.environ.get('CMD_VEL_STAMPED', '1') != '0'
EXIT_STALL_SEC = 5.0      # 비상구 앞 구역 안에서 이만큼 목표에 가까워지지 못하면 막힌 것으로 보고 바로 끝낸다
EXIT_APPROACH_DIST = 1.0  # 비상구 앞에서 막히면 앞 장애물까지 이 거리가 될 때까지 천천히 다가간 뒤 끝낸다(근거 사진 거리, m)
EXIT_APPROACH_SPEED = 0.08
EXIT_APPROACH_SEC = 10.0
EXIT_APPROACH_BACK = 1.1  # 먼저 Nav2 로 가는 곳: 목적지 앞(바라보는 방향의 반대쪽)으로 이만큼 물러난 지점(통로 가운데)
EXIT_APPROACH_NAV_SEC = 45.0
EXIT_ZONE_MARGIN = 0.3    # 비상구 앞 구역 가장자리(벽)에서 이 안쪽에 찍힌 점만 센다. 통로를 막는 물건은 가운데를 차지하고, 벽 쪽은 위치 추정 오차(0.2m 안팎)와 지도 끝(site 지도는 C2 동쪽 벽이 반만 있음) 때문에 벽이 새 장애물로 보일 수 있다
EXIT_NEAR_DIST = 1.0      # 로봇이 비상구 앞 구역에서 이 안에 있을 때만 바로 진입 불가로 본다(멀리서 본 점은 문틀 가장자리 라이다 잡음일 수 있다)
EXIT_MIN_HITS = 5         # 구역 안 '새 장애물' 점이 이만큼 있어야 비상구 앞 적재로 본다(점 하나 · 둘은 잡음. 실제 적재물은 2~3m 밖에서도 수십 점)
ESCAPE_TIMEOUT = 10.0
ESCAPE_NEAR = 0.40        # 목표가 실패했을 때 라이다 최소 거리가 이 아래면(장애물에 붙어 있으면) 재시도 전에 물러난다(m)
STUCK_SAME = 0.5          # 물러났다가 이 안에서 또 막히면 '같은 자리에서 두 번째'로 본다(m)
BLOCK_RADIUS = 0.25       # 막는 자리(가상 장애물)의 반지름(m)
SHADOW_WALL_TOL = 0.15    # 저장 지도의 벽에서 이 안에 찍힌 점은 벽으로 본다(위치 추정 오차 · 라이다 잡음). 그 밖이면 새 장애물
SHADOW_STEP = 0.05
SHADOW_DEPTH = 0.3        # 보인 면에서 뒤로(면에 수직으로) 채우는 깊이(m) = 장애물의 몸통으로 보는 두께. 지도의 벽을 만나면 거기서 멈춘다
SHADOW_GOAL_CLEAR = 0.45  # 목표(계획 경로의 끝) 둘레 이 안은 뒤쪽 표시를 찍지 않는다(목표가 충돌 구역이 되면 계획이 거부된다)
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
        # 제어기 방향: Nav2 제어기의 출력(/cmd_vel_nav, 속도 다듬기 전)을 받아 예상 호를 지도 좌표로 낸다
        self.cmd = None                     # (v, w, 받은 시각)
        self.create_subscription(TwistStamped if STAMPED else Twist, '/cmd_vel_nav', self.on_cmd_nav, 10)
        self.drive_pub = self.create_publisher(String, '/inspection/drive_plan', 5)
        self.create_timer(0.2, self.publish_drive_plan)
        latched = QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL, reliability=ReliabilityPolicy.RELIABLE)
        self.map_msg = None
        self.create_subscription(OccupancyGrid, '/map', lambda m: setattr(self, 'map_msg', m), latched)
        self.map_pub = self.create_publisher(OccupancyGrid, '/inspection/map', 1)
        self.create_timer(5.0, lambda: self.map_msg is not None and self.map_pub.publish(self.map_msg))
        self.scan_map_pub = self.create_publisher(String, '/inspection/scan_map', 5)
        self.create_subscription(LaserScan, '/scan', self.on_scan, qos_profile_sensor_data)
        # 지나지 못하는 자리 피하기
        self.plan = []                      # 최근 계획 경로 [(x, y)]
        self.create_subscription(Path, '/plan', self.on_plan, 5)
        self.fail_ids, self.fail_at, self.fail_count = set(), None, 0
        self.stuck_spots = []               # 이번 목표에서 막혔던 자리 [(x, y)]
        self.blocks = []                    # 가상 장애물 중심 [(x, y)]
        self.trail = []                     # 지나온 길 [(x, y)] (지도 좌표, 5cm 마다, 최근 3m)
        self.escape = None                  # 물러나는 중이면 {'target': (x, y), 'from': (x, y), 'until': 시각}
        self.rear_min = 9.0                 # 뒤쪽 라이다 최소 거리
        self.scan_min = 9.0                 # 사방 라이다 최소 거리
        self.scan_polar = []                # 최근 스캔 [(로봇 기준 각, 거리)]
        self.cmd_pub = self.create_publisher(TwistStamped if STAMPED else Twist, '/cmd_vel', 10)
        self.create_timer(0.1, self.escape_step)
        self.approach = None                # 비상구 앞에서 막힌 뒤 근거 사진 거리까지 다가가는 중 {'g', 'until'}
        self.create_timer(0.1, self.approach_step)
        self.new_hits = []                  # 저장 지도에 없는 장애물에 닿은 라이다 점 [(x, y)] (최근 스캔)
        self.fill, self.shadow_at = set(), 0.0   # 새 장애물의 몸통으로 채운 칸 {(cx, cy)} (지도 격자 좌표)
        self.shadow_off = False             # 계획이 실패해 이번 목표 동안 뒤쪽 표시를 껐는가
        self.plan_fail_ids = set()
        self.create_subscription(GoalStatusArray, '/compute_path_to_pose/_action/status', self.on_planner_status, 10)
        self.nav_active = False
        self.create_subscription(GoalStatusArray, '/follow_path/_action/status', self.on_follow_status, 10)
        self.create_subscription(GoalStatusArray, '/navigate_to_pose/_action/status', self.on_nav_status, 10)
        self.block_pub = self.create_publisher(OccupancyGrid, '/inspection/virtual_map', latched)
        self.create_timer(1.0, self.publish_blocks)
        # 금지구역: 서버가 보낸 직사각형 목록. 계획 맵(virtual_map 에 합침)과 제어 맵(keepout_map)에 막힌 칸으로 넣는다
        self.zones = []                     # [(x1, y1, x2, y2)] (지도 좌표)
        self.keepout_sent = None            # 마지막으로 보낸 (구역 목록, 지도 크기) — 바뀌었을 때만 다시 보낸다
        self.create_subscription(String, '/inspection/keepout', self.on_keepout, 5)
        self.keepout_pub = self.create_publisher(OccupancyGrid, '/inspection/keepout_map', latched)
        self.create_timer(1.0, self.publish_keepout)
        self.create_timer(0.5, self.check_exit_stall)
        self.get_logger().info(f'goal bridge ready (mode={MODE})')

    # ------------------------------------------------------------ 지나지 못하는 자리 피하기
    def on_plan(self, msg):
        self.plan = [(p.pose.position.x, p.pose.position.y) for p in msg.poses]

    def map_xy(self):
        try:
            t = self.tf_buffer.lookup_transform('map', 'base_footprint', Time()).transform.translation
            return t.x, t.y
        except Exception:
            return None

    def on_nav_status(self, msg):
        active = any(s.status in (GoalStatus.STATUS_ACCEPTED, GoalStatus.STATUS_EXECUTING) for s in msg.status_list)
        if not active and self.nav_active:      # 목표가 끝났다 → 표시를 지우고 다음 목표는 처음부터 다시 본다
            self.blocks, self.fail_at, self.fail_count, self.stuck_spots = [], None, 0, []
            self.shadow_off, self.plan, self.fill = False, [], set()
            self.publish_blocks()
        self.nav_active = active

    def on_planner_status(self, msg):
        for s in msg.status_list:
            gid = bytes(s.goal_info.goal_id.uuid)
            if s.status == GoalStatus.STATUS_ABORTED and gid not in self.plan_fail_ids:
                self.plan_fail_ids.add(gid)
                if self.nav_active and self.in_exit_zone(self.goal):
                    self.exit_blocked(self.goal, 'planning failed')
                    continue
                if self.nav_active and not self.shadow_off and self.fill:
                    self.get_logger().warn('planning failed with unseen area blocked → drop it for this goal and replan')
                    self.shadow_off = True
                    self.publish_blocks()

    def on_follow_status(self, msg):
        for s in msg.status_list:
            gid = bytes(s.goal_info.goal_id.uuid)
            if s.status != GoalStatus.STATUS_ABORTED or gid in self.fail_ids:
                continue
            self.fail_ids.add(gid)
            if self.in_exit_zone(self.goal):
                self.exit_blocked(self.goal, 'controller failed')
                continue
            xy = self.map_xy()
            if xy is None:
                continue
            if self.fail_at is None or math.hypot(xy[0] - self.fail_at[0], xy[1] - self.fail_at[1]) > STUCK_RADIUS:
                self.fail_at, self.fail_count = xy, 0          # 다른 자리에서의 실패 → 새로 센다
            self.fail_count += 1
            if self.fail_count >= STUCK_TRIES:
                self.start_escape(xy)
                self.fail_at, self.fail_count = None, 0

    def away_direction(self, yaw):
        """가까운 장애물들에서 멀어지는 방향(지도 좌표의 각). 0.7m 안의 라이다 점마다 로봇 쪽으로 미는 힘을 더한다(가까울수록 세다)."""
        sx = sy = 0.0
        for a, r in self.scan_polar:
            if r < 0.7:
                w = (0.7 - r) ** 2
                sx -= w * math.cos(a)
                sy -= w * math.sin(a)
        if math.hypot(sx, sy) < 1e-4:
            return None
        return yaw + math.atan2(sy, sx)

    def start_escape(self, xy, idle=False):
        """막힌 자리에서 빠져나오기 시작한다: 가까운 장애물에서 멀어지는 쪽으로 ESCAPE_DIST 만큼(그쪽 정보가 없으면 지나온 길로).
        idle=True 는 Nav2 목표가 끝난 뒤(재시도 전)에 부른 것이다."""
        if self.escape:
            return False
        try:
            t = self.tf_buffer.lookup_transform('map', 'base_footprint', Time()).transform.rotation
        except Exception:
            return False
        yaw = math.atan2(2 * (t.w * t.z + t.x * t.y), 1 - 2 * (t.y * t.y + t.z * t.z))
        heading = self.away_direction(yaw)
        if heading is None and len(self.trail) >= 3:            # 주변에 아무것도 없다 → 지나온 쪽으로
            bx, by = self.trail[-3]
            heading = math.atan2(by - xy[1], bx - xy[0])
        if heading is None:
            return False
        # 차체를 덜 돌려도 되는 쪽으로 간다: 그 방향이 뒤에 가까우면 후진, 앞에 가까우면 전진
        back = abs(math.atan2(math.sin(heading - yaw - math.pi), math.cos(heading - yaw - math.pi)))
        fwd = abs(math.atan2(math.sin(heading - yaw), math.cos(heading - yaw)))
        # 물러났다가 다시 왔는데 또 같은 자리에서 막혔다면 그 자리는 지날 수 없는 곳이다 → 빠져나온 뒤 그 자리를 막는다
        again = any(math.hypot(xy[0] - x, xy[1] - y) < STUCK_SAME for x, y in self.stuck_spots)
        self.stuck_spots.append(xy)
        self.escape = {'heading': heading, 'reverse': back <= fwd, 'from': xy, 'until': time.monotonic() + ESCAPE_TIMEOUT,
                       'block': xy if again and not idle else None, 'idle': idle}
        self.get_logger().warn(f'stuck at ({xy[0]:.2f}, {xy[1]:.2f}), nearest obstacle {self.scan_min:.2f}m → move away '
                               f'({"reverse" if back <= fwd else "forward"}, heading {math.degrees(heading):.0f}°), then replan')
        return True

    def escape_step(self):
        e = self.escape
        if not e:
            return
        try:
            t = self.tf_buffer.lookup_transform('map', 'base_footprint', Time()).transform
        except Exception:
            return
        x, y = t.translation.x, t.translation.y
        yaw = math.atan2(2 * (t.rotation.w * t.rotation.z + t.rotation.x * t.rotation.y),
                         1 - 2 * (t.rotation.y ** 2 + t.rotation.z ** 2))
        moved = math.hypot(e['from'][0] - x, e['from'][1] - y)
        face = yaw + math.pi if e['reverse'] else yaw           # 지금 차체가 나아가는 쪽
        err = math.atan2(math.sin(e['heading'] - face), math.cos(e['heading'] - face))
        # 나아가는 쪽(±35도)의 라이다 최소 거리
        ahead = min((r for a, r in self.scan_polar
                     if abs(math.atan2(math.sin(a - (math.pi if e['reverse'] else 0.0)),
                                       math.cos(a - (math.pi if e['reverse'] else 0.0)))) < 0.61), default=9.0)
        why = ('far enough' if moved >= ESCAPE_DIST else
               'clear' if moved >= 0.15 and self.scan_min >= ESCAPE_CLEAR else
               'blocked that way' if ahead < ESCAPE_REAR_MIN and abs(err) < 0.5 else
               'timeout' if time.monotonic() > e['until'] else
               'goal ended' if not self.nav_active and not e['idle'] else '')
        if why:
            self.drive(Twist())
            self.escape = None
            self.fail_at, self.fail_count = None, 0
            if e['block'] and moved >= BLOCK_RADIUS + 0.1 and self.nav_active:
                self.blocks.append(e['block'])
                self.publish_blocks()
                self.get_logger().warn(f'stuck twice at ({e["block"][0]:.2f}, {e["block"][1]:.2f}) → block that spot')
            self.get_logger().warn(f'moved away {moved:.2f}m ({why}), nearest obstacle now {self.scan_min:.2f}m → replan from here')
            return
        cmd = Twist()
        cmd.angular.z = max(-0.8, min(0.8, 2.0 * err))
        if abs(err) < 0.5:
            cmd.linear.x = -ESCAPE_SPEED if e['reverse'] else ESCAPE_SPEED
        self.drive(cmd)

    # ------------------------------------------------------------ 금지구역
    def on_keepout(self, msg):
        try:
            zones = sorted((float(z['x1']), float(z['y1']), float(z['x2']), float(z['y2'])) for z in json.loads(msg.data)['zones'])
        except (ValueError, KeyError, TypeError):
            return
        if zones != self.zones:
            self.get_logger().info(f'keepout zones: {len(zones)}')
            self.zones = zones
            self.publish_keepout()
            self.publish_blocks()           # 계획 맵에는 바로 넣는다(달리는 중이면 다음 경로 검사에서 다시 계획)

    def zone_cells(self):
        """금지구역이 덮는 지도 칸 {(cx, cy)}. 걸친 칸은 모두 넣는다."""
        m = self.map_msg
        if m is None:
            return set()
        res, w, h = m.info.resolution, m.info.width, m.info.height
        ox, oy = m.info.origin.position.x, m.info.origin.position.y
        cells = set()
        for x1, y1, x2, y2 in self.zones:
            for cx in range(max(0, int(math.floor((x1 - ox) / res))), min(w, int(math.ceil((x2 - ox) / res)))):
                for cy in range(max(0, int(math.floor((y1 - oy) / res))), min(h, int(math.ceil((y2 - oy) / res)))):
                    cells.add((cx, cy))
        return cells

    def publish_keepout(self):
        """제어 맵(지역 비용 지도)의 keepout_layer 가 받는 격자. 구역이 없어도 빈 격자를 보낸다(층이 지도를 기다리지 않게)."""
        m = self.map_msg
        if m is None:
            return
        key = (tuple(self.zones), m.info.width, m.info.height, m.info.origin.position.x, m.info.origin.position.y)
        if key == self.keepout_sent:
            return
        self.keepout_sent = key
        grid = OccupancyGrid()
        grid.header.frame_id = m.header.frame_id
        grid.header.stamp = self.get_clock().now().to_msg()
        grid.info = m.info
        data = [0] * (m.info.width * m.info.height)
        for cx, cy in self.zone_cells():
            data[cy * m.info.width + cx] = 100
        grid.data = data
        self.keepout_pub.publish(grid)

    def publish_blocks(self):
        m = self.map_msg
        if m is None:
            return
        res, w, h = m.info.resolution, m.info.width, m.info.height
        ox, oy = m.info.origin.position.x, m.info.origin.position.y
        n = int(BLOCK_RADIUS / res)
        cells = {(int((bx - ox) / res) + i, int((by - oy) / res) + j) for bx, by in self.blocks
                 for i in range(-n, n + 1) for j in range(-n, n + 1) if math.hypot(i, j) * res <= BLOCK_RADIUS}
        if not self.shadow_off:
            gx, gy = self.plan[-1] if self.plan else (1e9, 1e9)
            cells |= {(cx, cy) for cx, cy in self.fill
                      if math.hypot(ox + (cx + 0.5) * res - gx, oy + (cy + 0.5) * res - gy) > SHADOW_GOAL_CLEAR}
        cells |= self.zone_cells()          # 금지구역은 목표와 상관없이 늘 막혀 있다
        grid = OccupancyGrid()
        grid.header.frame_id = m.header.frame_id
        grid.header.stamp = self.get_clock().now().to_msg()
        grid.info = m.info
        data = [0] * (w * h)
        for cx, cy in cells:
            if 0 <= cx < w and 0 <= cy < h:
                data[cy * w + cx] = 100
        grid.data = data
        self.block_pub.publish(grid)

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
        if not self.escape:                  # 지나온 길(물러나는 동안은 쌓지 않는다)
            xy = (p.pose.position.x, p.pose.position.y)
            if not self.trail or math.hypot(xy[0] - self.trail[-1][0], xy[1] - self.trail[-1][1]) >= 0.05:
                self.trail.append(xy)
                del self.trail[:-60]

    def on_cmd_nav(self, msg):
        t = msg.twist if STAMPED else msg
        self.cmd = (t.linear.x, t.angular.z, time.monotonic())

    def drive(self, twist):
        """바퀴 명령을 보낸다(Jazzy 는 TwistStamped 로 감싼다). 브리지가 직접 내는 명령은 빠져나오기 · 비상구 앞 다가가기뿐이다."""
        if STAMPED:
            m = TwistStamped()
            m.header.stamp = self.get_clock().now().to_msg()
            m.header.frame_id = 'base_link'
            m.twist = twist
            self.cmd_pub.publish(m)
        else:
            self.cmd_pub.publish(twist)

    def publish_drive_plan(self):
        c = self.cmd
        if c is None or time.monotonic() - c[2] > 0.5 or (abs(c[0]) < 0.01 and abs(c[1]) < 0.05):
            return                          # 제어기가 명령을 내지 않는 중(정지 · 도착)
        try:
            t = self.tf_buffer.lookup_transform('map', 'base_footprint', Time())
        except Exception:
            return
        q = t.transform.rotation
        x, y = t.transform.translation.x, t.transform.translation.y
        yaw = math.atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y * q.y + q.z * q.z))
        v, w, dt = c[0], c[1], DRIVE_HORIZON / DRIVE_STEPS
        traj = [[round(x, 3), round(y, 3)]]
        for _ in range(DRIVE_STEPS):
            yaw += w * dt / 2               # 구간 가운데 방향으로 나아간다(호를 고르게)
            x, y = x + v * dt * math.cos(yaw), y + v * dt * math.sin(yaw)
            yaw += w * dt / 2
            traj.append([round(x, 3), round(y, 3)])
        self.drive_pub.publish(String(data=json.dumps({'v': round(v, 3), 'w': round(w, 3), 'traj': traj})))

    def on_scan(self, scan):
        """스캔이 찍힌 시각의 TF(map → 라이다)로 점을 지도 좌표로 바꿔 보낸다."""
        try:
            t = self.tf_buffer.lookup_transform('map', scan.header.frame_id, Time.from_msg(scan.header.stamp),
                                                timeout=Duration(seconds=0.1))
        except Exception:
            return
        tx, ty = t.transform.translation.x, t.transform.translation.y
        q = t.transform.rotation
        yaw = math.atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y * q.y + q.z * q.z))
        c, s = math.cos(yaw), math.sin(yaw)
        rear = [r for i, r in enumerate(scan.ranges) if scan.range_min < r < scan.range_max
                and abs(math.atan2(math.sin(scan.angle_min + i * scan.angle_increment - math.pi),
                                   math.cos(scan.angle_min + i * scan.angle_increment - math.pi))) < 0.61]
        self.rear_min = min(rear, default=9.0)
        self.scan_polar = [(scan.angle_min + i * scan.angle_increment, r) for i, r in enumerate(scan.ranges)
                           if scan.range_min < r < scan.range_max]
        self.scan_min = min((r for _, r in self.scan_polar), default=9.0)
        pts = []
        for i in range(0, len(scan.ranges), 2):
            r = scan.ranges[i]
            if not (scan.range_min < r < scan.range_max):
                continue
            a = scan.angle_min + i * scan.angle_increment
            lx, ly = r * math.cos(a), r * math.sin(a)
            pts.append([round(tx + c * lx - s * ly, 3), round(ty + s * lx + c * ly, 3)])
        self.scan_map_pub.publish(String(data=json.dumps({'pts': pts})))
        if time.monotonic() - self.shadow_at >= 1.0 and self.map_msg is not None:   # 전역 비용 지도 갱신 주기(1Hz)에 맞춘다
            self.shadow_at = time.monotonic()
            m = self.map_msg
            res, ox, oy = m.info.resolution, m.info.origin.position.x, m.info.origin.position.y
            seen = {(int((x - ox) / res), int((y - oy) / res)) for x, y in self.shadow_points(scan, tx, ty, yaw)}
            if not self.nav_active:
                self.fill = seen                 # 서 있을 때: 지금 보이는 면만
            else:
                keep, n = set(), len(scan.ranges)
                for cx, cy in self.fill:         # 주행 중: 기억하되, 빔이 그 칸을 지나 더 멀리 갔으면(빈 곳) 지운다
                    dx, dy = ox + (cx + 0.5) * res - tx, oy + (cy + 0.5) * res - ty
                    i = int(round((math.atan2(dy, dx) - yaw - scan.angle_min) / scan.angle_increment)) % n
                    r = scan.ranges[i]
                    if not (r > math.hypot(dx, dy) + 0.15):      # inf 는 '끝까지 비었다' → 지운다. nan 은 남긴다
                        keep.add((cx, cy))
                self.fill = keep | seen

    def shadow_points(self, scan, tx, ty, yaw):
        """저장 지도에 없는 장애물의 보인 면에서, 면에 수직으로 뒤쪽 SHADOW_DEPTH 까지의 점을 낸다(장애물의 몸통)."""
        m = self.map_msg
        res, w, h = m.info.resolution, m.info.width, m.info.height
        ox, oy, data = m.info.origin.position.x, m.info.origin.position.y, m.data

        def cell(x, y):                      # 0 빈 곳, 1 벽, -1 모름 · 지도 밖
            cx, cy = int((x - ox) / res), int((y - oy) / res)
            if not (0 <= cx < w and 0 <= cy < h):
                return -1
            v = data[cy * w + cx]
            return -1 if v < 0 else 1 if v >= 65 else 0

        k = int(SHADOW_WALL_TOL / res)
        n = len(scan.ranges)
        new = [False] * n                    # 이 빔이 '새 장애물'에 닿았는가
        dirs = [None] * n
        for i in range(n):
            r = scan.ranges[i]
            if not (scan.range_min < r < scan.range_max):
                continue
            a = yaw + scan.angle_min + i * scan.angle_increment
            dx, dy = math.cos(a), math.sin(a)
            dirs[i] = (dx, dy)
            hx, hy = tx + r * dx, ty + r * dy
            new[i] = cell(hx, hy) == 0 and not any(
                cell(hx + u * res, hy + v * res) != 0 for u in range(-k, k + 1) for v in range(-k, k + 1))
        # 이웃한 빔끼리 이어 장애물의 '면'(점의 줄)을 만든다
        runs, run = [], []
        for i in range(n):
            if new[i] and (not run or abs(scan.ranges[i] - scan.ranges[run[-1]]) < 0.15 and i - run[-1] == 1):
                run.append(i)
            else:
                if len(run) >= 3:
                    runs.append(run)
                run = [i] if new[i] else []
        if len(run) >= 3:
            runs.append(run)
        hit = {i: (tx + scan.ranges[i] * dirs[i][0], ty + scan.ranges[i] * dirs[i][1]) for r in runs for i in r}

        def straight(r):                     # 모서리에서 나눠 곧은 면들로(양 끝을 이은 선에서 가장 먼 점이 6cm 넘으면 거기서 자른다)
            (ax, ay), (bx, by) = hit[r[0]], hit[r[-1]]
            seg = math.hypot(bx - ax, by - ay)
            if len(r) < 3 or seg < 1e-3:
                return [r]
            dev = [abs((bx - ax) * (hit[i][1] - ay) - (by - ay) * (hit[i][0] - ax)) / seg for i in r]
            k = max(range(len(r)), key=lambda q: dev[q])
            return [r] if dev[k] < 0.06 else straight(r[:k + 1]) + straight(r[k:])

        self.new_hits = list(hit.values())
        out = []
        for r in (f for run in runs for f in straight(run)):
            (ax, ay), (bx, by) = hit[r[0]], hit[r[-1]]
            seg = math.hypot(bx - ax, by - ay)
            if seg < 0.1:                    # 너무 짧은 면은 방향을 믿을 수 없다
                continue
            # 면 전체(양 끝)로 방향을 정한다. 이웃한 두 점만으로 정하면 잡음 1cm 에 수직 방향이 10도씩 틀어져 옆의 틈까지 번진다
            nx, ny = -(by - ay) / seg, (bx - ax) / seg
            if nx * (ax - tx) + ny * (ay - ty) < 0:             # 로봇에서 멀어지는 쪽(면의 뒤)
                nx, ny = -nx, -ny
            steps = max(1, int(seg / SHADOW_STEP))
            for q in range(steps + 1):                          # 면의 양 끝 사이만 채운다(폭은 보인 면 그대로)
                sx, sy = ax + (bx - ax) * q / steps, ay + (by - ay) * q / steps
                d = SHADOW_STEP
                while d <= SHADOW_DEPTH:
                    x, y = sx + d * nx, sy + d * ny
                    if cell(x, y) != 0:
                        break
                    out.append((x, y))
                    d += SHADOW_STEP
        return out

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
            z = d.get('exitZone')
            if isinstance(z, list) and len(z) == 4:
                x1, y1, x2, y2 = (float(v) for v in z)
                g['exit_zone'] = (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))
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
                 stalled=False, user_cancel=False, preempted=False, handle=None, retried=False, retries=0, escapes=0)
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
        if g.get('exit_done'):          # 비상구 앞 구역에서 이미 진입 불가로 끝냄(그때 보낸 취소의 결과)
            return
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
        elif self.in_exit_zone(g):
            self.exit_blocked(g, 'goal failed')
            return
        else:
            # 실패했다 → 붙어 있으면 빠져나오고, 비용 지도를 비운 뒤, 길이 있으면 다시 보낸다(recover)
            self.recover(g, extra)
            return
        if self.goal is g:
            self.goal = None

    def recover(self, g, extra):
        """Nav2 목표가 실패한 뒤: 장애물에 붙어 있으면 먼저 빠져나온다(붙은 자리에서는 출발점이 충돌 구역이라 길이 있어도
        '경로 없음'이 된다). 그다음 비용 지도의 오래된 표시를 지우고, 새 스캔이 반영된 뒤 현재 위치에서 경로를 다시 계산한다.
        주행 중의 빠져나오기는 Nav2 가 내는 정지 명령과 섞여 느리다. 여기서는 Nav2 가 쉬고 있어 방해가 없다."""
        def after():
            self.clear_costmaps()
            self.create_timer_once(3.0, lambda: self.classify(g, extra))

        xy = self.map_xy()
        if xy and self.scan_min < ESCAPE_NEAR and g['escapes'] < 4 and self.start_escape(xy, idle=True):
            g['escapes'] += 1

            def wait():
                if self.escape is None:
                    holder['t'].cancel()
                    after()
            holder = {'t': self.create_timer(0.2, wait)}
        else:
            after()

    def create_timer_once(self, sec, fn):
        holder = {}

        def run():
            holder['t'].cancel()
            fn()
        holder['t'] = self.create_timer(sec, run)

    def classify(self, g, extra):
        def done(code, reason):
            z = g.get('exit_zone')
            if (code == 'BLOCKED_NO_PATH' and z and not g.get('exit_done') and self.goal is g
                    and len(self.exit_hits(z)) >= EXIT_MIN_HITS):
                # 멀리서 본 비상구 앞 적재: 복구 · 재계획을 다 해도 길이 없고 그 구역에 물건이 보인다 → 다가가 찍고 알린다
                return self.exit_blocked(g, 'no path, seen from afar')
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
                    if self.scan_min < ESCAPE_NEAR and g['escapes'] < 4 and not g['user_cancel'] and self.goal is g:
                        # 길이 없다고 나왔지만 아직 장애물에 붙어 있다 → 출발점 문제일 수 있으니 더 빠져나온 뒤 다시 본다
                        self.get_logger().warn(f'no path while {self.scan_min:.2f}m from an obstacle → move away and look again')
                        return self.recover(g, extra)
                    done('BLOCKED_NO_PATH', '경로 없음: 통로가 막혀 진입할 수 없음')
                elif g['retries'] < MAX_RETRIES and not g['user_cancel'] and self.goal is g:
                    # 길이 있다 → 다시 주행한다(오래된 표시 때문이었거나, 빠져나와 자세를 다시 잡았다)
                    g['retries'] += 1
                    self.get_logger().info(f'path exists → retry {g["retries"]}/{MAX_RETRIES}')
                    g.update(retried=True, stalled=False, best=None, progress_at=time.monotonic(), handle=None)
                    self.start_nav(g)
                else:
                    done(base, base_reason)
            h.get_result_async().add_done_callback(result)
        self.planner.send_goal_async(req).add_done_callback(accepted)

    # ------------------------------------------------------------ 비상구 앞 구역
    def in_exit_zone(self, g):
        """그 목표에 비상구 앞 구역이 있고, 지금 라이다에 보이는 '저장 지도에 없는 장애물'이 그 구역 안에 있는가.
        로봇 위치가 아니라 막은 물건의 위치로 본다: 비상구 앞 통로 밖(예: 통로로 들어가는 문)이 막힌 것은 주행 문제라
        다른 길로 돌아가야 하고, 통로 안에 물건이 있을 때만 비상구 앞 적재다. 로봇이 통로 밖에서 물건을 먼저 봐도 맞게 가린다."""
        z = g.get('exit_zone') if g else None
        if not z or g.get('exit_done'):
            return False
        xy = self.map_xy()
        if xy is None or math.hypot(max(z[0] - xy[0], 0, xy[0] - z[2]), max(z[1] - xy[1], 0, xy[1] - z[3])) > EXIT_NEAR_DIST:
            return False                 # 아직 멀다 → 평소처럼 복구 · 우회. 끝내 길이 없으면 classify 에서 다시 본다
        return len(self.exit_hits(z)) >= EXIT_MIN_HITS

    def exit_hits(self, z):
        m = EXIT_ZONE_MARGIN
        return [(x, y) for x, y in self.new_hits if z[0] + m <= x <= z[2] - m and z[1] + m <= y <= z[3] - m]

    def exit_blocked(self, g, why):
        """비상구 앞 구역 안에서 막힘: 복구 · 우회 · 재시도 없이 바로 진입 불가(BLOCKED_NO_PATH)로 끝낸다."""
        if g.get('exit_done') or self.goal is not g:
            return
        g['exit_done'] = True
        self.get_logger().warn(f'blocked inside exit zone ({why}) → approach to {EXIT_APPROACH_DIST}m, then BLOCKED_NO_PATH')
        z = g['exit_zone']
        inz = [(round(x, 2), round(y, 2)) for x, y in self.exit_hits(z)]
        self.get_logger().info(f'exit zone hits n={len(inz)}: {inz[:6]} robot={self.map_xy()}')
        self.escape = None
        self.drive(Twist())
        if g.get('handle'):
            g['handle'].cancel_goal_async()
        # 막은 물건이 멀리서 먼저 보였을 수 있다 → 근거 사진이 잘 나오게 그 앞 EXIT_APPROACH_DIST 까지 천천히 다가간 뒤 알린다
        # 취소와 엇갈려 Nav2 복구 동작(제자리 회전)이 몇 초 더 돌 수 있다 → 3초 뒤부터 움직인다(명령이 섞이지 않게)
        now = time.monotonic()
        # 1) 목적지 앞 EXIT_APPROACH_BACK 지점까지 Nav2 로 간다(문 앞 · 모퉁이에서 막혔을 때 통로 안으로 들어가 정면에 서려고).
        #    막은 물건은 목적지 쪽에 있으므로 그 지점까지는 보통 길이 있다. 못 가면 그 자리에서 2) 로 넘어간다.
        # 2) 목적지 쪽을 보며 천천히 다가가 앞 EXIT_APPROACH_DIST 에서 멈추고 알린다
        self.approach = {'g': g, 'start': now + 3.0, 'until': now + 3.0 + EXIT_APPROACH_NAV_SEC, 'stage': 'nav',
                         'handle': None, 'sent': False}

    def approach_nav(self, a, g):
        """다가가기 1단계: 목적지 앞 EXIT_APPROACH_BACK 지점까지 Nav2 로. 끝나거나(성공 · 실패) 시간이 다 되면 2단계로."""
        ax = g['x'] - EXIT_APPROACH_BACK * math.cos(g['yaw'])
        ay = g['y'] - EXIT_APPROACH_BACK * math.sin(g['yaw'])
        xy = self.map_xy()

        def creep():
            if a.get('handle'):
                a['handle'].cancel_goal_async()
            a.update(stage='creep', until=time.monotonic() + EXIT_APPROACH_SEC)

        if not a['sent']:
            a['sent'] = True
            # 이미 그 지점보다 목적지에 가깝거나 Nav2 가 준비되지 않았으면 바로 2단계
            if xy is None or math.hypot(g['x'] - xy[0], g['y'] - xy[1]) <= EXIT_APPROACH_BACK + 0.15                     or not self.nav.server_is_ready():
                return creep()
            self.get_logger().info(f'exit approach: go to ({ax:.2f}, {ay:.2f}) in front of the goal first')
            fut = self.nav.send_goal_async(NavigateToPose.Goal(pose=self.pose(ax, ay, g['yaw'])))

            def accepted(f):
                h = f.result()
                if not h.accepted or self.approach is not a:
                    return creep() if self.approach is a else None
                a['handle'] = h
                h.get_result_async().add_done_callback(lambda _r: creep() if self.approach is a and a['stage'] == 'nav' else None)
            fut.add_done_callback(accepted)
            return
        if time.monotonic() > a['until']:
            creep()

    def approach_step(self):
        """비상구 앞에서 막힌 뒤: 목적지 쪽을 보며 천천히 앞으로 간다. 앞(±20°) 라이다 거리가 EXIT_APPROACH_DIST 이하이거나
        목적지에 그만큼 가까워지거나 시간이 다 되면 멈추고 진입 불가로 알린다. Nav2 를 거치지 않는 직접 명령이라 아주 느리게 간다."""
        a = self.approach
        if not a:
            return
        g = a['g']
        if time.monotonic() < a['start']:
            return
        if a['stage'] == 'nav':
            self.approach_nav(a, g)
            return
        try:
            t = self.tf_buffer.lookup_transform('map', 'base_footprint', Time()).transform
            x, y = t.translation.x, t.translation.y
            yaw = math.atan2(2 * (t.rotation.w * t.rotation.z + t.rotation.x * t.rotation.y),
                             1 - 2 * (t.rotation.y ** 2 + t.rotation.z ** 2))
        except Exception:
            x = y = yaw = None
        if x is None:
            ahead, err = 9.0, 0.0
        else:
            err = math.atan2(g['y'] - y, g['x'] - x) - yaw          # 목적지 쪽(로봇 기준 각)
            err = math.atan2(math.sin(err), math.cos(err))
            # 앞 거리는 로봇 정면이 아니라 목적지 쪽 좁은 범위(±7°)로 잰다: 아직 돌고 있거나 벽에 붙어 있을 때 옆 벽을 장애물로 보지 않게
            ahead = min((r for ang, r in self.scan_polar
                         if abs(math.atan2(math.sin(ang - err), math.cos(ang - err))) < 0.12 and r > 0.05), default=9.0)
        done = (x is None or time.monotonic() > a['until'] or (ahead <= EXIT_APPROACH_DIST and abs(err) < 0.3)
                or math.hypot(g['x'] - x, g['y'] - y) <= EXIT_APPROACH_DIST)
        if done:
            self.drive(Twist())
            self.approach = None
            self.get_logger().warn(f'exit approach done (obstacle ahead {ahead:.2f}m) → BLOCKED_NO_PATH')
            self.report(g, 'ABORTED', 'BLOCKED_NO_PATH', '경로 없음: 비상구 앞 통로가 막힘',
                        recoveries=g.get('recoveries', 0), traveled=round(g.get('traveled', 0.0), 2),
                        plannedLength=None if g.get('planned') is None else round(g['planned'], 2))
            if self.goal is g:
                self.goal = None
            return
        cmd = Twist()
        cmd.angular.z = max(-0.6, min(0.6, 1.5 * err))
        if abs(err) < 0.3 and ahead > EXIT_APPROACH_DIST:
            cmd.linear.x = EXIT_APPROACH_SPEED
        self.drive(cmd)

    def check_exit_stall(self):
        """비상구 앞 구역 안에서 EXIT_STALL_SEC 동안 목표에 가까워지지 못하면(장애물 앞에서 기다리기만 함) 막힌 것으로 본다."""
        g = self.goal
        if g and self.nav_active and self.in_exit_zone(g) and time.monotonic() - g.get('progress_at', time.monotonic()) > EXIT_STALL_SEC:
            self.exit_blocked(g, f'no progress for {EXIT_STALL_SEC:.0f}s')

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
