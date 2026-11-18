import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Badge, fmtTime, useApi, usePoll } from '../../util';
import { Icon } from '../../Icon';
import { RouteChips } from '../../ui';

export function delayText(sec: number) {
  if (sec < 60) return `${sec}초 지연`;
  const m = Math.floor(sec / 60);
  return m < 60 ? `${m}분 지연` : `${Math.floor(m / 60)}시간 ${m % 60}분 지연`;
}

function elapsed(sec: number | null | undefined) {
  if (sec == null) return '';
  const m = Math.floor(sec / 60);
  return m < 1 ? `${sec}초째` : m < 60 ? `${m}분째` : `${Math.floor(m / 60)}시간 ${m % 60}분째`;
}

const SHOW = 10; // 로봇마다 대기열을 이만큼 보여 주고 나머지는 "외 N건"

/**
 * 예약 점검이 실행 버퍼에 밀려 있으면 사용자 화면 상단에 알린다(5초마다 확인).
 * 로봇마다 지금 하는 작업과, 그 뒤에 쌓인 예약 회차 전부(실행 순서·예정 시각·지연)를 보여 준다.
 */
export default function DelayBanner() {
  const api = useApi();
  const backlog = usePoll(() => api.scheduleBacklog(), 5000);
  const [folded, setFolded] = useState(() => {
    try { return localStorage.getItem('delayBanner.folded') === '1'; } catch { return false; }
  });
  const fold = (v: boolean) => {
    setFolded(v);
    try { localStorage.setItem('delayBanner.folded', v ? '1' : '0'); } catch { /* 저장 안 됨 */ }
  };

  const b = backlog.data;
  if (!b || b.total === 0) return null;
  const maxDelay = Math.max(...b.robots.map((r) => r.maxDelaySec));

  return (
    <div className="delay-banner" role="status">
      <div className="head">
        <Icon name="exclamationmark.triangle.fill" size={18} />
        밀린 점검 <span className="count">{b.total}</span>건
        <span className="muted small" style={{ fontWeight: 400 }}>
          · 최대 {delayText(maxDelay)} · 로봇이 지금 작업을 마치면 순서대로 이어서 실행합니다
        </span>
        <span className="tools">
          <Link to="/app/plans">점검 보기</Link>
          <button className="link" onClick={() => fold(!folded)}>{folded ? '펼치기' : '접기'}</button>
        </span>
      </div>
      {!folded && b.robots.map((r) => (
        <div className="robot" key={r.robotId}>
          <div className="line">
            <span className="tag">{r.robotCode ?? `로봇 #${r.robotId}`}</span>
            {r.current ? (
              <span>
                지금 <Link to={`/app/tasks/${r.current.taskId}`}>작업 #{r.current.taskId}</Link>{' '}
                {r.current.status && <Badge status={r.current.status} />}{' '}
                <RouteChips points={r.current.points} />
                {r.current.currentPoint && <> · 현재 <b>{r.current.currentPoint}</b> ({r.current.progress})</>}
                {r.current.requester && <span className="muted"> · 요청 {r.current.requester}</span>}
                {r.current.scheduleId && <span className="muted"> · 예약 작업</span>}
                {r.current.elapsedSec != null && <span className="muted"> · {elapsed(r.current.elapsedSec)}</span>}
              </span>
            ) : (
              <span className="muted">지금 작업 없음 — {r.waitReason ?? '로봇 상태 확인 중'}</span>
            )}
          </div>
          <div className="line">
            <span className="tag">대기 {r.count}건</span>
          </div>
          <ol>
            {r.queue.slice(0, SHOW).map((q) => (
              <li key={q.key}>
                <b>{q.name}</b> <RouteChips points={q.points} />
                {' '}· 예정 {fmtTime(q.plannedAt)} · <span className="late">{delayText(q.delaySec)}</span>
                {q.manualBy && <span className="muted"> · 지금 실행({q.manualBy})</span>}
              </li>
            ))}
            {r.queue.length > SHOW && <li className="muted">외 {r.queue.length - SHOW}건</li>}
          </ol>
        </div>
      ))}
    </div>
  );
}
