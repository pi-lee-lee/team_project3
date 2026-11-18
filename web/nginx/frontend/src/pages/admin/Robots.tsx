import { useNavigate } from 'react-router-dom';
import type { RobotSummary } from '../../api/types';
import { ErrorBox, useApi, usePoll } from '../../util';
import { Empty, Group, Meta, MetaLine, Page, Row, Tag } from '../../ui';
import { Icon } from '../../Icon';
import './admin.css';

/** 제어권을 가진 쪽: 사람이 조종 중이면 그 아이디, 점검 작업이면 "점검 작업" */
function controlText(r: RobotSummary) {
  if (!r.control) return '제어권 없음';
  return r.control.kind === 'MISSION' ? '점검 작업' : `조종 ${r.control.login}`;
}

/** A2 로봇 관리 — 목록. 로봇을 누르면 상세(상태·제공 기능·제어권·비상 정지)로 간다. */
export default function Robots() {
  const api = useApi();
  const nav = useNavigate();
  const robots = usePoll(() => api.adminRobots(), 2000);

  return (
    <Page title="로봇" width="normal"
      actions={<button className="nav-icon" aria-label="로봇 등록" title="로봇 등록" onClick={() => nav('/admin/robots/new')}>
        <Icon name="plus" size={24} /></button>}>
      <ErrorBox msg={robots.error} />
      {robots.data && robots.data.length === 0 && <Empty icon="cpu" title="등록된 로봇이 없습니다" />}
      {!!robots.data?.length && (
        <Group className="admin-list">
          {robots.data.map((r) => (
            <Row key={r.robotId} to={`/admin/robots/${r.robotId}`} rich className={r.enabled ? '' : 'dim'}
              icon="cpu" iconColor={r.connected ? 'var(--green)' : '#8e8e93'}
              title={<>
                <span className="title-pair">{r.code}<span className="title-light">{r.name}</span></span>
                <Tag tone={r.connected ? 'green' : 'red'}>{r.connected ? '연결됨' : '연결 안 됨'}</Tag>
                {!r.enabled && <Tag tone="gray">비활성</Tag>}
              </>}
              subtitle={
                <MetaLine>
                  <Tag tone={r.adapterType === 'ROSBRIDGE' ? 'indigo' : 'gray'}>{r.adapterType}</Tag>
                  <Meta icon="hand.raised.fill" strong={!!r.control}>{controlText(r)}</Meta>
                  {r.mission && (
                    <Meta icon="checklist" tone={r.mission.cancelRequested ? 'orange' : 'blue'}>
                      작업 #{r.mission.missionId}{r.mission.cancelRequested ? ' 취소 중' : ''}
                    </Meta>
                  )}
                </MetaLine>
              } />
          ))}
        </Group>
      )}
    </Page>
  );
}
