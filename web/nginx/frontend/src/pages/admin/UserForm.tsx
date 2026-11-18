import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ErrorBox, useAction, useApi, usePoll } from '../../util';
import { ActionBar, Field, Group, Page, Picker } from '../../ui';
import './admin.css';

/** A1-1 사용자 추가 */
export default function UserForm() {
  const api = useApi();
  const nav = useNavigate();
  const roles = usePoll(() => api.roles(), 0);
  const act = useAction();
  const [f, setF] = useState({ loginId: '', name: '', password: '', roleId: 3 });
  const valid = !!f.loginId && !!f.name && f.password.length >= 8;

  const save = () => act.run(async () => {
    await api.createUser(f);
    nav('/admin/users');
  });

  return (
    <Page title="사용자 추가" width="narrow" back={{ to: '/admin/users', label: '사용자' }}>
      <form onSubmit={(e) => { e.preventDefault(); if (valid) save(); }}>
        <Group>
          <Field label="아이디"><input value={f.loginId} autoComplete="off" placeholder="필수"
            onChange={(e) => setF({ ...f, loginId: e.target.value })} /></Field>
          <Field label="이름"><input value={f.name} placeholder="필수" onChange={(e) => setF({ ...f, name: e.target.value })} /></Field>
          <Field label="비밀번호" hint="8자 이상"><input type="password" value={f.password} autoComplete="new-password"
            onChange={(e) => setF({ ...f, password: e.target.value })} /></Field>
          <Field label="역할">
            <Picker variant="field" label="역할" value={f.roleId} onChange={(v) => setF({ ...f, roleId: v })}
              options={(roles.data ?? [{ roleId: 3, code: 'USER' as const, name: '사용자' }]).map((r) =>
                ({ value: r.roleId, label: r.name, sub: `${r.roleId} · ${r.code}` }))} />
          </Field>
        </Group>
        <ErrorBox msg={act.error || roles.error} />
        <ActionBar>
          <button type="button" onClick={() => nav('/admin/users')}>취소</button>
          <button type="submit" className="primary" disabled={act.busy || !valid}>저장</button>
        </ActionBar>
      </form>
    </Page>
  );
}
