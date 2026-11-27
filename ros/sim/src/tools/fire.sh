#!/bin/bash
# 사용: docker compose exec sim /sim/tools/fire.sh list | set <자리> normal|warning|emergency | reset | extinguish | detect <자리> [warning|emergency]
source /opt/ros/$ROS_DISTRO/setup.bash
exec python3 /sim/tools/fire.py "$@"
