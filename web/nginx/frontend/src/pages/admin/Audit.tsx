import { useState } from 'react';
import { ErrorBox, ROLE_LABEL, fmtTime, useApi, usePoll } from '../../util';

/** A5 감사 로그 */
export default function Audit() {
  const api = useApi();
  const rows = usePoll(() => api.audit(), 0);
  const [who, setWho] = useState('');
  const [action, setAction] = useState('');
  const list = (rows.data ?? []).filter(
    (r) => (!who || (r.login_id ?? '').includes(who)) && (!action || r.action === action),
  );
  const actions = [...new Set((rows.data ?? []).map((r) => r.action))];
  return (
    <section>
      <div className="row between">
        <h2>감사 로그</h2>
        <div className="row">
          <input placeholder="사용자" value={who} onChange={(e) => setWho(e.target.value)} size={10} />
          <select value={action} onChange={(e) => setAction(e.target.value)}>
            <option value="">동작 전체</option>
            {actions.map((a) => <option key={a}>{a}</option>)}
          </select>
          <button onClick={rows.reload}>새로고침</button>
        </div>
      </div>
      <ErrorBox msg={rows.error} />
      <table>
        <thead><tr><th>시각</th><th>사용자</th><th>역할</th><th>동작</th><th>대상</th><th>결과</th></tr></thead>
        <tbody>
          {list.map((r) => (
            <tr key={r.audit_id}>
              <td>{fmtTime(r.occurred_at)}</td><td>{r.login_id ?? '-'}</td>
              <td>{r.role_code ? ROLE_LABEL[r.role_code] ?? r.role_code : '-'}</td>
              <td className={r.action.includes('FAILED') ? 'bad' : ''}>{r.action}</td>
              <td className="mono">{r.target}</td>
              <td className={r.status && r.status >= 400 ? 'bad' : ''}>{r.status ?? '-'}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="muted">변경 요청(POST·PUT·PATCH·DELETE)과 로그인 성공·실패를 게이트웨이와 사용자 서비스가 기록합니다. 기록은 수정·삭제하지 않습니다.</p>
    </section>
  );
}
