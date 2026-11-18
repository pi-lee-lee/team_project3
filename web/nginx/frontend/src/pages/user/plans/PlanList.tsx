import { useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import type { Schedule } from '../../../api/types';
import { ErrorBox, fmtTime, useAction, useApi, usePoll } from '../../../util';
import { Icon } from '../../../Icon';
import { Empty, Group, Meta, MetaLine, Notice, Page, RobotChip, RouteChips, Row, Segmented } from '../../../ui';
import { KindTag, Outcome, ruleText } from './planText';

type Filter = 'all' | 'timed' | 'manual';

/**
 * 점검 (목록). 점검 요청과 예약 점검을 합친 "점검 계획" 목록이다.
 * 계획마다 실행 버튼이 있어 바로 점검을 요청할 수 있고(예전 점검 요청), 시각을 정해 둔 계획은 그때 자동으로 실행된다.
 */
export default function PlanList() {
  const api = useApi();
  const navigate = useNavigate();
  const location = useLocation();
  const list = usePoll(() => api.schedules(), 5000);
  const robots = usePoll(() => api.robots(), 5000);
  const act = useAction();
  const [filter, setFilter] = useState<Filter>('all');
  const [notice, setNotice] = useState<string | null>((location.state as { notice?: string } | null)?.notice ?? null);

  const points = usePoll(() => api.points(), 0);
  const robotCode = (id: number) => robots.data?.find((r) => r.robotId === id)?.code ?? `로봇 #${id}`;
  const robotOnline = (id: number) => robots.data?.find((r) => r.robotId === id)?.connected;
  const pointNames = Object.fromEntries((points.data ?? []).map((p) => [p.code, p.name]));
  const plans = (list.data?.schedules ?? []).filter((s) =>
    filter === 'all' ? true : filter === 'manual' ? s.kind === 'MANUAL' : s.kind !== 'MANUAL');

  const run = (s: Schedule) => act.run(async () => {
    const r = await api.runSchedule(s.schedule_id);
    if (r.outcome === 'CREATED' && r.taskId) navigate(`/app/tasks/${r.taskId}`);
    else if (r.outcome === 'QUEUED') setNotice(`"${s.name}" 을(를) 대기열에 담았습니다 — ${r.reason ?? '로봇이 비면'} · 끝나면 이어서 실행합니다`);
    else setNotice(`"${s.name}" 실행 실패: ${r.reason ?? r.outcome}`);
    await list.reload();
  });

  return (
    <Page title="점검" actions={
      <button className="primary" onClick={() => navigate('/app/plans/new')}><Icon name="plus" size={18} />새 점검</button>
    }>
      <Segmented<Filter> value={filter} onChange={setFilter}
        options={[['all', '전체'], ['timed', '예약'], ['manual', '수동']]} />
      {notice && <Notice tone="warn">{notice}</Notice>}
      <ErrorBox msg={act.error || list.error} />

      {!list.data ? null : plans.length === 0 ? (
        <Empty icon="checklist" title="점검 계획이 없습니다">
          새 점검에서 로봇과 점검 지점(방문 순서)을 고르고, 바로 실행하거나 실행 시각을 정해 두세요.
        </Empty>
      ) : (
        <Group footer="실행을 누르면 바로 점검을 요청합니다. 로봇이 다른 작업 중이면 대기열에 담았다가 끝나면 이어서 실행합니다.">
          {plans.map((s) => (
            <Row key={s.schedule_id} to={`/app/plans/${s.schedule_id}`} rich
              className={s.kind !== 'MANUAL' && !s.enabled ? 'dim' : ''}
              icon={s.kind === 'MANUAL' ? 'hand.raised.fill' : 'calendar.badge.clock'}
              iconColor={s.kind === 'MANUAL' ? 'var(--indigo)' : s.enabled ? 'var(--orange)' : '#8e8e93'}
              title={<>{s.name}<KindTag kind={s.kind} enabled={s.enabled} /></>}
              subtitle={<>
                <MetaLine>
                  <RobotChip code={robotCode(s.robot_id)} online={robotOnline(s.robot_id)} />
                  <RouteChips points={s.points} names={pointNames} />
                </MetaLine>
                <MetaLine>
                  <Meta icon="clock">{ruleText(s)}</Meta>
                  {s.kind !== 'MANUAL' && s.enabled && s.next_run_at && <Meta icon="arrow.triangle.2.circlepath" strong>다음 {fmtTime(s.next_run_at)}</Meta>}
                </MetaLine>
                {s.last_outcome && (
                  <MetaLine>
                    <Outcome o={s.last_outcome} />
                    <Meta icon="clock.arrow.circlepath">{fmtTime(s.last_ran_at)}</Meta>
                    {s.last_task_id && <Meta icon="checklist">작업 #{s.last_task_id}</Meta>}
                  </MetaLine>
                )}
              </>}
              right={
                <button className="pill-btn primary" disabled={act.busy}
                  onClick={(e) => { e.preventDefault(); e.stopPropagation(); run(s); }}>실행</button>
              } />
          ))}
        </Group>
      )}
    </Page>
  );
}
