"""투척 기구 브리지(실로봇용): 서버의 투척 계약 ↔ 기구의 시리얼. (docs/design/design_02_INTERFACES.md 2.2 절)

서버와의 약속(모두 std_msgs/String, JSON) — 시뮬레이션의 mock_launcher.py 와 같다:
  /inspection/actuator         ← {"commandId": "...", "kind": "LAUNCH", "count": 1, "params": {}}
  /inspection/actuator_status  → {"commandId", "state": ACCEPTED|DONE|FAILED, "code", "reason", "launched"}
  /inspection/actuator_state   → {"ready": bool, "remaining": N|null, "fault": ""}  (1초마다)

기구와의 약속(시리얼, 한 줄에 하나, 줄 끝 \\n):
  브리지 → 기구   L <id> <count>            발사
  기구 → 브리지   OK <id> <launched>         결과(성공)
                  ERR <id> <code>            결과(실패. code: NOT_READY·EMPTY·JAMMED·ESTOP 등)
  브리지 → 기구   S                          상태 묻기(1초마다)
  기구 → 브리지   ST <ready 0|1> <remaining|-1>   상태(-1 = 남은 수를 모름)
<id> 는 브리지가 붙이는 짧은 번호다(commandId 는 길고 기구가 다루기 어려워 그대로 보내지 않는다).
기구 쪽 형식이 다르게 정해지면 이 파일만 바꾼다(토픽 계약과 서버는 그대로).

설정(ROS 파라미터, 없으면 환경변수): port(LAUNCHER_PORT, 기본 /dev/ttyUSB1), baud(LAUNCHER_BAUD, 기본 115200),
  timeout_sec(LAUNCHER_TIMEOUT, 기본 10 — 이 시간 안에 결과가 없으면 TIMEOUT 으로 실패)
실행: python3 launcher_bridge.py --ros-args -p port:=/dev/ttyACM0 -p baud:=115200   (pyserial 필요: pip install pyserial)
시뮬레이션에서는 실행하지 않는다(기구가 없다). 실물 기구로 시험한 적은 아직 없다.
"""
import json
import os
import sys
import threading
import time
from collections import OrderedDict

import rclpy
from rclpy.node import Node
from std_msgs.msg import String

KEEP_RESULTS = 200
STATE_STALE_SEC = 3.0       # 이 시간 동안 기구의 상태 응답이 없으면 준비되지 않음으로 알린다


class LauncherBridge(Node):
    def __init__(self, serial_module):
        super().__init__('launcher_bridge')
        port = self.declare_parameter('port', os.environ.get('LAUNCHER_PORT', '/dev/ttyUSB1')).value
        baud = int(self.declare_parameter('baud', int(os.environ.get('LAUNCHER_BAUD', '115200'))).value)
        self.timeout_sec = float(self.declare_parameter('timeout_sec', float(os.environ.get('LAUNCHER_TIMEOUT', '10'))).value)
        self.serial_module = serial_module
        try:
            self.ser = serial_module.Serial(port, baud, timeout=0.2)
        except serial_module.SerialException as e:
            raise SystemExit(f'투척 기구 시리얼 포트를 열지 못했습니다 ({port}, {baud}bps): {e}')
        self.lock = threading.Lock()        # 쓰기(타이머·명령)가 겹치지 않게
        self.results = OrderedDict()        # commandId → 마지막으로 보낸 상태(dict)
        self.pending = None                 # 실행 중인 명령 {'commandId', 'id', 'deadline'}
        self.seq = 0
        self.ready, self.remaining, self.fault = False, None, 'NO_RESPONSE'
        self.state_at = 0.0
        self.inbox = []                     # 읽기 스레드 → ROS 스레드로 넘기는 줄
        self.inbox_lock = threading.Lock()
        self.status_pub = self.create_publisher(String, '/inspection/actuator_status', 10)
        self.state_pub = self.create_publisher(String, '/inspection/actuator_state', 10)
        self.create_subscription(String, '/inspection/actuator', self.on_command, 10)
        self.create_timer(1.0, self.tick)
        self.create_timer(0.05, self.drain)
        threading.Thread(target=self.read_loop, daemon=True).start()
        self.get_logger().info(f'launcher bridge ready ({port}, {baud}bps)')

    # ------------------------------------------------------------ 시리얼
    def write_line(self, line):
        try:
            with self.lock:
                self.ser.write((line + '\n').encode('ascii'))
            return True
        except (self.serial_module.SerialException, OSError) as e:
            self.get_logger().warn(f'serial write failed: {e}')
            self.fault = 'SERIAL_ERROR'
            return False

    def read_loop(self):
        """별도 스레드: 줄을 읽어 모아 둔다(처리는 ROS 스레드의 drain 에서)."""
        while rclpy.ok():
            try:
                raw = self.ser.readline()
            except (self.serial_module.SerialException, OSError) as e:
                self.get_logger().warn(f'serial read failed: {e}')
                self.fault = 'SERIAL_ERROR'
                time.sleep(1.0)
                continue
            line = raw.decode('ascii', errors='ignore').strip()
            if line:
                with self.inbox_lock:
                    self.inbox.append(line)

    def drain(self):
        with self.inbox_lock:
            lines, self.inbox = self.inbox, []
        for line in lines:
            self.on_line(line)

    def on_line(self, line):
        p = line.split()
        try:
            if p[0] == 'ST' and len(p) >= 3:
                self.ready = p[1] == '1'
                n = int(p[2])
                self.remaining = None if n < 0 else n
                self.fault = ''
                self.state_at = time.monotonic()
            elif p[0] in ('OK', 'ERR') and len(p) >= 3:
                g = self.pending
                if not g or p[1] != g['id']:
                    self.get_logger().warn(f'기다리지 않은 결과: {line}')
                    return
                self.pending = None
                if p[0] == 'OK':
                    self.send(g['commandId'], 'DONE', launched=int(p[2]))
                else:
                    self.send(g['commandId'], 'FAILED', p[2], f'기구가 실패를 알림({p[2]})')
            else:
                self.get_logger().warn(f'알 수 없는 줄: {line}')
        except (ValueError, IndexError):
            self.get_logger().warn(f'해석할 수 없는 줄: {line}')

    # ------------------------------------------------------------ 토픽
    def tick(self):
        self.write_line('S')
        g = self.pending
        if g and time.monotonic() > g['deadline']:
            self.pending = None
            self.send(g['commandId'], 'FAILED', 'TIMEOUT', f'{self.timeout_sec:.0f}초 안에 기구의 결과가 없음')
        fresh = time.monotonic() - self.state_at < STATE_STALE_SEC
        fault = self.fault if fresh or self.fault else 'NO_RESPONSE'
        body = {'ready': fresh and self.ready and self.pending is None, 'remaining': self.remaining if fresh else None,
                'fault': fault}
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
            self.status_pub.publish(String(data=json.dumps(self.results[command_id], ensure_ascii=False)))
            return
        if kind != 'LAUNCH' or count < 1:
            return self.send(command_id, 'FAILED', 'UNSUPPORTED', f'지원하지 않는 명령: {kind} x{count}')
        if self.pending is not None:
            return self.send(command_id, 'FAILED', 'NOT_READY', f'다른 명령 실행 중({self.pending["commandId"]})')
        if time.monotonic() - self.state_at >= STATE_STALE_SEC or not self.ready:
            return self.send(command_id, 'FAILED', 'NOT_READY', '기구가 준비되지 않음(상태 응답 없음 또는 ready=0)')
        self.seq = self.seq % 9999 + 1
        g = {'commandId': command_id, 'id': str(self.seq), 'deadline': time.monotonic() + self.timeout_sec}
        if not self.write_line(f'L {g["id"]} {count}'):
            return self.send(command_id, 'FAILED', 'NOT_READY', '기구로 명령을 보내지 못함(시리얼 오류)')
        self.pending = g
        self.send(command_id, 'ACCEPTED')


def main():
    try:
        import serial      # pyserial. 시뮬레이션 이미지에는 없으므로 실행할 때만 불러온다
    except ImportError:
        sys.exit('launcher_bridge: pyserial 이 없습니다. 로봇에서 "pip install pyserial"(또는 apt install python3-serial) 후 다시 실행하세요.')
    rclpy.init()
    rclpy.spin(LauncherBridge(serial))


if __name__ == '__main__':
    main()
