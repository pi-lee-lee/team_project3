"""모의 투척 기구: 기구가 없는 로봇(시뮬레이션)에서 투척 계약에 답한다. (docs/plan/INTERFACES.md 2.2 절)

서버와의 약속(모두 std_msgs/String, JSON):
  /inspection/actuator         ← {"commandId": "...", "kind": "LAUNCH", "count": 1, "params": {}}
  /inspection/actuator_status  → {"commandId", "state": ACCEPTED|DONE|FAILED, "code", "reason", "launched"}
  /inspection/actuator_state   → {"ready": bool, "remaining": N, "fault": ""}  (1초마다)

동작: 명령을 받으면 ACCEPTED, LAUNCH_SEC(1.5초) 뒤 DONE(launched = 쏜 개수). 같은 commandId 가 다시 오면
실행하지 않고 지난 결과를 다시 보낸다(실행 중이면 ACCEPTED 를 다시 보낸다).
실패 code: EMPTY(남은 탄 없음) · NOT_READY(다른 명령 실행 중) · UNSUPPORTED(LAUNCH 가 아닌 명령) · 강제 실패로 준 값.

환경변수: LAUNCHER_REMAINING(기본 5. 쏠 때마다 줄어든다), LAUNCHER_FAIL(값이 있으면 그 code 로 항상 FAILED)
시험용 토픽 /inspection/actuator_mock ← {"remaining": 5} 또는 {"fail": "JAMMED"} / {"fail": ""} 로 실행 중에 바꾼다.
"""
import json
import os
from collections import OrderedDict

import rclpy
from rclpy.node import Node
from std_msgs.msg import String

LAUNCH_SEC = 1.5
KEEP_RESULTS = 200          # 지난 결과를 기억하는 명령 수


class MockLauncher(Node):
    def __init__(self):
        super().__init__('mock_launcher')
        self.remaining = int(os.environ.get('LAUNCHER_REMAINING', '') or 5)
        self.fail = os.environ.get('LAUNCHER_FAIL', '').strip()
        self.results = OrderedDict()        # commandId → 마지막으로 보낸 상태(dict)
        self.busy = None                    # 실행 중인 commandId
        self.timer = None
        self.status_pub = self.create_publisher(String, '/inspection/actuator_status', 10)
        self.state_pub = self.create_publisher(String, '/inspection/actuator_state', 10)
        self.create_subscription(String, '/inspection/actuator', self.on_command, 10)
        self.create_subscription(String, '/inspection/actuator_mock', self.on_mock, 10)
        self.create_timer(1.0, self.publish_state)
        self.get_logger().info(f'mock launcher ready (remaining={self.remaining}, fail={self.fail or "-"})')

    def publish_state(self):
        body = {'ready': self.busy is None and not self.fail, 'remaining': self.remaining, 'fault': self.fail}
        self.state_pub.publish(String(data=json.dumps(body)))

    def send(self, command_id, state, code='', reason='', launched=0):
        body = {'commandId': command_id, 'state': state, 'code': code, 'reason': reason, 'launched': launched}
        self.results[command_id] = body
        self.results.move_to_end(command_id)
        while len(self.results) > KEEP_RESULTS:
            self.results.popitem(last=False)
        self.status_pub.publish(String(data=json.dumps(body, ensure_ascii=False)))

    def on_command(self, msg):
        try:
            d = json.loads(msg.data)
            command_id = str(d['commandId'])
            kind = str(d.get('kind', 'LAUNCH'))
            count = int(d.get('count', 1))
        except (ValueError, KeyError, TypeError) as e:
            self.get_logger().warn(f'invalid actuator command: {e}')
            return
        if command_id in self.results:      # 재전송: 실행하지 않고 지난 결과(실행 중이면 ACCEPTED)를 다시 보낸다
            self.get_logger().info(f'{command_id}: 다시 받음 → 지난 결과 재전송')
            self.status_pub.publish(String(data=json.dumps(self.results[command_id], ensure_ascii=False)))
            return
        if kind != 'LAUNCH' or count < 1:
            return self.send(command_id, 'FAILED', 'UNSUPPORTED', f'지원하지 않는 명령: {kind} x{count}')
        if self.fail:
            return self.send(command_id, 'FAILED', self.fail, f'모의 기구 강제 실패({self.fail})')
        if self.busy is not None:
            return self.send(command_id, 'FAILED', 'NOT_READY', f'다른 명령 실행 중({self.busy})')
        if self.remaining <= 0:
            return self.send(command_id, 'FAILED', 'EMPTY', '남은 탄 없음')
        self.busy = command_id
        self.send(command_id, 'ACCEPTED')
        self.publish_state()
        self.timer = self.create_timer(LAUNCH_SEC, lambda: self.finish(command_id, count))

    def finish(self, command_id, count):
        self.timer.cancel()
        self.destroy_timer(self.timer)
        self.timer = None
        self.busy = None
        if self.fail:                       # 실행 중에 강제 실패로 바뀜
            self.send(command_id, 'FAILED', self.fail, f'모의 기구 강제 실패({self.fail})')
        else:
            launched = min(count, self.remaining)
            self.remaining -= launched
            self.send(command_id, 'DONE', launched=launched)
            self.get_logger().info(f'{command_id}: {launched}개 투척 (남은 탄 {self.remaining})')
        self.publish_state()

    def on_mock(self, msg):
        try:
            d = json.loads(msg.data)
            if 'remaining' in d:
                self.remaining = max(0, int(d['remaining']))
            if 'fail' in d:
                self.fail = str(d['fail'] or '').strip()
        except (ValueError, TypeError, AttributeError) as e:
            self.get_logger().warn(f'invalid mock setting: {e}')
            return
        self.get_logger().info(f'mock 설정 변경: remaining={self.remaining}, fail={self.fail or "-"}')
        self.publish_state()


def main():
    rclpy.init()
    rclpy.spin(MockLauncher())


if __name__ == '__main__':
    main()
