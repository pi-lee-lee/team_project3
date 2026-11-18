import { Link, useParams } from 'react-router-dom';
import type { Observation } from '../../api/types';
import { Badge, ErrorBox, TERMINAL, fmtTime, useAction, useApi, usePoll } from '../../util';
import { Group, Meta, MetaLine, Page, PointBadge, Row, Tag } from '../../ui';
import { Icon } from '../../Icon';
import { EVENT_LABEL, ObservationTags, SOURCE, eventText } from './inspectionText';
import './user.css';

/** U4 작업 상세: 작업 정보 · 관측 목록(누르면 관측 화면) · 진행 기록 */
export default function TaskDetail() {
  const { id } = useParams();
  const api = useApi();
  const task = usePoll(() => api.task(Number(id)), 2000, [id]);
  const act = useAction();
  const t = task.data;
  const back = { to: '/app/tasks', label: '작업' };
  if (!t) return <Page title={`작업 #${id}`} back={back} width="narrow"><ErrorBox msg={task.error} /></Page>;
  const cancellable = !TERMINAL.includes(t.status) && t.status !== 'CANCEL_REQUESTED';

  return (
    <Page title={`작업 #${t.task_id}`} back={back} width="narrow">
      <ErrorBox msg={act.error || task.error} />
      <Group>
        <Row title="상태" right={<Badge status={t.status} />} />
        {t.status_reason && <Row title={<span className="bad">{t.status_reason}</span>} />}
        <Row title="로봇" detail={t.robot_code} />
        <Row title="요청자" detail={t.requester_login} />
        <Row title="요청 시각" detail={fmtTime(t.created_at)} />
        {t.note && <Row title="메모" detail={t.note} />}
        {t.recheck_of != null && <Row title="재점검" detail={`관측 #${t.recheck_of} 다시 보기`} />}
        {t.schedule_id != null && <Row title="예약 점검" detail={`예약 #${t.schedule_id} 이 만든 작업`} />}
        {t.kind === 'RESPONSE' && (t.incident_id != null
          ? <Row title={<>종류<Tag tone="red" icon="flame.fill">화재 출동</Tag></>} detail={`사건 #${t.incident_id}`} to={`/app/incidents/${t.incident_id}`} />
          : <Row title="종류" right={<Tag tone="red" icon="flame.fill">화재 출동</Tag>} />)}
      </Group>
      <Group footer={cancellable ? '로봇이 지금 하는 이동을 멈추고 작업을 끝냅니다.' : undefined}>
        {cancellable ? (
          <Row destructive title={act.busy ? '요청 중…' : '작업 취소'}
            onClick={() => { if (!act.busy) act.run(async () => task.setData(await api.cancelTask(t.task_id))); }} />
        ) : (
          <Row destructive className="is-disabled" title={t.status === 'CANCEL_REQUESTED' ? '취소 요청됨' : '작업 취소'} />
        )}
      </Group>

      <div className="split">
        <Group header={`관측 ${t.observations.length}`}>
          {t.observations.length === 0
            ? <Row title={<span className="muted">아직 관측이 없습니다</span>} />
            : t.observations.map((o) => <ObservationRow key={o.observation_id} o={o} />)}
        </Group>
        <Group header="진행 기록">
          {t.events.length === 0 && <Row title={<span className="muted">기록 없음</span>} />}
          {t.events.map((e) => {
            const text = eventText(e);
            return (
              <div key={e.event_id} className="cell">
                <span className={`ev-dot src-${e.source}`} />
                <span className="cell-main">
                  <span className="cell-title ev-title">{EVENT_LABEL[e.type] ?? e.type}
                    <Tag tone={e.source === 'ROBOT' ? 'green' : e.source === 'USER' ? 'blue' : 'gray'}>{SOURCE[e.source]}{e.actor ? ` ${e.actor}` : ''}</Tag>
                  </span>
                  {text && <span className="cell-sub">{text}</span>}
                </span>
                <span className="cell-detail small">{fmtTime(e.occurred_at, false)}</span>
              </div>
            );
          })}
        </Group>
      </div>
    </Page>
  );
}

/** 관측 한 칸: 썸네일 + 지점 + 요약, 누르면 관측 화면 */
function ObservationRow({ o }: { o: Observation }) {
  const api = useApi();
  return (
    <Link className="cell tappable rich" to={`/app/tasks/${o.task_id}/observations/${o.observation_id}`}>
      {o.has_image
        ? <img className="thumb-sm" src={api.imageUrl(o.observation_id)} alt="" loading="lazy" />
        : <span className="thumb-sm ph"><Icon name="photo" size={20} /></span>}
      <span className="cell-main">
        <span className="cell-title"><span className="order-num">{o.seq}</span><PointBadge code={o.point_code} />{o.point_name}</span>
        <span className="cell-sub">
          <MetaLine><ObservationTags o={o} /></MetaLine>
          <MetaLine><Meta icon="clock">{fmtTime(o.captured_at)}</Meta></MetaLine>
          {o.status === 'UNABLE' && o.reason && <span className="note-line">{o.reason}</span>}
        </span>
      </span>
      <Icon name="chevron.right" size={20} className="chev" />
    </Link>
  );
}
