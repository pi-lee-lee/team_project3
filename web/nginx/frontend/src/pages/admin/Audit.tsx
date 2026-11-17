import { useState } from 'react';
import type { AuditRow } from '../../api/types';
import { ErrorBox, ROLE_LABEL, fmtTime, useApi, usePoll } from '../../util';
import { Empty, Field, Group, Meta, MetaLine, Page, Picker, Row, Tag } from '../../ui';
import type { Tone } from '../../ui';
import { Icon } from '../../Icon';
import './admin.css';

/** 역할별 색(사용자 목록과 같은 색) */
const ROLE_TONE: Record<string, Tone> = { ADMIN: 'purple', SUPERVISOR: 'indigo', MANAGER: 'blue', USER: 'teal' };

/** 결과: 실패(4xx·5xx 또는 동작 이름에 FAILED) / 성공 / 알 수 없음 */
function outcome(r: AuditRow): 'ok' | 'fail' | 'none' {
  if (r.action.includes('FAILED') || (r.status !== null && r.status >= 400)) return 'fail';
  return r.status !== null ? 'ok' : 'none';
}

/** HTTP 응답 코드 색: 2xx 초록, 4xx 주황, 5xx 빨강, 그 밖은 회색 */
function statusTone(s: number): Tone {
  if (s >= 500) return 'red';
  if (s >= 400) return 'orange';
  if (s >= 200 && s < 300) return 'green';
  return 'gray';
}

const OUTCOME_ICON = {
  ok: { icon: 'checkmark.circle.fill', color: 'var(--green)' },
  fail: { icon: 'xmark.circle.fill', color: 'var(--red)' },
  none: { icon: 'list.bullet.clipboard', color: '#8e8e93' },
};

/** A5 감사 로그 (읽기 전용) */
export default function Audit() {
  const api = useApi();
  const rows = usePoll(() => api.audit(), 0);
  const [who, setWho] = useState('');
  const [action, setAction] = useState('');
  const list = (rows.data ?? []).filter(
    (r) => (!who || (r.login_id ?? '').includes(who)) && (!action || r.action === action),
  );
  const actions = [...new Set((rows.data ?? []).map((r) => r.action))].sort();

  return (
    <Page title="감사 로그" width="normal"
      actions={<button className="nav-icon" aria-label="새로고침" title="새로고침" onClick={rows.reload}>
        <Icon name="arrow.clockwise" size={22} /></button>}>
      <Group header="필터">
        <Field label="사용자"><input value={who} placeholder="아이디 일부" autoComplete="off" onChange={(e) => setWho(e.target.value)} /></Field>
        <Field label="동작">
          <Picker variant="field" label="동작" value={action} onChange={setAction}
            options={[{ value: '', label: '전체' }, ...actions.map((a) => ({ value: a, label: a }))]} />
        </Field>
      </Group>

      <ErrorBox msg={rows.error} />
      {rows.data && list.length === 0 && <Empty icon="list.bullet.clipboard" title="기록이 없습니다" />}
      {list.length > 0 && (
        <Group className="admin-list" header={`${list.length}건`}
          footer="변경 요청(POST·PUT·PATCH·DELETE)과 로그인 성공·실패를 게이트웨이와 사용자 서비스가 기록합니다. 기록은 수정·삭제하지 않습니다.">
          {list.map((r) => {
            const o = outcome(r);
            return (
              <Row key={r.audit_id} rich icon={OUTCOME_ICON[o].icon} iconColor={OUTCOME_ICON[o].color}
                title={<>
                  <span className={`audit-action ${o === 'fail' ? 'bad' : ''}`}>{r.action}</span>
                  {r.status !== null && <Tag tone={statusTone(r.status)}>{r.status}</Tag>}
                </>}
                subtitle={<>
                  <MetaLine>
                    <Meta icon="person.crop.circle" strong={!!r.login_id}>{r.login_id ?? '알 수 없음'}</Meta>
                    {r.role_code && <Tag tone={ROLE_TONE[r.role_code] ?? 'gray'}>{ROLE_LABEL[r.role_code] ?? r.role_code}</Tag>}
                    <Meta icon="clock">{fmtTime(r.occurred_at)}</Meta>
                  </MetaLine>
                  {r.target && <span className="mono audit-target" title={r.target}>{r.target}</span>}
                </>} />
            );
          })}
        </Group>
      )}
    </Page>
  );
}
