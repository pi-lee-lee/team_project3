import { useEffect, useState } from 'react';
import type { Incident } from './api/types';
import { ago, useAction, useApi, usePoll } from './util';
import { Icon } from './Icon';
import './emergency.css';

const GRADE_KO: Record<string, string> = { NORMAL: '정상', WARNING: '경고', EMERGENCY: '비상', UNKNOWN: '판독 불가' };
/** "나중에"로 닫은 뒤 다시 띄울 때까지(ms). 서버의 승인 재알림 간격(기본 30초)과 맞춘다 */
const SNOOZE_MS = 30_000;

/**
 * 투척 승인 팝업. 대응 로봇이 투척 위치에 도착해 승인을 기다리는 사건(AWAITING_APPROVAL)이 있으면 띄운다.
 * 비상 팝업(EmergencyDialog)보다 위에 뜬다 — 승인은 지금 사람이 해야 하는 일이기 때문이다.
 *
 * - 로봇의 실시간 카메라 화면과 도착 후 재판독 결과를 보여 주고, "투척 승인" 단추를 둔다.
 * - 승인은 사용자 역할과 대시보드 계정이 할 수 있다(게이트웨이 규칙). "오탐으로 닫기"는 canDismiss(사용자 역할)만.
 * - "나중에"는 이 화면에서만 잠깐 닫는다. 승인하지 않으면 SNOOZE_MS 뒤 다시 뜬다.
 */
export function LaunchDialog({ canDismiss, onOpen }: {
  canDismiss: boolean;
  /** "사건 상세": 사건 화면을 연다 */
  onOpen: (incidentId: number) => void;
}) {
  const api = useApi();
  const q = usePoll(() => api.incidents(true), 2000);
  const robots = usePoll(() => api.robots(), 30000);
  const [snooze, setSnooze] = useState<Record<number, number>>({});
  const [, tick] = useState(0);
  const act = useAction();
  useEffect(() => {
    const h = setInterval(() => tick((n) => n + 1), 5000);   // 미룬 시간이 지나면 다시 그리게
    return () => clearInterval(h);
  }, []);

  const now = Date.now();
  const waiting = (q.data ?? []).filter((i) => i.state === 'AWAITING_APPROVAL' && (snooze[i.incidentId] ?? 0) < now);
  const inc: Incident | undefined = waiting[0];
  if (!inc) return null;

  const robot = robots.data?.find((r) => r.robotId === inc.responderId);
  const rc = inc.recheck;
  const later = () => setSnooze((s) => ({ ...s, [inc.incidentId]: Date.now() + SNOOZE_MS }));
  const approve = () => {
    if (!window.confirm(`사건 #${inc.incidentId}: 투척을 승인합니다. 로봇이 바로 투척합니다.`)) return;
    act.run(async () => { await api.approveIncident(inc.incidentId); q.reload(); });
  };
  const dismiss = () => {
    if (!window.confirm(`사건 #${inc.incidentId} 을 오탐으로 닫습니다. 로봇은 투척하지 않고 풀려납니다.`)) return;
    act.run(async () => { await api.dismissIncident(inc.incidentId, '투척 승인 팝업에서 오탐으로 닫음'); q.reload(); });
  };
  return (
    <div className="emg-scrim lch-scrim" role="alertdialog" aria-modal="true" aria-labelledby="lch-title">
      <div className="emg-box lch-box">
        <div className="lch-head">
          <span className="emg-icon lch-icon"><Icon name="flame.fill" size={52} /></span>
          <div className="lch-titles">
            <div className="lch-label">투척 승인 요청</div>
            <h1 id="lch-title">사건 #{inc.incidentId} · 로봇이 투척 위치에 도착했습니다</h1>
          </div>
          {waiting.length > 1 && <span className="lch-more">승인 대기 {waiting.length}건</span>}
        </div>
        <div className="lch-main">
          <div className="lch-camera">
            {inc.responderId != null
              ? <img src={api.streamUrl(inc.responderId)} alt="대응 로봇 카메라" />
              : <span>카메라 없음</span>}
            <span className="lch-live"><i />실시간 · {robot?.code ?? `로봇 ${inc.responderId}`}</span>
          </div>
          <div className="lch-info">
            <div><span>도착 후 재판독</span><b className={rc?.grade === 'EMERGENCY' ? 'red' : ''}>{rc?.grade ? GRADE_KO[rc.grade] ?? rc.grade : '-'}</b></div>
            <div><span>열원 비율</span><b>{rc?.value != null ? `${(rc.value * 100).toFixed(1)}%` : '-'}</b></div>
            <div><span>조준</span><b className={rc?.aimed ? '' : 'orange'}>{rc?.bearingDeg != null ? `${rc.bearingDeg > 0 ? '왼쪽' : '오른쪽'} ${Math.abs(rc.bearingDeg).toFixed(1)}°` : '-'}{rc?.aimed ? ' · 범위 안' : rc?.bearingDeg != null ? ' · 범위 밖' : ''}</b></div>
            <div><span>화재 위치</span><b>({inc.x.toFixed(1)}, {inc.y.toFixed(1)})</b></div>
            <div><span>감지</span><b>{ago(inc.createdAt)}</b></div>
            {rc?.reason && <p>{rc.reason}</p>}
            {inc.launchMode === 'AUTO' && <p className="orange">자동 투척 모드였지만 조건을 채우지 못해 승인으로 넘어왔습니다.</p>}
          </div>
        </div>
        {act.error && <p className="lch-error">{act.error}</p>}
        <div className="emg-actions lch-actions">
          <button className="emg-open lch-later" onClick={later}>나중에</button>
          <button className="emg-open" onClick={() => { later(); onOpen(inc.incidentId); }}>
            <Icon name="doc.text.magnifyingglass" size={24} />사건 상세
          </button>
          {canDismiss && <button className="emg-open" disabled={act.busy} onClick={dismiss}><Icon name="nosign" size={24} />오탐으로 닫기</button>}
          <button className="emg-ok lch-approve" disabled={act.busy} onClick={approve} autoFocus>
            <Icon name="flame.fill" size={28} />투척 승인
          </button>
        </div>
      </div>
    </div>
  );
}
