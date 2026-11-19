import { useEffect, useRef, useState } from 'react';
import type { MapInfo, MapView, Point, RobotStatus } from '../../api/types';
import { ErrorBox, useAction, useApi, useAuth, usePoll } from '../../util';
import { Icon } from '../../Icon';
import { Page, Picker, Segmented } from '../../ui';
import { mapGeo } from '../../mapGeo';
import './user.css';

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
// 방향키(카메라 모드): 위·아래 = 전진·후진, 왼쪽·오른쪽 = 제자리 회전. W·A·S·D 도 같다.
const KEYS: Record<string, [number, number]> = {
  ArrowUp: [1, 0], ArrowDown: [-1, 0], ArrowLeft: [0, 1], ArrowRight: [0, -1],
  w: [1, 0], s: [-1, 0], a: [0, 1], d: [0, -1],
};
const isTyping = (t: EventTarget | null) =>
  t instanceof HTMLInputElement || t instanceof HTMLSelectElement || t instanceof HTMLTextAreaElement;

type Mode = 'camera' | 'map';
const MODES: [Mode, string][] = [['camera', '카메라'], ['map', '지도']];

/** U1 관제·조종: 카메라 모드(영상 + 방향키 조종) / 지도 모드(지도 위 위치·경로·라이다 + 클릭 이동) */
export default function Monitor() {
  const api = useApi();
  const { me } = useAuth();
  const robots = usePoll(() => api.robots(), 0);
  const [robotId, setRobotId] = useState<number | null>(null);
  const [mode, setMode] = useState<Mode>('camera');
  useEffect(() => {
    if (robotId === null && robots.data?.length) {
      setRobotId((robots.data.find((r) => r.enabled && r.connected) ?? robots.data.find((r) => r.enabled))?.robotId ?? null);
    }
  }, [robots.data, robotId]);

  const st = usePoll(() => (robotId ? api.robotStatus(robotId) : Promise.resolve(null)), 1000, [robotId]);
  const act = useAction();
  const s = st.data;
  const iHold = !!s?.control && s.control.kind === 'USER' && s.control.userId === me?.userId;
  const canAcquire = !!s?.connected && (!s?.control || iHold);
  const acquire = () => act.run(async () => { await api.acquireControl(robotId!); await st.reload(); });

  return (
    <Page title="관제" width="wide">
      <div className="row wrap monitor-bar">
        <Segmented value={mode} options={MODES} onChange={setMode} />
        {/* 로봇 고르기: 이름표 + 선택 상자. 높이·모양을 카메라/지도 세그먼트와 맞춘다 */}
        <Picker label="로봇" icon="cpu" value={robotId} onChange={setRobotId}
          options={(robots.data ?? []).filter((r) => r.enabled).map((r) => ({
            value: r.robotId, label: `${r.code} · ${r.name}`, sub: r.connected ? (r.mission ? '작업 중' : '연결됨') : '연결 안 됨',
          }))} />
      </div>
      <ErrorBox msg={act.error || st.error} />
      {robotId && (
        <div className="monitor">
          <div className="main-view">
            {mode === 'camera'
              ? <CameraView robotId={robotId} s={s} iHold={iHold} canAcquire={canAcquire} onAcquire={acquire} />
              : <MapPanel robotId={robotId} iHold={iHold} />}
          </div>
          <div className="side">
            <StatusCard s={s} />
            <div className="card">
              <div>제어권: {s?.control ? `${s.control.login} (${s.control.kind === 'MISSION' ? '점검 작업 중' : '조종'})` : '없음'}</div>
              {iHold ? (
                <button onClick={() => act.run(async () => { await api.releaseControl(robotId); await st.reload(); })}><Icon name="hand.raised.fill" size={16} />제어권 반납</button>
              ) : (
                <button className="primary" disabled={act.busy || !canAcquire} onClick={acquire}><Icon name="hand.raised.fill" size={16} />제어권 획득</button>
              )}
              {mode === 'camera'
                ? <div className="muted small">방향키로 이동 (누르는 동안만). 제어권이 없으면 방향키를 누를 때 자동으로 요청합니다.</div>
                : <div className="muted small">지도를 클릭해 목적지를 고른 뒤 "이 위치로 이동". 이동은 로봇의 Nav2 가 장애물을 피해 수행합니다.</div>}
            </div>
            {/* 비상 정지는 옆 칸 맨 아래(PC·태블릿 가로에서는 영상 아래 끝과 맞춘다) */}
          <button className="danger estop" onClick={() => act.run(async () => { await api.estop(robotId); await st.reload(); })}>
              <Icon name="exclamationmark.octagon.fill" size={22} />비상 정지
            </button>
          </div>
        </div>
      )}
      <p className="muted">조종은 제어권을 가진 1명만 할 수 있고, 점검 작업 중에는 제어권을 얻을 수 없습니다. 연결이 끊기면 로봇이 0.5초 안에 멈춥니다.</p>
    </Page>
  );
}

function StatusCard({ s }: { s: RobotStatus | null }) {
  return (
    <div className="card">
      <div className={s?.connected ? 'ok' : 'bad'}><Icon name={s?.connected ? 'checkmark.circle.fill' : 'xmark.circle.fill'} size={16} /> {s?.connected ? '연결 정상' : '연결 끊김'}</div>
      <div>전방 장애물 {s?.frontObstacleM != null ? `${s.frontObstacleM.toFixed(2)} m` : '-'}</div>
      <div>배터리 {s?.batteryPercent != null ? `${s.batteryPercent.toFixed(0)}%` : '정보 없음'}</div>
      <div className="ages">
        {s?.ageMs && Object.entries(s.ageMs).map(([k, v]) => (
          <span key={k} className={v == null ? 'muted' : v > 2000 ? 'warn-t' : ''}>{k} {v == null ? '없음' : `${(v / 1000).toFixed(1)}s`}</span>
        ))}
      </div>
      {s?.capabilities && <Capabilities caps={s.capabilities} />}
    </div>
  );
}

// ------------------------------------------------------------------ 카메라 모드
function CameraView({ robotId, s, iHold, canAcquire, onAcquire }: {
  robotId: number; s: RobotStatus | null; iHold: boolean; canAcquire: boolean; onAcquire: () => void;
}) {
  const api = useApi();
  const ws = useRef<WebSocket | null>(null);
  const cmd = useRef<[number, number]>([0, 0]);
  const held = useRef<Set<string>>(new Set());
  const [msg, setMsg] = useState('');
  const [active, setActive] = useState<string | null>(null);
  const acquireRef = useRef({ canAcquire, onAcquire, iHold });
  acquireRef.current = { canAcquire, onAcquire, iHold };

  // 조종 WebSocket: 제어권을 가진 동안 열어 두고, 누르고 있는 동안 100ms 마다 최신 명령을 보낸다
  useEffect(() => {
    if (!iHold) return;
    const sock = new WebSocket(api.teleopUrl(robotId));
    ws.current = sock;
    sock.onmessage = (e) => { const m = JSON.parse(e.data); if (m.type === 'error') setMsg(m.message); };
    sock.onclose = () => setMsg('조종 연결이 닫혔습니다');
    sock.onopen = () => setMsg('');
    const timer = setInterval(() => {
      const [l, a] = cmd.current;
      if (sock.readyState === WebSocket.OPEN && (l !== 0 || a !== 0)) {
        sock.send(JSON.stringify({ linear: l * SPEED.lin, angular: a * SPEED.ang }));
      }
    }, 100);
    return () => { clearInterval(timer); sock.close(); ws.current = null; };
  }, [iHold, robotId, api]);

  // 방향키: 카메라 모드에 있는 동안 전역으로 받는다(입력 상자·선택 상자에 포커스가 있으면 무시)
  useEffect(() => {
    const recompute = () => {
      let l = 0, a = 0;
      held.current.forEach((k) => { const v = KEYS[k]; l += v[0]; a += v[1]; });
      cmd.current = [Math.max(-1, Math.min(1, l)), Math.max(-1, Math.min(1, a))];
      setActive(held.current.size ? [...held.current][0] : null);
    };
    const down = (e: KeyboardEvent) => {
      if (isTyping(e.target)) return;
      if (e.key === ' ') { e.preventDefault(); stop(); return; }
      const k = KEYS[e.key] ? e.key : KEYS[e.key.toLowerCase()] ? e.key.toLowerCase() : null;
      if (!k) return;
      e.preventDefault();                      // 방향키로 화면이 스크롤되지 않게
      const { iHold: hold, canAcquire: can, onAcquire: acq } = acquireRef.current;
      if (!hold) { if (can && !e.repeat) acq(); return; }
      held.current.add(k);
      recompute();
    };
    const up = (e: KeyboardEvent) => {
      const k = KEYS[e.key] ? e.key : e.key.toLowerCase();
      if (held.current.delete(k)) { recompute(); if (!held.current.size) sendStop(); }
    };
    const blur = () => { if (held.current.size) { held.current.clear(); recompute(); sendStop(); } };
    window.addEventListener('keydown', down);
    window.addEventListener('keyup', up);
    window.addEventListener('blur', blur);
    return () => { window.removeEventListener('keydown', down); window.removeEventListener('keyup', up); window.removeEventListener('blur', blur); };
  }, []);

  const sendStop = () => {
    cmd.current = [0, 0];
    if (ws.current?.readyState === WebSocket.OPEN) ws.current.send(JSON.stringify({ linear: 0, angular: 0 }));
  };
  const stop = () => { held.current.clear(); setActive(null); sendStop(); };
  const press = (name: string) => { if (!iHold) { if (canAcquire) onAcquire(); return; } held.current = new Set([name]); cmd.current = KEYS[name]; setActive(name); };
  const btn = (name: string, label: React.ReactNode) => (
    <button className={active === name ? 'pressed' : ''}
      onPointerDown={() => press(name)} onPointerUp={stop} onPointerLeave={() => active === name && stop()}>{label}</button>
  );

  return (
    <div className="camera-view">
      <div className="video">
        {s?.connected ? <img src={api.streamUrl(robotId)} alt="실시간 영상" /> : <div className="novideo">영상 없음 (연결 끊김)</div>}
        {/* 안내는 영상 위쪽, 방향키는 영상 안 아래 가운데에 반투명으로 겹쳐 영상을 가리지 않게 한다 */}
        <div className={`drive-hint ${iHold ? 'on' : ''}`}>
          <Icon name={iHold ? 'arrow.up' : 'hand.raised.fill'} size={14} />
          {iHold ? (active ? '이동 중' : '방향키 ↑↓ 전진·후진 · ←→ 회전 · Space 정지') : '방향키를 누르면 제어권을 요청합니다'}
        </div>
        <div className={`pad pad-overlay ${iHold ? 'holding' : ''}`} aria-label="방향키">
          <span />{btn('ArrowUp', <Icon name="arrow.up" size={22} />)}<span />
          {btn('ArrowLeft', <Icon name="arrow.counterclockwise" size={22} />)}<button onClick={stop} aria-label="정지"><Icon name="stop.fill" size={20} /></button>{btn('ArrowRight', <Icon name="arrow.clockwise" size={22} />)}
          <span />{btn('ArrowDown', <Icon name="arrow.down" size={22} />)}<span />
        </div>
      </div>
      {msg && <div className="bad small teleop-msg">{msg}</div>}
    </div>
  );
}

// ------------------------------------------------------------------ 지도 모드
type Target = { x: number; y: number; yaw: number | null };
type Pose = { x: number; y: number; yaw: number };
const POSE_MS = 200;

/**
 * TurtleBot3 Waffle Pi 를 위에서 본 모양으로, 지도 축척 그대로 그린다.
 * 치수는 URDF(turtlebot3_waffle_pi.urdf)에서 가져왔다. 원점 = base_footprint(바퀴 축 가운데), +x = 앞.
 */
const WAFFLE = {
  body: { x: -0.064, y: 0, w: 0.266, h: 0.266 },                       // base_link 충돌 상자
  wheels: [{ x: 0, y: 0.144 }, { x: 0, y: -0.144 }], wheelR: 0.033, wheelW: 0.018,
  casters: [{ x: -0.177, y: 0.064 }, { x: -0.177, y: -0.064 }],       // 뒤쪽 볼 캐스터
  lidar: { x: -0.049, y: 0, r: 0.055 },                                // LDS-01
  camera: { x: 0.078, y: 0, w: 0.015, h: 0.03 },                       // Raspberry Pi 카메라
};

export function drawRobot(g: CanvasRenderingContext2D, cx: number, cy: number, yaw: number, ppm: number) {
  const W = WAFFLE;
  g.save();
  g.translate(cx, cy);
  g.rotate(-yaw);
  g.scale(ppm, -ppm);                      // 이제 단위 = m, y 위쪽
  const px = 1 / ppm;                      // 화면 1px
  const rect = (x: number, y: number, w: number, h: number) => g.rect(x - w / 2, y - h / 2, w, h);
  // 바퀴
  g.fillStyle = '#1c1c1e';
  W.wheels.forEach((w) => { g.beginPath(); rect(w.x, w.y, W.wheelR * 2, W.wheelW); g.fill(); });
  // 몸체
  g.fillStyle = 'rgba(0, 122, 255, 0.9)'; g.strokeStyle = '#fff'; g.lineWidth = 1.5 * px;
  g.beginPath(); g.roundRect(W.body.x - W.body.w / 2, W.body.y - W.body.h / 2, W.body.w, W.body.h, 0.02); g.fill(); g.stroke();
  // 캐스터
  g.fillStyle = 'rgba(255, 255, 255, 0.55)';
  W.casters.forEach((c) => { g.beginPath(); g.arc(c.x, c.y, 0.012, 0, Math.PI * 2); g.fill(); });
  // 라이다
  g.fillStyle = '#2c2c2e'; g.strokeStyle = 'rgba(255, 255, 255, 0.8)'; g.lineWidth = 1 * px;
  g.beginPath(); g.arc(W.lidar.x, W.lidar.y, W.lidar.r, 0, Math.PI * 2); g.fill(); g.stroke();
  // 카메라(앞)
  g.fillStyle = '#fff';
  g.beginPath(); rect(W.camera.x, W.camera.y, W.camera.w, W.camera.h); g.fill();
  // 앞 방향 표시
  g.strokeStyle = '#fff'; g.lineWidth = 1.5 * px; g.lineCap = 'round';
  g.beginPath(); g.moveTo(0.02, 0.05); g.lineTo(0.055, 0); g.lineTo(0.02, -0.05); g.stroke();
  g.restore();
}

function MapPanel({ robotId, iHold }: { robotId: number; iHold: boolean }) {
  const api = useApi();
  const info = usePoll<MapInfo | null>(() => api.mapInfo(robotId).catch(() => null), 10000, [robotId]);
  // 로봇 위치 토픽(/inspection/map_pose)이 5Hz 이므로 같은 주기로 받는다. 사이 프레임은 아래에서 보간해 그린다.
  const view = usePoll<MapView | null>(() => api.mapView(robotId), POSE_MS, [robotId]);
  const robotLayer = useRef<HTMLCanvasElement>(null);
  const anim = useRef<{ from: Pose | null; to: Pose | null; t0: number }>({ from: null, to: null, t0: 0 });
  const shown = useRef<Pose | null>(null);
  const points = usePoll<Point[]>(() => api.points(), 0);
  // 설정 "주행 경로 표시(제어기 방향)": 켜 두었을 때만 주황 실선을 그린다(기본은 숨김)
  const settings = usePoll(() => api.settings().catch(() => null), 10000);
  const showControl = settings.data?.['display.control_direction'] === true;
  const [img, setImg] = useState<HTMLImageElement | null>(null);
  const [target, setTarget] = useState<Target | null>(null);
  const drag = useRef<{ x: number; y: number; px: number; py: number } | null>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const [cssScale, setCssScale] = useState(1);     // 지도 1칸 = 화면 몇 px (CSS 기준)
  const act = useAction();
  const m = info.data;

  // 지도 이미지: 버전이 바뀔 때만 다시 받는다(SLAM 중에는 지도가 자란다)
  useEffect(() => {
    if (!m) return;
    const i = new Image();
    i.onload = () => setImg(i);
    i.src = api.mapImageUrl(robotId, m.version);
  }, [m?.version, robotId, api]); // eslint-disable-line react-hooks/exhaustive-deps

  // 화면 크기에 맞춘 축척. 캔버스는 CSS 크기 × devicePixelRatio 로 그려 선명하게 한다.
  useEffect(() => {
    const c = canvas.current;
    if (!c || !m) return;
    const fit = () => {
      const W = c.parentElement!.clientWidth;
      setCssScale(Math.min(W / m.width, 560 / m.height));
    };
    fit();
    const ro = new ResizeObserver(fit);
    ro.observe(c.parentElement!);
    return () => ro.disconnect();
  }, [m]);

  // 지도 좌표 ↔ 화면(CSS px) 좌표
  // 변환식은 mapGeo.ts 한 곳에 있다(점검 지점 지정 지도와 같은 식)
  const geo = m ? mapGeo(m, cssScale) : null;
  const toPx = (x: number) => geo!.toPx(x);
  const toPy = (y: number) => geo!.toPy(y);
  const toWorld = (cx: number, cy: number) => geo!.toWorld(cx, cy);

  // 그리기
  useEffect(() => {
    const c = canvas.current;
    if (!c || !m || !img) return;
    const dpr = window.devicePixelRatio || 1;
    const cw = m.width * cssScale, ch = m.height * cssScale;
    c.style.width = `${cw}px`;
    c.style.height = `${ch}px`;
    c.width = Math.round(cw * dpr);
    c.height = Math.round(ch * dpr);
    const g = c.getContext('2d')!;
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    g.imageSmoothingEnabled = true;            // 지도 그림은 4배 해상도로 다듬어 오므로 부드럽게 축소
    g.drawImage(img, 0, 0, cw, ch);
    const v = view.data;
    // 계획 경로: 점선
    if (v?.path?.length) {
      g.strokeStyle = '#007aff'; g.lineWidth = 2.5; g.lineJoin = 'round'; g.lineCap = 'round';
      g.setLineDash([0.1, 6]);             // 길이 0 에 가까운 선 + 둥근 끝 = 점
      g.beginPath();
      v.path.forEach(([x, y], i) => (i ? g.lineTo(toPx(x), toPy(y)) : g.moveTo(toPx(x), toPy(y))));
      g.stroke();
      g.setLineDash([]);
    }
    // 제어기 방향: 지금 속도 명령을 3초 유지했을 때 갈 호(실선) + 끝의 화살촉. 점선(A* 경로)과 어긋난 만큼이 제어기의 판단이다
    const ct = showControl ? v?.control?.traj : null;
    if (ct && ct.length > 1) {
      g.strokeStyle = '#ff9500'; g.fillStyle = '#ff9500'; g.lineWidth = 3; g.lineJoin = 'round'; g.lineCap = 'round';
      g.beginPath();
      ct.forEach(([x, y], i) => (i ? g.lineTo(toPx(x), toPy(y)) : g.moveTo(toPx(x), toPy(y))));
      g.stroke();
      const [ax, ay] = ct[ct.length - 2], [bx, by] = ct[ct.length - 1];
      const ex = toPx(bx), ey = toPy(by), ang = Math.atan2(ey - toPy(ay), ex - toPx(ax));
      if (Math.hypot(ex - toPx(ct[0][0]), ey - toPy(ct[0][1])) > 6) {      // 제자리 회전이면 화살촉을 그리지 않는다
        g.beginPath();
        g.moveTo(ex + 9 * Math.cos(ang), ey + 9 * Math.sin(ang));
        g.lineTo(ex + 6 * Math.cos(ang + 2.4), ey + 6 * Math.sin(ang + 2.4));
        g.lineTo(ex + 6 * Math.cos(ang - 2.4), ey + 6 * Math.sin(ang - 2.4));
        g.closePath(); g.fill();
      }
    }
    // 라이다: 이웃한 점(0.25m 이내)을 이어 하나의 선으로 그린다
    if (v?.scan?.length) {
      g.strokeStyle = 'rgba(255, 59, 48, 0.85)'; g.lineWidth = 1.5; g.lineJoin = 'round'; g.lineCap = 'round';
      g.beginPath();
      let prev: [number, number] | null = null;
      for (const pt of v.scan) {
        if (prev && Math.hypot(pt[0] - prev[0], pt[1] - prev[1]) < 0.25) g.lineTo(toPx(pt[0]), toPy(pt[1]));
        else g.moveTo(toPx(pt[0]), toPy(pt[1]));
        prev = pt;
      }
      const first = v.scan[0];                 // 360° 스캔의 끝과 처음 잇기
      if (prev && Math.hypot(first[0] - prev[0], first[1] - prev[1]) < 0.25) g.lineTo(toPx(first[0]), toPy(first[1]));
      g.stroke();
    }
    // 점검 지점
    points.data?.forEach((p) => {
      g.strokeStyle = '#30b0c7'; g.lineWidth = 2; g.fillStyle = '#fff';
      g.beginPath(); g.arc(toPx(p.x), toPy(p.y), 6, 0, Math.PI * 2); g.fill(); g.stroke();
      g.fillStyle = '#30b0c7'; g.font = '600 11px -apple-system, system-ui, sans-serif'; g.textAlign = 'center';
      g.fillText(p.code, toPx(p.x), toPy(p.y) - 10);
    });
    // 목적지와 도착 방향(드래그로 지정)
    const goal: Target | null = target
      ?? (v?.manualGoal && ['SENT', 'ACTIVE'].includes(v.manualGoal.state) ? v.manualGoal : null);
    if (goal) {
      const gx = toPx(goal.x), gy = toPy(goal.y);
      g.strokeStyle = '#af52de'; g.fillStyle = 'rgba(175, 82, 222, 0.15)'; g.lineWidth = 2;
      g.beginPath(); g.arc(gx, gy, 9, 0, Math.PI * 2); g.fill(); g.stroke();
      if (goal.yaw != null) {
        const L = 26, ex = gx + L * Math.cos(-goal.yaw), ey = gy + L * Math.sin(-goal.yaw);
        g.beginPath(); g.moveTo(gx, gy); g.lineTo(ex, ey); g.stroke();
        g.beginPath();
        g.moveTo(ex, ey);
        g.lineTo(ex - 8 * Math.cos(-goal.yaw - 0.5), ey - 8 * Math.sin(-goal.yaw - 0.5));
        g.lineTo(ex - 8 * Math.cos(-goal.yaw + 0.5), ey - 8 * Math.sin(-goal.yaw + 0.5));
        g.closePath(); g.fillStyle = '#af52de'; g.fill();
      }
    }
  }, [m, img, view.data, points.data, target, cssScale, showControl]); // eslint-disable-line react-hooks/exhaustive-deps

  // 새 위치가 오면 지금 그려진 위치에서 새 위치로 POSE_MS 동안 옮겨 간다
  useEffect(() => {
    const p = view.data?.pose ?? null;
    anim.current = { from: shown.current ?? p, to: p, t0: performance.now() };
  }, [view.data]);

  // 로봇은 위 겹 캔버스에 화면 주사율(보통 60fps)로 그린다 — 지도·경로를 매 프레임 다시 그리지 않는다
  useEffect(() => {
    const c = robotLayer.current;
    if (!c || !m) return;
    const dpr = window.devicePixelRatio || 1;
    const cw = m.width * cssScale, ch = m.height * cssScale;
    c.style.width = `${cw}px`;
    c.style.height = `${ch}px`;
    c.width = Math.round(cw * dpr);
    c.height = Math.round(ch * dpr);
    const g = c.getContext('2d')!;
    let raf = 0;
    const frame = (now: number) => {
      const { from, to, t0 } = anim.current;
      g.setTransform(1, 0, 0, 1, 0, 0);
      g.clearRect(0, 0, c.width, c.height);
      g.setTransform(dpr, 0, 0, dpr, 0, 0);
      if (from && to) {
        const k = Math.min(1, (now - t0) / POSE_MS);
        let dy = to.yaw - from.yaw;
        dy = Math.atan2(Math.sin(dy), Math.cos(dy));        // -180°↔180° 경계에서 반대로 돌지 않게
        const p = { x: from.x + (to.x - from.x) * k, y: from.y + (to.y - from.y) * k, yaw: from.yaw + dy * k };
        shown.current = p;
        drawRobot(g, toPx(p.x), toPy(p.y), p.yaw, cssScale / m.resolution);
      } else {
        shown.current = null;
      }
      raf = requestAnimationFrame(frame);
    };
    raf = requestAnimationFrame(frame);
    return () => cancelAnimationFrame(raf);
  }, [m, cssScale]); // eslint-disable-line react-hooks/exhaustive-deps

  // 누른 곳 = 목적지, 누른 채 끌면 = 도착했을 때 로봇이 바라볼 방향
  const local = (e: React.PointerEvent<HTMLCanvasElement>) => {
    const rect = canvas.current!.getBoundingClientRect();
    return { cx: e.clientX - rect.left, cy: e.clientY - rect.top };
  };
  const onDown = (e: React.PointerEvent<HTMLCanvasElement>) => {
    if (!m) return;
    const { cx, cy } = local(e);
    const w = toWorld(cx, cy);
    drag.current = { x: w.x, y: w.y, px: cx, py: cy };
    canvas.current!.setPointerCapture(e.pointerId);
    setTarget({ x: round2(w.x), y: round2(w.y), yaw: null });
  };
  const onMove = (e: React.PointerEvent<HTMLCanvasElement>) => {
    const d = drag.current;
    if (!d) return;
    const { cx, cy } = local(e);
    if (Math.hypot(cx - d.px, cy - d.py) < 8) return;          // 짧은 움직임은 클릭으로 본다
    setTarget({ x: round2(d.x), y: round2(d.y), yaw: Math.atan2(-(cy - d.py), cx - d.px) });
  };
  const onUp = () => { drag.current = null; };

  const go = () => act.run(async () => {
    const p = view.data?.pose;
    // 방향을 끌어 정하지 않았으면 로봇이 있는 곳에서 목적지를 바라보는 방향
    const yaw = target!.yaw ?? (p ? Math.atan2(target!.y - p.y, target!.x - p.x) : 0);
    await api.goTo(robotId, target!.x, target!.y, yaw);
    setTarget(null);
  });

  const mg = view.data?.manualGoal;
  const goalText: Record<string, string> = { SENT: '전송됨', ACTIVE: '이동 중', SUCCEEDED: '도착', ABORTED: '실패', CANCELED: '취소됨' };
  return (
    <div className="map-view">
      {!m && <div className="novideo map-empty">지도를 기다리는 중… (로봇의 지도 서버·SLAM 이 실행 중이어야 합니다)</div>}
      <div className="map-canvas">
        <canvas ref={canvas} onPointerDown={onDown} onPointerMove={onMove} onPointerUp={onUp} onPointerCancel={onUp}
          className={iHold ? 'clickable' : ''} />
        <canvas ref={robotLayer} className="robot-layer" aria-hidden />
      </div>
      <div className="map-legend small">
        <span><i className="lg robot" /> 로봇</span><span><i className="lg path" /> 계획 경로(A*)</span>{showControl && <span><i className="lg control" /> 제어기 방향</span>}
        <span><i className="lg scan" /> 라이다</span><span><i className="lg point" /> 점검 지점</span><span><i className="lg goal" /> 목적지·방향</span>
        {view.data?.pose ? <span className="muted">위치 x {view.data.pose.x.toFixed(2)} · y {view.data.pose.y.toFixed(2)} · θ {(view.data.pose.yaw * 180 / Math.PI).toFixed(0)}°</span>
          : <span className="warn-t">위치 추정 없음</span>}
      </div>
      <div className="row wrap">
        {target ? (
          <>
            <span>목적지 ({target.x}, {target.y}){target.yaw != null ? ` · 방향 ${Math.round(target.yaw * 180 / Math.PI)}°` : ''}</span>
            <button className="primary" disabled={!iHold || act.busy} onClick={go}><Icon name="location.fill" size={16} />이 위치로 이동</button>
            <button onClick={() => setTarget(null)}>지우기</button>
            {!iHold && <span className="warn-t small">제어권을 먼저 획득하세요</span>}
          </>
        ) : <span className="muted small">지도를 눌러 목적지를 고르고, 누른 채 끌면 도착했을 때 바라볼 방향을 정합니다</span>}
        {mg && <span className="small">지도 이동: <b>{goalText[mg.state] ?? mg.state}</b>{mg.reason ? ` · ${mg.reason}` : ''}</span>}
        {mg && ['SENT', 'ACTIVE'].includes(mg.state) && <button onClick={() => act.run(() => api.cancelGoTo(robotId))}>이동 취소</button>}
      </div>
      <ErrorBox msg={act.error} />
    </div>
  );
}

const round2 = (v: number) => Math.round(v * 100) / 100;
