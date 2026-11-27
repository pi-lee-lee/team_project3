import { useParams } from 'react-router-dom';
import type { IncidentImageKind } from '../../api/types';
import { ErrorBox, ago, fmtTime, useAction, useApi, usePoll } from '../../util';
import { ActionBar, Group, Notice, Page, Row, Tag } from '../../ui';
import { SOURCE } from './inspectionText';
import {
  INCIDENT_TYPE, INCIDENT_EVENT, IncidentStateTag, IncidentSteps, LAUNCH_MODE, checkText, gradeText, incidentEventText, isOpenIncident,
} from './scenarioText';
import './user.css';

const PHOTOS: [IncidentImageKind, string][] = [['detection', '감지 사진'], ['recheck', '도착 후'], ['after', '투척 후']];

/**
 * U7-1 사건 상세: 지금 단계 · 재판독 결과 · 사진 · 사건 기록, 그리고 사람이 하는 일
 * (투척 승인 · 수동 투척 · 오탐으로 닫기 · 조치 완료). 쏠지 말지의 판단과 명령은 서버가 한다.
 */
export default function IncidentDetail() {
  const { id } = useParams();
  const api = useApi();
  const q = usePoll(() => api.incident(Number(id)), 3000, [id]);
  const robots = usePoll(() => api.robots(), 0);
  const act = useAction();
  const i = q.data;
  const back = { to: '/app/incidents', label: '사건' };
  if (!i) return <Page title={`사건 #${id}`} back={back} width="narrow"><ErrorBox msg={q.error} /></Page>;

  const open = isOpenIncident(i.state);
  const robotCode = (rid: number | null) => (rid == null ? '-' : robots.data?.find((r) => r.robotId === rid)?.code ?? `로봇 #${rid}`);
  const run = (ask: string | null, fn: () => Promise<unknown>) => {
    if (act.busy || (ask && !window.confirm(ask))) return;
    act.run(async () => { await fn(); await q.reload(); });
  };
  // 로봇이 투척 위치에 서 있을 때만 쏠 수 있다
  const canLaunch = ['ARRIVED', 'AWAITING_APPROVAL', 'LAUNCHED', 'MONITORING'].includes(i.state);

  return (
    <Page title={`사건 #${i.incidentId}`} back={back} width="narrow"
      sub={<>{INCIDENT_TYPE[i.type] ?? '화재 감지'} · {fmtTime(i.createdAt)} ({ago(i.createdAt)})</>}>
      <div className={open ? 'has-action-bar' : ''}>
        <ErrorBox msg={act.error || q.error} />
        {i.state === 'AWAITING_APPROVAL' && <Notice tone="warn">로봇이 투척 위치에서 승인을 기다리고 있습니다. 아래 사진과 재판독 결과를 보고 승인하거나 닫으세요.</Notice>}
        {i.state === 'FAILED' && <Notice tone="warn">대응에 실패했습니다: {i.closeReason}. 현장을 확인한 뒤 사건을 닫으세요.</Notice>}
        <IncidentSteps incident={i} />

        <Group>
          <Row title="상태" right={<IncidentStateTag state={i.state} />} />
          <Row title="등급" detail={gradeText(i.grade)} />
          <Row title="투척 모드" right={<Tag tone={i.launchMode === 'AUTO' ? 'purple' : 'blue'}>{LAUNCH_MODE[i.launchMode]}</Tag>} />
          <Row title="위치" detail={`x ${i.x.toFixed(2)} · y ${i.y.toFixed(2)}`} />
          <Row title="감지한 로봇" detail={robotCode(i.detectedBy)} />
          <Row title="대응 로봇" detail={robotCode(i.responderId)} />
          {i.taskId ? <Row title="출동 작업" detail={`작업 #${i.taskId}`} to={`/app/tasks/${i.taskId}`} /> : <Row title="출동 작업" detail="아직 없음" />}
          {i.approvedBy && <Row title="승인" detail={`${i.approvedBy} · ${fmtTime(i.approvedAt)}`} />}
          {i.closedAt && <Row title="닫음" detail={`${i.closedBy === 'SYSTEM' ? '자동' : i.closedBy} · ${fmtTime(i.closedAt)}`} />}
          {i.closeReason && i.state !== 'FAILED' && <Row title="사유" detail={i.closeReason} />}
        </Group>

        <Group header="판독" footer="도착 후 재판독: 로봇 카메라로 열화상 이미지를 다시 봅니다. 조준 각은 화면 가운데에서 벗어난 정도입니다.">
          <Row title="도착 후 재판독" subtitle={checkText(i.recheck)} />
          <Row title="투척 후 판독" subtitle={checkText(i.afterCheck)} />
        </Group>

        <div className="inc-photos">
          {PHOTOS.map(([kind, label]) => (
            <figure key={kind}>
              {i.images[kind]
                ? <a href={api.incidentImageUrl(i.incidentId, kind)} target="_blank" rel="noreferrer">
                  <img src={api.incidentImageUrl(i.incidentId, kind, String(i.updatedAt))} alt={label} /></a>
                : <span className="ph">없음</span>}
              <figcaption>{label}</figcaption>
            </figure>
          ))}
        </div>

        <Group header="사건 기록">
          {(i.events ?? []).map((e) => {
            const text = incidentEventText(e);
            return (
              <div key={e.event_id} className="cell">
                <span className={`ev-dot src-${e.source}`} />
                <span className="cell-main">
                  <span className="cell-title ev-title">{INCIDENT_EVENT[e.type] ?? e.type}
                    <Tag tone={e.source === 'ROBOT' ? 'green' : e.source === 'USER' ? 'blue' : 'gray'}>{SOURCE[e.source]}{e.actor ? ` ${e.actor}` : ''}</Tag>
                  </span>
                  {text && <span className="cell-sub">{text}</span>}
                </span>
                <span className="cell-detail small">{fmtTime(e.occurred_at, false)}</span>
              </div>
            );
          })}
        </Group>

        {open && (
          <Group footer="수동 투척 · 조치 완료는 1 관리자 · 2 매니저만 할 수 있습니다.">
            <Row icon="paperplane.fill" title="수동 투척" className={canLaunch ? '' : 'is-disabled'}
              subtitle={canLaunch ? '모드와 무관하게 지금 쏩니다' : '로봇이 투척 위치에 있을 때만 쏠 수 있습니다'}
              onClick={canLaunch ? () => run('지금 투척할까요?', () => api.launchIncident(i.incidentId)) : undefined} />
            <Row icon="checkmark.seal.fill" title="조치 완료로 닫기" subtitle="현장 조치가 끝났을 때"
              onClick={() => run('조치 완료로 사건을 닫을까요?', () => api.resolveIncident(i.incidentId))} />
            <Row icon="bell.slash" destructive title="오탐으로 닫기" subtitle="화재가 아니었을 때 — 출동한 로봇을 돌려보냅니다"
              onClick={() => run('오탐으로 사건을 닫을까요?', () => api.dismissIncident(i.incidentId))} />
          </Group>
        )}
        {i.state === 'AWAITING_APPROVAL' && (
          <ActionBar>
            <button className="danger" disabled={act.busy} onClick={() => run('투척을 승인할까요? 승인하면 바로 쏩니다.', () => api.approveIncident(i.incidentId))}>
              {act.busy ? '요청 중…' : '투척 승인'}</button>
          </ActionBar>
        )}
      </div>
    </Page>
  );
}
