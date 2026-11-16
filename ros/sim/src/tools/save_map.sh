#!/bin/bash
# SLAM 으로 만든 지도를 /maps/site.pgm, /maps/site.yaml 로 저장하고(호스트의 ros/maps), 고립 잡음 점을 정리한다.
set -e
source /opt/ros/humble/setup.bash
ros2 run nav2_map_server map_saver_cli -f /maps/site --ros-args -p use_sim_time:=true -p save_map_timeout:=10.0
rm -f /maps/site.raw.pgm
python3 /sim/tools/clean_map.py /maps/site.pgm
