"""시뮬레이션 전체 실행.

SIM_MODE=nav  (기본) : 저장된 지도 + AMCL 위치 추정 + Nav2 — 실제 운영과 같은 구성
SIM_MODE=slam        : slam_toolbox 로 지도를 만들면서 Nav2 로 이동 — 지도 작성 단계
공통: Gazebo 서버(헤드리스) + TurtleBot3 + rosbridge + rosapi + 영상 서버 + 로봇 측 노드(목표 브리지, 워치독)
"""
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import ExecuteProcess, IncludeLaunchDescription, TimerAction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node
from nav2_common.launch import RewrittenYaml


def generate_launch_description():
    mode = os.environ.get('SIM_MODE', 'nav')
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
    spawn = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(tb3_gazebo, 'launch', 'spawn_turtlebot3.launch.py')),
        launch_arguments={'x_pose': '0.0', 'y_pose': '0.0'}.items())
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

    return LaunchDescription([
        gzserver, state_publisher, spawn, rosbridge, rosapi, video, watchdog,
        TimerAction(period=15.0, actions=[nav]),        # Gazebo·로봇이 뜬 뒤 Nav2 시작
        TimerAction(period=20.0, actions=[bridge]),
    ])
