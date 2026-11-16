"""시험용 적재물 놓기·치우기 (Gazebo 에 상자를 생성·삭제한다).

  /sim/tools/obstacle.sh place detour    C1 복도 팔레트 — 옆으로 비켜 지나갈 수 있음
  /sim/tools/obstacle.sh place reroute   C2 아래쪽 막힘 — 생산동을 거쳐 돌아가야 함
  /sim/tools/obstacle.sh place block     C2 위쪽 막힘 — P2(비상구 앞) 진입 불가
  /sim/tools/obstacle.sh clear [이름]     치우기 (이름이 없으면 전부)
"""
import sys

import rclpy
from gazebo_msgs.srv import DeleteEntity, SpawnEntity

sys.path.insert(0, '/sim/worlds')
from world_spec import OBSTACLES  # noqa: E402


def sdf(name, sx, sy):
    return f'''<sdf version="1.6"><model name="{name}"><static>true</static><link name="link">
<collision name="c"><geometry><box><size>{sx} {sy} 0.6</size></box></geometry></collision>
<visual name="v"><geometry><box><size>{sx} {sy} 0.6</size></box></geometry>
<material><ambient>0.55 0.4 0.2 1</ambient><diffuse>0.55 0.4 0.2 1</diffuse></material></visual>
</link></model></sdf>'''


def call(node, cli, req):
    if not cli.wait_for_service(timeout_sec=10):
        raise SystemExit('gazebo service not available')
    fut = cli.call_async(req)
    rclpy.spin_until_future_complete(node, fut, timeout_sec=15)
    return fut.result()


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ('place', 'clear'):
        raise SystemExit(__doc__)
    rclpy.init()
    node = rclpy.create_node('obstacle_tool')
    spawn = node.create_client(SpawnEntity, '/spawn_entity')
    delete = node.create_client(DeleteEntity, '/delete_entity')
    names = sys.argv[2:] or list(OBSTACLES)
    for n in names:
        if n not in OBSTACLES:
            raise SystemExit(f'unknown obstacle {n}: {list(OBSTACLES)}')
        x, y, sx, sy = OBSTACLES[n]
        if sys.argv[1] == 'place':
            req = SpawnEntity.Request(name=f'obstacle_{n}', xml=sdf(f'obstacle_{n}', sx, sy))
            req.initial_pose.position.x, req.initial_pose.position.y, req.initial_pose.position.z = x, y, 0.3
            r = call(node, spawn, req)
            print(f'place {n}: {r.success} {r.status_message}')
        else:
            r = call(node, delete, DeleteEntity.Request(name=f'obstacle_{n}'))
            print(f'clear {n}: {r.success}')
    rclpy.shutdown()


if __name__ == '__main__':
    main()
