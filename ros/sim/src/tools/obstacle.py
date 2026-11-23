"""시험용 적재물 놓기·치우기 (Gazebo 에 상자를 생성·삭제한다).

  /sim/tools/obstacle.sh place pallet    생산동 가운데 팔레트(P1 → P3 경로 위) — 옆으로 비켜 지나갈 수 있음
  /sim/tools/obstacle.sh place pallet2   전기실 가운데 팔레트(P1 → P4 경로 위) — 옆으로 비켜 지나갈 수 있음
  /sim/tools/obstacle.sh place door      생산동 → C2 문 막힘 — C1 · C2 아래쪽으로 돌아가야 함
  /sim/tools/obstacle.sh place aisle     전기실 → 생산동 문 바로 아래 골목 막힘(P4 → P1 경로 위) — 랙 1 위로 돌아 나와야 함
  /sim/tools/obstacle.sh place block     C2 위쪽 막힘 — P3(비상구 앞) 진입 불가
  /sim/tools/obstacle.sh place exit      비상구(P3) 바로 앞 낮은 상자(높이 0.22m) — 진입 불가, 다가온 로봇 사진에 상자가 찍힘
  /sim/tools/obstacle.sh place c1door    C1 → 생산동 문 막힘 — C1 복도 끝까지 가서 C2 로 올라가야 함(구역 밖 우회 시험)
  /sim/tools/obstacle.sh place detour    C1 복도 팔레트 — C1 을 따라갈 때 옆으로 비켜 지나감
  /sim/tools/obstacle.sh place reroute   C2 아래쪽 막힘
  /sim/tools/obstacle.sh place gap 0.6   C1 복도에 폭 0.6m 틈(좁은 통로)만 남김 — reroute 와 함께 놓으면 틈이 유일한 길
  /sim/tools/obstacle.sh clear [이름]     치우기 (이름이 없으면 전부, gap 포함). 비용 지도도 비운다 — 로봇이 보지 못하는 곳에
                                         치운 장애물의 표시가 남아 있으면 다음 계획이 없는 장애물을 돌아간다.
"""
import sys

import rclpy
from gazebo_msgs.srv import DeleteEntity, SpawnEntity
from nav2_msgs.srv import ClearEntireCostmap

sys.path.insert(0, '/sim/worlds')
from world_spec import OBSTACLE_H, OBSTACLES, gap_boxes  # noqa: E402


def sdf(name, sx, sy, h=0.6):
    return f'''<sdf version="1.6"><model name="{name}"><static>true</static><link name="link">
<collision name="c"><geometry><box><size>{sx} {sy} {h}</size></box></geometry></collision>
<visual name="v"><geometry><box><size>{sx} {sy} {h}</size></box></geometry>
<material><ambient>0.55 0.4 0.2 1</ambient><diffuse>0.55 0.4 0.2 1</diffuse></material></visual>
</link></model></sdf>'''


def call(node, cli, req):
    if not cli.wait_for_service(timeout_sec=10):
        raise SystemExit('gazebo service not available')
    fut = cli.call_async(req)
    # 로봇이 달리는 중에는 에뮬레이션 Gazebo 응답이 15초를 넘기기도 했다 → 넉넉히 기다린다
    rclpy.spin_until_future_complete(node, fut, timeout_sec=60)
    if fut.result() is None:
        raise SystemExit('gazebo service timed out')
    return fut.result()


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ('place', 'clear'):
        raise SystemExit(__doc__)
    rclpy.init()
    node = rclpy.create_node('obstacle_tool')
    spawn = node.create_client(SpawnEntity, '/spawn_entity')
    delete = node.create_client(DeleteEntity, '/delete_entity')
    args = sys.argv[2:]
    boxes = dict(OBSTACLES)
    if 'gap' in args:                      # place gap 폭 / clear gap
        i = args.index('gap')
        width = float(args.pop(i + 1)) if sys.argv[1] == 'place' else 0.5
        args[i:i + 1] = ['gap_s', 'gap_n']
        boxes.update(gap_boxes(width))
    elif sys.argv[1] == 'clear':
        boxes.update(gap_boxes(0.5))       # 치울 때는 이름만 쓴다
    names = args or list(boxes)
    for n in names:
        if n not in boxes:
            raise SystemExit(f'unknown obstacle {n}: {list(OBSTACLES) + ["gap 폭"]}')
        x, y, sx, sy = boxes[n]
        if sys.argv[1] == 'place':
            h = OBSTACLE_H.get(n, 0.6)
            req = SpawnEntity.Request(name=f'obstacle_{n}', xml=sdf(f'obstacle_{n}', sx, sy, h))
            req.initial_pose.position.x, req.initial_pose.position.y, req.initial_pose.position.z = x, y, h / 2
            r = call(node, spawn, req)
            ok = r.success or 'already exists' in r.status_message     # 이미 놓여 있으면 그대로 둔다
            print(f'place {n}: {ok} {r.status_message}')
        else:
            r = call(node, delete, DeleteEntity.Request(name=f'obstacle_{n}'))
            print(f'clear {n}: {r.success}')
    if sys.argv[1] == 'clear':
        for cm in ('global_costmap', 'local_costmap'):
            cli = node.create_client(ClearEntireCostmap, f'/{cm}/clear_entirely_{cm}')
            if cli.wait_for_service(timeout_sec=2):
                rclpy.spin_until_future_complete(node, cli.call_async(ClearEntireCostmap.Request()), timeout_sec=10)
    rclpy.shutdown()


if __name__ == '__main__':
    main()
