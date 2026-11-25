#!/bin/bash
# 사용: docker compose exec sim /sim/tools/target.sh gauge 0.35 | lamp red | extinguisher remove|move|restore | status | reset
source /opt/ros/$ROS_DISTRO/setup.bash
exec python3 /sim/tools/target.py "$@"
