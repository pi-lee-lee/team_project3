"""Gazebo(Harmonic, gz sim) 모델을 지우고 만들고 옮기는 공통 코드 (target.py, fire.py, obstacle.py 가 쓴다). 파일 이름이 gz.py 이면 Gazebo 파이썬 패키지 gz 와 겹쳐 gazebo.py 로 둔다.

월드 서비스는 Gazebo 자체 통신(gz-transport, 파이썬 gz.transport13)으로 바로 부른다:
    /world/factory/create   (gz.msgs.EntityFactory → Boolean)
    /world/factory/remove   (gz.msgs.Entity → Boolean)
    /world/factory/set_pose (gz.msgs.Pose → Boolean)
    /world/factory/scene/info (Empty → Scene: 모델 목록)
만들기 · 지우기 · 옮기기는 '/blocking' 판을 쓴다(그냥 판은 다음 물리 걸음에 처리돼, 바로 목록을 읽으면 아직 남아 있다).
처음에는 ROS 서비스(ros_gz_bridge)와 `gz model --list` 명령을 썼는데, 서비스를 찾는 데 6초 · 목록 명령에 3초가 걸려
장애물 하나 놓는 데 12초가 걸렸다(그 사이 로봇이 2~3m 를 지나가 '달리는 도중에 앞에 놓기' 시험이 맞지 않았다).
ROS 노드(self.node)는 ROS 쪽 일(비용 지도 비우기 · 감지 보고)을 하는 도구가 처음 쓸 때 만든다(rclpy 준비에 2초 남짓).

겪은 문제(Gazebo Classic 때부터)를 여기서 막는다.
1. 서비스 응답이 사라짐: 응답이 없으면 다시 부른다(지우기 · 만들기 · 옮기기 모두 다시 불러도 결과가 같다).
2. 같은 이름으로 지우고 바로 만들면 카메라 화면에서 새 모델까지 사라지는 일이 있었다(화면 쪽 삭제가 늦게 처리됨).
   → 만들 때마다 이름 뒤에 번호를 붙이고(target_lamp__123), 지울 때는 같은 계열 이름을 모두 찾아 지운다.
"""
import math
import time

import gz.msgs10.boolean_pb2 as gz_bool
import gz.msgs10.empty_pb2 as gz_empty
import gz.msgs10.entity_factory_pb2 as gz_factory
import gz.msgs10.entity_pb2 as gz_entity
import gz.msgs10.pose_pb2 as gz_pose
import gz.msgs10.scene_pb2 as gz_scene
import gz.transport13 as gz_transport

WORLD = 'factory'
TRY_TIMEOUT_MS = 20000      # 로봇이 달리는 중에는 Gazebo 응답이 몇 초씩 늦기도 했다
TRIES = 4


class Gazebo:
    def __init__(self, node_name):
        self.node_name = node_name
        self._node = None
        self.gz = gz_transport.Node()

    @property
    def node(self):
        if self._node is None:
            import rclpy
            rclpy.init()
            self._node = rclpy.create_node(self.node_name)
        return self._node

    def _call(self, service, req, req_type, res_type=gz_bool.Boolean):
        for _ in range(TRIES):
            ok, res = self.gz.request(f'/world/{WORLD}/{service}', req, req_type, res_type, TRY_TIMEOUT_MS)
            if ok:
                return res
        raise SystemExit(f'Gazebo 서비스 응답 없음: /world/{WORLD}/{service}')

    def models(self, base=None):
        """모델 이름 목록. base 를 주면 그 계열(base, base__번호)만."""
        scene = self._call('scene/info', gz_empty.Empty(), gz_empty.Empty, gz_scene.Scene)
        names = [m.name for m in scene.model]
        return names if base is None else [n for n in names if n == base or n.startswith(base + '__')]

    def delete(self, name):
        """모델 하나를 지운다(없으면 False)."""
        req = gz_entity.Entity(name=name, type=gz_entity.Entity.MODEL)
        return bool(self._call('remove/blocking', req, gz_entity.Entity).data)

    def spawn(self, name, model_xml, x=None, y=None, z=None):
        """<model> XML 을 만든다. x · y · z 를 주면 그 자리에(아니면 SDF 의 <pose> 그대로)."""
        req = gz_factory.EntityFactory(name=name, allow_renaming=False, sdf=f'<sdf version="1.8">{model_xml}</sdf>')
        if x is not None:
            req.pose.position.x, req.pose.position.y, req.pose.position.z = float(x), float(y), float(z or 0.0)
        return bool(self._call('create/blocking', req, gz_factory.EntityFactory).data)

    def set_pose(self, name, x, y, z=0.0, yaw=0.0):
        """모델을 그 자리로 바로 옮긴다."""
        req = gz_pose.Pose(name=name)
        req.position.x, req.position.y, req.position.z = float(x), float(y), float(z)
        req.orientation.z, req.orientation.w = math.sin(yaw / 2), math.cos(yaw / 2)
        return bool(self._call('set_pose/blocking', req, gz_pose.Pose).data)

    def remove(self, base):
        """그 계열 모델을 모두 지운다. 지운 개수를 돌려준다."""
        names = self.models(base)
        for n in names:
            self.delete(n)
        end = time.monotonic() + 5.0          # 목록(scene/info)에 반영되기까지 조금 걸릴 수 있다
        while (left := self.models(base)) and time.monotonic() < end:
            time.sleep(0.2)
        if left:
            raise SystemExit(f'지우지 못했습니다: {left}')
        return len(names)

    def replace(self, base, make_model):
        """그 계열을 지우고 새로 만든다. make_model(이름) → <pose> 가 든 <model> XML.
        자세를 따로 주지 않으므로 SDF 의 <pose> 가 그대로 쓰인다."""
        self.remove(base)
        name = f'{base}__{int(time.time()) % 1000000}'
        if not self.spawn(name, make_model(name)) and name not in self.models(base):
            raise SystemExit(f'{name} 을(를) 만들지 못했습니다')
        return name

    def close(self):
        if self._node is not None:
            import rclpy
            rclpy.shutdown()
