import { useState } from 'react';
import type { TaskStatus } from '../../api/types';
import { Badge, ErrorBox, fmtTime, useApi, usePoll } from '../../util';
import { Empty, Group, Meta, MetaLine, Page, RobotChip, RouteChips, Row, Segmented, Tag } from '../../ui';
import './user.css';

type Filter = 'all' | 'active' | 'done' | 'failed';
/** 상태별 앞 아이콘과 색 */
const STATUS_ICON: Record<TaskStatus, [string, string]> = {
  REQUESTED: ['clock', 'var(--blue)'], DISPATCHED: ['play.fill', 'var(--blue)'], RUNNING: ['play.fill', 'var(--blue)'],
  CANCEL_REQUESTED: ['hand.raised.fill', 'var(--orange)'], COMPLETED: ['checkmark.circle.fill', 'var(--green)'],
  FAILED: ['xmark.circle.fill', 'var(--red)'], CANCELLED: ['nosign', '#8e8e93'], INTERRUPTED: ['exclamationmark.triangle.fill', 'var(--red)'],
};
const FILTERS: [Filter, string][] = [['all', '전체'], ['active', '진행 중'], ['done', '완료'], ['failed', '실패·취소']];

/** U3 작업 목록: 칸을 누르면 작업 상세 */
export default function Tasks() {
  const api = useApi();
  const [filter, setFilter] = useState<Filter>('all');
  const tasks = usePoll(() => api.tasks(filter === 'all' ? undefined : filter), 2000, [filter]);
  return (
    <Page title="작업">
      <Segmented value={filter} options={FILTERS} onChange={setFilter} full />
      <ErrorBox msg={tasks.error} />
      {tasks.data && tasks.data.length === 0 ? (
        <Empty icon="checklist" title="작업이 없습니다" />
      ) : tasks.data && (
        <Group>
          {tasks.data.map((t) => (
            <Row key={t.task_id} to={`/app/tasks/${t.task_id}`} rich
              icon={STATUS_ICON[t.status][0]} iconColor={STATUS_ICON[t.status][1]}
              title={<>작업 #{t.task_id}<Badge status={t.status} />
                {/* 점검 계획이 만든 작업: 시각이 되어 자동으로 돈 것은 "예약", 실행 버튼으로 돌린 것은 "계획" */}
                {t.schedule_id ? (t.note?.startsWith('예약 점검')
                  ? <Tag tone="orange" icon="calendar.badge.clock">예약</Tag>
                  : <Tag tone="indigo" icon="checklist">계획</Tag>) : null}
                {t.recheck_of ? <Tag tone="purple" icon="arrow.uturn.backward">재점검</Tag> : null}</>}
              subtitle={<>
                <MetaLine><RobotChip code={t.robot_code} /><RouteChips points={t.points} /></MetaLine>
                <MetaLine>
                  <Meta icon="person.crop.circle">{t.requester_login}</Meta>
                  <Meta icon="clock">{fmtTime(t.created_at)}</Meta>
                  <Meta icon="photo" strong={t.observations > 0}>관측 {t.observations}</Meta>
                </MetaLine>
                {t.status_reason && (
                  <MetaLine>{['FAILED', 'INTERRUPTED'].includes(t.status)
                    ? <Meta icon="exclamationmark.triangle.fill" tone="red">{t.status_reason}</Meta>
                    : <Meta icon="hand.raised.fill">{t.status_reason}</Meta>}</MetaLine>
                )}
                {t.note && <span className="note-line">{t.note}</span>}
              </>} />
          ))}
        </Group>
      )}
    </Page>
  );
}
