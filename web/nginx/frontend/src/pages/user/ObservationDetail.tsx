import { useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import type { Review } from '../../api/types';
import { ErrorBox, ReasonBadge, fmtTime, useAction, useApi, usePoll } from '../../util';
import { ActionBar, Empty, Field, Group, Notice, Page, Row, Segmented } from '../../ui';
import { RESULT, ResultText } from './inspectionText';
import './user.css';

type Choice = '' | Review['result'];
const CHOICES: [Choice, string][] = [['NORMAL', '정상'], ['ABNORMAL', '이상'], ['UNABLE', '확인 불가']];

/** U4-1 관측: 사진 · 품질 분석 · 사람 판정 입력 · 재점검 요청 */
export default function ObservationDetail() {
  const { id, obsId } = useParams();
  const api = useApi();
  const navigate = useNavigate();
  const task = usePoll(() => api.task(Number(id)), 5000, [id]);
  const act = useAction();
  const [choice, setChoice] = useState<Choice>('');
  const [comment, setComment] = useState('');
  const [saved, setSaved] = useState(false);
  const back = { to: `/app/tasks/${id}`, label: `작업 #${id}` };

  const o = task.data?.observations.find((x) => x.observation_id === Number(obsId));
  if (!o) {
    return (
      <Page title="관측" back={back} width="narrow">
        <ErrorBox msg={task.error} />
        {task.data && <Empty icon="photo" title="관측을 찾을 수 없습니다" />}
      </Page>
    );
  }

  const needComment = choice === 'UNABLE';
  const canSave = !!choice && !act.busy && (!needComment || !!comment.trim());
  const save = () => act.run(async () => {
    await api.review(o.observation_id, choice, comment.trim());
    setChoice(''); setComment(''); setSaved(true);
    await task.reload();
  });
  const recheck = () => {
    if (act.busy) return;
    act.run(async () => navigate(`/app/tasks/${(await api.recheck(o.observation_id)).task_id}`));
  };

  return (
    <Page title={`${o.point_code} ${o.point_name}`} back={back} width="narrow"
      sub={`${o.seq}번째 지점 · ${fmtTime(o.captured_at)}${o.recheck_of ? ` · 관측 #${o.recheck_of} 재점검` : ''}`}>
      <div className="has-action-bar">
        <ErrorBox msg={act.error || task.error} />
        {o.has_image ? (
          <a className="photo-link" href={api.imageUrl(o.observation_id)} target="_blank" rel="noreferrer" title="원본 열기">
            <img className="photo-full" src={api.imageUrl(o.observation_id)} alt={`${o.point_code} 관측 사진`} />
          </a>
        ) : <div className="novideo photo-empty">촬영 없음</div>}

        {o.status === 'UNABLE' ? (
          <Group header="확인 불가">
            <Row title={<><ReasonBadge code={o.reason_code} />{o.reason ?? '사유 없음'}</>} />
          </Group>
        ) : (
          <Group header="품질" footer={o.verdict ? undefined : '분석 워커가 사진을 분석하는 중입니다.'}>
            <Row title="밝기" detail={o.brightness != null ? o.brightness.toFixed(0) : '-'} />
            <Row title="선명도" detail={o.sharpness != null ? o.sharpness.toFixed(0) : '-'} />
            <Row title="결과" detail={o.verdict === 'OK' ? <span className="ok">양호</span>
              : o.verdict === 'RETAKE' ? <span className="warn-t">재촬영 후보</span> : '분석 중…'} />
            {o.verdict === 'RETAKE' && o.analysis_reasons && <Row title="사유" detail={o.analysis_reasons} />}
          </Group>
        )}

        <Group header="판정" footer={needComment ? '확인 불가는 사유를 꼭 적어야 합니다.' : undefined}>
          <Row title="현재 판정" detail={<ResultText result={o.review_result} />} />
          {o.review_comment && <Row title="의견" detail={o.review_comment} />}
          <div className="cell">
            <Segmented value={choice} options={CHOICES} onChange={(v) => { setChoice(v); setSaved(false); }} full />
          </div>
          <Field label={needComment ? '사유 (필수)' : '의견'} stack>
            <textarea rows={2} value={comment} placeholder={needComment ? '확인 불가 사유' : '의견 (선택)'}
              onChange={(e) => setComment(e.target.value)} />
          </Field>
        </Group>
        {saved && <Notice tone="ok">판정을 저장했습니다.</Notice>}
        <ActionBar>
          <button className="primary" disabled={!canSave} onClick={save}>{act.busy ? '저장 중…' : '판정 저장'}</button>
        </ActionBar>

        {o.reviews && o.reviews.length > 0 && (
          <Group header="판정 이력">
            {o.reviews.map((r) => (
              <Row key={r.review_id} title={<span className={RESULT[r.result]?.[1]}>{RESULT[r.result]?.[0] ?? r.result}</span>}
                subtitle={r.comment ?? undefined} detail={`${r.reviewer_login} · ${fmtTime(r.reviewed_at)}`} />
            ))}
          </Group>
        )}

        <Group>
          <Row icon="arrow.uturn.backward" title="재점검 요청" subtitle="이 지점만 다시 점검하는 작업을 만듭니다" onClick={recheck} />
          <Row icon="clock.arrow.circlepath" title="지점 이력" to={`/app/history/${o.point_id}`} />
        </Group>
      </div>
    </Page>
  );
}
