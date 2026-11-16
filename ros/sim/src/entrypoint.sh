#!/bin/bash
set -e
source /opt/ros/humble/setup.bash
source /usr/share/gazebo/setup.sh 2>/dev/null || true
export GAZEBO_MODEL_PATH="${GAZEBO_MODEL_PATH}:$(ros2 pkg prefix turtlebot3_gazebo)/share/turtlebot3_gazebo/models"
# 카메라 센서 렌더링에 필요한 가상 디스플레이
Xvfb :99 -screen 0 640x480x24 -nolisten tcp >/dev/null 2>&1 &
export DISPLAY=:99
sleep 1
exec ros2 launch /sim/sim.launch.py
