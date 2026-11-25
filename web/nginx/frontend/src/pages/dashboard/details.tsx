// 상세 창: 대시보드의 항목을 누르면 화면 위에 뜬다(조회 전용).
// Ref.kind 하나 = 상세 화면 하나이고, 맨 아래 DETAILS 표에 등록한다. 상세 안에서 다른 상세로 넘어갈 수 있다(뒤로 가기 지원).
import type { ReactNode } from 'react';
import type { Observation } from '../../api/types';
import { REASON_LABEL, ago, fmtTime, useApi, usePoll } from '../../util';
import { Icon } from '../../Icon';
import { EVENT_LABEL, RESULT, SOURCE, eventText } from '../user/inspectionText';
import {
  CHECKER_LABEL, GRADE, INCIDENT_EVENT, INCIDENT_STATE, IncidentSteps, LAUNCH_MODE, PhotoOverlay, checkText, gradeText,
  incidentEventText, resultBoxes, valueText,
} from '../user/scenarioText';
import { fmtDur, type DashData, type Ref } from './data';
import { Dot, Pill, TaskPill, robotActivity } from './panels';

interface DetailProps<K extends Ref['kind']> { r: Extract<Ref, { kind: K }>; d: DashData; open: (ref: Ref) => void }
interface DetailDef<K extends Ref['kind']> { title: (r: Extract<Ref, { kind: K }>) => string; icon: string; Body: (p: DetailProps<K>) => ReactNode }

const Loading = ({ error }: { error: string | null }) => <div className="dz-empty">{error ?? '불러오는 중…'}</div>;
const KV = ({ k, children }: { k: string; children: ReactNode }) => <div className="dz-kv"><span>{k}</span><div>{children ?? '-'}</div></div>;
const Section = ({ title, children }: { title: string; children: ReactNode }) => <section className="dz-sec"><h4>{title}</h4>{children}</section>;

const REVIEW_TONE: Record<string, string> = { NORMAL: 'green', ABNORMAL: 'orange', UNABLE: 'orange' };   // 빨강은 비상(화재)만
function ObsPills({ o }: { o: Observation }) {
  return (
    <>
      {o.status === 'UNABLE' ? <Pill tone="orange">확인 불가</Pill>
        : o.verdict === 'OK' ? <Pill tone="green">품질 양호</Pill>
          : o.verdict === 'RETAKE' ? <Pill tone="orange">재촬영 후보</Pill> : <Pill>분석 중</Pill>}
      {o.review_result ? <Pill tone={REVIEW_TONE[o.review_result]}>판정 {RESULT[o.review_result]?.[0]}</Pill> : <Pill>판정 없음</Pill>}
    </>
  );
}

/** 관측 목록(사진 카드). 누르면 관측 상세. */
function ObsGrid({ list, open, showPoint = true }: { list: Observation[]; open: (ref: Ref) => void; showPoint?: boolean }) {
  const api = useApi();
  if (!list.length) return <div className="dz-empty">관측이 없습니다</div>;
  return (
    <div className="dz-obs-grid">
      {list.map((o) => (
        <button key={o.observation_id} className="dz-obs" onClick={() => open({ kind: 'observation', id: o.observation_id, taskId: o.task_id })}>
          {o.has_image ? <img src={api.imageUrl(o.observation_id)} alt="" loading="lazy" />
            : <span className="noimg"><Icon name="nosign" size={30} />{o.reason_code ? REASON_LABEL[o.reason_code] ?? o.reason_code : '사진 없음'}</span>}
          <span className="cap">
            <b>{showPoint ? `${o.point_code} ${o.point_name}` : fmtTime(o.captured_at)}</b>
            <span className="dim">{showPoint ? fmtTime(o.captured_at) : `작업 #${o.task_id}`}</span>
            <span className="pills"><ObsPills o={o} /></span>
          </span>
        </button>
      ))}
    </div>
  );
}

// ------------------------------------------------------------------ 작업
function TaskDetail({ r, open }: DetailProps<'task'>) {
  const api = useApi();
  const q = usePoll(() => api.task(r.id), 3000, [r.id]);
  const t = q.data;
  if (!t) return <Loading error={q.error} />;
  return (
    <div className="dz-cols">
      <div>
        <Section title="작업">
          <KV k="상태"><TaskPill status={t.status} /> {t.status_reason && <span className="dim">{t.status_reason}</span>}</KV>
          <KV k="로봇">{t.robot_code}</KV>
          <KV k="경로">{t.points.map((p) => `${p.code} ${p.name}`).join(' → ')}</KV>
          <KV k="요청">{t.requester_login} · {fmtTime(t.created_at)} ({ago(t.created_at)})</KV>
          {t.schedule_id && <KV k="점검 계획"><button className="dz-link" onClick={() => open({ kind: 'schedule', id: t.schedule_id! })}>계획 #{t.schedule_id} 보기</button></KV>}
          {t.note && <KV k="메모">{t.note}</KV>}
        </Section>
        <Section title={`관측 ${t.observations.length}건`}><ObsGrid list={t.observations} open={open} /></Section>
      </div>
      <Section title="진행 기록">
        <div className="dz-timeline">
          {t.events.map((e) => (
            <div key={e.event_id}>
              <span className="mono dim">{fmtTime(e.occurred_at, false)}</span>
              <Dot tone="blue" />
              <span><b>{EVENT_LABEL[e.type] ?? e.type}</b> <span className="dim">{eventText(e)}</span></span>
              <span className="dim">{SOURCE[e.source]}{e.actor ? ` · ${e.actor}` : ''}</span>
            </div>
          ))}
        </div>
      </Section>
    </div>
  );
}

// ------------------------------------------------------------------ 관측
function ObservationDetail({ r, open }: DetailProps<'observation'>) {
  const api = useApi();
  const q = usePoll(() => api.task(r.taskId), 5000, [r.taskId]);
  const res = usePoll(() => api.observationResults(r.id).catch(() => []), 5000, [r.id]);
  const rr = res.data ?? [];
  const o = q.data?.observations.find((x) => x.observation_id === r.id);
  if (!q.data) return <Loading error={q.error} />;
  if (!o) return <div className="dz-empty">관측을 찾을 수 없습니다</div>;
  return (
    <div className="dz-cols photo">
      <div className="dz-photo">
        {o.has_image
          ? <PhotoOverlay className="dz-ov" src={api.imageUrl(o.observation_id)} alt={`${o.point_code} 사진`}
            boxes={resultBoxes(rr, Object.fromEntries(rr.map((x) => [x.ruleId, x.rule?.regions?.INSPECTOR])))} />
          : <span className="noimg"><Icon name="nosign" size={48} />사진 없음</span>}
      </div>
      <div>
        {rr.length > 0 && (
          <Section title="규칙 판독 (초록 = 찾은 자리, 파란 점선 = 기대 영역)">
            {rr.map((x) => (
              <KV key={x.ruleId} k={x.rule?.name ?? `규칙 #${x.ruleId}`}>
                <Pill tone={GRADE[x.grade]?.[1]}>{gradeText(x.grade)}</Pill>{' '}
                <span className="dim">{CHECKER_LABEL[x.rule?.kind ?? ''] ?? ''} · 읽은 값 {valueText(x.value, x.unit)}{x.reason ? ` · ${x.reason}` : ''}</span>
              </KV>
            ))}
          </Section>
        )}
        <Section title="관측">
          <KV k="지점"><button className="dz-link" onClick={() => open({ kind: 'point', id: o.point_id })}>{o.point_code} {o.point_name}</button></KV>
          <KV k="촬영">{fmtTime(o.captured_at)} ({ago(o.captured_at)})</KV>
          <KV k="작업"><button className="dz-link" onClick={() => open({ kind: 'task', id: o.task_id })}>작업 #{o.task_id}</button> · {o.requester_login}</KV>
          <KV k="상태"><span className="pills"><ObsPills o={o} /></span></KV>
          {o.status === 'UNABLE' && <KV k="사유">{o.reason_code ? `${REASON_LABEL[o.reason_code] ?? o.reason_code} · ` : ''}{o.reason}</KV>}
        </Section>
        <Section title="사진 품질 분석">
          {o.verdict ? <>
            <KV k="밝기">{o.brightness?.toFixed(1)}</KV>
            <KV k="선명도">{o.sharpness?.toFixed(1)}</KV>
            {o.analysis_reasons && <KV k="사유">{o.analysis_reasons}</KV>}
          </> : <div className="dim">{o.status === 'UNABLE' ? '사진이 없어 분석하지 않았습니다' : '분석 중…'}</div>}
        </Section>
        <Section title="사람 판정">
          {o.review_result ? <>
            <KV k="결과"><Pill tone={REVIEW_TONE[o.review_result]}>{RESULT[o.review_result]?.[0]}</Pill> {o.reviewer_login}</KV>
            {o.review_comment && <KV k="의견">{o.review_comment}</KV>}
          </> : <div className="dim">아직 판정하지 않았습니다 (판정은 사용자 화면의 작업 상세에서 합니다)</div>}
        </Section>
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ 로봇
const CAP: Record<string, [string, string]> = {
  VERIFIED: ['정상', 'green'], SUPPORTED: ['토픽 있음', 'gray'], STALE: ['멈춤', 'orange'], UNSUPPORTED: ['미지원', 'red'], UNKNOWN: ['알 수 없음', 'gray'],
};
function RobotDetail({ r, d, open }: DetailProps<'robot'>) {
  const api = useApi();
  const s = d.robots.find((x) => x.robotId === r.id);
  if (!s) return <div className="dz-empty">로봇을 찾을 수 없습니다</div>;
  const [text, tone] = robotActivity(s);
  const back = d.backlog?.robots.find((b) => b.robotId === r.id);
  return (
    <div className="dz-cols photo">
      <div className="dz-photo">
        {s.connected ? <img src={api.streamUrl(s.robotId)} alt={`${s.code} 카메라`} /> : <span className="noimg"><Icon name="wifi.slash" size={48} />연결 끊김</span>}
      </div>
      <div>
        <Section title="상태">
          <KV k="현재"><Pill tone={tone}>{text}</Pill></KV>
          <KV k="연결">{s.adapterType === 'MOCK' ? '모의 로봇' : 'rosbridge'} · {s.connected ? '연결됨' : '끊김'}</KV>
          <KV k="배터리">{s.batteryPercent != null ? `${Math.round(s.batteryPercent)}%` : '-'}</KV>
          <KV k="위치">{s.pose ? `x ${s.pose.x.toFixed(2)} · y ${s.pose.y.toFixed(2)} · θ ${(s.pose.yaw * 180 / Math.PI).toFixed(0)}°` : '위치 추정 없음'}</KV>
          <KV k="앞 장애물">{s.frontObstacleM != null ? `${s.frontObstacleM.toFixed(2)} m` : '-'}</KV>
          <KV k="제어권">{s.control ? `${s.control.kind === 'MISSION' ? '점검 임무' : '사용자'} · ${s.control.login} · ${ago(s.control.since)}` : '없음'}</KV>
          {s.mission && <KV k="임무"><button className="dz-link" onClick={() => open({ kind: 'task', id: s.mission!.missionId })}>작업 #{s.mission.missionId} 보기</button></KV>}
          {back && back.count > 0 && <KV k="대기 예약">{back.count}건 · 최대 {fmtDur(back.maxDelaySec)} 지연</KV>}
          <KV k="투척 기구">{s.launcher
            ? <><Pill tone={s.launcher.ready ? 'green' : 'red'}>{s.launcher.ready ? '준비됨' : '준비 안 됨'}</Pill>{' '}
              <span className="dim">{s.launcher.remaining >= 0 ? `남은 수 ${s.launcher.remaining}` : '남은 수 모름'}{s.launcher.fault ? ` · ${s.launcher.fault}` : ''}</span></>
            : <span className="dim">없음 또는 응답 없음</span>}</KV>
        </Section>
        {s.capabilities && (
          <Section title="제공 기능">
            <div className="pills">{Object.entries(s.capabilities).map(([k, v]) => <Pill key={k} tone={CAP[v]?.[1]}>{k} · {CAP[v]?.[0] ?? v}</Pill>)}</div>
          </Section>
        )}
        {s.ageMs && (
          <Section title="토픽 수신 (마지막으로 받은 뒤 지난 시간)">
            <div className="pills">{Object.entries(s.ageMs).map(([k, v]) => <Pill key={k} tone={v == null ? 'red' : v > 5000 ? 'orange' : 'green'}>{k} · {v == null ? '없음' : `${(v / 1000).toFixed(1)}초`}</Pill>)}</div>
          </Section>
        )}
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ 사건(화재 대응)
function IncidentDetail({ r, d, open }: DetailProps<'incident'>) {
  const api = useApi();
  const q = usePoll(() => api.incident(r.id), 3000, [r.id]);
  const i = q.data;
  if (!i) return <Loading error={q.error} />;
  const robot = (id: number | null) => (id == null ? '-' : d.robots.find((x) => x.robotId === id)?.code ?? `로봇 #${id}`);
  const [label, tone] = INCIDENT_STATE[i.state] ?? [i.state, 'gray'];
  const photos: ['detection' | 'recheck' | 'after', string][] = [['detection', '감지 사진'], ['recheck', '도착 후'], ['after', '투척 후']];
  return (
    <>
      <IncidentSteps incident={i} className="dz-steps" />
      <div className="dz-cols">
        <div>
          <Section title="사건">
            <KV k="상태"><Pill tone={tone}>{label}</Pill> {i.closeReason && <span className="dim">{i.closeReason}</span>}</KV>
            <KV k="투척 모드">{LAUNCH_MODE[i.launchMode]}</KV>
            <KV k="위치">x {i.x.toFixed(2)} · y {i.y.toFixed(2)}</KV>
            <KV k="감지">{robot(i.detectedBy)} · {fmtTime(i.createdAt)} ({ago(i.createdAt)})</KV>
            <KV k="대응 로봇">
              {i.responderId != null ? <button className="dz-link" onClick={() => open({ kind: 'robot', id: i.responderId! })}>{robot(i.responderId)}</button> : '-'}
            </KV>
            <KV k="출동 작업">{i.taskId ? <button className="dz-link" onClick={() => open({ kind: 'task', id: i.taskId! })}>작업 #{i.taskId} 보기</button> : '아직 없음'}</KV>
            <KV k="도착 후 재판독">{checkText(i.recheck)}</KV>
            <KV k="투척 후 판독">{checkText(i.afterCheck)}</KV>
            {i.approvedBy && <KV k="승인">{i.approvedBy} · {fmtTime(i.approvedAt)}</KV>}
          </Section>
          <Section title="사진">
            <div className="dz-obs-grid three">
              {photos.map(([kind, name]) => (
                <div key={kind} className="dz-obs static">
                  {i.images[kind] ? <img src={api.incidentImageUrl(i.incidentId, kind, String(i.updatedAt))} alt={name} />
                    : <span className="noimg"><Icon name="photo" size={28} />없음</span>}
                  <span className="cap"><b>{name}</b></span>
                </div>
              ))}
            </div>
          </Section>
        </div>
        <Section title="사건 기록">
          <div className="dz-timeline">
            {(i.events ?? []).map((e) => (
              <div key={e.event_id}>
                <span className="mono dim">{fmtTime(e.occurred_at, false)}</span>
                <Dot tone={e.source === 'USER' ? 'purple' : e.source === 'ROBOT' ? 'green' : 'blue'} />
                <span><b>{INCIDENT_EVENT[e.type] ?? e.type}</b> <span className="dim">{incidentEventText(e)}</span></span>
                <span className="dim">{SOURCE[e.source]}{e.actor ? ` · ${e.actor}` : ''}</span>
              </div>
            ))}
          </div>
        </Section>
      </div>
      {i.state === 'AWAITING_APPROVAL' && <div className="dz-note">투척 승인은 사용자 화면의 "사건"에서 합니다(이 화면은 조회 전용).</div>}
    </>
  );
}

// ------------------------------------------------------------------ 점검 계획(예약)
const OUTCOME: Record<string, [string, string]> = {
  CREATED: ['실행', 'green'], SKIPPED_BUSY: ['건너뜀(사용 중)', 'orange'], SKIPPED_OFFLINE: ['건너뜀(연결 끊김)', 'orange'],
  MISSED: ['놓침', 'orange'], FAILED: ['실패', 'red'], CANCELLED: ['취소', 'gray'],
};
const KIND: Record<string, string> = { MANUAL: '수동 실행', ONCE: '한 번', INTERVAL: '일정 간격', DAILY: '매일', WEEKLY: '매주' };
const DOW = ['', '월', '화', '수', '목', '금', '토', '일'];
function ScheduleDetail({ r, d, open }: DetailProps<'schedule'>) {
  const api = useApi();
  const q = usePoll(() => api.schedule(r.id), 5000, [r.id]);
  const s = q.data;
  if (!s) return <Loading error={q.error} />;
  const when = s.kind === 'ONCE' ? s.run_at_local?.replace('T', ' ')
    : s.kind === 'INTERVAL' ? `${s.interval_minutes}분마다${s.window_start ? ` (${s.window_start}~${s.window_end})` : ''}`
      : s.kind === 'DAILY' ? `매일 ${s.time_of_day}`
        : s.kind === 'WEEKLY' ? `${(s.days_of_week ?? []).map((n) => DOW[n]).join('·')} ${s.time_of_day}` : '실행 버튼으로만';
  const waiting = (d.backlog?.robots ?? []).flatMap((b) => b.queue).filter((x) => x.scheduleId === s.schedule_id);
  return (
    <div className="dz-cols">
      <Section title="계획">
        <KV k="상태"><Pill tone={s.enabled ? 'green' : 'gray'}>{s.enabled ? '사용 중' : '꺼짐'}</Pill></KV>
        <KV k="실행 방식">{KIND[s.kind]} · {when}</KV>
        <KV k="경로">{s.points}</KV>
        <KV k="로봇">{d.robots.find((x) => x.robotId === s.robot_id)?.code ?? `#${s.robot_id}`}</KV>
        <KV k="다음 실행">{s.next_run_at ? fmtTime(s.next_run_at) : '-'}</KV>
        <KV k="만든 사람">{s.creator_login}</KV>
        {s.note && <KV k="메모">{s.note}</KV>}
        {waiting.map((w) => <KV key={w.key} k="대기 중">예정 {fmtTime(w.plannedAt)} · {fmtDur(w.delaySec)} 지연{w.waitReason ? ` · ${w.waitReason}` : ''}</KV>)}
      </Section>
      <Section title="실행 이력">
        {!s.runs?.length ? <div className="dim">아직 실행한 적이 없습니다</div> : (
          <div className="dz-timeline">
            {s.runs.map((run) => (
              <div key={run.run_id}>
                <span className="mono dim">{fmtTime(run.planned_at)}</span>
                <Pill tone={OUTCOME[run.outcome]?.[1]}>{OUTCOME[run.outcome]?.[0] ?? run.outcome}</Pill>
                <span>{run.task_id ? <button className="dz-link" onClick={() => open({ kind: 'task', id: run.task_id! })}>작업 #{run.task_id}</button> : <span className="dim">{run.reason}</span>}</span>
                <span className="dim">{run.delay_sec ? `${fmtDur(run.delay_sec)} 지연` : ''}</span>
              </div>
            ))}
          </div>
        )}
      </Section>
    </div>
  );
}

// ------------------------------------------------------------------ 점검 지점
function PointDetail({ r, open }: DetailProps<'point'>) {
  const api = useApi();
  const q = usePoll(() => api.pointHistory(r.id), 5000, [r.id]);
  if (!q.data) return <Loading error={q.error} />;
  const { point: p, observations } = q.data;
  return (
    <>
      <Section title="지점">
        <div className="dz-kv-row">
          <KV k="이름">{p.code} {p.name}</KV>
          <KV k="위치">x {p.x} · y {p.y} · 방향 {p.yaw_deg}°</KV>
          {p.description && <KV k="설명">{p.description}</KV>}
        </div>
      </Section>
      <Section title={`점검 이력 (최근 ${observations.length}건)`}><ObsGrid list={observations} open={open} showPoint={false} /></Section>
    </>
  );
}

// ------------------------------------------------------------------ 작업 목록(요약 타일에서)
const GROUP: Record<string, string> = { active: '진행 중 작업', done: '완료한 작업', failed: '실패·취소한 작업' };
function TaskList({ r, open }: DetailProps<'tasks'>) {
  const api = useApi();
  const q = usePoll(() => api.tasks(r.group), 3000, [r.group]);
  if (!q.data) return <Loading error={q.error} />;
  if (!q.data.length) return <div className="dz-empty">해당하는 작업이 없습니다</div>;
  return (
    <div className="dz-list">
      {q.data.slice(0, 40).map((t) => (
        <button key={t.task_id} className="dz-item" onClick={() => open({ kind: 'task', id: t.task_id })}>
          <span className="grow">
            <b>작업 #{t.task_id}</b> <span className="dim">{t.robot_code} · {t.points}</span>
            <span className="line dim">{t.requester_login} · {fmtTime(t.created_at)} · 관측 {t.observations}건{t.status_reason ? ` · ${t.status_reason}` : ''}</span>
          </span>
          <TaskPill status={t.status} />
        </button>
      ))}
    </div>
  );
}

// ------------------------------------------------------------------ 시스템
function SystemDetail({ d }: DetailProps<'system'>) {
  if (!d.system) return <Loading error={null} />;
  return (
    <div className="dz-cols">
      <Section title="서비스">
        {d.system.services.map((s) => <KV key={s.name} k={s.name}><Pill tone={s.status === 'UP' ? 'green' : 'red'}>{s.status}</Pill></KV>)}
      </Section>
      <Section title="로봇 연결">
        {d.system.robots.map((x) => (
          <KV key={x.code} k={x.code}>
            <Pill tone={!x.enabled ? 'gray' : x.connected ? 'green' : 'red'}>{!x.enabled ? '사용 안 함' : x.connected ? '연결됨' : '끊김'}</Pill>
            {' '}<span className="dim">전송 대기 {x.outboxPending}건</span>
          </KV>
        ))}
      </Section>
    </div>
  );
}

// ------------------------------------------------------------------ 등록
type DetailTable = { [K in Ref['kind']]: DetailDef<K> };
export const DETAILS: DetailTable = {
  task: { title: (r) => `작업 #${r.id}`, icon: 'checklist', Body: TaskDetail },
  observation: { title: (r) => `관측 #${r.id}`, icon: 'photo', Body: ObservationDetail },
  robot: { title: () => '로봇 상세', icon: 'cpu', Body: RobotDetail },
  schedule: { title: (r) => `점검 계획 #${r.id}`, icon: 'calendar.badge.clock', Body: ScheduleDetail },
  point: { title: () => '점검 지점', icon: 'mappin.and.ellipse', Body: PointDetail },
  incident: { title: (r) => `화재 사건 #${r.id}`, icon: 'flame.fill', Body: IncidentDetail },
  tasks: { title: (r) => GROUP[r.group], icon: 'checklist', Body: TaskList },
  system: { title: () => '시스템 상태', icon: 'server.rack', Body: SystemDetail },
};
