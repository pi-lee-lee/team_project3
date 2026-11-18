#!/usr/bin/env python3
"""시뮬레이션 명령 노드: 웹(관리자 "시연" 화면)에서 시뮬레이션 도구를 실행할 수 있게 한다.

웹 서버는 sim 컨테이너의 셸을 쓸 수 없으므로, 이 노드가 토픽으로 명령을 받아 대신 실행한다.
시뮬레이션에만 있는 노드다(실제 로봇에는 띄우지 않는다).

    /sim/command         ← {"id": "abc", "tool": "fire" | "target", "args": ["place", "office_south", "emergency", "--detect"]}
    /sim/command_status  → {"id": "abc", "ok": true, "code": 0, "output": "…(끝 2000자)"}

허용하는 도구는 fire · target 뿐이다(TOOLS). 인자는 글자·숫자·점·밑줄·줄표·등호만 받는다.
같은 id 가 다시 오면 실행하지 않고 지난 결과를 다시 보낸다. 명령은 한 번에 하나씩 차례로 실행한다.
"""
import json
import queue
import re
import subprocess
import threading

import rclpy
from rclpy.node import Node
from std_msgs.msg import String

TOOLS = {'fire': '/sim/tools/fire.sh', 'target': '/sim/tools/target.sh'}
ARG_OK = re.compile(r'^[A-Za-z0-9._=\-]{1,60}$')
TIMEOUT_SEC = 150


class SimControl(Node):
    def __init__(self):
        super().__init__('sim_control')
        self.pub = self.create_publisher(String, '/sim/command_status', 10)
        self.create_subscription(String, '/sim/command', self.on_command, 10)
        self.done = {}                 # id → 결과(재전송용)
        self.seen = set()
        self.jobs = queue.Queue()
        threading.Thread(target=self.work, daemon=True).start()
        self.get_logger().info('sim_control 준비: /sim/command')

    def on_command(self, msg):
        try:
            c = json.loads(msg.data)
            cid = str(c['id'])
        except Exception:                                   # noqa: BLE001 - 모양이 틀린 명령은 버린다
            return
        if cid in self.done:
            self.pub.publish(String(data=json.dumps(self.done[cid], ensure_ascii=False)))
            return
        if cid in self.seen:
            return                                          # 실행 중(같은 명령의 재전송)
        self.seen.add(cid)
        self.jobs.put((cid, c.get('tool'), [str(a) for a in c.get('args', [])]))

    def work(self):
        while True:
            cid, tool, args = self.jobs.get()
            res = {'id': cid, 'ok': False, 'code': -1, 'output': ''}
            if tool not in TOOLS:
                res['output'] = f'허용하지 않는 도구: {tool}'
            elif not all(ARG_OK.match(a) for a in args):
                res['output'] = '허용하지 않는 인자'
            else:
                try:
                    r = subprocess.run([TOOLS[tool], *args], capture_output=True, text=True, timeout=TIMEOUT_SEC)
                    res.update(ok=r.returncode == 0, code=r.returncode, output=(r.stdout + r.stderr)[-2000:])
                except subprocess.TimeoutExpired:
                    res['output'] = f'{TIMEOUT_SEC}초 안에 끝나지 않음'
                except Exception as e:                      # noqa: BLE001
                    res['output'] = str(e)
            self.done[cid] = res
            if len(self.done) > 200:
                self.done.pop(next(iter(self.done)))
            self.get_logger().info(f'{tool} {" ".join(args)} → {"ok" if res["ok"] else "실패"}')
            self.pub.publish(String(data=json.dumps(res, ensure_ascii=False)))


def main():
    rclpy.init()
    rclpy.spin(SimControl())


if __name__ == '__main__':
    main()
