import { useState } from 'react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import { Badge, ErrorBox, fmtTime, useAction, useApi, useAuth, usePoll } from '../../../util';
import { Icon } from '../../../Icon';
import { ActionBar, Empty, Group, Meta, MetaLine, Notice, Page, PointBadge, RobotChip, RouteChips, Row, Switch, Tag } from '../../../ui';
import type { ScheduleOutcome } from '../../../api/types';
import { delayText } from '../DelayBanner';
import { KindTag, Outcome, ruleText } from './planText';

const OUTCOME_ICON: Record<ScheduleOutcome, [string, string]> = {
  CREATED: ['checkmark.circle.fill', 'var(--green)'], FAILED: ['xmark.circle.fill', 'var(--red)'],
  MISSED: ['exclamationmark.triangle.fill', 'var(--orange)'], CANCELLED: ['nosign', '#8e8e93'],
  SKIPPED_BUSY: ['exclamationmark.triangle.fill', 'var(--orange)'], SKIPPED_OFFLINE: ['exclamationmark.triangle.fill', 'var(--orange)'],
};

/** 점검 (상세): 실행, 대기 중인 회차, 계획 내용, 실행 기록, 켜기·끄기, 삭제 */
export default function PlanDetail() {
  const { id } = useParams();
  const sid = Number(id);
  const api = useApi();
  const navigate = useNavigate();
  const location = useLocation();
  const { me } = useAuth();
  const plan = usePoll(() => api.schedule(sid), 5000, [sid]);
  const pending = usePoll(() => api.pendingRuns(), 5000);
  const robots = usePoll(() => api.robots(), 0);
  const points = usePoll(() => api.points(), 0);
  const act = useAction();
  const [notice, setNotice] = useState<string | null>((location.state as { notice?: string } | null)?.notice ?? null);

  const s = plan.data;
  if (!s) return <Page title="점검" back={{ to: '/app/plans', label: '점검' }} width="narrow"><ErrorBox msg={plan.error} /></Page>;

  const canEdit = me?.role !== 'USER' || s.created_by === me?.userId;
  const robot = robots.data?.find((r) => r.robotId === s.robot_id);
  const queued = (pending.data ?? []).filter((p) => p.scheduleId === sid);
  const timed = s.kind !== 'MANUAL';
  const reload = () => Promise.all([plan.reload(), pending.reload()]);

  const run = () => act.run(async () => {
    const r = await api.runSchedule(sid);
    if (r.outcome === 'CREATED' && r.taskId) navigate(`/app/tasks/${r.taskId}`);
    else if (r.outcome === 'QUEUED') setNotice(`대기열에 담았습니다 — ${r.reason ?? '로봇이 비면'} · 끝나면 이어서 실행합니다`);
    else setNotice(`실행 실패: ${r.reason ?? r.outcome}`);
    await reload();
  });

  return (
    <Page title={s.name} back={{ to: '/app/plans', label: '점검' }} width="narrow"
      actions={canEdit && <button onClick={() => navigate(`/app/plans/${sid}/edit`)}>편집</button>}
      sub={<MetaLine>
        <KindTag kind={s.kind} enabled={s.enabled} />
        <RobotChip code={robot?.code ?? `로봇 #${s.robot_id}`} online={robot?.connected} />
        <RouteChips points={s.points} />
      </MetaLine>}>
      {notice && <Notice tone="warn">{notice}</Notice>}
      <ErrorBox msg={act.error || plan.error} />

      <ActionBar>
        <button className="primary" disabled={act.busy} onClick={run}><Icon name="play.fill" size={18} />지금 실행</button>
      </ActionBar>

      {queued.length > 0 && (
        <Group header={`대기 중 ${queued.length}건`} footer="로봇이 지금 작업을 마치면 순서대로 이어서 실행합니다. 서버를 다시 시작하면 대기열은 비워집니다.">
          {queued.map((p) => (
            <Row key={p.key} rich icon="clock" iconColor="var(--orange)"
              title={<>예정 {fmtTime(p.plannedAt)}<Tag tone="orange">{delayText(p.delaySec)}</Tag>{p.manualBy && <Tag tone="blue" icon="play.fill">{p.manualBy} 실행</Tag>}</>}
              subtitle={<MetaLine><Meta icon="hand.raised.fill">{p.waitReason ?? '로봇 상태 확인 중'}</Meta></MetaLine>}
              right={canEdit && (
                <button className="pill-btn" disabled={act.busy} onClick={() => {
                  if (confirm(`${fmtTime(p.plannedAt)} 예정 회차의 대기를 취소할까요?`)) {
                    act.run(async () => { await api.cancelPendingRun(p.key); await reload(); });
                  }
                }}>대기 취소</button>
              )} />
          ))}
        </Group>
      )}

      <Group header="계획">
        <Row title="로봇" right={<span className="row"><span className="muted small">{robot?.name}</span><RobotChip code={robot?.code ?? `#${s.robot_id}`} online={robot?.connected} /></span>} />
        <Row title="실행 방식" right={<span className="row"><span className="cell-detail">{ruleText(s)}</span><KindTag kind={s.kind} enabled={s.enabled} /></span>} />
        {timed && <Row title="다음 실행" detail={s.enabled && s.next_run_at ? fmtTime(s.next_run_at) : '-'} />}
        {timed && (
          <Row title="자동 실행" right={
            <Switch label="자동 실행" checked={s.enabled} disabled={!canEdit || act.busy}
              onChange={(v) => act.run(async () => { plan.setData(await api.setScheduleEnabled(sid, v)); await pending.reload(); })} />
          } />
        )}
        {s.note && <Row title="메모" detail={s.note} />}
        <Row title="만든 사람" detail={s.creator_login} />
      </Group>

      <Group header="점검 구간 · 방문 순서">
        {s.point_ids.map((pid, i) => {
          const p = points.data?.find((x) => x.point_id === pid);
          return (
            <Row key={`${pid}-${i}`} to={`/app/history/${pid}`}
              title={<span className="row"><span className="order-num">{i + 1}</span><PointBadge code={p?.code ?? `#${pid}`} />{p?.name}</span>}
              subtitle={p?.description ?? undefined} />
          );
        })}
      </Group>

      <Group header="실행 기록">
        {s.runs?.length ? s.runs.map((r) => (
          <Row key={r.run_id} rich to={r.task_id ? `/app/tasks/${r.task_id}` : undefined}
            icon={OUTCOME_ICON[r.outcome][0]} iconColor={OUTCOME_ICON[r.outcome][1]}
            title={<><Outcome o={r.outcome} />{(r.delay_sec ?? 0) >= 60 ? <Tag tone="orange">{delayText(r.delay_sec!)}</Tag> : r.outcome === 'CREATED' && <Tag tone="green">정시</Tag>}</>}
            subtitle={<>
              <MetaLine>
                <Meta icon="clock">예정 {fmtTime(r.planned_at)}</Meta>
                <Meta icon="play.fill">처리 {fmtTime(r.ran_at)}</Meta>
                {r.task_id && <Meta icon="checklist" strong>작업 #{r.task_id}</Meta>}
              </MetaLine>
              {r.reason && <span className="note-line">{r.reason}</span>}
            </>}
            right={r.task_status ? <Badge status={r.task_status} /> : undefined} />
        )) : <Empty icon="clock" title="아직 실행된 적이 없습니다" />}
      </Group>

      {canEdit && (
        <Group>
          <Row destructive title="점검 계획 삭제" onClick={() => {
            if (confirm(`"${s.name}" 을(를) 지울까요? 지난 실행 기록과 작업은 남습니다.`)) {
              act.run(async () => {
                await api.deleteSchedule(sid);
                navigate('/app/plans', { state: { notice: `"${s.name}" 을(를) 지웠습니다` } });
              });
            }
          }} />
        </Group>
      )}
    </Page>
  );
}
