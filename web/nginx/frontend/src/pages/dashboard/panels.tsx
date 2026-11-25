// 관제 대시보드 패널. 패널 하나 = 함수 하나이고, 맨 아래 PANELS 표에 등록한다.
// 어디에 얼마나 크게 놓을지는 layout.ts 가 정한다 — 패널을 더하거나 옮길 때 이 두 곳만 고친다.
import { useEffect, useRef, useState, type ReactNode } from 'react';
import type { RobotStatus } from '../../api/types';
import { STATUS_LABEL, ago, fmtTime, useApi, usePoll } from '../../util';
import { Icon } from '../../Icon';
import { drawZone, mapGeo } from '../../mapGeo';
import { drawRobot } from '../user/Monitor';
import { EVENT_LABEL, eventText } from '../user/inspectionText';
import { INCIDENT_STATE, LAUNCH_MODE, checkText } from '../user/scenarioText';
import { POINT_STATE_TEXT, fmtDur, pointState, type DashData, type Ref } from './data';

export interface PanelProps { d: DashData; open: (ref: Ref) => void }
export interface PanelDef {
  title: string;
  icon: string;
  Body: (p: PanelProps) => ReactNode;
  /** 제목 옆 숫자·꼬리표 */
  extra?: (d: DashData) => ReactNode;
  /** 제목 줄과 틀 없이 그린다(요약 타일 줄) */
  bare?: boolean;
}

const Empty = ({ children }: { children: ReactNode }) => <div className="dz-empty">{children}</div>;
export const Dot = ({ tone }: { tone: string }) => <i className={`dz-dot ${tone}`} />;
export const Pill = ({ tone = 'gray', children }: { tone?: string; children: ReactNode }) => <span className={`dz-pill ${tone}`}>{children}</span>;

const TASK_TONE: Record<string, string> = {
  REQUESTED: 'gray', DISPATCHED: 'blue', RUNNING: 'blue', CANCEL_REQUESTED: 'orange',
  COMPLETED: 'green', FAILED: 'red', CANCELLED: 'gray', INTERRUPTED: 'red',
};
export const TaskPill = ({ status }: { status: string }) => <Pill tone={TASK_TONE[status] ?? 'gray'}>{STATUS_LABEL[status] ?? status}</Pill>;

// ------------------------------------------------------------------ 요약 타일
function Kpi({ d, open }: PanelProps) {
  const t = d.overview?.today;
  const online = d.robots.filter((r) => r.enabled && r.connected).length;
  const enabled = d.robots.filter((r) => r.enabled).length;
  const queued = d.backlog?.total ?? 0;
  const critical = d.alerts.filter((a) => a.severity === 'CRITICAL').length;
  const tiles: { label: string; value: ReactNode; sub?: string; tone?: string; icon: string; ref?: Ref }[] = [
    { label: '경고', value: d.alerts.length, sub: critical ? `비상 ${critical}건` : '비상 없음', tone: critical ? 'red' : d.alerts.length ? 'orange' : 'green', icon: 'bell.fill' },
    { label: '로봇 연결', value: <>{online}<small>/{enabled}</small></>, sub: enabled - online ? `${enabled - online}대 끊김` : '모두 연결됨', tone: enabled - online ? 'red' : 'green', icon: 'cpu', ref: d.robotId ? { kind: 'robot', id: d.robotId } : undefined },
    { label: '진행 중 작업', value: d.activeTasks.length, sub: '지금 수행 중', tone: 'blue', icon: 'play.fill', ref: { kind: 'tasks', group: 'active' } },
    { label: '대기 중 예약', value: queued, sub: queued ? '로봇이 비면 이어서 실행' : '밀린 예약 없음', tone: queued ? 'orange' : 'gray', icon: 'hourglass' },
    { label: '오늘 완료', value: t?.tasks.completed ?? '-', sub: `오늘 요청 ${t?.tasks.total ?? '-'}건`, tone: 'green', icon: 'checkmark.circle.fill', ref: { kind: 'tasks', group: 'done' } },
    { label: '오늘 실패·중단', value: t?.tasks.failed ?? '-', sub: `취소 ${t?.tasks.cancelled ?? '-'}건`, tone: t?.tasks.failed ? 'red' : 'gray', icon: 'xmark.circle.fill', ref: { kind: 'tasks', group: 'failed' } },
    { label: '판정 대기', value: t?.observations.unreviewed ?? '-', sub: `오늘 촬영 ${t?.observations.total ?? '-'}건`, tone: t?.observations.unreviewed ? 'blue' : 'gray', icon: 'eye' },
    { label: '이상 · 확인 불가', value: <>{t?.observations.abnormal ?? '-'}<small> · {t?.observations.unable ?? '-'}</small></>, sub: `정상 ${t?.observations.normal ?? '-'}건`, tone: t?.observations.abnormal || t?.observations.unable ? 'orange' : 'gray', icon: 'exclamationmark.triangle.fill' },   // 이상 판정도 경고 색(빨강은 비상 = 화재만)
  ];
  return (
    <div className="dz-kpis">
      {tiles.map((k) => (
        <button key={k.label} className={`dz-kpi ${k.tone ?? ''}`} disabled={!k.ref} onClick={() => k.ref && open(k.ref)}>
          <span className="k-label"><Icon name={k.icon} size={18} />{k.label}</span>
          <span className="k-value">{k.value}</span>
          <span className="k-sub">{k.sub}</span>
        </button>
      ))}
    </div>
  );
}

// ------------------------------------------------------------------ 로봇
export function robotActivity(r: RobotStatus) {
  if (!r.enabled) return ['사용 안 함', 'gray'];
  if (!r.connected) return ['연결 끊김', 'red'];
  if (r.mission) return [`점검 중 · 작업 #${r.mission.missionId}`, 'blue'];
  if (r.control?.kind === 'USER') return [`수동 조종 · ${r.control.login}`, 'purple'];
  return ['대기', 'green'];
}

function Robots({ d, open }: PanelProps) {
  if (!d.robots.length) return <Empty>등록된 로봇이 없습니다</Empty>;
  return (
    <div className="dz-list">
      {d.robots.map((r) => {
        const [text, tone] = robotActivity(r);
        return (
          <button key={r.robotId} className={`dz-item robot ${d.robotId === r.robotId ? 'sel' : ''}`} onClick={() => open({ kind: 'robot', id: r.robotId })}>
            <span className={`dz-avatar ${tone}`}><Icon name="cpu" size={24} /></span>
            <span className="grow">
              <b>{r.code}</b> <span className="dim">{r.name}</span>
              <span className="line"><Dot tone={tone} />{text}</span>
            </span>
            <span className="robot-meta">
              <span><Icon name="battery" size={16} />{r.batteryPercent != null ? `${Math.round(r.batteryPercent)}%` : '-'}</span>
              <span className="dim">{r.pose ? `x ${r.pose.x.toFixed(1)} · y ${r.pose.y.toFixed(1)}` : '위치 없음'}</span>
            </span>
          </button>
        );
      })}
    </div>
  );
}

// ------------------------------------------------------------------ 지도
/** 로봇을 고르는 단추(로봇이 여러 대일 때만 보인다). 지도와 카메라가 같은 로봇을 본다. */
function RobotTabs({ d }: { d: DashData }) {
  if (d.robots.length < 2) return <span className="dim">{d.robots.find((r) => r.robotId === d.robotId)?.code}</span>;
  return (
    <span className="dz-tabs">
      {d.robots.map((r) => (
        <button key={r.robotId} className={r.robotId === d.robotId ? 'on' : ''} onClick={() => d.setRobotId(r.robotId)}>{r.code}</button>
      ))}
    </span>
  );
}

function MapPanel({ d, open }: PanelProps) {
  const api = useApi();
  // 설정 "주행 경로 표시(제어기 방향)": 켜 두었을 때만 주황 실선을 그린다(기본은 숨김)
  const settings = usePoll(() => api.settings().catch(() => null), 10000);
  const showControl = settings.data?.['display.control_direction'] === true;
  // 금지구역(관리자가 관제 화면에서 그린 것): 붉은 빗금 상자로 보여 준다
  const zones = usePoll(() => (d.robotId ? api.zones(d.robotId).catch(() => []) : Promise.resolve([])), 3000, [d.robotId]);
  const box = useRef<HTMLDivElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const [img, setImg] = useState<HTMLImageElement | null>(null);
  const m = d.map;
  useEffect(() => {
    if (!m || !d.robotId) { setImg(null); return; }
    const i = new Image();
    i.onload = () => setImg(i);
    i.src = api.mapImageUrl(d.robotId, m.version);
  }, [m?.version, d.robotId, api]); // eslint-disable-line react-hooks/exhaustive-deps

  // 화면은 고정 크기(1920×1080)이므로 패널 크기도 고정이다. 처음 한 번만 재면 된다.
  const [size, setSize] = useState<{ w: number; h: number } | null>(null);
  useEffect(() => { if (box.current) setSize({ w: box.current.clientWidth, h: box.current.clientHeight }); }, []);
  const geo = m && size ? mapGeo(m, Math.min(size.w / m.width, size.h / m.height)) : null;

  useEffect(() => {
    const c = canvas.current;
    if (!c || !m || !img || !geo) return;
    const dpr = 2;                              // 화면 전체를 확대해 띄우므로 넉넉한 해상도로 그린다
    c.style.width = `${geo.cw}px`; c.style.height = `${geo.ch}px`;
    c.width = Math.round(geo.cw * dpr); c.height = Math.round(geo.ch * dpr);
    const g = c.getContext('2d')!;
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    g.drawImage(img, 0, 0, geo.cw, geo.ch);
    zones.data?.forEach((z) => drawZone(g, geo.toPx, geo.toPy, z, { label: z.name || '금지구역' }));
    const v = d.view;
    if (v?.path?.length) {
      g.strokeStyle = '#0a84ff'; g.lineWidth = 3; g.lineJoin = 'round'; g.lineCap = 'round';
      g.setLineDash([0.1, 7]);
      g.beginPath();
      v.path.forEach(([x, y], i) => (i ? g.lineTo(geo.toPx(x), geo.toPy(y)) : g.moveTo(geo.toPx(x), geo.toPy(y))));
      g.stroke();
      g.setLineDash([]);
    }
    // 제어기 방향: 지금 속도 명령을 3초 유지했을 때 갈 호(주황 실선) + 화살촉. 점선(A* 경로)과 어긋난 만큼이 제어기의 판단이다
    const ct = showControl ? v?.control?.traj : null;
    if (ct && ct.length > 1) {
      g.strokeStyle = '#ff9500'; g.fillStyle = '#ff9500'; g.lineWidth = 4; g.lineJoin = 'round'; g.lineCap = 'round';
      g.beginPath();
      ct.forEach(([x, y], i) => (i ? g.lineTo(geo.toPx(x), geo.toPy(y)) : g.moveTo(geo.toPx(x), geo.toPy(y))));
      g.stroke();
      const [ax, ay] = ct[ct.length - 2], [bx, by] = ct[ct.length - 1];
      const ex = geo.toPx(bx), ey = geo.toPy(by), ang = Math.atan2(ey - geo.toPy(ay), ex - geo.toPx(ax));
      if (Math.hypot(ex - geo.toPx(ct[0][0]), ey - geo.toPy(ct[0][1])) > 6) {   // 제자리 회전이면 화살촉을 그리지 않는다
        g.beginPath();
        g.moveTo(ex + 11 * Math.cos(ang), ey + 11 * Math.sin(ang));
        g.lineTo(ex + 8 * Math.cos(ang + 2.4), ey + 8 * Math.sin(ang + 2.4));
        g.lineTo(ex + 8 * Math.cos(ang - 2.4), ey + 8 * Math.sin(ang - 2.4));
        g.closePath(); g.fill();
      }
    }
    if (v?.pose) drawRobot(g, geo.toPx(v.pose.x), geo.toPy(v.pose.y), v.pose.yaw, geo.scale / m.resolution);
  }, [m, img, d.view, geo?.scale, showControl, zones.data]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="dz-map" ref={box}>
      {!m && <Empty>지도를 기다리는 중…</Empty>}
      {geo && (
        <div className="dz-map-stage" style={{ width: geo.cw, height: geo.ch }}>
          <canvas ref={canvas} />
          {/* 점검 지점: 누르면 지점 상세. 색 = 가장 최근 점검 상태 */}
          {d.overview?.points.map((p) => {
            const st = pointState(p);
            const current = d.view?.mission?.currentPointId === p.point_id;
            // 로봇과 겹치면 반투명: 로봇(캔버스)이 비쳐 보이게 한다. 단추는 로봇 위에 그대로 있어 눌린다
            const rp = d.view?.pose;
            const over = !!rp && Math.hypot(rp.x - p.x, rp.y - p.y) < 0.4;
            return (
              <button key={p.point_id} className={`dz-pin ${st} ${current ? 'current' : ''} ${over ? 'over' : ''}`} style={{ left: geo.toPx(p.x), top: geo.toPy(p.y) }}
                title={`${p.code} ${p.name} · ${POINT_STATE_TEXT[st]}`} onClick={() => open({ kind: 'point', id: p.point_id })}>
                <span>{p.code}</span>
              </button>
            );
          })}
          {/* 열린 사건: 화재 위치. 누르면 사건 상세 */}
          {d.incidents.map((i) => (
            <button key={`inc${i.incidentId}`} className="dz-fire" style={{ left: geo.toPx(i.x), top: geo.toPy(i.y) }}
              title={`사건 #${i.incidentId} · ${INCIDENT_STATE[i.state]?.[0] ?? i.state}`} onClick={() => open({ kind: 'incident', id: i.incidentId })}>
              <Icon name="flame.fill" size={20} /><span>사건 #{i.incidentId}</span>
            </button>
          ))}
        </div>
      )}
      <div className="dz-legend">
        {(['ok', 'wait', 'warn', 'bad', 'none'] as const).map((s) => <span key={s}><Dot tone={`pt-${s}`} />{POINT_STATE_TEXT[s]}</span>)}
        <span style={{ color: '#0a84ff' }}>┄ 계획 경로(A*)</span>
        {!!zones.data?.length && <span style={{ color: '#ff3b30' }}>▨ 금지구역</span>}
        {showControl && <span style={{ color: '#ff9500' }}>━▶ 제어기 방향</span>}
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ 카메라
function Camera({ d }: PanelProps) {
  const api = useApi();
  const r = d.robots.find((x) => x.robotId === d.robotId);
  const [failed, setFailed] = useState(false);
  // 연결이 돌아오면 영상을 다시 붙인다
  useEffect(() => setFailed(false), [d.robotId, r?.connected]);
  if (!r) return <Empty>로봇 없음</Empty>;
  if (!r.connected || failed) return <Empty><Icon name="wifi.slash" size={28} /><br />영상 없음</Empty>;
  return <img className="dz-camera" src={api.streamUrl(r.robotId)} alt={`${r.code} 카메라`} onError={() => setFailed(true)} />;
}

// ------------------------------------------------------------------ 경고
function Alerts({ d, open }: PanelProps) {
  if (!d.alerts.length) return <Empty><Icon name="checkmark.circle.fill" size={30} className="ok-ink" /><br />지금 주의할 일이 없습니다</Empty>;
  return (
    <div className="dz-list scroll">
      {d.alerts.map((a) => (
        <button key={a.key} className={`dz-item alert ${a.severity === 'CRITICAL' ? 'red' : 'orange'}`} onClick={() => open(a.ref)}>
          <Icon name={a.icon} size={22} />
          <span className="grow">
            <b>{a.title}</b>
            {a.detail && <span className="line dim">{a.detail}</span>}
          </span>
          <span className="when">{a.at ? ago(a.at) : '지금'}</span>
        </button>
      ))}
    </div>
  );
}

// ------------------------------------------------------------------ 최근 이벤트
const EVENT_TONE: Record<string, string> = {
  COMPLETED: 'green', OBSERVATION_SAVED: 'green', ARRIVED: 'green',
  MISSION_FAILED: 'red', EMERGENCY_STOP: 'red', MISSION_INTERRUPTED: 'red', DISPATCH_FAILED: 'red',
  ARRIVAL_FAILED: 'orange', ARRIVAL_BLOCKED: 'orange', OBSERVATION_UNABLE: 'orange', PREFLIGHT_FAILED: 'orange',
  CANCEL_REQUESTED: 'orange', CANCELLED: 'gray',
};
function Events({ d, open }: PanelProps) {
  const ev = d.overview?.events ?? [];
  if (!ev.length) return <Empty>기록이 없습니다</Empty>;
  return (
    <div className="dz-list scroll tight">
      {ev.map((e) => (
        <button key={e.event_id} className="dz-item event" onClick={() => open({ kind: 'task', id: e.task_id })}>
          <span className="when mono">{fmtTime(e.occurred_at, false)}</span>
          <Dot tone={EVENT_TONE[e.type] ?? 'blue'} />
          <span className="grow ellipsis"><b>{EVENT_LABEL[e.type] ?? e.type}</b> <span className="dim">{eventText(e)}</span></span>
          <span className="dim">#{e.task_id}{e.robot_code ? ` · ${e.robot_code}` : ''}</span>
        </button>
      ))}
    </div>
  );
}

// ------------------------------------------------------------------ 진행·대기 작업
function Queue({ d, open }: PanelProps) {
  const queue = (d.backlog?.robots ?? []).flatMap((b) => b.queue.map((q) => ({ ...q, robotCode: b.robotCode })));
  if (!d.activeTasks.length && !queue.length) return <Empty>진행 중이거나 기다리는 작업이 없습니다</Empty>;
  return (
    <div className="dz-list scroll">
      {d.activeTasks.map((t) => (
        <button key={`t${t.task_id}`} className="dz-item" onClick={() => open({ kind: 'task', id: t.task_id })}>
          <span className="dz-avatar blue"><Icon name="play.fill" size={20} /></span>
          <span className="grow">
            <b>작업 #{t.task_id}</b> <span className="dim">{t.robot_code} · {t.points}</span>
            <span className="line dim">{t.requester_login} · {ago(t.created_at)} 요청{t.note ? ` · ${t.note}` : ''}</span>
          </span>
          <TaskPill status={t.status} />
        </button>
      ))}
      {queue.map((q) => (
        <button key={`q${q.key}`} className="dz-item" onClick={() => open({ kind: 'schedule', id: q.scheduleId })}>
          <span className="dz-avatar orange"><Icon name="hourglass" size={20} /></span>
          <span className="grow">
            <b>{q.name}</b> <span className="dim">{q.robotCode} · {q.points}</span>
            <span className="line dim">예정 {fmtTime(q.plannedAt)} · {fmtDur(q.delaySec)} 지연{q.waitReason ? ` · ${q.waitReason}` : ''}</span>
          </span>
          <Pill tone="orange">대기 {q.order}</Pill>
        </button>
      ))}
    </div>
  );
}

// ------------------------------------------------------------------ 사건(화재 대응)
const INC_TONE: Record<string, string> = { blue: 'blue', red: 'red', orange: 'orange', purple: 'purple', green: 'green', gray: 'gray' };
function Incidents({ d, open }: PanelProps) {
  if (!d.incidents.length) return <Empty><Icon name="checkmark.circle.fill" size={28} className="ok-ink" /><br />진행 중인 화재 사건이 없습니다</Empty>;
  return (
    <div className="dz-list scroll">
      {d.incidents.map((i) => {
        const [label, tone] = INCIDENT_STATE[i.state] ?? [i.state, 'gray'];
        const wait = i.state === 'AWAITING_APPROVAL';
        return (
          <button key={i.incidentId} className={`dz-item alert ${wait || i.state === 'FAILED' || i.state === 'DETECTED' ? 'red' : 'orange'}`}
            onClick={() => open({ kind: 'incident', id: i.incidentId })}>
            <Icon name="flame.fill" size={22} />
            <span className="grow">
              <b>사건 #{i.incidentId}</b> <span className="dim">({i.x.toFixed(1)}, {i.y.toFixed(1)}) · {LAUNCH_MODE[i.launchMode]}</span>
              <span className="line dim">{i.recheck?.grade ? `재판독 ${checkText(i.recheck)}` : i.closeReason ?? `감지 ${ago(i.createdAt)}`}</span>
            </span>
            <Pill tone={INC_TONE[tone] ?? 'gray'}>{label}</Pill>
            <span className="when">{ago(i.createdAt)}</span>
          </button>
        );
      })}
    </div>
  );
}

// ------------------------------------------------------------------ 점검 지점 현황
function Points({ d, open }: PanelProps) {
  const pts = d.overview?.points ?? [];
  if (!pts.length) return <Empty>점검 지점이 없습니다</Empty>;
  return (
    <div className="dz-list scroll">
      {pts.map((p) => {
        const st = pointState(p);
        return (
          <button key={p.point_id} className="dz-item" onClick={() => open({ kind: 'point', id: p.point_id })}>
            <span className={`dz-code pt-${st}`}>{p.code}</span>
            <span className="grow">
              <b>{p.name}</b>
              <span className="line dim">{p.captured_at ? `최근 점검 ${ago(p.captured_at)} · ${fmtTime(p.captured_at)}` : '점검 기록 없음'}</span>
            </span>
            <Pill tone={`pt-${st}`}>{POINT_STATE_TEXT[st]}</Pill>
          </button>
        );
      })}
    </div>
  );
}

// ------------------------------------------------------------------ 예약 일정
const KIND: Record<string, string> = { MANUAL: '수동', ONCE: '한 번', INTERVAL: '간격', DAILY: '매일', WEEKLY: '매주' };
const LAST: Record<string, string> = { CREATED: '실행', SKIPPED_BUSY: '건너뜀', SKIPPED_OFFLINE: '건너뜀', MISSED: '놓침', FAILED: '실패', CANCELLED: '취소' };
function Schedules({ d, open }: PanelProps) {
  const list = d.schedules.filter((s) => s.enabled && s.next_run_at)
    .sort((a, b) => new Date(a.next_run_at!).getTime() - new Date(b.next_run_at!).getTime());
  if (!list.length) return <Empty>예정된 점검이 없습니다</Empty>;
  return (
    <div className="dz-list scroll">
      {list.map((s) => (
        <button key={s.schedule_id} className="dz-item" onClick={() => open({ kind: 'schedule', id: s.schedule_id })}>
          <span className="dz-time">{fmtTime(s.next_run_at)}</span>
          <span className="grow">
            <b>{s.name}</b>
            <span className="line dim">{s.points ?? '-'}{s.last_outcome ? ` · 지난 회차 ${LAST[s.last_outcome] ?? s.last_outcome}` : ''}</span>
          </span>
          <Pill>{KIND[s.kind] ?? s.kind}</Pill>
        </button>
      ))}
    </div>
  );
}

// ------------------------------------------------------------------ 등록
export const PANELS: Record<string, PanelDef> = {
  kpi: { title: '요약', icon: 'gauge', Body: Kpi, bare: true },
  robots: { title: '로봇', icon: 'cpu', Body: Robots, extra: (d) => <span className="dim">{d.robots.length}대</span> },
  map: { title: '현장 지도', icon: 'map.fill', Body: MapPanel, extra: (d) => <RobotTabs d={d} /> },
  camera: { title: '로봇 카메라', icon: 'video', Body: Camera, extra: (d) => <RobotTabs d={d} /> },
  alerts: { title: '경고', icon: 'bell.fill', Body: Alerts, extra: (d) => (d.alerts.length ? <Pill tone={d.alerts.some((a) => a.severity === 'CRITICAL') ? 'red' : 'orange'}>{d.alerts.length}</Pill> : null) },
  events: { title: '최근 이벤트', icon: 'list.bullet', Body: Events },
  queue: { title: '진행 · 대기 작업', icon: 'checklist', Body: Queue, extra: (d) => <span className="dim">진행 {d.activeTasks.length} · 대기 {d.backlog?.total ?? 0}</span> },
  points: { title: '점검 지점 현황', icon: 'mappin.and.ellipse', Body: Points },
  incidents: { title: '화재 사건', icon: 'flame.fill', Body: Incidents, extra: (d) => (d.incidents.length ? <Pill tone="red">{d.incidents.length}</Pill> : <span className="dim">없음</span>) },
  schedules: { title: '예정된 점검', icon: 'calendar.badge.clock', Body: Schedules },
};
