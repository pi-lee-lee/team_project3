import { useEffect } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { ErrorBox, ReasonBadge, ago, fmtTime, useApi, usePoll } from '../../util';

const RESULT: Record<string, [string, string]> = { NORMAL: ['정상', 'ok'], ABNORMAL: ['이상', 'bad'], UNABLE: ['확인 불가', 'warn-t'] };

/** U5 지점 이력 */
export default function History() {
  const api = useApi();
  const [params, setParams] = useSearchParams();
  const points = usePoll(() => api.points(), 0);
  const pointId = Number(params.get('point')) || null;
  useEffect(() => {
    if (!pointId && points.data?.length) setParams({ point: String(points.data[0].point_id) }, { replace: true });
  }, [pointId, points.data, setParams]);
  const hist = usePoll(() => (pointId ? api.pointHistory(pointId) : Promise.resolve(null)), 5000, [pointId]);
  const obs = hist.data?.observations ?? [];
  const last = obs.find((o) => o.status === 'CAPTURED');
  const lastAgeH = last ? (Date.now() - new Date(last.captured_at).getTime()) / 3600000 : null;

  return (
    <section>
      <div className="row between">
        <h2>지점 이력</h2>
        <select value={pointId ?? ''} onChange={(e) => setParams({ point: e.target.value })}>
          {points.data?.map((p) => <option key={p.point_id} value={p.point_id}>{p.code} {p.name}</option>)}
        </select>
      </div>
      <ErrorBox msg={hist.error} />
      <div className={lastAgeH === null || lastAgeH > 24 ? 'warn-t' : 'muted'}>
        마지막 촬영: {last ? `${ago(last.captured_at)} (${fmtTime(last.captured_at)})` : '없음'}
      </div>
      <div className="thumbs">
        {obs.map((o) => (
          <Link key={o.observation_id} to={`/app/tasks/${o.task_id}`} className="thumb">
            {o.has_image ? <img src={api.imageUrl(o.observation_id)} alt="" /> : <div className="novideo">촬영 없음</div>}
            <div className="small">{fmtTime(o.captured_at)} · 작업 #{o.task_id}</div>
            {o.recheck_of && <div className="small muted">재점검 ← 관측 #{o.recheck_of}</div>}
            {o.status === 'UNABLE' && <div className="small warn-t"><ReasonBadge code={o.reason_code} /> {o.reason}</div>}
            {o.verdict === 'RETAKE' && <div className="small warn-t">재촬영 후보</div>}
            <div className="small">
              판정: {o.review_result ? <span className={RESULT[o.review_result][1]}>{RESULT[o.review_result][0]}</span> : <span className="muted">없음</span>}
            </div>
          </Link>
        ))}
      </div>
      {obs.length === 0 && <p className="muted">이 지점의 관측이 아직 없습니다.</p>}
    </section>
  );
}
