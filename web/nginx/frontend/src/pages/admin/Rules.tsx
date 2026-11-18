import { useNavigate, useParams } from 'react-router-dom';
import { ErrorBox, fmtTime, useApi, usePoll } from '../../util';
import { Empty, Group, Meta, MetaLine, Page, Row, Tag } from '../../ui';
import { Icon } from '../../Icon';
import { CHECKER_LABEL, GradeTag, valueText } from '../user/scenarioText';
import './admin.css';

/**
 * A3-2 점검 규칙 — 목록. 지점에서 찍은 사진을 무엇으로(판독기) 어떤 기준으로(등급) 볼지 정한다.
 * 규칙을 누르면 수정 화면으로 간다.
 */
export default function Rules() {
  const { id } = useParams<{ id: string }>();
  const pointId = Number(id);
  const api = useApi();
  const nav = useNavigate();
  const points = usePoll(() => api.adminPoints(), 0);
  const rules = usePoll(() => api.pointRules(pointId), 5000, [pointId]);
  const point = points.data?.find((p) => p.point_id === pointId);

  return (
    <Page title="점검 규칙" back={{ to: '/admin/points', label: '점검 지점' }} width="normal"
      sub={point ? `${point.code} ${point.name}` : undefined}
      actions={<button className="nav-icon" aria-label="규칙 추가" title="규칙 추가" onClick={() => nav(`/admin/points/${pointId}/rules/new`)}>
        <Icon name="plus" size={24} /></button>}>
      <ErrorBox msg={rules.error} />
      {rules.data && rules.data.length === 0 && (
        <Empty icon="ruler" title="규칙이 없습니다">오른쪽 위 + 로 규칙을 더하면, 이 지점의 사진을 판독해 정상 · 경고 · 비상으로 나눕니다.</Empty>
      )}
      {!!rules.data?.length && (
        <Group className="admin-list" footer="꺼 둔 규칙은 판독하지 않고, 그 규칙이 열어 둔 경고는 풀립니다.">
          {rules.data.map((r) => (
            <Row key={r.ruleId} to={`/admin/points/${pointId}/rules/${r.ruleId}/edit`} rich className={r.enabled ? '' : 'dim'}
              icon="ruler" iconColor={r.enabled ? 'var(--indigo)' : '#8e8e93'}
              title={<>{r.name}<Tag tone="indigo">{CHECKER_LABEL[r.kind] ?? r.kind}</Tag>
                {!r.enabled && <Tag tone="gray">꺼짐</Tag>}
                {r.target?.useAsReference && <Tag tone="teal" icon="location.fill">위치 기준</Tag>}</>}
              subtitle={<MetaLine>
                {r.latest ? <>
                  <GradeTag grade={r.latest.grade} />
                  <Meta icon="gauge">읽은 값 {valueText(r.latest.value, r.latest.unit)}</Meta>
                  <Meta icon="clock">{fmtTime(r.latest.analyzedAt)}</Meta>
                </> : <Meta icon="clock">아직 판독한 적이 없습니다</Meta>}
              </MetaLine>} />
          ))}
        </Group>
      )}
    </Page>
  );
}
