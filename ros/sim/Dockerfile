# sim 컨테이너 실행 환경 이미지 (코드는 넣지 않는다).
# compose 가 ros/sim/src → /sim, ros/robot/src → /robot, ros/maps → /maps 로 연결해 구동한다.
# Gazebo Classic 패키지는 amd64만 제공되므로 compose에서 platform: linux/amd64로 실행한다.
FROM ros:humble-ros-base

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
        ros-humble-turtlebot3-gazebo \
        ros-humble-turtlebot3-navigation2 \
        ros-humble-navigation2 \
        ros-humble-nav2-bringup \
        ros-humble-slam-toolbox \
        ros-humble-rosbridge-server \
        ros-humble-rosapi \
        ros-humble-web-video-server \
        xvfb xauth libgl1-mesa-dri mesa-utils \
    && rm -rf /var/lib/apt/lists/*

# 카메라 영상 압축 전송(JPEG): 카메라가 /camera/image_raw/compressed 도 함께 발행한다.
# 서버는 이 압축 토픽만 받는다(실제 로봇에서 Wi-Fi 로 원본 영상을 보내지 않기 위해).
RUN apt-get update && apt-get install -y --no-install-recommends ros-humble-compressed-image-transport \
    && rm -rf /var/lib/apt/lists/*

ENV TURTLEBOT3_MODEL=waffle_pi \
    LIBGL_ALWAYS_SOFTWARE=1 \
    ROS_DOMAIN_ID=30 \
    SIM_MODE=nav

WORKDIR /sim
# 9090: rosbridge(WebSocket), 8080: web_video_server(MJPEG·스냅샷)
EXPOSE 9090 8080
# 상태 검사: 위치(odom)와 압축 카메라 영상(image_raw/compressed)이 모두 발행되어야 healthy
HEALTHCHECK --interval=15s --timeout=8s --start-period=120s --retries=10 \
    CMD bash -c "source /opt/ros/humble/setup.bash && t=\$(timeout 6 ros2 topic list) && echo \"\$t\" | grep -q '^/odom$' && echo \"\$t\" | grep -q '^/camera/image_raw/compressed$'"
CMD ["bash", "/sim/entrypoint.sh"]
