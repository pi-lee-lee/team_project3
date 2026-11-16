import { useState } from 'react';
import type { RoleInfo, UserRow } from '../../api/types';
import { ErrorBox, fmtTime, useAction, useApi, usePoll } from '../../util';
import { Icon } from '../../Icon';

/** A1 사용자 관리 (+ A1-1 사용자 추가 모달) */
export default function Users() {
  const api = useApi();
  const users = usePoll(() => api.users(), 0);
  const roles = usePoll(() => api.roles(), 0);
  const act = useAction();
  const [adding, setAdding] = useState(false);

  const change = (fn: () => Promise<unknown>) => act.run(async () => { await fn(); await users.reload(); });

  return (
    <section>
      <div className="row between">
        <h2>사용자 관리</h2>
        <button className="primary" onClick={() => setAdding(true)}><Icon name="plus" size={16} />사용자 추가</button>
      </div>
      <ErrorBox msg={act.error || users.error} />
      <table>
        <thead>
          <tr><th>아이디</th><th>이름</th><th>역할</th><th>상태</th><th>마지막 로그인</th><th>작업</th></tr>
        </thead>
        <tbody>
          {users.data?.map((u) => (
            <tr key={u.userId}>
              <td>{u.loginId}</td>
              <td>{u.name}</td>
              <td>
                <select value={u.roleId} disabled={act.busy}
                  onChange={(e) => change(() => api.updateUser(u.userId, { roleId: Number(e.target.value) }))}>
                  {roles.data?.map((r) => <option key={r.roleId} value={r.roleId}>{r.roleId} {r.name}</option>)}
                </select>
              </td>
              <td className={u.status === 'ACTIVE' ? 'ok' : 'bad'}>{u.status === 'ACTIVE' ? '활성' : '정지'}</td>
              <td>{fmtTime(u.lastLoginAt)}</td>
              <td className="actions">
                <button className="link" disabled={act.busy}
                  onClick={() => change(() => api.updateUser(u.userId, { status: u.status === 'ACTIVE' ? 'SUSPENDED' : 'ACTIVE' }))}>
                  {u.status === 'ACTIVE' ? '정지' : '해제'}
                </button>
                <button className="link" disabled={act.busy} onClick={() => change(() => api.revokeSessions(u.userId))}>
                  세션 종료
                </button>
                <button className="link" disabled={act.busy} onClick={() => {
                  const pw = prompt(`${u.loginId} 의 새 비밀번호 (8자 이상)`);
                  if (pw) change(() => api.resetPassword(u.userId, pw));
                }}>비밀번호 재설정</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="muted">역할·상태를 바꾸거나 세션을 종료하면 그 사용자의 기존 로그인은 10초 안에 끊깁니다.</p>
      {adding && roles.data && (
        <AddUser roles={roles.data} onClose={() => setAdding(false)} onSaved={() => { setAdding(false); users.reload(); }} />
      )}
    </section>
  );
}

function AddUser({ roles, onClose, onSaved }: { roles: RoleInfo[]; onClose: () => void; onSaved: (u: UserRow) => void }) {
  const api = useApi();
  const [f, setF] = useState({ loginId: '', name: '', password: '', roleId: 3 });
  const act = useAction();
  return (
    <div className="modal-bg" onClick={onClose}>
      <form className="modal" onClick={(e) => e.stopPropagation()}
        onSubmit={(e) => { e.preventDefault(); act.run(async () => onSaved(await api.createUser(f))); }}>
        <h3>사용자 추가</h3>
        <label>아이디<input value={f.loginId} onChange={(e) => setF({ ...f, loginId: e.target.value })} /></label>
        <label>이름<input value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} /></label>
        <label>비밀번호 (8자 이상)<input type="password" value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} /></label>
        <label>역할
          <select value={f.roleId} onChange={(e) => setF({ ...f, roleId: Number(e.target.value) })}>
            {roles.map((r) => <option key={r.roleId} value={r.roleId}>{r.roleId} {r.name}</option>)}
          </select>
        </label>
        <ErrorBox msg={act.error} />
        <div className="row end">
          <button type="button" onClick={onClose}>취소</button>
          <button className="primary" disabled={act.busy}>저장</button>
        </div>
      </form>
    </div>
  );
}
