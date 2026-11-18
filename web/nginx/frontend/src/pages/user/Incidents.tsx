import type { LaunchMode } from '../../api/types';
import { ErrorBox, ago, fmtTime, useAction, useApi, usePoll } from '../../util';
import { Empty, Group, Meta, MetaLine, Page, Row, Segmented, Tag } from '../../ui';
import { IncidentStateTag, LAUNCH_MODE, checkText, isOpenIncident } from './scenarioText';
import './user.css';

const MODES: [LaunchMode, string][] = [['APPROVAL', '사람 승인'], ['AUTO', '자동 투척']];

/**
 * U7 사건(화재 대응) — 목록. 순찰 로봇이 비상 등급의 열원을 보면 사건이 생기고 대응 로봇이 출동한다.
 * 위쪽에서 투척 모드를 바꾼다(1 관리자 이상). 새로 생기는 사건부터 적용된다.
 */
export default function Incidents() {
  const api = useApi();
  const incidents = usePoll(() => api.incidents(false), 3000);
  const settings = usePoll(() => api.settings(), 10000);
  const act = useAction();
  const mode = (settings.data?.['launch.mode'] as LaunchMode | undefined) ?? 'APPROVAL';
  const setMode = (v: LaunchMode) => {
    if (v === mode || act.busy) return;
    if (!window.confirm(`투척 모드를 "${LAUNCH_MODE[v]}"(으)로 바꿀까요? 새로 생기는 사건부터 적용됩니다.`)) return;
    act.run(async () => settings.setData(await api.saveSetting('launch.mode', v)));
  };

  return (
    <Page title="사건">
      <ErrorBox msg={act.error || incidents.error} />
      <Group header="투척 모드" footer={mode === 'AUTO'
        ? '자동 투척: 로봇이 도착해 다시 본 결과가 비상이고 조준 범위 안이면 승인 없이 쏩니다. 조건을 못 채우면 승인을 기다립니다.'
        : '사람 승인: 로봇이 도착하면 승인을 기다립니다. 사건 화면에서 승인해야 쏩니다.'}>
        <div className="cell"><Segmented value={mode} options={MODES} onChange={setMode} full /></div>
      </Group>
      {incidents.data && incidents.data.length === 0 ? (
        <Empty icon="flame.fill" title="사건이 없습니다" />
      ) : incidents.data && (
        <Group>
          {incidents.data.map((i) => {
            const open = isOpenIncident(i.state);
            return (
              <Row key={i.incidentId} to={`/app/incidents/${i.incidentId}`} rich className={open ? '' : 'dim'}
                icon="flame.fill" iconColor={!open ? '#8e8e93' : i.state === 'AWAITING_APPROVAL' ? 'var(--orange)' : 'var(--red)'}
                title={<>사건 #{i.incidentId}<IncidentStateTag state={i.state} /><Tag tone={i.launchMode === 'AUTO' ? 'purple' : 'blue'}>{LAUNCH_MODE[i.launchMode]}</Tag></>}
                subtitle={<>
                  <MetaLine>
                    <Meta icon="location.fill">x {i.x.toFixed(2)} · y {i.y.toFixed(2)}</Meta>
                    <Meta icon="clock">{fmtTime(i.createdAt)} ({ago(i.createdAt)})</Meta>
                    {i.taskId && <Meta icon="checklist">출동 작업 #{i.taskId}</Meta>}
                  </MetaLine>
                  {i.recheck?.grade && <MetaLine><Meta icon="viewfinder">재판독 {checkText(i.recheck)}</Meta></MetaLine>}
                  {i.closeReason && <span className="note-line">{i.closeReason}</span>}
                </>} />
            );
          })}
        </Group>
      )}
    </Page>
  );
}
