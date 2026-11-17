import { Link, useParams } from 'react-router-dom';
import { ErrorBox, ReasonBadge, ago, fmtTime, useApi, usePoll } from '../../util';
import { Empty, Meta, MetaLine, Page } from '../../ui';
import { ObservationTags } from './inspectionText';
import './user.css';

/** U5-1 지점 하나의 관측 사진 이력. 사진을 누르면 그 관측 화면 */
export default function PointHistory() {
  const { pointId } = useParams();
  const api = useApi();
  const hist = usePoll(() => api.pointHistory(Number(pointId)), 5000, [pointId]);
  const obs = hist.data?.observations ?? [];
  const p = hist.data?.point;
  const last = obs.find((o) => o.status === 'CAPTURED');
  const lastAgeH = last ? (Date.now() - new Date(last.captured_at).getTime()) / 3600000 : null;

  return (
    <Page title={p ? `${p.code} ${p.name}` : '지점'} back={{ to: '/app/history', label: '지점 이력' }}
      sub={hist.data && (
        <span className={lastAgeH === null || lastAgeH > 24 ? 'warn-t' : undefined}>
          마지막 촬영: {last ? `${ago(last.captured_at)} (${fmtTime(last.captured_at)})` : '없음'}
        </span>
      )}>
      <ErrorBox msg={hist.error} />
      {hist.data && obs.length === 0 && <Empty icon="photo.on.rectangle" title="이 지점의 관측이 아직 없습니다" />}
      <div className="thumbs">
        {obs.map((o) => (
          <Link key={o.observation_id} to={`/app/tasks/${o.task_id}/observations/${o.observation_id}`} className="thumb">
            {o.has_image ? <img src={api.imageUrl(o.observation_id)} alt="" loading="lazy" /> : <div className="novideo">촬영 없음</div>}
            <MetaLine><ObservationTags o={o} /></MetaLine>
            <MetaLine>
              <Meta icon="clock">{fmtTime(o.captured_at)}</Meta>
              <Meta icon="checklist">작업 #{o.task_id}</Meta>
            </MetaLine>
            {o.status === 'UNABLE' && <span className="note-line"><ReasonBadge code={o.reason_code} />{o.reason}</span>}
          </Link>
        ))}
      </div>
    </Page>
  );
}
