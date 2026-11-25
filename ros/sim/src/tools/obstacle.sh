#!/bin/bash
# 사용: docker compose exec sim /sim/tools/obstacle.sh place block | clear
source /opt/ros/$ROS_DISTRO/setup.bash
exec python3 /sim/tools/obstacle.py "$@"
