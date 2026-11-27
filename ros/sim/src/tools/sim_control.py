#!/usr/bin/env python3
"""시뮬레이션 명령 노드: 웹(관리자 "시연" 화면)에서 시뮬레이션 도구를 실행할 수 있게 한다.

웹 서버는 sim 컨테이너의 셸을 쓸 수 없으므로, 이 노드가 토픽으로 명령을 받아 대신 실행한다.
시뮬레이션에만 있는 노드다(실제 로봇에는 띄우지 않는다).

    /sim/command         ← {"id": "abc", "tool": "fire" | "target", "args": ["set", "c2_east", "emergency"]}
    /sim/command_status  → {"id": "abc", "ok": true, "code": 0, "output": "…(끝 2000자)"}

허용하는 도구는 fire · target · obstacle 뿐이다(TOOLS). 인자는 글자·숫자·점·밑줄·줄표·등호만 받는다.
같은 id 가 다시 오면 실행하지 않고 지난 결과를 다시 보낸다. 명령은 한 번에 하나씩 차례로 실행한다.

투척 흉내: 모의 투척 기구(mock_launcher)가 투척을 마쳤다고 알리면(/inspection/actuator_status, state DONE)
EXTINGUISH_SEC(기본 4초, 환경변수 SIM_EXTINGUISH_SEC) 뒤 fire.sh extinguish 로 화재 사진을 꺼짐(정상)으로 바꾼다
— 소화액을 맞고 불이 꺼진 것처럼. 0 이면 바꾸지 않는다(투척 뒤에도 불이 남는 경우 시험).
"""
import json
import os
import queue
import re
import subprocess
import threading
import time

import rclpy
from rclpy.node import Node
from std_msgs.msg import String

TOOLS = {'fire': '/sim/tools/fire.sh', 'target': '/sim/tools/target.sh', 'obstacle': '/sim/tools/obstacle.sh'}
ARG_OK = re.compile(r'^[A-Za-z0-9._=\-]{1,60}$')
TIMEOUT_SEC = 150
EXTINGUISH_SEC = float(os.environ.get('SIM_EXTINGUISH_SEC', '') or 4)


class SimControl(Node):
    def __init__(self):
        super().__init__('sim_control')
        self.pub = self.create_publisher(String, '/sim/command_status', 10)
        self.create_subscription(String, '/sim/command', self.on_command, 10)
        self.create_subscription(String, '/inspection/actuator_status', self.on_actuator, 10)
        self.launched = set()          # 이미 꺼 준 투척 명령(재전송된 DONE 은 다시 끄지 않는다)
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

    def on_actuator(self, msg):
        try:
            d = json.loads(msg.data)
        except ValueError:
            return
        cid = str(d.get('commandId', ''))
        if d.get('state') != 'DONE' or EXTINGUISH_SEC <= 0 or not cid or cid in self.launched:
            return
        self.launched.add(cid)

        def later():
            time.sleep(EXTINGUISH_SEC)
            self.jobs.put((f'extinguish-{cid}', 'fire', ['extinguish']))
        threading.Thread(target=later, daemon=True).start()
        self.get_logger().info(f'투척 {cid} 끝 → {EXTINGUISH_SEC:.0f}초 뒤 화재 사진을 꺼짐으로')

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
