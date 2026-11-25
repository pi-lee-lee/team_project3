"""시뮬레이션 전체 실행.

SIM_MODE=nav  (기본) : 저장된 지도(SIM_MAP: reference 설계도 지도(기본) / site SLAM 지도) + AMCL 위치 추정 + Nav2 — 실제 운영과 같은 구성
SIM_MODE=slam        : slam_toolbox 로 지도를 만들면서 Nav2 로 이동 — 지도 작성 단계
공통: Gazebo Harmonic 서버(헤드리스, gz sim -s) + TurtleBot3 + ros_gz 연결(토픽 · 카메라 · 월드 서비스)
      + rosbridge + rosapi + 영상 서버 + 로봇 측 노드(목표 브리지, 워치독)
      + 시뮬레이션 부담 줄이기: 시계 50Hz(clock_relay.py), 카메라는 누가 볼 때만 그림(camera_gate.py, SIM_CAMERA_ON_DEMAND=0 이면 늘 그림)
      + 오도메트리는 미끄러짐 없는 Gazebo OdometryPublisher(SIM_TRUE_ODOM=0 이면 패키지의 DiffDrive odom)
ROS 2 Jazzy: 실제 터틀봇과 같은 판이라 바퀴 명령 /cmd_vel 이 TwistStamped 다(TurtleBot3 Jazzy 연결 설정 그대로).
SIM_LAUNCHER=mock (기본) : 모의 투척 기구(/robot/mock_launcher.py)를 띄운다. none 이면 띄우지 않는다(투척 기구 없는 로봇)
"""
import os
import re

import yaml

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import ExecuteProcess, IncludeLaunchDescription, TimerAction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node
from nav2_common.launch import RewrittenYaml


LIDAR_MIN = float(os.environ.get('LIDAR_MIN_RANGE', '0.16'))
LIDAR_MAX = float(os.environ.get('LIDAR_MAX_RANGE', '8.0'))
# 카메라 · IMU 갱신 주기(Hz). Gazebo Harmonic 은 GPU 없이 소프트웨어로 그려 카메라 30Hz(패키지 기본)면 시뮬레이션이
# 실제 시간의 5% 남짓으로 느려졌다(서버 응답 · 계획이 함께 밀려 시간에 민감한 시험이 실패). 점검 사진 · 관제 영상에는 5Hz 면 된다.
CAMERA_HZ = float(os.environ.get('SIM_CAMERA_HZ', '5'))
IMU_HZ = float(os.environ.get('SIM_IMU_HZ', '50'))
# 바퀴 관절 상태(/joint_states) 주기. 패키지 모델은 물리 한 걸음(4ms)마다 내서 초당 160번 넘게 나왔다(tf 계산 노드가 매번 깨어남)
JOINT_HZ = float(os.environ.get('SIM_JOINT_HZ', '30'))
# 카메라는 '신호를 받을 때만 한 장 그리는' 카메라로 바꾸고, camera_gate.py 가 누가 영상을 받을 때만 CAMERA_HZ 로 신호를 보낸다.
# 그리는 일의 절반쯤이 카메라라 아무도 안 볼 때(0.5Hz 로만 그림)는 시뮬레이션이 빨라진다(0.88 → 0.95). 0 이면 패키지처럼 늘 그린다
CAMERA_ON_DEMAND = os.environ.get('SIM_CAMERA_ON_DEMAND', '1') != '0'
# 오도메트리(/odom · odom→base_footprint tf): Harmonic 의 바퀴 계산(DiffDrive)은 제자리 회전 · 빠져나오기 때 바퀴가 헛돌아
# 방향이 크게 틀어졌다(한 번의 e2e 동안 67°). AMCL 은 '시뮬레이션 odom 은 정확하다'고 보고 오차 계수를 0.05 로 둬서(nav2_params.yaml)
# 따라잡지 못하고 1m 넘게 밀렸다. 그래서 바퀴 구동은 DiffDrive 가 그대로 하고, odom 은 Gazebo 의 OdometryPublisher 가
# 로봇의 실제 움직임으로 낸다(Classic 때처럼 미끄러짐 없는 odom). 0 이면 패키지처럼 DiffDrive 의 odom 을 쓴다. 실제 로봇과는 관계없다
TRUE_ODOM = os.environ.get('SIM_TRUE_ODOM', '1') != '0'
WORLD = 'factory'      # world_spec.py 가 만드는 월드 이름(월드 서비스 /world/factory/... 의 이름)


def robot_sdf(tb3_gazebo, model):
    """TurtleBot3 Gazebo 모델에서 라이다 측정 거리만 실물에 맞게 바꾼 사본을 만든다.

    패키지 기본 모델은 LDS-01(0.12~3.5m)이다. 실물 라이다는 8m 이상 재므로(LDS-02: 0.16~8m)
    LIDAR_MIN_RANGE·LIDAR_MAX_RANGE 로 바꾼다. 카메라 · IMU 갱신 주기는 SIM_CAMERA_HZ · SIM_IMU_HZ(시뮬레이션 부담 줄이기).
    나머지(모양 · 바퀴 · 라이다 10Hz · 360점)는 그대로다.
    """
    src = os.path.join(tb3_gazebo, 'models', f'turtlebot3_{model}', 'model.sdf')
    sdf = open(src, encoding='utf-8').read()
    i = sdf.index('<sensor name="hls_lfcd_lds"')
    j = sdf.index('</sensor>', i)
    lidar = re.sub(r'<range>\s*<min>[^<]*</min>\s*<max>[^<]*</max>',
                   f'<range>\n            <min>{LIDAR_MIN}</min>\n            <max>{LIDAR_MAX}</max>', sdf[i:j], count=1)
    if lidar == sdf[i:j]:
        raise RuntimeError(f'lidar range block not found in {src}')
    sdf = sdf[:i] + lidar + sdf[j:]
    sdf = _sensor_rate(sdf, 'camera', CAMERA_HZ)
    if CAMERA_ON_DEMAND:
        sdf = _triggered_camera(sdf)
    if TRUE_ODOM:
        sdf = _true_odom(sdf)
    sdf = _sensor_rate(sdf, 'tb3_imu', IMU_HZ)
    jsp = '<plugin filename="gz-sim-joint-state-publisher-system" name="gz::sim::systems::JointStatePublisher">'
    if jsp in sdf:
        sdf = sdf.replace(jsp, jsp + f'\n      <update_rate>{JOINT_HZ:g}</update_rate>', 1)
    out = f'/tmp/turtlebot3_{model}.sdf'
    with open(out, 'w', encoding='utf-8') as f:
        f.write(sdf)
    return out


def _true_odom(sdf):
    """DiffDrive 의 odom · tf 를 쓰지 않는 토픽으로 돌리고, OdometryPublisher 가 같은 이름(odom, /tf)으로 낸다."""
    i = sdf.index('<plugin filename="gz-sim-diff-drive-system"')
    j = sdf.index('</plugin>', i)
    dd = sdf[i:j]
    for a, b in (('<odom_topic>odom</odom_topic>', '<odom_topic>diff_drive/odom_unused</odom_topic>'),
                 ('<tf_topic>/tf</tf_topic>', '<tf_topic>/diff_drive/tf_unused</tf_topic>')):
        if a not in dd:
            raise RuntimeError(f'DiffDrive 설정에 {a} 가 없습니다')
        dd = dd.replace(a, b)
    odom = ('\n    <plugin filename="gz-sim-odometry-publisher-system" name="gz::sim::systems::OdometryPublisher">'
            '<odom_frame>odom</odom_frame><robot_base_frame>base_footprint</robot_base_frame>'
            '<odom_topic>odom</odom_topic><tf_topic>/tf</tf_topic>'
            '<odom_publish_frequency>30</odom_publish_frequency><dimensions>2</dimensions></plugin>')
    return sdf[:i] + dd + sdf[j:j + len('</plugin>')] + odom + sdf[j + len('</plugin>'):]


def _triggered_camera(sdf):
    """카메라 센서를 /camera/trigger 신호가 올 때만 그리게 한다(<triggered> 는 SDF 1.9 부터라 판을 올린다)."""
    k = sdf.find('<sensor name="camera"')
    c = sdf.index('<camera', k)
    c = sdf.index('>', c) + 1
    sdf = sdf[:c] + '\n          <triggered>true</triggered><trigger_topic>/camera/trigger</trigger_topic>' + sdf[c:]
    return sdf.replace('<sdf version="1.8">', '<sdf version="1.9">', 1)


def _sensor_rate(sdf, name, hz):
    """<sensor name="name"> 안의 첫 <update_rate> 를 hz 로 바꾼다(그 센서가 없으면 그대로)."""
    k = sdf.find(f'<sensor name="{name}"')
    if k < 0:
        return sdf
    e = sdf.index('</sensor>', k)
    part = re.sub(r'<update_rate>[^<]*</update_rate>', f'<update_rate>{hz:g}</update_rate>', sdf[k:e], count=1)
    return sdf[:k] + part + sdf[e:]


def bridge_yaml(tb3_gazebo, model):
    """TurtleBot3 연결 설정에서 시계(clock)만 뺀 사본. 시계는 clock_relay.py 가 줄여서 넘긴다(Gazebo 는 물리 한 걸음마다 낸다)."""
    src = os.path.join(tb3_gazebo, 'params', f'turtlebot3_{model}_bridge.yaml')
    entries = yaml.safe_load(open(src, encoding='utf-8'))
    keep = [e for e in entries if e.get('ros_topic_name') != 'clock']
    if len(keep) != len(entries) - 1:
        raise RuntimeError(f'clock entry not found in {src}')
    out = f'/tmp/turtlebot3_{model}_bridge.yaml'
    with open(out, 'w', encoding='utf-8') as f:
        yaml.safe_dump(keep, f, sort_keys=False)
    return out


def generate_launch_description():
    mode = os.environ.get('SIM_MODE', 'nav')
    model = os.environ.get('TURTLEBOT3_MODEL', 'waffle_pi')
    ros_gz_sim = get_package_share_directory('ros_gz_sim')
    tb3_gazebo = get_package_share_directory('turtlebot3_gazebo')
    nav2_bringup = get_package_share_directory('nav2_bringup')
    nav2_params = '/sim/config/nav2_params.yaml'   # TurtleBot3 기본값에서 이 시설에 맞게 고친 설정
    world = os.environ.get('SIM_WORLD', '/sim/worlds/inspection.world')
    # 저장 지도(1겹 기존 맵): SIM_MAP=reference(기본) 는 world_spec.py 가 월드와 같은 정의로 그린 설계도 지도라 시뮬레이션 월드와
    # 벽 위치가 똑같다. site 는 Gazebo Classic 때 SLAM 으로 만든 지도로, Harmonic 월드와 군데군데 어긋나(C2 동쪽 벽 윗부분 ·
    # 선반 몸통이 없음) 벽이 '새 장애물'로 잡히고 위치 추정이 밀렸다. site 는 지우지 않고 남겨 둔다(SIM_MAP=site 로 쓸 수 있다)
    map_name = os.environ.get('SIM_MAP', 'reference')
    map_yaml = f'/maps/{map_name}.yaml' if mode == 'nav' else '/maps/reference.yaml'
    if not os.path.exists(map_yaml):
        raise RuntimeError(f'지도가 없습니다: {map_yaml} (SIM_MAP 은 reference 또는 site)')

    params = RewrittenYaml(
        source_file=nav2_params,
        param_rewrites={'use_sim_time': 'True', 'yaml_filename': map_yaml},
        convert_types=True)

    # Gazebo 서버만(-s, 화면 없음), 바로 실행(-r). 월드 이름은 world_spec.py 의 <world name="factory">
    gzserver = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(ros_gz_sim, 'launch', 'gz_sim.launch.py')),
        launch_arguments={'gz_args': f'-r -s -v2 {world}', 'on_exit_shutdown': 'true'}.items())
    state_publisher = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(tb3_gazebo, 'launch', 'robot_state_publisher.launch.py')),
        launch_arguments={'use_sim_time': 'true'}.items())
    spawn = Node(package='ros_gz_sim', executable='create', output='screen',
                 arguments=['-world', WORLD, '-name', model, '-file', robot_sdf(tb3_gazebo, model),
                            '-x', '0.0', '-y', '0.0', '-z', '0.01'])
    # ROS ↔ Gazebo 연결: TurtleBot3 Jazzy 설정(바퀴 · 오도메트리 · tf · 라이다 · IMU · 카메라 정보)에서 시계만 뺀 것.
    # 시계(/clock)는 clock_relay.py 하나만 낸다 — 둘이 내면 tf 가 '시간이 거꾸로 감'으로 계속 비워진다
    gz_bridge = Node(package='ros_gz_bridge', executable='parameter_bridge', output='screen',
                     arguments=['--ros-args', '-p', f'config_file:={bridge_yaml(tb3_gazebo, model)}'])
    clock = ExecuteProcess(cmd=['python3', '/sim/clock_relay.py'], output='screen')
    gate = [ExecuteProcess(cmd=['python3', '/sim/camera_gate.py'], output='screen',
                           additional_env={'SIM_CAMERA_HZ': f'{CAMERA_HZ:g}'})] if CAMERA_ON_DEMAND else []
    # 시뮬레이션 도구(sim/tools)가 쓰는 월드 서비스: 물체 만들기 · 지우기 · 옮기기
    world_srv = Node(package='ros_gz_bridge', executable='parameter_bridge', name='world_services', output='screen',
                     arguments=[f'/world/{WORLD}/create@ros_gz_interfaces/srv/SpawnEntity',
                                f'/world/{WORLD}/remove@ros_gz_interfaces/srv/DeleteEntity',
                                f'/world/{WORLD}/set_pose@ros_gz_interfaces/srv/SetEntityPose'])
    # 카메라 영상: image_transport 로 내보내 /camera/image_raw/compressed(JPEG)도 함께 나온다
    camera = Node(package='ros_gz_image', executable='image_bridge', output='screen', arguments=['/camera/image_raw'])
    # Nav2 서버(Jazzy 는 열네 개)를 한 프로세스로 합친다(use_composition). 따로 띄우면 가만히 있어도 서버마다 통신 · 시계 처리로
    # 10~26% 씩, 합쳐 2코어 남짓을 써서 시뮬레이션 속도가 0.65 까지 떨어졌다 → 합치면 0.9 넘게
    nav = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(nav2_bringup, 'launch', 'bringup_launch.py')),
        launch_arguments={'slam': 'True' if mode == 'slam' else 'False', 'map': map_yaml,
                          'use_sim_time': 'True', 'params_file': params, 'autostart': 'True',
                          'use_composition': 'True'}.items())

    rosbridge = Node(package='rosbridge_server', executable='rosbridge_websocket', name='rosbridge_websocket',
                     parameters=[{'port': 9090}])
    rosapi = Node(package='rosapi', executable='rosapi_node', name='rosapi')   # 토픽 목록 조회(제공 기능 확인)
    video = Node(package='web_video_server', executable='web_video_server', name='web_video_server',
                 parameters=[{'port': 8080, 'address': '0.0.0.0'}])
    # 로봇 측 노드(ros/robot/src → /robot): 실제 로봇에도 같은 노드를 둔다
    bridge = ExecuteProcess(cmd=['python3', '/robot/nav2_goal_bridge.py'], output='screen',
                            additional_env={'SIM_MODE': mode})
    watchdog = ExecuteProcess(cmd=['python3', '/robot/cmd_vel_watchdog.py'], output='screen')
    # 시뮬레이션 터틀봇에는 투척 기구가 없다 → 같은 토픽 계약에 답하는 모의 노드(실로봇은 launcher_bridge.py)
    launcher_mode = os.environ.get('SIM_LAUNCHER', 'mock')
    if launcher_mode not in ('mock', 'none'):
        raise RuntimeError(f'SIM_LAUNCHER 는 mock 또는 none 이어야 합니다: {launcher_mode}')
    launcher = [ExecuteProcess(cmd=['python3', '/robot/mock_launcher.py'], output='screen')] if launcher_mode == 'mock' else []
    # 시뮬레이션 명령 노드: 웹의 "시연" 화면이 토픽으로 시뮬레이션 도구(fire · target)를 실행한다(시뮬레이션 전용)
    launcher.append(ExecuteProcess(cmd=['python3', '/sim/tools/sim_control.py'], output='screen'))

    return LaunchDescription([
        gzserver, clock, gz_bridge, world_srv, camera, *gate, state_publisher,
        TimerAction(period=5.0, actions=[spawn]),       # 월드가 뜬 뒤 로봇 만들기
        rosbridge, rosapi, video, watchdog, *launcher,
        TimerAction(period=15.0, actions=[nav]),        # Gazebo·로봇이 뜬 뒤 Nav2 시작
        TimerAction(period=20.0, actions=[bridge]),
    ])
