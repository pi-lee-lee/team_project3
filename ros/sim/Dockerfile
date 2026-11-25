# sim 컨테이너 실행 환경 이미지 (코드는 넣지 않는다).
# compose 가 ros/sim/src → /sim, ros/robot/src → /robot, ros/maps → /maps 로 연결해 구동한다.
# ROS 2 배포판은 빌드 인자 ROS_DISTRO 한 곳에서 정한다(SCENARIOS.md 3.4). 기본 jazzy + Gazebo Harmonic(gz sim).
# 실제 터틀봇(라즈베리파이, Jazzy)과 같은 판이라 로봇 측 노드(ros/robot/src)를 그대로 쓴다(/cmd_vel 은 TwistStamped).
ARG ROS_DISTRO=jazzy
FROM ros:${ROS_DISTRO}-ros-base
ARG ROS_DISTRO

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
        ros-${ROS_DISTRO}-turtlebot3-gazebo \
        ros-${ROS_DISTRO}-turtlebot3-navigation2 \
        ros-${ROS_DISTRO}-navigation2 \
        ros-${ROS_DISTRO}-nav2-bringup \
        ros-${ROS_DISTRO}-slam-toolbox \
        ros-${ROS_DISTRO}-rosbridge-server \
        ros-${ROS_DISTRO}-rosapi \
        ros-${ROS_DISTRO}-web-video-server \
        ros-${ROS_DISTRO}-ros-gz \
        ros-${ROS_DISTRO}-compressed-image-transport \
        xvfb xauth libgl1-mesa-dri libegl1 mesa-utils \
    && rm -rf /var/lib/apt/lists/*

# 카메라 영상 압축 전송(JPEG): 카메라 영상 연결(ros_gz_image)이 /camera/image_raw/compressed 도 함께 발행한다.
# 서버는 이 압축 토픽만 받는다(실제 로봇에서 Wi-Fi 로 원본 영상을 보내지 않기 위해).
# ROS_DISTRO 는 기반 이미지가 환경 변수로도 넣어 둔다 → 스크립트는 /opt/ros/$ROS_DISTRO/setup.bash 를 쓴다.
ENV TURTLEBOT3_MODEL=waffle_pi \
    LIBGL_ALWAYS_SOFTWARE=1 \
    ROS_DOMAIN_ID=30 \
    SIM_MODE=nav

WORKDIR /sim
# 9090: rosbridge(WebSocket), 8080: web_video_server(MJPEG·스냅샷)
EXPOSE 9090 8080
# 상태 검사: 위치(odom)와 압축 카메라 영상(image_raw/compressed)이 모두 발행되어야 healthy
HEALTHCHECK --interval=15s --timeout=8s --start-period=150s --retries=10 \
    CMD bash -c "source /opt/ros/\$ROS_DISTRO/setup.bash && t=\$(timeout 6 ros2 topic list) && echo \"\$t\" | grep -q '^/odom$' && echo \"\$t\" | grep -q '^/camera/image_raw/compressed$'"
CMD ["bash", "/sim/entrypoint.sh"]
