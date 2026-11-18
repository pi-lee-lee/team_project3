import { useEffect, useMemo, useState } from 'react';
import type { AlertRow } from './api/types';
import { ago, fmtTime, useApi, usePoll } from './util';
import { Icon } from './Icon';
import './emergency.css';

/**
 * 비상 경고 팝업. 등급이 비상(EMERGENCY, 붉은색)인 열린 경고가 있으면 화면 전체를 덮는 큰 창을 띄운다.
 * 경고(주황) · 판독 불가는 띄우지 않는다.
 *
 * - 사용자가 "확인"을 눌러야 닫힌다(바깥을 눌러도, Esc 를 눌러도 닫히지 않는다).
 * - canAck(사용자 역할): "확인" = 서버에 확인(ACKED)을 남긴다. 누가 확인했는지 기록되고 다른 화면에서도 닫힌다.
 *   서버가 다시 여는 경우(등급이 비상으로 올라감, 승인 대기 재알림)에는 다시 뜬다.
 * - canAck 가 아니면(조회 전용인 대시보드 계정): 이 화면에서만 닫는다. 같은 경고가 갱신되면 다시 뜬다.
 */
export function EmergencyDialog({ canAck, onOpen }: {
  /** 서버에 확인을 남길 수 있는 역할인가 */
  canAck: boolean;
  /** "상세 보기": 경고가 가리키는 대상(사건 · 관측)을 연다 */
  onOpen: (a: AlertRow) => void;
}) {
  const api = useApi();
  const q = usePoll(() => api.alerts('OPEN'), 3000);
  // 이 화면에서 닫은 것: "경고 ID:갱신 시각". 갱신되면 열쇠가 달라져 다시 뜬다
  const [closed, setClosed] = useState<Set<string>>(() => {
    try { return new Set(JSON.parse(sessionStorage.getItem('emergency.closed') ?? '[]')); } catch { return new Set(); }
  });
  const key = (a: AlertRow) => `${a.alert_id}:${a.updated_at}`;
  const list = useMemo(
    () => (q.data ?? []).filter((a) => a.grade === 'EMERGENCY' && a.state === 'OPEN' && !closed.has(key(a))),
    [q.data, closed],
  );
  const [busy, setBusy] = useState(false);

  // 팝업이 떠 있는 동안 탭 제목으로도 알린다(다른 탭을 보고 있을 때)
  useEffect(() => {
    if (!list.length) return;
    const title = document.title;
    let on = false;
    const h = setInterval(() => { on = !on; document.title = on ? `🔴 비상 ${list.length}건` : title; }, 900);
    return () => { clearInterval(h); document.title = title; };
  }, [list.length]);

  if (!list.length) return null;

  const closeLocal = (items: AlertRow[]) => {
    const next = new Set(closed);
    items.forEach((a) => next.add(key(a)));
    setClosed(next);
    try { sessionStorage.setItem('emergency.closed', JSON.stringify([...next].slice(-200))); } catch { /* 저장 못 해도 동작에는 지장 없다 */ }
  };
  const confirm = async (items: AlertRow[]) => {
    setBusy(true);
    try {
      if (canAck) await Promise.all(items.map((a) => api.ackAlert(a.alert_id, '비상 팝업에서 확인').catch(() => null)));
      closeLocal(items);
      q.reload();
    } finally {
      setBusy(false);
    }
  };
  const first = list[0];
  const rest = list.slice(1);
  return (
    <div className="emg-scrim" role="alertdialog" aria-modal="true" aria-labelledby="emg-title">
      <div className="emg-box">
        <div className="emg-head">
          <span className="emg-icon"><Icon name={first.type === 'FIRE_DETECTED' ? 'flame.fill' : 'exclamationmark.octagon.fill'} size={72} /></span>
          <div>
            <div className="emg-label">비상</div>
            <div className="emg-count">{list.length > 1 ? `${list.length}건이 확인을 기다립니다` : '즉시 확인이 필요합니다'}</div>
          </div>
        </div>
        <h1 id="emg-title">{first.title}</h1>
        {first.detail && <p className="emg-detail">{first.detail}</p>}
        <p className="emg-meta">
          {first.point_code ? `${first.point_code} ${first.point_name ?? ''} · ` : ''}
          {first.x != null && first.y != null ? `위치 (${first.x.toFixed(1)}, ${first.y.toFixed(1)}) · ` : ''}
          {fmtTime(first.opened_at)} 발생 ({ago(first.opened_at)})
        </p>
        <div className="emg-actions">
          <button className="emg-open" onClick={() => { closeLocal([first]); onOpen(first); }}>
            <Icon name="doc.text.magnifyingglass" size={26} />상세 보기
          </button>
          <button className="emg-ok" disabled={busy} onClick={() => confirm([first])} autoFocus>
            <Icon name="checkmark" size={26} />확인
          </button>
        </div>
        {rest.length > 0 && (
          <div className="emg-rest">
            <div className="emg-rest-head">
              <b>다른 비상 {rest.length}건</b>
              <button disabled={busy} onClick={() => confirm(list)}>모두 확인</button>
            </div>
            {rest.slice(0, 4).map((a) => (
              <button key={a.alert_id} className="emg-row" onClick={() => { closeLocal([a]); onOpen(a); }}>
                <Icon name={a.type === 'FIRE_DETECTED' ? 'flame.fill' : 'exclamationmark.octagon.fill'} size={22} />
                <span>{a.title}</span><span className="emg-when">{ago(a.opened_at)}</span>
              </button>
            ))}
            {rest.length > 4 && <div className="emg-more">외 {rest.length - 4}건 — "경고" 화면에서 봅니다</div>}
          </div>
        )}
        {!canAck && <p className="emg-note">이 계정은 조회 전용입니다. 여기서 닫아도 경고는 열린 채로 남습니다.</p>}
      </div>
    </div>
  );
}
