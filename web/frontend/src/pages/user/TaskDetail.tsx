import { useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import type { Observation, TaskEvent } from '../../api/types';
import { Badge, ErrorBox, ReasonBadge, TERMINAL, fmtTime, useAction, useApi, usePoll } from '../../util';

const EVENT_LABEL: Record<string, string> = {
  REQUESTED: '요청됨', ACCEPTED: '로봇 접수', DISPATCH_FAILED: '로봇 전달 실패', DISPATCH_UNKNOWN: '전달 결과 불명',
  PREFLIGHT_OK: '출발 전 검사 통과', PREFLIGHT_FAILED: '출발 전 검사 실패', STARTED: '출발', MOVING: '이동 시작',
  ARRIVED: '도착', ARRIVAL_FAILED: '도착 실패', ARRIVAL_BLOCKED: '진입 불가 (경로 없음)', OBSERVATION_SAVED: '촬영 저장', OBSERVATION_UNABLE: '확인 불가',
  COMPLETED: '완료', CANCEL_REQUESTED: '취소 요청', CANCELLED: '취소됨', CANCEL_NOT_APPLIED: '취소 미적용',
  CANCEL_SEND_FAILED: '취소 전달 실패', MISSION_FAILED: '실패', MISSION_INTERRUPTED: '중단(상태 불명)',
  EMERGENCY_STOP: '비상 정지', REVIEWED: '사람 판정',
};
const SOURCE = { USER: '사용자', ROBOT: '로봇', SYSTEM: '시스템' };
const RESULT: Record<string, [string, string]> = { NORMAL: ['정상', 'ok'], ABNORMAL: ['이상', 'bad'], UNABLE: ['확인 불가', 'warn-t'] };

function eventText(e: TaskEvent) {
  const d = e.detail || {};
  const parts: string[] = [];
  if (d.code || d.pointCode) parts.push(String(d.code ?? d.pointCode));
  if (Array.isArray(d.points)) parts.push((d.points as string[]).join(', '));
  if (d.result) parts.push(RESULT[String(d.result)]?.[0] ?? String(d.result));
  if (d.reason) parts.push(String(d.reason));
  if (d.recoveries) parts.push(`복구 동작 ${d.recoveries}회`);
  if (Array.isArray(d.reasons)) parts.push((d.reasons as string[]).join(', '));
  if (d.robotState) parts.push(`로봇 상태 ${d.robotState}`);
  if (d.captured !== undefined) parts.push(`촬영 ${d.captured} · 확인 불가 ${d.unable}`);
  return parts.join(' · ');
}

/** U4 작업 상세 (+ U4-1 관측 판정 입력) */
export default function TaskDetail() {
  const { id } = useParams();
  const api = useApi();
  const navigate = useNavigate();
  const task = usePoll(() => api.task(Number(id)), 2000, [id]);
  const act = useAction();
  const t = task.data;
  if (!t) return <section><ErrorBox msg={task.error} /></section>;
  const done = TERMINAL.includes(t.status);

  return (
    <section>
      <div className="row between">
        <h2>작업 #{t.task_id} · {t.robot_code} <Badge status={t.status} /></h2>
        <button className="warn" disabled={done || t.status === 'CANCEL_REQUESTED' || act.busy}
          onClick={() => act.run(async () => task.setData(await api.cancelTask(t.task_id)))}>취소 요청</button>
      </div>
      <div className="muted">
        요청자 {t.requester_login} · {fmtTime(t.created_at)} {t.note && `· ${t.note}`}
        {t.recheck_of && <> · 재점검 (관측 #{t.recheck_of})</>}
        {t.status_reason && <> · <span className="bad">{t.status_reason}</span></>}
      </div>
      <ErrorBox msg={act.error || task.error} />
      <div className="detail">
        <div className="card timeline">
          <h3>진행 기록</h3>
          {t.events.map((e) => (
            <div key={e.event_id} className={`ev src-${e.source}`}>
              <span className="dot" />
              <span className="time">{fmtTime(e.occurred_at, false)}</span>
              <b>{EVENT_LABEL[e.type] ?? e.type}</b>
              <span className="muted small"> {SOURCE[e.source]}{e.actor ? ` ${e.actor}` : ''}</span>
              <div className="small">{eventText(e)}</div>
            </div>
          ))}
        </div>
        <div className="obs-list">
          {t.observations.length === 0 && <div className="card muted">아직 관측이 없습니다.</div>}
          {t.observations.map((o) => (
            <ObservationCard key={o.observation_id} o={o} onChanged={task.reload}
              onRecheck={(newId) => navigate(`/app/tasks/${newId}`)} />
          ))}
        </div>
      </div>
    </section>
  );
}

function ObservationCard({ o, onChanged, onRecheck }: { o: Observation; onChanged: () => void; onRecheck: (id: number) => void }) {
  const api = useApi();
  const [result, setResult] = useState<string | null>(null);
  const [comment, setComment] = useState('');
  const act = useAction();
  return (
    <div className="card obs">
      <div className="photo">
        {o.has_image ? <a href={api.imageUrl(o.observation_id)} target="_blank" rel="noreferrer"><img src={api.imageUrl(o.observation_id)} alt={o.point_code} /></a>
          : <div className="novideo">촬영 없음</div>}
      </div>
      <div className="info">
        <div><b>{o.seq}. {o.point_code} {o.point_name}</b> <span className="muted small">{fmtTime(o.captured_at)}</span></div>
        {o.status === 'UNABLE' && <div className="warn-t"><ReasonBadge code={o.reason_code} /> 확인 불가: {o.reason}</div>}
        {o.status === 'CAPTURED' && (
          <div className="small">
            품질: {o.verdict ? <>밝기 {o.brightness?.toFixed(0)} · 선명도 {o.sharpness?.toFixed(0)} → {' '}
              {o.verdict === 'OK' ? <span className="ok">양호</span> : <span className="warn-t">재촬영 후보 ({o.analysis_reasons})</span>}</>
              : <span className="muted">분석 중…</span>}
          </div>
        )}
        <div className="small">
          현재 판정: {o.review_result ? <span className={RESULT[o.review_result][1]}>{RESULT[o.review_result][0]}</span> : <span className="muted">없음</span>}
          {o.review_comment && <span className="muted"> · {o.review_comment}</span>}
        </div>
        <div className="row">
          {Object.entries(RESULT).map(([k, [label]]) => (
            <button key={k} className={`r-${k} ${result === k ? 'on' : ''}`} onClick={() => setResult(k)}>{label}</button>
          ))}
        </div>
        {result && (
          <div className="row">
            <input className="grow" placeholder={result === 'UNABLE' ? '확인 불가 사유 (필수)' : '의견 (선택)'} value={comment} onChange={(e) => setComment(e.target.value)} />
            <button className="primary" disabled={act.busy || (result === 'UNABLE' && !comment.trim())}
              onClick={() => act.run(async () => { await api.review(o.observation_id, result, comment); setResult(null); setComment(''); onChanged(); })}>판정 저장</button>
          </div>
        )}
        <ErrorBox msg={act.error} />
        {o.reviews && o.reviews.length > 0 && (
          <div className="small muted">판정 이력: {o.reviews.map((r) => `${r.reviewer_login} ${RESULT[r.result][0]} (${fmtTime(r.reviewed_at, false)})`).join(' → ')}</div>
        )}
        <div className="row between">
          <button className="link" disabled={act.busy} onClick={() => act.run(async () => onRecheck((await api.recheck(o.observation_id)).task_id))}>↺ 재점검 요청</button>
          <Link className="small" to={`/app/history?point=${o.point_id}`}>지점 이력 →</Link>
        </div>
      </div>
    </div>
  );
}
