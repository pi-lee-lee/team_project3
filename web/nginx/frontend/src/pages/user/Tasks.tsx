import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Badge, ErrorBox, fmtTime, useApi, usePoll } from '../../util';

const TABS: [string | undefined, string][] = [[undefined, '전체'], ['active', '진행 중'], ['done', '완료'], ['failed', '실패·취소']];

/** U3 작업 목록 */
export default function Tasks() {
  const api = useApi();
  const navigate = useNavigate();
  const [group, setGroup] = useState<string | undefined>(undefined);
  const tasks = usePoll(() => api.tasks(group), 2000, [group]);
  return (
    <section>
      <h2>작업 목록</h2>
      <div className="tabs">
        {TABS.map(([g, label]) => (
          <button key={label} className={group === g ? 'on' : ''} onClick={() => setGroup(g)}>{label}</button>
        ))}
      </div>
      <ErrorBox msg={tasks.error} />
      <table className="clickable">
        <thead><tr><th>#</th><th>로봇</th><th>지점</th><th>상태</th><th>관측</th><th>요청자</th><th>요청 시각</th></tr></thead>
        <tbody>
          {tasks.data?.map((t) => (
            <tr key={t.task_id} onClick={() => navigate(`/app/tasks/${t.task_id}`)}>
              <td>{t.task_id}{t.recheck_of && <span className="muted small"> 재점검</span>}</td>
              <td>{t.robot_code}</td><td>{t.points}</td>
              <td><Badge status={t.status} /></td>
              <td>{t.observations}</td>
              <td>{t.requester_login}</td><td>{fmtTime(t.created_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {tasks.data?.length === 0 && <p className="muted">작업이 없습니다.</p>}
    </section>
  );
}
