import { Link } from 'react-router-dom';
import { ago, useApi, usePoll } from '../../util';
import { Icon } from '../../Icon';
import { INCIDENT_STATE } from './scenarioText';

/**
 * 열린 사건(화재 대응)이 있으면 사용자 화면 맨 위에 알린다(3초마다 확인).
 * 투척 승인을 기다리는 사건이 있으면 더 진하게 보인다 — 사람이 눌러야 다음으로 넘어가기 때문이다.
 */
export default function IncidentBanner() {
  const api = useApi();
  const q = usePoll(() => api.incidents(true), 3000);
  const list = q.data ?? [];
  if (!list.length) return null;
  const waiting = list.filter((i) => i.state === 'AWAITING_APPROVAL');
  return (
    <div className={`incident-banner ${waiting.length ? 'wait' : ''}`} role="alert">
      <Icon name="flame.fill" size={18} />
      {waiting.length ? `투척 승인 대기 ${waiting.length}건` : `진행 중인 화재 사건 ${list.length}건`}
      {(waiting.length ? waiting : list).slice(0, 3).map((i) => (
        <span className="item" key={i.incidentId}>
          · <Link to={`/app/incidents/${i.incidentId}`}>사건 #{i.incidentId}</Link> {INCIDENT_STATE[i.state]?.[0]} ({ago(i.createdAt)})
        </span>
      ))}
      <span className="grow" />
      <Link to="/app/incidents">사건 보기</Link>
    </div>
  );
}
