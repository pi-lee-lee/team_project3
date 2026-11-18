import { useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import type { Review } from '../../api/types';
import { ErrorBox, ReasonBadge, fmtTime, useAction, useApi, usePoll } from '../../util';
import { ActionBar, Empty, Field, Group, Notice, Page, Row, Segmented } from '../../ui';
import { RESULT, ResultText } from './inspectionText';
import { CHECKER_LABEL, GradeTag, PhotoOverlay, resultBoxes, valueText } from './scenarioText';
import './user.css';

type Choice = '' | Review['result'];
const CHOICES: [Choice, string][] = [['NORMAL', '정상'], ['ABNORMAL', '이상'], ['UNABLE', '확인 불가']];

/** U4-1 관측: 사진 · 품질 분석 · 사람 판정 입력 · 재점검 요청 */
export default function ObservationDetail() {
  const { id, obsId } = useParams();
  const api = useApi();
  const navigate = useNavigate();
  const task = usePoll(() => api.task(Number(id)), 5000, [id]);
  // 규칙별 판독 결과(등급 · 읽은 값 · 찾은 자리). 분석이 끝나면 채워진다
  const results = usePoll(() => api.observationResults(Number(obsId)).catch(() => []), 5000, [obsId]);
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

  const rr = results.data ?? [];
  // 기대 영역은 판독 당시 규칙의 것(터틀봇 사진 기준)
  const boxes = resultBoxes(rr, Object.fromEntries(rr.map((r) => [r.ruleId, r.rule?.regions?.INSPECTOR])));

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
          boxes.length ? <>
            <a href={api.imageUrl(o.observation_id)} target="_blank" rel="noreferrer" title="원본 열기">
              <PhotoOverlay src={api.imageUrl(o.observation_id)} alt={`${o.point_code} 관측 사진`} boxes={boxes} />
            </a>
            <div className="ov-legend"><span><i />찾은 자리</span><span><i className="expected" />기대 영역</span></div>
          </> : (
            <a className="photo-link" href={api.imageUrl(o.observation_id)} target="_blank" rel="noreferrer" title="원본 열기">
              <img className="photo-full" src={api.imageUrl(o.observation_id)} alt={`${o.point_code} 관측 사진`} />
            </a>
          )
        ) : <div className="novideo photo-empty">촬영 없음</div>}

        {rr.length > 0 && (
          <Group header="규칙 판독" footer="사진을 규칙의 판독기로 읽고 등급 기준으로 나눈 결과입니다. 사람 판정이 있으면 그것이 우선합니다.">
            {rr.map((r) => (
              <Row key={r.ruleId} rich
                title={<>{r.rule?.name ?? `규칙 #${r.ruleId}`}<GradeTag grade={r.grade} /></>}
                subtitle={<>
                  {CHECKER_LABEL[r.rule?.kind ?? ''] ?? r.rule?.kind ?? ''} · 읽은 값 {valueText(r.value, r.unit)}
                  {r.reason ? ` · ${r.reason}` : ''}
                </>} />
            ))}
          </Group>
        )}

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
