"""시뮬레이션 전체 실행.

SIM_MODE=nav  (기본) : 저장된 지도 + AMCL 위치 추정 + Nav2 — 실제 운영과 같은 구성
SIM_MODE=slam        : slam_toolbox 로 지도를 만들면서 Nav2 로 이동 — 지도 작성 단계
공통: Gazebo 서버(헤드리스) + TurtleBot3 + rosbridge + rosapi + 영상 서버 + 로봇 측 노드(목표 브리지, 워치독)
SIM_LAUNCHER=mock (기본) : 모의 투척 기구(/robot/mock_launcher.py)를 띄운다. none 이면 띄우지 않는다(투척 기구 없는 로봇)
"""
import os
import re

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import ExecuteProcess, IncludeLaunchDescription, TimerAction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node
from nav2_common.launch import RewrittenYaml


LIDAR_MIN = float(os.environ.get('LIDAR_MIN_RANGE', '0.16'))
LIDAR_MAX = float(os.environ.get('LIDAR_MAX_RANGE', '8.0'))


def robot_sdf(tb3_gazebo, model):
    """TurtleBot3 Gazebo 모델에서 라이다 측정 거리만 실물에 맞게 바꾼 사본을 만든다.

    패키지 기본 모델은 LDS-01(0.12~3.5m)이다. 실물 라이다는 8m 이상 재므로(LDS-02: 0.16~8m)
    LIDAR_MIN_RANGE·LIDAR_MAX_RANGE 로 바꾼다. 나머지(모양·바퀴·카메라·5Hz·360점)는 그대로다.
    """
    src = os.path.join(tb3_gazebo, 'models', f'turtlebot3_{model}', 'model.sdf')
    sdf = open(src, encoding='utf-8').read()
    i = sdf.index('<sensor name="hls_lfcd_lds"')
    j = sdf.index('</sensor>', i)
    lidar = re.sub(r'<range>\s*<min>[^<]*</min>\s*<max>[^<]*</max>',
                   f'<range>\n            <min>{LIDAR_MIN}</min>\n            <max>{LIDAR_MAX}</max>', sdf[i:j], count=1)
    if lidar == sdf[i:j]:
        raise RuntimeError(f'lidar range block not found in {src}')
    out = f'/tmp/turtlebot3_{model}.sdf'
    with open(out, 'w', encoding='utf-8') as f:
        f.write(sdf[:i] + lidar + sdf[j:])
    return out


def generate_launch_description():
    mode = os.environ.get('SIM_MODE', 'nav')
    model = os.environ.get('TURTLEBOT3_MODEL', 'waffle_pi')
    gazebo_ros = get_package_share_directory('gazebo_ros')
    tb3_gazebo = get_package_share_directory('turtlebot3_gazebo')
    nav2_bringup = get_package_share_directory('nav2_bringup')
    nav2_params = '/sim/config/nav2_params.yaml'   # TurtleBot3 기본값에서 이 시설에 맞게 고친 설정
    world = os.environ.get('SIM_WORLD', '/sim/worlds/inspection.world')
    map_yaml = '/maps/site.yaml' if os.path.exists('/maps/site.yaml') else '/maps/reference.yaml'

    params = RewrittenYaml(
        source_file=nav2_params,
        param_rewrites={'use_sim_time': 'True', 'yaml_filename': map_yaml},
        convert_types=True)

    gzserver = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(gazebo_ros, 'launch', 'gzserver.launch.py')),
        launch_arguments={'world': world}.items())
    state_publisher = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(tb3_gazebo, 'launch', 'robot_state_publisher.launch.py')),
        launch_arguments={'use_sim_time': 'true'}.items())
    spawn = Node(package='gazebo_ros', executable='spawn_entity.py', output='screen',
                 arguments=['-entity', model, '-file', robot_sdf(tb3_gazebo, model), '-x', '0.0', '-y', '0.0', '-z', '0.01'])
    nav = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(nav2_bringup, 'launch', 'bringup_launch.py')),
        launch_arguments={'slam': 'True' if mode == 'slam' else 'False', 'map': map_yaml,
                          'use_sim_time': 'True', 'params_file': params, 'autostart': 'True',
                          'use_composition': 'False'}.items())

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
        gzserver, state_publisher, spawn, rosbridge, rosapi, video, watchdog, *launcher,
        TimerAction(period=15.0, actions=[nav]),        # Gazebo·로봇이 뜬 뒤 Nav2 시작
        TimerAction(period=20.0, actions=[bridge]),
    ])
