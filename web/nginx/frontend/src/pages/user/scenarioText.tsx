// 시나리오 화면(규칙 · 경고 · 사건)이 함께 쓰는 표시 문구와 작은 부품.
import type { CSSProperties, ReactNode } from 'react';
import type { Grade, Incident, IncidentCheck, IncidentEvent, IncidentState, LaunchMode, RuleResult } from '../../api/types';
import { Tag, type Tone } from '../../ui';

/** 등급: [이름, 꼬리표 색] */
export const GRADE: Record<Grade, [string, Tone]> = {
  NORMAL: ['정상', 'green'], WARNING: ['경고', 'orange'], EMERGENCY: ['비상', 'red'], UNKNOWN: ['판독 불가', 'gray'],
};
export const gradeText = (g: string | null | undefined) => (g ? GRADE[g as Grade]?.[0] ?? g : '-');

export function GradeTag({ grade }: { grade: string | null | undefined }) {
  if (!grade) return <Tag tone="gray">결과 없음</Tag>;
  const [label, tone] = GRADE[grade as Grade] ?? [grade, 'gray'];
  return <Tag tone={tone}>{label}</Tag>;
}

export const CHECKER_LABEL: Record<string, string> = {
  OBJECT: '물체 유무 · 위치', GAUGE: '계기판 바늘', LAMP: '표시등 색', THERMAL: '열화상', MARKER: '마커',
};

/** 읽은 값 표시: 숫자는 자릿수를 줄이고 단위를 붙인다. 이름 값은 알려진 것만 한국어로 */
const VALUE_LABEL: Record<string, string> = {
  IN_REGION: '제자리에 있음', OUT_OF_REGION: '영역 밖에 있음', MISSING: '없음', PRESENT: '있음', ABSENT: '없음(정상)',
  green: '초록', yellow: '노랑', red: '빨강', off: '꺼짐',
};
export function valueText(v: number | string | null | undefined, unit?: string | null) {
  if (v === null || v === undefined || v === '') return '-';
  if (typeof v === 'number') return `${Math.abs(v) >= 100 ? v.toFixed(0) : v.toFixed(2)}${unit ? ` ${unit}` : ''}`;
  return VALUE_LABEL[v] ?? v;
}

export const LAUNCH_MODE: Record<LaunchMode, string> = { APPROVAL: '사람 승인', AUTO: '자동 투척' };

/** 사건 상태: [이름, 색] */
export const INCIDENT_STATE: Record<IncidentState, [string, Tone]> = {
  DETECTED: ['감지됨', 'red'], DISPATCHED: ['출동 중', 'blue'], ARRIVED: ['도착 · 재판독 중', 'blue'],
  AWAITING_APPROVAL: ['투척 승인 대기', 'orange'], LAUNCHING: ['투척 중', 'purple'], MONITORING: ['투척함 · 현장 감시 중', 'red'], LAUNCHED: ['투척함 · 확인 필요', 'purple'],
  RESOLVED: ['조치 완료', 'green'], DISMISSED: ['오탐으로 닫음', 'gray'], FAILED: ['대응 실패', 'red'],
};
export const isOpenIncident = (s: IncidentState) => s !== 'RESOLVED' && s !== 'DISMISSED';

export function IncidentStateTag({ state }: { state: IncidentState }) {
  const [label, tone] = INCIDENT_STATE[state] ?? [state, 'gray'];
  return <Tag tone={tone}>{label}</Tag>;
}

/** 단계 표시: 감지 → 출동 → 도착 → 승인 대기 → 투척 → 종료 */
const STEPS: [string, IncidentState[]][] = [
  ['감지', ['DETECTED']], ['출동', ['DISPATCHED']], ['도착', ['ARRIVED']], ['승인 대기', ['AWAITING_APPROVAL']],
  ['투척 · 감시', ['LAUNCHING', 'LAUNCHED', 'MONITORING']], ['종료', ['RESOLVED', 'DISMISSED']],
];
/** 열원 확인(HEAT): 감지 → 출동 → 도착 · 확인 → 종료(투척 없음) */
const HEAT_STEPS: [string, IncidentState[]][] = [
  ['감지', ['DETECTED']], ['출동', ['DISPATCHED']], ['도착 · 확인', ['ARRIVED']], ['종료', ['RESOLVED', 'DISMISSED']],
];
/** 지금 단계 번호(0부터). 실패는 멈춘 자리를 사건 기록에서 찾기 어렵므로 -1 로 두고 따로 표시한다 */
export function incidentStep(i: Pick<Incident, 'state'> & { type?: string }) {
  return (i.type === 'HEAT' ? HEAT_STEPS : STEPS).findIndex(([, states]) => states.includes(i.state));
}
export function IncidentSteps({ incident, className = 'inc-steps' }: { incident: Pick<Incident, 'state' | 'launchMode'> & { type?: string }; className?: string }) {
  const cur = incidentStep(incident);
  const failed = incident.state === 'FAILED';
  const heat = incident.type === 'HEAT';
  return (
    <ol className={`${className} ${failed ? 'failed' : ''}`}>
      {(heat ? HEAT_STEPS : STEPS).map(([label], i) => (
        // 자동 투척 모드에서는 승인 대기를 건너뛸 수 있다
        <li key={label} className={`${cur > i || incident.state === 'RESOLVED' || incident.state === 'DISMISSED' ? 'done' : ''} ${cur === i ? 'now' : ''}`}>
          <i />{label}{!heat && i === 3 && incident.launchMode === 'AUTO' ? <small> (자동이면 생략)</small> : null}
        </li>
      ))}
    </ol>
  );
}

export const INCIDENT_EVENT: Record<string, string> = {
  DETECTED: '감지', DETECTION_REPEATED: '같은 자리 다시 감지', REOPENED: '닫은 뒤에도 감지 계속 · 다시 엶', REOPENED_AS: '새 사건으로 다시 열림', PREEMPTED: '점검 작업을 멈춤', DISPATCHED: '출동',
  ARRIVED: '투척 위치 도착', RECHECKED: '도착 후 재판독', APPROVAL_REQUESTED: '투척 승인 요청', APPROVAL_REMINDER: '승인 재알림',
  APPROVED: '투척 승인', LAUNCH_ORDERED: '투척 명령', LAUNCH_REJECTED: '투척 명령 거부됨', AIM_CORRECTED: '조준 보정(제자리 회전)', AIM_FAILED: '조준 보정 실패', LAUNCHED: '투척 완료', MONITORING: '열원이 남음 · 현장 감시 시작', MONITOR_CHECKED: '현장 감시 판독(등급 변화)', MONITOR_STOPPED: '현장 감시 끊김',
  AFTER_CHECKED: '투척 후 판독', ROBOT_RELEASED: '로봇 대기 해제', RESOLVED: '조치 완료', DISMISSED: '오탐으로 닫음', FAILED: '대응 실패',
  HEAT_CHECKED: '열원 앞에서 확인', ESCALATED: '화재로 커짐 · 화재 대응으로 넘김', PATROL_RESUMED: '순찰 이어서 시작', PATROL_RESUME_SKIPPED: '순찰 이어가기 안 함',
};
/** 사건 종류: FIRE(화재 · 투척) · HEAT(열원 확인 — 과열을 보고 그 앞에 가서 확인, 투척 없음) */
export const INCIDENT_TYPE: Record<string, string> = { FIRE: '화재 감지', HEAT: '열원 확인' };
export function incidentEventText(e: IncidentEvent) {
  const d = e.detail || {};
  const parts: string[] = [];
  if (d.grade) parts.push(gradeText(String(d.grade)));
  if (typeof d.value === 'number') parts.push(`열원 비율 ${(d.value * 100).toFixed(1)}%`);
  if (typeof d.bearingDeg === 'number') parts.push(`조준 ${d.bearingDeg}°${d.aimed === false ? ' (범위 밖)' : ''}`);
  if (d.robotCode) parts.push(String(d.robotCode));
  if (d.taskId) parts.push(`작업 #${d.taskId}`);
  if (d.commandId) parts.push(String(d.commandId));
  if (typeof d.launched === 'number') parts.push(`${d.launched}발`);
  if (d.reason) parts.push(String(d.reason));
  return parts.join(' · ');
}

/** 재판독 결과 한 줄 */
export function checkText(c: IncidentCheck | null | undefined) {
  if (!c || !c.grade) return '아직 없음';
  const parts = [gradeText(c.grade)];
  if (typeof c.value === 'number') parts.push(`열원 비율 ${(c.value * 100).toFixed(1)}%`);
  if (typeof c.bearingDeg === 'number') parts.push(`조준 ${c.bearingDeg}°${c.aimed ? '' : ' (범위 밖)'}`);
  if (c.reason) parts.push(c.reason);
  return parts.join(' · ');
}

/** 사진 위에 사각형을 겹쳐 그린다. 사각형은 사진 크기 대비 비율 [x0, y0, x1, y1] */
export interface Box { box: number[] | null | undefined; kind: 'found' | 'expected'; label?: string }
export function PhotoOverlay({ src, alt, boxes, className = '', children }: { src: string; alt: string; boxes: Box[]; className?: string; children?: ReactNode }) {
  return (
    <div className={`photo-overlay ${className}`}>
      <img src={src} alt={alt} />
      {boxes.filter((b) => Array.isArray(b.box) && b.box.length === 4).map((b, i) => {
        const [x0, y0, x1, y1] = b.box as number[];
        const st: CSSProperties = { left: `${x0 * 100}%`, top: `${y0 * 100}%`, width: `${(x1 - x0) * 100}%`, height: `${(y1 - y0) * 100}%` };
        return <span key={i} className={`ov-box ${b.kind}`} style={st}>{b.label && <b>{b.label}</b>}</span>;
      })}
      {children}
    </div>
  );
}

/** 판독 결과에서 겹쳐 그릴 사각형: 찾은 자리(초록)와 기대 영역(파란 점선) */
export function resultBoxes(results: RuleResult[], regions?: Record<number, number[] | undefined>): Box[] {
  const out: Box[] = [];
  results.forEach((r) => {
    const expected = regions?.[r.ruleId] ?? (r.evidence?.expectedRegion as number[] | undefined);
    if (expected) out.push({ box: expected, kind: 'expected' });
    if (r.located?.bbox) out.push({ box: r.located.bbox, kind: 'found', label: r.rule?.name });
  });
  return out;
}
