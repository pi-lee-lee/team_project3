import { ErrorBox, useApi, usePoll } from '../../util';
import { Group, Meta, MetaLine, Page, Row, Tag } from '../../ui';
import type { Tone } from '../../ui';
import './admin.css';

const AGE_KEYS = ['odom', 'scan', 'camera', 'battery'];

/** 데이터 갱신 꼬리표: 2초 이내 초록, 넘으면 주황, 받은 적 없으면 회색 */
function AgeTag({ k, v }: { k: string; v: number | null | undefined }) {
  const none = v === null || v === undefined;
  const tone: Tone = none ? 'gray' : v > 2000 ? 'orange' : 'green';
  return <Tag tone={tone}>{k} {none ? '없음' : `${(v / 1000).toFixed(1)}s`}</Tag>;
}

/** A6 시스템 상태: 서비스 UP/DOWN, 로봇 연결과 데이터 갱신 */
export default function SystemStatus() {
  const api = useApi();
  const s = usePoll(() => api.system(), 5000);

  return (
    <Page title="시스템 상태" sub="5초마다 새로고침" width="normal">
      <ErrorBox msg={s.error} />

      {s.data && (
        <Group header="서비스" className="admin-list">
          {s.data.services.map((x) => {
            const up = x.status === 'UP';
            return (
              <Row key={x.name} title={x.name}
                icon="server.rack" iconColor={up ? 'var(--green)' : 'var(--red)'}
                right={<Tag tone={up ? 'green' : 'red'} icon={up ? 'checkmark.circle.fill' : 'xmark.circle.fill'}>{up ? 'UP' : x.status || 'DOWN'}</Tag>} />
            );
          })}
        </Group>
      )}

      {s.data && (
        <Group header="로봇 연결과 데이터 갱신" className="admin-list"
          footer={'갱신 = 마지막 수신 후 경과 시간. 2초를 넘으면 주황색으로 표시합니다. 서버 ↔ rosbridge 구간이 끊기면 rosbridge 가 "끊김"이 됩니다.'}>
          {s.data.robots.length === 0 && <Row title="등록된 로봇이 없습니다" />}
          {s.data.robots.map((r) => (
            <Row key={r.code} rich className={r.enabled ? '' : 'dim'}
              icon="antenna" iconColor={!r.enabled ? '#8e8e93' : r.connected ? 'var(--green)' : 'var(--red)'}
              title={<>
                {r.code}
                <Tag tone={!r.enabled ? 'gray' : r.connected ? 'green' : 'red'}>
                  rosbridge {r.enabled ? (r.connected ? '연결' : '끊김') : '비활성'}
                </Tag>
              </>}
              subtitle={<>
                <MetaLine>{AGE_KEYS.map((k) => <AgeTag key={k} k={k} v={r.ageMs?.[k]} />)}</MetaLine>
                <MetaLine>
                  <Meta icon="tray" tone={r.outboxPending > 0 ? 'orange' : undefined} strong={r.outboxPending > 0}>
                    미전송 결과 {r.outboxPending}건
                  </Meta>
                </MetaLine>
              </>} />
          ))}
        </Group>
      )}
    </Page>
  );
}
