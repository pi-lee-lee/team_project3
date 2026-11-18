#!/bin/bash
# 사용: docker compose exec sim /sim/tools/fire.sh list | place <자리> [normal|warning|emergency] [--detect] | detect <자리> [warning|emergency] | clear [자리]
source /opt/ros/humble/setup.bash
exec python3 /sim/tools/fire.py "$@"
