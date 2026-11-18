import { Link, useNavigate } from 'react-router-dom';
import type { UserRow } from '../../api/types';
import { ErrorBox, ROLE_LABEL, fmtTime, useApi, usePoll } from '../../util';
import { Avatar, Empty, Group, Meta, MetaLine, Page, Tag } from '../../ui';
import type { Tone } from '../../ui';
import { Icon } from '../../Icon';
import './admin.css';

/** 역할별 색: 권한이 클수록 진한 색 */
const ROLE_TONE: Record<string, Tone> = { ADMIN: 'purple', SUPERVISOR: 'indigo', MANAGER: 'blue', USER: 'teal' };

/**
 * 사용자 한 칸. 공통 Row 는 앞쪽에 아이콘 타일만 받으므로, 이름 첫 글자 아바타를 앞에 두려고 같은 칸 구조(.cell.rich)를 직접 그린다.
 */
function UserCell({ u }: { u: UserRow }) {
  const active = u.status === 'ACTIVE';
  const tone = ROLE_TONE[u.role] ?? 'gray';
  return (
    <Link className={`cell tappable rich ${active ? '' : 'dim'}`} to={`/admin/users/${u.userId}`}>
      <Avatar name={u.name} tone={active ? tone : 'gray'} />
      <span className="cell-main">
        <span className="cell-title">
          {u.name}
          <Tag tone={tone}>{ROLE_LABEL[u.role] ?? u.roleName}</Tag>
          <Tag tone={active ? 'green' : 'red'}>{active ? '활성' : '정지'}</Tag>
        </span>
        <span className="cell-sub">
          <MetaLine>
            <Meta icon="person.crop.circle">{u.loginId}</Meta>
            <Meta icon="clock">{u.lastLoginAt ? `마지막 로그인 ${fmtTime(u.lastLoginAt)}` : '로그인 기록 없음'}</Meta>
          </MetaLine>
        </span>
      </span>
      <Icon name="chevron.right" size={20} className="chev" />
    </Link>
  );
}

/** A1 사용자 관리 — 목록. 사용자를 누르면 상세(역할·상태·보안)로 간다. */
export default function Users() {
  const api = useApi();
  const nav = useNavigate();
  const users = usePoll(() => api.users(), 0);

  return (
    <Page title="사용자" width="normal"
      actions={<button className="nav-icon" aria-label="사용자 추가" title="사용자 추가" onClick={() => nav('/admin/users/new')}>
        <Icon name="plus" size={24} /></button>}>
      <ErrorBox msg={users.error} />
      {users.data && users.data.length === 0 && <Empty icon="person.2" title="사용자가 없습니다" />}
      {!!users.data?.length && (
        <Group className="admin-list" footer="역할·상태를 바꾸거나 세션을 종료하면 그 사용자의 기존 로그인은 10초 안에 끊깁니다.">
          {users.data.map((u) => <UserCell key={u.userId} u={u} />)}
        </Group>
      )}
    </Page>
  );
}
