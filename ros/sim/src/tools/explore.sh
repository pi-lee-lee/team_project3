#!/bin/bash
# SLAM 모드에서 경유점을 돌며 지도를 만든다: docker compose exec sim /sim/tools/explore.sh
source /opt/ros/$ROS_DISTRO/setup.bash
exec python3 /sim/tools/explore.py
