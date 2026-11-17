import { useNavigate } from 'react-router-dom';
import { ErrorBox, useApi, usePoll } from '../../util';
import { Empty, Group, Meta, MetaLine, Page, PointBadge, Row, Tag } from '../../ui';
import { Icon } from '../../Icon';
import './admin.css';

/**
 * 도착 방향. yaw 0° = 지도 +x(오른쪽), 반시계 방향이 + 이므로 위쪽 화살표를 (90 − yaw)° 만큼 시계 방향으로 돌린다.
 */
function Heading({ deg }: { deg: number }) {
  return (
    <span className="meta">
      <span className="yaw-arrow" style={{ transform: `rotate(${90 - Number(deg)}deg)` }}><Icon name="arrow.up" size={15} /></span>
      방향 {deg}°
    </span>
  );
}

/** A3 점검 지점 — 목록. 지점을 누르면 수정 화면으로 간다. */
export default function Points() {
  const api = useApi();
  const nav = useNavigate();
  const points = usePoll(() => api.adminPoints(), 0);

  return (
    <Page title="점검 지점" width="normal"
      actions={<button className="nav-icon" aria-label="지점 추가" title="지점 추가" onClick={() => nav('/admin/points/new')}>
        <Icon name="plus" size={24} /></button>}>
      <ErrorBox msg={points.error} />
      {points.data && points.data.length === 0 && <Empty icon="mappin.and.ellipse" title="등록된 지점이 없습니다" />}
      {!!points.data?.length && (
        <Group className="admin-list" footer="비활성 지점은 새 요청에서 숨기고 지난 기록은 그대로 둡니다.">
          {points.data.map((p) => (
            <Row key={p.point_id} to={`/admin/points/${p.point_id}/edit`} rich className={p.active ? '' : 'dim'}
              icon="mappin.and.ellipse" iconColor={p.active ? 'var(--teal)' : '#8e8e93'}
              title={<>
                <PointBadge code={p.code} />{p.name}
                {!p.active && <Tag tone="gray">비활성</Tag>}
              </>}
              subtitle={<>
                {p.description && <MetaLine><span className="meta-text">{p.description}</span></MetaLine>}
                <MetaLine>
                  <Meta icon="location.fill">x {Number(p.x).toFixed(2)} · y {Number(p.y).toFixed(2)}</Meta>
                  <Heading deg={p.yaw_deg} />
                </MetaLine>
              </>} />
          ))}
        </Group>
      )}
    </Page>
  );
}
