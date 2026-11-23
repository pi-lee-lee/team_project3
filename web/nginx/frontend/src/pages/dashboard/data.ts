// 관제 대시보드가 쓰는 데이터를 한 곳에서 불러온다.
// 패널은 여기서 만든 DashData 만 읽는다 — 새 정보가 필요하면 이 파일에 폴링 한 줄을 더하고 DashData 에 싣는다.
import { useEffect, useMemo, useState } from 'react';
import type {
  Backlog, DashAlert, DashOverview, DashPoint, Incident, LaunchMode, MapInfo, MapView, RobotStatus, Schedule, SystemStatus, TaskRow,
} from '../../api/types';
import { REASON_LABEL, useApi, usePoll } from '../../util';

/** 상세 창을 여는 열쇠. 패널의 어느 항목이든 이 값 하나로 상세를 띄운다(details.tsx 의 DETAILS 표). */
export type Ref =
  | { kind: 'task'; id: number }
  | { kind: 'observation'; id: number; taskId: number }
  | { kind: 'robot'; id: number }
  | { kind: 'schedule'; id: number }
  | { kind: 'point'; id: number }
  | { kind: 'incident'; id: number }
  | { kind: 'tasks'; group: 'active' | 'done' | 'failed' }
  | { kind: 'system' };

/** 등급: CRITICAL = 비상(빨강), WARNING = 경고(주황). 경고가 없으면 정상. */
export type Severity = 'CRITICAL' | 'WARNING';
export interface Alert { key: string; severity: Severity; icon: string; title: string; detail: string; at: string | number | null; ref: Ref }

export interface DashData {
  overview: DashOverview | null;
  robots: RobotStatus[];
  activeTasks: TaskRow[];
  backlog: Backlog | null;
  schedules: Schedule[];
  system: SystemStatus | null;
  alerts: Alert[];
  /** 열린 사건(화재 대응)과 지금의 투척 모드 */
  incidents: Incident[];
  launchMode: LaunchMode | null;
  /** 지도·카메라에 보이는 로봇 */
  robotId: number | null;
  setRobotId: (id: number) => void;
  map: MapInfo | null;
  view: MapView | null;
  /** 서버 시계 - 기기 시계 (ms), 예약 기준 시간대 */
  clock: { offsetMs: number; zone: string } | null;
  /** 불러오기 실패 안내(서버에 닿지 않을 때) */
  error: string | null;
}

// 주기(ms). 관제 화면이라 짧게 잡되, 지도 위 위치만 더 자주 받는다.
const FAST = 3000, SLOW = 15000, POSE = 500;

export function useDashData(): DashData {
  const api = useApi();
  const overview = usePoll(() => api.dashboard(), FAST);
  const robots = usePoll(async () => {
    const list = await api.robots();
    // 상태(위치·배터리·토픽 나이)는 로봇마다 따로 받는다. 한 대가 실패해도 목록은 보인다.
    return Promise.all(list.map((r) => api.robotStatus(r.robotId).catch(() => r as RobotStatus)));
  }, FAST);
  const activeTasks = usePoll(() => api.tasks('active'), FAST);
  const backlog = usePoll(() => api.scheduleBacklog(), FAST);
  const schedules = usePoll(() => api.schedules(), SLOW);
  const system = usePoll(() => api.system(), 5000);

  const [robotId, setRobotId] = useState<number | null>(null);
  useEffect(() => {
    if (robotId === null && robots.data?.length) {
      setRobotId((robots.data.find((r) => r.enabled && r.connected) ?? robots.data[0]).robotId);
    }
  }, [robots.data, robotId]);
  const map = usePoll<MapInfo | null>(() => (robotId ? api.mapInfo(robotId).catch(() => null) : Promise.resolve(null)), 10000, [robotId]);
  const view = usePoll<MapView | null>(() => (robotId ? api.mapView(robotId).catch(() => null) : Promise.resolve(null)), POSE, [robotId]);

  const [clock, setClock] = useState<DashData['clock']>(null);
  useEffect(() => {
    const sync = async () => {
      try {
        const t0 = performance.now(), d0 = Date.now();
        const r = await api.serverTime();
        const rtt = performance.now() - t0;
        setClock({ offsetMs: r.epochMs + rtt / 2 - (d0 + rtt), zone: r.zone });
      } catch { /* 다음 주기에 다시 */ }
    };
    sync();
    const h = setInterval(sync, 10 * 60 * 1000);
    return () => clearInterval(h);
  }, [api]);

  const alerts = useMemo(
    () => buildAlerts(overview.data, robots.data ?? [], backlog.data, system.data),
    [overview.data, robots.data, backlog.data, system.data],
  );

  return {
    overview: overview.data, robots: robots.data ?? [], activeTasks: activeTasks.data ?? [], backlog: backlog.data,
    schedules: schedules.data?.schedules ?? [], system: system.data, alerts,
    incidents: overview.data?.incidents ?? [], launchMode: overview.data?.launchMode ?? null,
    robotId, setRobotId, map: map.data, view: view.data, clock,
    error: overview.error ?? robots.error,
  };
}

// ------------------------------------------------------------------ 경고
// 서버가 보낸 경고 종류 → [아이콘, 제목]. 새 종류(예: 소화기 미비치 EXTINGUISHER_MISSING, 화재 감지 FIRE_DETECTED)는 여기에 한 줄을 더한다.
const ALERT_TEXT: Record<string, [string, string]> = {
  OBS_ABNORMAL: ['exclamationmark.octagon.fill', '이상 판정'],
  OBS_UNABLE: ['nosign', '확인 불가'],
  OBS_RETAKE: ['photo', '재촬영 후보'],
  TASK_FAILED: ['xmark.circle.fill', '작업 실패'],
  TASK_INTERRUPTED: ['exclamationmark.triangle.fill', '작업 중단(상태 불명)'],
  // 경고 표에서 오는 것(확인 · 해제를 남긴다)
  RULE_VIOLATION: ['ruler', '규칙 위반'],
  EXIT_BLOCKED: ['door.left.hand.open', '비상구 앞 통로 막힘'],
  FIRE_DETECTED: ['flame.fill', '화재 감지'],
  HEAT_WARNING: ['flame.fill', '열원 감지'],
};

function fromServer(a: DashAlert): Alert {
  const [icon, label] = ALERT_TEXT[a.type] ?? ['exclamationmark.triangle.fill', a.type];
  const where = a.point_code ? `${a.point_code} ${a.point_name ?? ''}`.trim() : a.task_id ? `작업 #${a.task_id}` : '';
  const ref: Ref = a.ref_kind === 'incident' && a.ref_id ? { kind: 'incident', id: a.ref_id }
    : a.ref_kind === 'observation' && a.ref_id && a.task_id ? { kind: 'observation', id: a.ref_id, taskId: a.task_id }
      : a.ref_kind === 'robot' && a.ref_id ? { kind: 'robot', id: a.ref_id }
        : { kind: 'task', id: a.task_id ?? a.ref_id ?? 0 };
  return {
    key: a.alert_id ? `alert-${a.alert_id}` : `${a.type}-${a.ref_kind}-${a.ref_id}`, severity: a.severity, icon,
    // 경고 표에서 온 것은 제목이 이미 있다(지점 · 규칙 이름 등)
    title: a.title ? a.title : where ? `${where} · ${label}` : label,
    detail: a.title ? [a.detail, a.state === 'ACKED' ? '확인함' : ''].filter(Boolean).join(' · ')
      : a.detail ? (REASON_LABEL[a.detail] ?? a.detail) : a.task_id && a.point_code ? `작업 #${a.task_id}` : '',
    at: a.at, ref,
  };
}

/** 서버 경고 + 화면이 아는 상태(서비스 중지, 로봇 연결 끊김, 예약 지연)를 한 목록으로. 심각한 것 먼저, 그다음 최근 순. */
function buildAlerts(o: DashOverview | null, robots: RobotStatus[], backlog: Backlog | null, sys: SystemStatus | null): Alert[] {
  const out: Alert[] = [];
  sys?.services.filter((s) => s.status !== 'UP').forEach((s) => out.push({
    key: `svc-${s.name}`, severity: 'CRITICAL', icon: 'server.rack', title: `${s.name} 응답 없음`, detail: `상태 ${s.status}`, at: null, ref: { kind: 'system' },
  }));
  robots.filter((r) => r.enabled && !r.connected).forEach((r) => out.push({
    key: `robot-${r.robotId}`, severity: 'CRITICAL', icon: 'wifi.slash', title: `${r.code} 연결 끊김`, detail: r.name, at: null, ref: { kind: 'robot', id: r.robotId },
  }));
  backlog?.robots.filter((b) => b.count > 0).forEach((b) => out.push({
    key: `delay-${b.robotId}`, severity: 'WARNING', icon: 'hourglass',
    title: `${b.robotCode ?? `로봇 ${b.robotId}`} · 예약 ${b.count}건 대기`,
    detail: `최대 ${fmtDur(b.maxDelaySec)} 지연${b.waitReason ? ` · ${b.waitReason}` : ''}`, at: null,
    ref: b.queue[0] ? { kind: 'schedule', id: b.queue[0].scheduleId } : { kind: 'robot', id: b.robotId },
  }));
  o?.alerts.forEach((a) => out.push(fromServer(a)));
  const rank = (a: Alert) => (a.severity === 'CRITICAL' ? 0 : 1);
  const time = (a: Alert) => (a.at ? new Date(a.at).getTime() : Infinity);   // 시각이 없는 것은 "지금 상태"라 맨 앞
  return out.sort((a, b) => rank(a) - rank(b) || time(b) - time(a));
}

// ------------------------------------------------------------------ 표시 도우미
export function fmtDur(sec: number | null | undefined) {
  if (sec == null) return '-';
  if (sec < 60) return `${Math.round(sec)}초`;
  if (sec < 3600) return `${Math.floor(sec / 60)}분`;
  return `${Math.floor(sec / 3600)}시간 ${Math.floor((sec % 3600) / 60)}분`;
}

export type PointState = 'ok' | 'bad' | 'warn' | 'wait' | 'none';
/** 지점의 현재 상태: 가장 최근 관측과 그 판정으로 정한다. */
export function pointState(p: DashPoint): PointState {
  if (!p.observation_id) return 'none';
  // 사람 판정이 있으면 그것이 우선한다
  if (p.review_result === 'ABNORMAL') return 'bad';
  if (p.review_result === 'NORMAL') return 'ok';
  // 규칙 등급: 3 비상 · 2 경고 · 1 판독 불가 · 0 정상
  if (p.grade_rank === 3) return 'bad';
  if (p.grade_rank === 2 || p.grade_rank === 1) return 'warn';
  if (p.grade_rank === 0 && p.status === 'CAPTURED' && p.verdict !== 'RETAKE') return 'ok';
  if (p.status === 'UNABLE' || p.review_result === 'UNABLE' || p.verdict === 'RETAKE') return 'warn';
  return 'wait';
}
export const POINT_STATE_TEXT: Record<PointState, string> = {
  ok: '정상', bad: '비상 · 이상', warn: '경고 · 확인 필요', wait: '판정 대기', none: '기록 없음',
};
