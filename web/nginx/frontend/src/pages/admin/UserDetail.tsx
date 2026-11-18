import { useState } from 'react';
import { useParams } from 'react-router-dom';
import { ErrorBox, ROLE_LABEL, fmtTime, useAction, useApi, usePoll } from '../../util';
import { Empty, Field, Group, Notice, Page, Picker, Row, Switch } from '../../ui';
import './admin.css';

/** A1 사용자 상세: 정보 · 역할 · 상태 · 보안(비밀번호 재설정, 세션 종료). 바꾸면 바로 저장된다. */
export default function UserDetail() {
  const { id } = useParams<{ id: string }>();
  const userId = Number(id);
  const api = useApi();
  const users = usePoll(() => api.users(), 0);
  const roles = usePoll(() => api.roles(), 0);
  const act = useAction();
  const [pw, setPw] = useState('');
  const [msg, setMsg] = useState<string | null>(null);
  const back = { to: '/admin/users', label: '사용자' };

  const u = users.data?.find((x) => x.userId === userId);
  const change = (fn: () => Promise<unknown>, done?: string) => act.run(async () => {
    setMsg(null);
    await fn();
    await users.reload();
    if (done) setMsg(done);
  });

  if (!users.data) return <Page title="사용자" width="narrow" back={back}><ErrorBox msg={users.error} /></Page>;
  if (!u) return <Page title="사용자" width="narrow" back={back}><Empty icon="person.crop.circle" title="사용자를 찾을 수 없습니다" /></Page>;

  return (
    <Page title={u.name} width="narrow" back={back}>
      <ErrorBox msg={act.error || users.error} />
      {msg && <Notice tone="ok">{msg}</Notice>}

      <Group header="정보">
        <Row title="아이디" detail={u.loginId} />
        <Row title="이름" detail={u.name} />
        <Row title="가입" detail={fmtTime(u.createdAt)} />
        <Row title="마지막 로그인" detail={fmtTime(u.lastLoginAt)} />
      </Group>

      <Group header="권한">
        <Field label="역할">
          <Picker variant="field" label="역할" value={u.roleId} disabled={act.busy}
            onChange={(v) => change(() => api.updateUser(u.userId, { roleId: v }), '역할을 바꿨습니다.')}
            options={(roles.data ?? [{ roleId: u.roleId, code: u.role, name: ROLE_LABEL[u.role] ?? u.roleName }]).map((r) =>
              ({ value: r.roleId, label: r.name, sub: `${r.roleId} · ${r.code}` }))} />
        </Field>
        <Field label="사용" hint={u.status === 'ACTIVE' ? '활성' : '정지됨'}>
          <Switch label="계정 사용" checked={u.status === 'ACTIVE'} disabled={act.busy}
            onChange={(on) => change(() => api.updateUser(u.userId, { status: on ? 'ACTIVE' : 'SUSPENDED' }),
              on ? '계정을 다시 사용하게 했습니다.' : '계정을 정지했습니다.')} />
        </Field>
      </Group>

      <Group header="보안" footer="역할·상태를 바꾸거나 세션을 종료하면 그 사용자의 기존 로그인은 10초 안에 끊깁니다.">
        <Field label="새 비밀번호" hint="8자 이상">
          <span className="inline-input">
            <input type="password" value={pw} autoComplete="new-password" placeholder="입력"
              onChange={(e) => setPw(e.target.value)} />
            <button type="button" className="pill-btn" disabled={act.busy || pw.length < 8}
              onClick={(e) => {
                e.preventDefault();
                change(async () => { await api.resetPassword(u.userId, pw); setPw(''); }, '비밀번호를 재설정했습니다.');
              }}>저장</button>
          </span>
        </Field>
        <Row destructive title="세션 종료" onClick={() => {
          if (act.busy) return;
          if (confirm(`${u.loginId} 의 모든 로그인 세션을 종료할까요?`)) {
            change(() => api.revokeSessions(u.userId), '세션을 종료했습니다.');
          }
        }} />
      </Group>
    </Page>
  );
}
