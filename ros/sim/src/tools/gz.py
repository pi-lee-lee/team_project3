"""Gazebo 모델을 지우고 만드는 공통 코드 (target.py, fire.py 가 쓴다).

겪은 문제 두 가지를 여기서 막는다.
1. 서비스 응답이 사라짐: 도구가 뜨자마자 부르면 Gazebo 가 응답을 돌려줄 상대를 아직 찾지 못해 응답을 버린다
   (gzserver 로그 "failed to send response to /delete_entity"). 요청은 처리됐는데 도구는 끝없이 기다리게 된다.
   → 처음 부르기 전에 잠깐 기다리고, 응답이 없으면 다시 부른다(지우기·만들기 모두 다시 불러도 결과가 같다).
2. 같은 이름으로 지우고 바로 만들면 카메라 화면에서 새 모델까지 사라지는 일이 있었다(화면 쪽 삭제가 늦게 처리됨).
   → 만들 때마다 이름 뒤에 번호를 붙이고(target_lamp__123), 지울 때는 같은 계열 이름을 모두 찾아 지운다.
"""
import time

import rclpy
from gazebo_msgs.srv import DeleteEntity, GetModelList, SpawnEntity

SETTLE_SEC = 1.0
TRY_TIMEOUT_SEC = 20.0      # 로봇이 달리는 중에는 에뮬레이션 Gazebo 응답이 15초를 넘기기도 했다
TRIES = 4


class Gazebo:
    def __init__(self, node_name):
        rclpy.init()
        self.node = rclpy.create_node(node_name)
        self._spawn = self.node.create_client(SpawnEntity, '/spawn_entity')
        self._delete = self.node.create_client(DeleteEntity, '/delete_entity')
        self._list = self.node.create_client(GetModelList, '/get_model_list')
        for cli in (self._spawn, self._delete, self._list):
            if not cli.wait_for_service(timeout_sec=15):
                raise SystemExit(f'Gazebo 서비스가 없습니다: {cli.srv_name}')
        end = time.monotonic() + SETTLE_SEC
        while time.monotonic() < end:
            rclpy.spin_once(self.node, timeout_sec=0.1)

    def _call(self, cli, req):
        for _ in range(TRIES):
            fut = cli.call_async(req)
            rclpy.spin_until_future_complete(self.node, fut, timeout_sec=TRY_TIMEOUT_SEC)
            if fut.done() and fut.result() is not None:
                return fut.result()
            fut.cancel()
        raise SystemExit(f'Gazebo 서비스 응답 없음: {cli.srv_name}')

    def models(self, base=None):
        """모델 이름 목록. base 를 주면 그 계열(base, base__번호)만."""
        names = list(self._call(self._list, GetModelList.Request()).model_names)
        return names if base is None else [n for n in names if n == base or n.startswith(base + '__')]

    def remove(self, base):
        """그 계열 모델을 모두 지운다. 지운 개수를 돌려준다."""
        names = self.models(base)
        for n in names:
            self._call(self._delete, DeleteEntity.Request(name=n))
        left = self.models(base)
        if left:
            raise SystemExit(f'지우지 못했습니다: {left}')
        return len(names)

    def replace(self, base, make_model):
        """그 계열을 지우고 새로 만든다. make_model(이름) → <pose> 가 든 <model> XML.
        자세를 따로 주지 않으므로 SDF 의 <pose> 가 그대로 쓰인다."""
        self.remove(base)
        name = f'{base}__{int(time.time()) % 1000000}'
        r = self._call(self._spawn, SpawnEntity.Request(name=name, xml=f'<sdf version="1.6">{make_model(name)}</sdf>'))
        if not r.success and name not in self.models(base):     # 응답을 놓쳐 다시 불렀으면 "이미 있음"으로 온다
            raise SystemExit(f'{name} 을(를) 만들지 못했습니다: {r.status_message}')
        return name

    def close(self):
        rclpy.shutdown()
