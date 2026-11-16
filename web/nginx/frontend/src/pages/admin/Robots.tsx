import { useState } from 'react';
import type { RobotSummary } from '../../api/types';
import { ErrorBox, useAction, useApi, usePoll } from '../../util';
import { Capabilities } from '../user/Monitor';

const SIM_CONFIG = {
  rosbridgeUrl: 'ws://sim:9090',
  videoUrl: 'http://sim:8080',
  imageTransport: 'compressed', // 카메라 영상은 압축 토픽(<image>/compressed)으로 받는다. 'raw' 로 두면 원본
  topics: {
    odom: '/odom', scan: '/scan', camera: '/camera/camera_info', image: '/camera/image_raw',
    battery: '/battery_state', teleop: '/cmd_vel_teleop', goal: '/inspection/goal',
    goalCancel: '/inspection/goal_cancel', goalStatus: '/inspection/goal_status', bridge: '/inspection/bridge_status',
  },
};

/** A2 로봇 관리 (+ A2-1 로봇 연결 설정) */
export default function Robots() {
  const api = useApi();
  const robots = usePoll(() => api.adminRobots(), 2000);
  const act = useAction();
  const [editing, setEditing] = useState<Partial<RobotSummary> | null>(null);

  const run = (fn: () => Promise<unknown>) => act.run(async () => { await fn(); await robots.reload(); });

  return (
    <section>
      <div className="row between">
        <h2>로봇 관리</h2>
        <button className="primary" onClick={() => setEditing({ adapterType: 'ROSBRIDGE', enabled: true, config: SIM_CONFIG })}>
          + 로봇 등록
        </button>
      </div>
      <ErrorBox msg={act.error || robots.error} />
      {robots.data?.map((r) => (
        <div key={r.robotId} className="card robot">
          <div className="row between">
            <div>
              <b>{r.code}</b> · {r.name} <span className="muted">({r.adapterType}{r.enabled ? '' : ', 비활성'})</span>
              <div className={r.connected ? 'ok' : 'bad'}>
                ● {r.connected ? '연결됨' : '연결 안 됨'}
                {' · '}제어: {r.control ? `${r.control.login} (${r.control.kind === 'MISSION' ? '점검 작업' : '조종'})` : '없음'}
                {r.mission && ` · 작업 #${r.mission.missionId} 진행 중`}
              </div>
            </div>
            <div className="row">
              <button onClick={() => setEditing(r)}>연결 설정</button>
              <button className="warn" disabled={!r.control || r.control.kind !== 'USER'} onClick={() => run(() => api.revokeControl(r.robotId))}>
                제어권 회수
              </button>
              <button className="danger" disabled={!r.enabled} onClick={() => run(() => api.estop(r.robotId))}>비상 정지</button>
            </div>
          </div>
          {r.enabled && <RobotCaps id={r.robotId} />}
        </div>
      ))}
      {editing && (
        <RobotForm robot={editing} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); robots.reload(); }} />
      )}
    </section>
  );
}

function RobotCaps({ id }: { id: number }) {
  const api = useApi();
  const st = usePoll(() => api.robotStatus(id), 3000, [id]);
  return st.data?.capabilities ? <Capabilities caps={st.data.capabilities} /> : null;
}

/** A2-1: 시뮬레이션 → 실제 로봇 교체는 주소·토픽만 바꾼다. */
function RobotForm({ robot, onClose, onSaved }: { robot: Partial<RobotSummary>; onClose: () => void; onSaved: () => void }) {
  const api = useApi();
  const act = useAction();
  const [code, setCode] = useState(robot.code ?? '');
  const [name, setName] = useState(robot.name ?? '');
  const [adapterType, setAdapterType] = useState(robot.adapterType ?? 'ROSBRIDGE');
  const [enabled, setEnabled] = useState(robot.enabled ?? true);
  const [config, setConfig] = useState(JSON.stringify(robot.config ?? {}, null, 2));

  const save = () => act.run(async () => {
    let cfg: unknown;
    try { cfg = JSON.parse(config); } catch { throw new Error('연결 설정이 올바른 JSON 이 아닙니다'); }
    await api.saveRobot({ robotId: robot.robotId, code, name, adapterType, config: cfg, enabled });
    onSaved();
  });

  return (
    <div className="modal-bg" onClick={onClose}>
      <div className="modal wide" onClick={(e) => e.stopPropagation()}>
        <h3>{robot.robotId ? `로봇 연결 설정 · ${robot.code}` : '로봇 등록'}</h3>
        {!robot.robotId && <label>코드<input value={code} onChange={(e) => setCode(e.target.value)} placeholder="tb3-real" /></label>}
        <label>이름<input value={name} onChange={(e) => setName(e.target.value)} /></label>
        <label>어댑터
          <select value={adapterType} onChange={(e) => setAdapterType(e.target.value as RobotSummary['adapterType'])}>
            <option value="ROSBRIDGE">ROSBRIDGE (시뮬레이션·실제 TurtleBot3)</option>
            <option value="MOCK">MOCK (ROS 없이 시험)</option>
          </select>
        </label>
        <label>연결 설정 (rosbridge 주소, 영상 주소, 토픽 이름)
          <textarea rows={14} value={config} onChange={(e) => setConfig(e.target.value)} className="mono" />
        </label>
        <label className="row"><input type="checkbox" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} /> 사용</label>
        <p className="muted">실제 로봇: rosbridgeUrl 을 ws://로봇IP:9090, videoUrl 을 http://로봇IP:8080 으로 바꾸고 로봇에서 rosbridge·web_video_server·목표 브리지를 실행합니다. 카메라는 압축 토픽(compressed_image_transport)을 발행해야 합니다.</p>
        <ErrorBox msg={act.error} />
        <div className="row end">
          <button onClick={onClose}>취소</button>
          <button className="primary" disabled={act.busy} onClick={save}>저장·재연결</button>
        </div>
      </div>
    </div>
  );
}
