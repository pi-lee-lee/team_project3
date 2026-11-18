import { Navigate, useSearchParams } from 'react-router-dom';
import { ErrorBox, useApi, usePoll } from '../../util';
import { Empty, Group, Meta, MetaLine, Page, PointBadge, Row } from '../../ui';
import './user.css';

/** U5 지점 이력 — 지점 목록. 지점을 누르면 그 지점의 관측 사진 이력 */
export default function History() {
  const api = useApi();
  const [params] = useSearchParams();
  const points = usePoll(() => api.points(), 0);
  // 옛 주소(/app/history?point=N) 호환
  const legacy = params.get('point');
  if (legacy && Number(legacy)) return <Navigate to={`/app/history/${Number(legacy)}`} replace />;

  return (
    <Page title="지점 이력">
      <ErrorBox msg={points.error} />
      {points.data && points.data.length === 0 ? (
        <Empty icon="mappin.and.ellipse" title="점검 지점이 없습니다" />
      ) : points.data && (
        <Group>
          {points.data.map((p) => (
            <Row key={p.point_id} rich icon="mappin.and.ellipse" iconColor="var(--teal)" to={`/app/history/${p.point_id}`}
              title={<><PointBadge code={p.code} />{p.name}</>}
              subtitle={<>
                {p.description && <MetaLine><Meta icon="list.bullet">{p.description}</Meta></MetaLine>}
                <MetaLine><Meta icon="photo.on.rectangle">관측 사진 이력 보기</Meta></MetaLine>
              </>} />
          ))}
        </Group>
      )}
    </Page>
  );
}
