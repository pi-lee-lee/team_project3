#!/bin/bash
set -e
source /opt/ros/$ROS_DISTRO/setup.bash
# Gazebo Harmonic(gz sim)이 모델 · 사진 판 재질을 찾는 곳: TurtleBot3 모델 + 이 저장소의 모델(사진 판)
export GZ_SIM_RESOURCE_PATH="${GZ_SIM_RESOURCE_PATH}:$(ros2 pkg prefix turtlebot3_gazebo)/share/turtlebot3_gazebo/models:/sim/models"
export TURTLEBOT3_MODEL="${TURTLEBOT3_MODEL:-waffle_pi}"   # waffle_pi(라즈베리파이 카메라) 또는 waffle(RealSense)

# 카메라 · 라이다(gpu_lidar) 렌더링에 필요한 가상 디스플레이(GPU 없이 소프트웨어 OpenGL 로 그린다).
# 컨테이너가 재시작되면 이전 Xvfb 의 잠금 파일이 남아 새 Xvfb 가 뜨지 않는다 → 지우고 시작한다.
rm -f /tmp/.X99-lock /tmp/.X11-unix/X99
Xvfb :99 -screen 0 640x480x24 -nolisten tcp >/tmp/xvfb.log 2>&1 &
export DISPLAY=:99
for i in $(seq 1 50); do
  [ -e /tmp/.X11-unix/X99 ] && break
  sleep 0.2
done
if ! kill -0 $! 2>/dev/null || [ ! -e /tmp/.X11-unix/X99 ]; then
  echo "Xvfb 를 시작하지 못했습니다 (카메라 영상이 나오지 않음):" >&2
  cat /tmp/xvfb.log >&2
  exit 1
fi
echo "TurtleBot3 model: ${TURTLEBOT3_MODEL}, display ${DISPLAY}, mode ${SIM_MODE:-nav}"
exec ros2 launch /sim/sim.launch.py
