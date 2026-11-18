import { useState } from 'react';
import { Link } from 'react-router-dom';
import type { AlertRow } from '../../api/types';
import { ErrorBox, ago, fmtTime, useAction, useApi, usePoll } from '../../util';
import { Empty, Group, Meta, MetaLine, Page, PointBadge, Segmented, Tag } from '../../ui';
import { Icon } from '../../Icon';
import './user.css';

type Filter = 'open' | 'resolved';
const FILTERS: [Filter, string][] = [['open', '열린 경고'], ['resolved', '해제된 경고']];
const TYPE: Record<string, [string, string]> = {
  RULE_VIOLATION: ['규칙 위반', 'ruler'], FIRE_DETECTED: ['화재 감지', 'flame.fill'], HEAT_WARNING: ['열원 감지', 'flame.fill'],
};

/** 경고가 가리키는 대상의 화면 주소. 없으면 null */
export function alertLink(a: Pick<AlertRow, 'ref_kind' | 'ref_id' | 'task_id'>) {
  if (a.ref_kind === 'incident') return `/app/incidents/${a.ref_id}`;
  if (a.ref_kind === 'observation' && a.task_id) return `/app/tasks/${a.task_id}/observations/${a.ref_id}`;
  if (a.ref_kind === 'task') return `/app/tasks/${a.ref_id}`;
  if (a.task_id) return `/app/tasks/${a.task_id}`;
  return null;
}

/**
 * U6 경고: 규칙 위반 · 화재 감지처럼 확인과 해제를 남기는 경고 목록.
 * 확인 = "봤다"(목록에 남는다), 해제 = 끝냄(1 관리자 · 2 매니저). 규칙 위반은 다음 점검이 정상이면 스스로 풀린다.
 */
export default function Alerts() {
  const api = useApi();
  const [filter, setFilter] = useState<Filter>('open');
  const alerts = usePoll(() => api.alerts(filter === 'open' ? 'OPEN,ACKED' : 'RESOLVED'), 3000, [filter]);
  const act = useAction();
  const run = (fn: () => Promise<unknown>) => { if (!act.busy) act.run(async () => { await fn(); await alerts.reload(); }); };

  return (
    <Page title="경고">
      <Segmented value={filter} options={FILTERS} onChange={setFilter} full />
      <ErrorBox msg={act.error || alerts.error} />
      {alerts.data && alerts.data.length === 0 ? (
        <Empty icon={filter === 'open' ? 'checkmark.circle.fill' : 'tray'} title={filter === 'open' ? '열린 경고가 없습니다' : '해제된 경고가 없습니다'} />
      ) : alerts.data && (
        <Group>
          {alerts.data.map((a) => {
            const to = alertLink(a);
            const [typeLabel, icon] = TYPE[a.type] ?? [a.type, 'exclamationmark.triangle.fill'];
            const emergency = a.grade === 'EMERGENCY';
            return (
              <div key={a.alert_id} className="cell rich">
                <span className="cell-icon" style={{ background: a.state === 'RESOLVED' ? '#8e8e93' : emergency ? 'var(--red)' : 'var(--orange)' }}>
                  <Icon name={icon} size={18} /></span>
                <span className="cell-main">
                  <span className="cell-title">
                    {to ? <Link to={to}>{a.title}</Link> : a.title}
                    <Tag tone={emergency ? 'red' : 'orange'}>{emergency ? '비상' : '경고'}</Tag>
                    {a.state === 'ACKED' && <Tag tone="blue" icon="checkmark">확인함</Tag>}
                    {a.state === 'RESOLVED' && <Tag tone="gray">해제</Tag>}
                  </span>
                  <span className="cell-sub">
                    {a.detail && <MetaLine><span className="meta-text">{a.detail}</span></MetaLine>}
                    <MetaLine>
                      {a.point_code && <PointBadge code={a.point_code} name={a.point_name ?? undefined} />}
                      <Meta icon="ruler">{typeLabel}</Meta>
                      <Meta icon="clock">{fmtTime(a.opened_at)} ({ago(a.opened_at)})</Meta>
                      {a.acked_by && <Meta icon="person.crop.circle">확인 {a.acked_by}</Meta>}
                      {a.resolved_by && <Meta icon="checkmark.circle.fill">해제 {a.resolved_by === 'SYSTEM' ? '자동' : a.resolved_by} · {fmtTime(a.resolved_at)}</Meta>}
                    </MetaLine>
                    {a.comment && <span className="note-line">{a.comment}</span>}
                  </span>
                </span>
                {a.state !== 'RESOLVED' && (
                  <span className="cell-actions">
                    {a.state === 'OPEN' && <button type="button" disabled={act.busy} onClick={() => run(() => api.ackAlert(a.alert_id))}>확인</button>}
                    <button type="button" disabled={act.busy} title="1 관리자 · 2 매니저만 할 수 있습니다"
                      onClick={() => { if (window.confirm('이 경고를 해제할까요?')) run(() => api.resolveAlert(a.alert_id)); }}>해제</button>
                  </span>
                )}
              </div>
            );
          })}
        </Group>
      )}
    </Page>
  );
}
