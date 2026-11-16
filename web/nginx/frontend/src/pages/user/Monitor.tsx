import { useEffect, useRef, useState } from 'react';
import { ErrorBox, useAction, useApi, useAuth, usePoll } from '../../util';

const CAP_LABEL: Record<string, [string, string]> = {
  VERIFIED: ['✓', 'ok'], SUPPORTED: ['토픽 있음', 'muted'], STALE: ['멈춤', 'warn-t'],
  UNSUPPORTED: ['✕ 미지원', 'bad'], UNKNOWN: ['?', 'muted'],
};

export function Capabilities({ caps }: { caps: Record<string, string> }) {
  return (
    <div className="chips">
      <b>제공 기능</b>
      {Object.entries(caps).map(([k, v]) => (
        <span key={k} className={`chip ${CAP_LABEL[v]?.[1] ?? ''}`}>{k} {CAP_LABEL[v]?.[0] ?? v}</span>
      ))}
    </div>
  );
}

const SPEED = { lin: 0.18, ang: 0.9 };
const KEYS: Record<string, [number, number]> = {
  w: [1, 0], s: [-1, 0], a: [0, 1], d: [0, -1], ArrowUp: [1, 0], ArrowDown: [-1, 0], ArrowLeft: [0, 1], ArrowRight: [0, -1],
};

/** U1 관제·조종 */
export default function Monitor() {
  const api = useApi();
  const { me } = useAuth();
  const robots = usePoll(() => api.robots(), 0);
  const [robotId, setRobotId] = useState<number | null>(null);
  useEffect(() => {
    if (robotId === null && robots.data?.length) {
      setRobotId((robots.data.find((r) => r.enabled && r.connected) ?? robots.data.find((r) => r.enabled))?.robotId ?? null);
    }
  }, [robots.data, robotId]);

  const st = usePoll(() => (robotId ? api.robotStatus(robotId) : Promise.resolve(null)), 1000, [robotId]);
  const act = useAction();
  const s = st.data;
  const iHold = !!s?.control && s.control.kind === 'USER' && s.control.userId === me?.userId;

  return (
    <section>
      <div className="row between">
        <h2>관제·조종</h2>
        <select value={robotId ?? ''} onChange={(e) => setRobotId(Number(e.target.value))}>
          {robots.data?.filter((r) => r.enabled).map((r) => <option key={r.robotId} value={r.robotId}>{r.code} · {r.name}</option>)}
        </select>
      </div>
      <ErrorBox msg={act.error || st.error} />
      {robotId && (
        <div className="monitor">
          <div className="video">
            {s?.connected ? <img src={api.streamUrl(robotId)} alt="실시간 영상" /> : <div className="novideo">영상 없음 (연결 끊김)</div>}
          </div>
          <div className="side">
            <div className="card">
              <div className={s?.connected ? 'ok' : 'bad'}>● {s?.connected ? '연결 정상' : '연결 끊김'}</div>
              <div>위치 {s?.pose ? `x ${s.pose.x.toFixed(2)}  y ${s.pose.y.toFixed(2)}  θ ${(s.pose.yaw * 180 / Math.PI).toFixed(0)}°` : '-'}</div>
              <div>전방 장애물 {s?.frontObstacleM != null ? `${s.frontObstacleM.toFixed(2)} m` : '-'}</div>
              <div>배터리 {s?.batteryPercent != null ? `${s.batteryPercent.toFixed(0)}%` : '정보 없음'}</div>
              <div className="ages">
                {s?.ageMs && Object.entries(s.ageMs).map(([k, v]) => (
                  <span key={k} className={v == null ? 'muted' : v > 2000 ? 'warn-t' : ''}>{k} {v == null ? '없음' : `${(v / 1000).toFixed(1)}s`}</span>
                ))}
              </div>
              {s?.capabilities && <Capabilities caps={s.capabilities} />}
            </div>
            <div className="card">
              <div>제어권: {s?.control ? `${s.control.login} (${s.control.kind === 'MISSION' ? '점검 작업 중' : '조종'})` : '없음'}</div>
              {iHold ? (
                <button onClick={() => act.run(async () => { await api.releaseControl(robotId); await st.reload(); })}>제어권 반납</button>
              ) : (
                <button className="primary" disabled={act.busy || !!s?.control || !s?.connected}
                  onClick={() => act.run(async () => { await api.acquireControl(robotId); await st.reload(); })}>제어권 획득</button>
              )}
              <Teleop robotId={robotId} enabled={iHold} />
            </div>
          </div>
          <button className="danger estop" onClick={() => act.run(async () => { await api.estop(robotId); await st.reload(); })}>
            비상 정지
          </button>
        </div>
      )}
      <p className="muted">조종은 제어권을 가진 1명만 할 수 있고, 점검 작업 중에는 제어권을 얻을 수 없습니다. 버튼을 누르고 있는 동안만 움직입니다. 연결이 끊기면 로봇이 0.5초 안에 멈춥니다.</p>
    </section>
  );
}

/** 누르고 있는 동안 100ms 마다 최신 속도 명령을 보낸다. 떼면 0 을 보낸다. */
function Teleop({ robotId, enabled }: { robotId: number; enabled: boolean }) {
  const api = useApi();
  const ws = useRef<WebSocket | null>(null);
  const cmd = useRef<[number, number]>([0, 0]);
  const [msg, setMsg] = useState('');
  const [active, setActive] = useState<string | null>(null);

  useEffect(() => {
    if (!enabled) return;
    const sock = new WebSocket(api.teleopUrl(robotId));
    ws.current = sock;
    sock.onmessage = (e) => {
      const m = JSON.parse(e.data);
      if (m.type === 'error') setMsg(m.message);
    };
    sock.onclose = () => setMsg('조종 연결이 닫혔습니다');
    sock.onopen = () => setMsg('');
    const timer = setInterval(() => {
      const [l, a] = cmd.current;
      if (sock.readyState === WebSocket.OPEN && (l !== 0 || a !== 0)) {
        sock.send(JSON.stringify({ linear: l * SPEED.lin, angular: a * SPEED.ang }));
      }
    }, 100);
    const down = (e: KeyboardEvent) => {
      const k = KEYS[e.key];
      if (k && !(e.target instanceof HTMLInputElement)) { e.preventDefault(); press(e.key, k); }
    };
    const up = (e: KeyboardEvent) => { if (KEYS[e.key]) release(); };
    window.addEventListener('keydown', down);
    window.addEventListener('keyup', up);
    return () => {
      clearInterval(timer);
      window.removeEventListener('keydown', down);
      window.removeEventListener('keyup', up);
      sock.close();
      ws.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, robotId]);

  const press = (name: string, v: [number, number]) => { cmd.current = v; setActive(name); };
  const release = () => {
    cmd.current = [0, 0];
    setActive(null);
    if (ws.current?.readyState === WebSocket.OPEN) ws.current.send(JSON.stringify({ linear: 0, angular: 0 }));
  };
  const btn = (name: string, label: string, v: [number, number]) => (
    <button disabled={!enabled} className={active === name ? 'pressed' : ''}
      onPointerDown={() => press(name, v)} onPointerUp={release} onPointerLeave={() => active === name && release()}>{label}</button>
  );
  return (
    <div className="teleop">
      <div className="pad">
        <span />{btn('w', '↑', [1, 0])}<span />
        {btn('a', '←', [0, 1])}<button disabled={!enabled} onClick={release}>■</button>{btn('d', '→', [0, -1])}
        <span />{btn('s', '↓', [-1, 0])}<span />
      </div>
      <div className="muted small">W A S D / 방향키</div>
      {msg && <div className="bad small">{msg}</div>}
    </div>
  );
}
