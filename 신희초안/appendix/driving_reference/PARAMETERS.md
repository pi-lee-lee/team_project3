# 적용값과 변경 위치

현재 소스·실행기 기준이다. S는 smooth_base.py, F는 fall_patrol.py다. 파일의 원본 경로와 사본은 [EVIDENCE](EVIDENCE.md), [SOURCE_INDEX](SOURCE_INDEX.md)에서 찾는다.

## ROS 2 파라미터와 덮어쓰기

부모 생성자가 내부 기본값을 설정한 뒤 F 생성자가 ROS 파라미터를 읽는다. linear_speed는 F의 값으로 덮어쓴다. 실행기는 순찰 노드에 server_url, voice_enabled:=true, waypoint_count:=3, linear_speed:=0.15를 전달한다.

| 항목 | 현재 값·단위 | 적용·변경 위치 |
| --- | --- | --- |
| linear_speed | 0.15 m/s | S326 기본값 → F101 덮어쓰기. 실행 인자 -p linear_speed:=값. F102는 0보다 크고 0.20 이하를 허용 |
| waypoint_count | 3개 | F94, 실행기203–204에서 3 지정. F102는 2~20 허용 |
| waypoint_wait_seconds | 기본 2 s | F95. 도착 후 대기 F581–595 |
| localization_timeout_sec | 기본 2 s | F81에서 저장. 현재 갱신 시간 검사에 사용되지 않음. F144–146은 current_pose 존재만 확인 |
| server_url | 실행기에서 서버 PC의 127.0.0.1:8000 | F84, 실행기154·203. Pi 음성용 서버 주소 인자와 구별 |
| voice_enabled | true | F89, 실행기204. false는 음성 교환만 제외하며 자세·영상 의존성은 유지 |
| pose_timeout_sec | 기본 1.5 s | F96·163–176·367–371. 메시지 시각·수신 경과·건강 상태 검사 |

파라미터를 바꾸려면 해당 ROS 노드의 실행 인자로 전달한다. 런타임 변경 콜백은 두 핵심 파일에서 확인되지 않아 재시작 적용을 기준으로 검토한다. map_frame·base_frame은 F82–83에서 선언되지만 이 주행 코드의 TF 조회·목표 변환에는 사용되지 않는다.

## smooth_base.py 내부 조정값

아래는 ROS 파라미터로 선언된 값이 아닌 내부 속성이다. 현재 실행 경로에서 자식이 덮어쓰지 않는다. 변경은 새 프로젝트의 사본에서 코드 또는 설정화를 검토한다.

| 항목 | 현재 값·단위 | 의미·근거 줄 |
| --- | --- | --- |
| max_angular | 0.45 rad/s | 최종 각속도 상한 S327·770·917 |
| lookahead | 0.35 m | 앞쪽 추종점 선택 S330·845 |
| goal_tolerance | 0.12 m | 도착 거리 S331·881 |
| robot_radius | 0.25 m | 장애물 부풀림 반경 S332·654. 물리 실측값의 보증은 아님 |
| obs_threshold | 0.30 m | 전방 ±30°의 회피 진입 S333·687·887 |
| stop_dist | 0.20 m | 전 방향 유효 라이다 최소거리에 따른 주행·회전 차단 S334·690·750 |
| replan_cooldown | 1.5 s | 경로 부재 시 회피 재계획·추종점 차단 재계획 S336·820·894. 회피 최초 진입은 즉시 재계획 |
| linear_accel / linear_decel | 0.12 / 0.20 m/s² | 선속도 증가·감소 제한 S339–340·765–768 |
| angular_accel / angular_decel | 0.70 / 1.00 rad/s² | 각속도 변화 제한 S341–342·769–771 |
| turn_in_place_angle / turn_exit_angle | 0.8 / 0.35 rad | 방향 오차에 따른 회전 진입/해제 S328·343·901–907 |
| turn_speed / avoid_turn | 0.30 / 0.25 rad/s | 추종 중 제자리 회전 / 장애물 회피 회전 S329·335 |
| goal_slow_distance | 0.50 m | 목표 감속 구간 계산 S344·910 |
| clearance_margin / clearance_weight | 0.30 m / 3.0 | 부풀린 장애물 밖의 추가 비용 S345–346·149–164 |
| obstacle_release / release_hold | 0.43 m / 0.4 s | 전방 여유가 유지되어야 회피 해제 S347–348·830–839 |
| scan_timeout | 0.6 s | 라이다 수신 경과 검사 S358·750 |
| frame_timeout | 최종 1.5 s | S368의 1.0을 F135에서 덮어씀 |
| estop_distance_threshold / estop_release_delay | 0.5 m / 0.8 s | 자세 메시지의 lidar 거리 근거를 사용한 사람 근접 정지·해제 F373–388 |

S758–788의 평활화는 dt를 0.001~0.10초로 제한한다. 긴급·차단·목표 변경 정지는 S738–744에서 평활화를 건너뛰고 0을 발행한다. stationary 회전도 선속도를 즉시 0으로 만든다.

## 설정 파일의 적용 대상

- params_robot.yaml의 최상위 노드는 lying_detector다. 영상·자세 판정 설정이며 patrol의 속도·순찰 지점·A* 값은 여기서 설정하지 않는다.
- tb3_localization_real.launch.py는 nav2_bringup에 설치된 params/nav2_params.yaml을 AMCL·지도 제공에 전달한다. 패키지의 params_robot.yaml과 별개다.
- new_map.yaml은 resolution 0.05 m/cell, origin [-3.94, -1.06, 0], trinary, occupied_thresh 0.65, free_thresh 0.25다. new_map.pgm은 124×75 셀이다. 이 지도에서 0.25 m 부풀림은 ceil(0.25/0.05)=5셀이다.
- 지도 임계값은 map_server가 점유격자로 바꾸는 설정이다. 주행 측 make_blocked_grid는 받은 격자 값이 0이 아닌 칸을 모두 막는다. 지도 origin의 회전은 0만 지원한다.
