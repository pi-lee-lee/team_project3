import { useParams } from 'react-router-dom';
import { ErrorBox, useAction, useApi, usePoll } from '../../util';
import { Empty, Group, Page, Row } from '../../ui';
import { Capabilities } from '../user/Monitor';
import './admin.css';

/** A2 로봇 상세: 연결 상태 · 제공 기능 · 제어권 · 작업, 그리고 연결 설정 · 제어권 회수 · 비상 정지 */
export default function RobotDetail() {
  const { id } = useParams<{ id: string }>();
  const robotId = Number(id);
  const api = useApi();
  const robots = usePoll(() => api.adminRobots(), 2000);
  const r = robots.data?.find((x) => x.robotId === robotId);
  const status = usePoll(() => (r?.enabled ? api.robotStatus(robotId) : Promise.resolve(null)), 3000, [robotId, r?.enabled]);
  const act = useAction();
  const back = { to: '/admin/robots', label: '로봇' };

  const run = (fn: () => Promise<unknown>) => act.run(async () => { await fn(); await robots.reload(); });

  if (!robots.data) return <Page title="로봇" width="narrow" back={back}><ErrorBox msg={robots.error} /></Page>;
  if (!r) return <Page title="로봇" width="narrow" back={back}><Empty icon="cpu" title="로봇을 찾을 수 없습니다" /></Page>;

  const caps = status.data?.capabilities;
  const battery = status.data?.batteryPercent;

  return (
    <Page title={r.code} sub={r.name} width="narrow" back={back}>
      <ErrorBox msg={act.error || robots.error} />

      <Group header="상태">
        <Row title="연결" detail={<span className={r.connected ? 'ok' : 'bad'}>{r.connected ? '연결됨' : '연결 안 됨'}</span>} />
        <Row title="어댑터" detail={r.adapterType} />
        <Row title="사용" detail={r.enabled ? '사용' : '비활성'} />
        {battery !== undefined && battery !== null && <Row title="배터리" detail={`${Math.round(battery)}%`} />}
      </Group>

      {r.enabled && caps && (
        <Group header="제공 기능">
          <div className="cell cell-pad"><Capabilities caps={caps} /></div>
        </Group>
      )}

      <Group header="제어">
        <Row title="제어권" detail={r.control ? `${r.control.login} (${r.control.kind === 'MISSION' ? '점검 작업' : '조종'})` : '없음'} />
        <Row title="작업" detail={r.mission ? `#${r.mission.missionId} 진행 중${r.mission.cancelRequested ? ' · 취소 요청' : ''}` : '없음'} />
      </Group>

      <Group footer="실제 로봇으로 바꿀 때는 연결 설정에서 주소·토픽만 바꿉니다.">
        <Row icon="antenna" title="연결 설정" to={`/admin/robots/${r.robotId}/edit`} />
        {r.control?.kind === 'USER' && (
          <Row icon="hand.raised.fill" iconColor="var(--orange)" title="제어권 회수" onClick={() => {
            if (act.busy) return;
            if (confirm(`${r.control?.login} 의 ${r.code} 조종 제어권을 회수할까요?`)) run(() => api.revokeControl(r.robotId));
          }} />
        )}
      </Group>

      {r.enabled && (
        <Group>
          <Row destructive title="비상 정지" onClick={() => { if (!act.busy) run(() => api.estop(r.robotId)); }} />
        </Group>
      )}
    </Page>
  );
}
