# 기존 환경의 실행·연결

아래 명령은 이미 빌드·설정된 기존 Ubuntu ROS 2 Humble 환경을 설명한다. 이번 자료 제작에서는 명령 실행·빌드·의존성 설치를 수행하지 않았다. project_ws 원본은 읽기 전용으로 보존했다.

## 실행 위치와 순서

원래 실행기는 Pi에서 bringup·카메라·음성을, 서버 PC에서 지도/AMCL·자세 판정·순찰·FastAPI·영상 서버 등을 관리한다. 순찰 명령의 server_url은 서버 PC 내부의 127.0.0.1:8000이다. Pi 음성 프로그램에는 Pi에서 접근할 서버 주소를 별도로 전달한다. 실행기 근거는 scripts/demo_launcher.py 149–210행이다.

기존 환경의 절차는 bringup·카메라·웹 서버 준비 → 지도/AMCL과 RViz → 초기 위치 지정 → 자세 노드·순찰 노드 → 순찰 지점 지정 → 웹 시작 순이다. 실행기는 프로세스를 미리 띄울 수 있으나 주행은 위치·지점·센서·웹 조건이 충족되어야 진행된다.

다음은 별도 터미널에서 사용할 기존 명령 예시다. PROJECT_WS는 실행 PC의 준비된 전체 작업공간 경로로 설정한다.

```bash
export PROJECT_WS=/path/to/prepared/project_ws
source /opt/ros/humble/setup.bash
source "$PROJECT_WS/install/setup.bash"

ros2 launch my_bot_fall tb3_localization_real.launch.py \
  map:="$PROJECT_WS/src/maps/new_map.yaml" use_sim_time:=false

ros2 run my_bot_fall lying_detector --ros-args \
  --params-file "$(ros2 pkg prefix my_bot_fall)/share/my_bot_fall/config/params_robot.yaml"

ros2 run my_bot_fall patrol --ros-args \
  -p server_url:=http://127.0.0.1:8000 -p voice_enabled:=true \
  -p waypoint_count:=3 -p linear_speed:=0.15
```

각 ROS 2 실행 명령은 별도 터미널에서 실행한다. Pi bringup·카메라·음성, 서버는 먼저 준비한다. 음성을 제외하는 시험은 patrol에 voice_enabled:=false를 전달한다. 카메라·자세 판정·서버 조건은 계속 필요하다.

RViz의 2D Pose Estimate로 초기 위치를 지정하고 2D Goal Pose로 지점 3개를 등록한다. 지도 밖·부풀린 장애물 영역·서로 0.25m 미만인 지점은 거부한다. 마지막 지점 등록 후 ready에서 웹 시작 명령을 기다린다. 목표의 최종 방향은 현재 추종의 도착 조건에 포함되지 않는다.

## 주행 노드가 사용하는 연결

| 방향 | 토픽·형식 | 용도·제공 주체 |
| --- | --- | --- |
| 입력 | /map · nav_msgs/OccupancyGrid | map_server. Transient Local·Reliable 구독 |
| 입력 | /amcl_pose · geometry_msgs/PoseWithCovarianceStamped | AMCL 위치·방향. 같은 지도 QoS로 구독 |
| 입력 | /goal_pose · geometry_msgs/PoseStamped | RViz 순찰 지점 등록. 빈 frame 또는 map 허용 |
| 입력 | /scan · sensor_msgs/LaserScan | bringup/라이다. Best Effort 구독 |
| 입력 | /image_raw/compressed · sensor_msgs/CompressedImage | 카메라. Best Effort, 수신 시각 확인·JPEG 보관 |
| 입력 | /pose_state · std_msgs/String | lying_detector의 JSON. stamp·people·camera_status·observation_valid 등을 검사 |
| 입력 | /rosout · rcl_interfaces/Log | 선택한 진단 로그 전달 |
| 출력 | /cmd_vel · geometry_msgs/Twist | 실제 이동 명령. 하나의 유효한 주행 발행 경로를 유지 |
| 출력 | /astar_path · nav_msgs/Path | RViz 계획 경로 |
| 출력 | /fall_patrol/state · String, /fall_patrol/waypoint · Int32 | 상태·현재 목적지 표시 |
| 선택적 교환 | /fall_patrol/voice_request·voice_result · String | 별도 Pi 음성 노드와 요청·결과 교환 |

map → odom → base_footprint와 로봇/라이다 프레임 연결은 AMCL·bringup 환경에서 확인한다. 이 주행 클래스는 /amcl_pose를 직접 사용한다. FallPatrol의 TF 관련 import·파라미터만으로 위치 freshness 검사가 수행되는 것은 아니다.

ROS_DOMAIN_ID·QoS·시계·센서 장착 축을 대조한다. 라이다는 base 진행 방향과 정렬된 장착을 전제로 계산하며 센서 오프셋 TF를 적용해 점을 변환하는 구현은 없다.

## HTTP·외부 프로그램

- /health, GET/PUT /control, PUT /status는 주기적인 웹 상태·실행 제어에 사용한다. /control은 drive가 run 또는 stop인 JSON을 요구한다.
- 사건 발생 시 POST /events multipart, GET/PATCH /events/{id}와 상태·사진·메모 처리가 필요하다.
- 별도 WebLog가 POST /logs를 전송한다. 로그는 최대 200건의 메모리 큐를 쓰는 best effort다. 이 로그 전송 실패와 주행 HTTP 실패의 영향은 다르다.
- 웹 주기는 처리 후 0.5초 대기, HTTP 제한은 1초다. /status 성공 후 갱신한 server_seen이 3초를 넘거나 HTTP 오류가 발생하면 정지·새 시작 대기로 간다.
- NumPy·OpenCV·rclpy·ROS 메시지·tf2_ros가 import된다. 별도 lying_detector는 모델·추론 의존성이 필요하다. setup.py의 install_requires는 setuptools만 나열하므로 전체 의존성을 자동 설치하지 않는다.

기존 localization launch는 지도 서버·AMCL·RViz를 구성한다. 실제 경로 계산·추종은 이 커스텀 코드가 수행한다. teleop·다른 주행 노드·Nav2 controller의 /cmd_vel 발행과 함께 사용할 때 제어권을 먼저 정한다.

## 발췌 묶음의 범위와 이식 검토

복사본에는 필수 보조 모듈 4개와 설정·실행기·지도·패키지 메타데이터를 넣었다. lying_detector_node.py·voice_node.py, 모델 파일, 서버 구현, 음성 스크립트·음원, 출력 장치 패키지, 설치된 nav2_params.yaml은 포함하지 않았다. 패키지 설치 메타데이터의 원래 모델·엔트리포인트 참조를 유지했으므로 빌드·실행하려면 전체 구성의 보완이 필요하다.

원본 demo_launcher.py는 전체 낙상·음성·NUCLEO 실행과 log/demo 생성을 포함한다. 여기서는 실행 설정을 읽기 위한 사본으로 다룬다. 원문 README의 프로젝트 밖 링크와 명령도 기존 전체 배치를 기준으로 해석한다.

다른 프로젝트에서는 순수 계산 함수와 추종·속도 제한을 우선 대조하고, 순찰 상태·웹 API·자세/음성 정책의 채택 여부를 각각 정한다. 부모의 estop_enabled만 바꿔도 자식의 자세·서버 조건이 제거되는 구조는 아니다. 새 프로젝트의 입력 유효성·정지·재시작 정책을 정한 뒤 연결한다.
