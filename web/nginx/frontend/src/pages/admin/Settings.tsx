import { useEffect, useState } from 'react';
import type { LaunchMode } from '../../api/types';
import { ErrorBox, useAction, useApi, usePoll } from '../../util';
import { Field, Group, Notice, Page, Picker, Segmented } from '../../ui';
import './admin.css';

/**
 * 설정 키의 이름과 설명. 값이 정해지지 않은 항목(사거리 · 열원 기준 등)을 코드가 아니라 여기서 받는다
 * (docs/design/design_02_INTERFACES.md 8장). 서버의 기본값 목록(SettingsService)에 있는 키만 저장된다.
 */
type Kind = 'mode' | 'number' | 'json' | 'robot' | 'bool';
const GROUPS: { header: string; footer?: string; items: [key: string, label: string, kind: Kind, hint: string][] }[] = [
  {
    header: '투척',
    footer: '사건은 만들어질 때의 모드를 갖고 갑니다. 진행 중인 사건은 모드를 바꿔도 그대로입니다.',
    items: [
      ['launch.mode', '투척 모드', 'mode', '사람 승인: 도착 뒤 승인을 기다린다 · 자동 투척: 재판독이 비상이고 조준 범위 안이면 바로 쏜다'],
      ['launch.range_m', '사거리 (m)', 'number', '화재 위치에서 이만큼 떨어진 곳에 선다'],
      ['launch.range_tolerance_m', '사거리 허용 범위 (m)', 'number', '정확한 사거리에 설 자리가 없을 때 이만큼 가깝거나 먼 자리도 후보로 본다'],
      ['launch.aim_tolerance_deg', '조준 범위 (°)', 'number', '대상이 정면에서 이 각도 안에 있어야 자동 투척한다'],
      ['launch.count', '한 번에 쏘는 수', 'number', ''],
      ['launch.search_steps', '재판독 횟수', 'number', '도착 뒤 열원이 안 보이면 이 횟수까지 다시 본다'],
      ['launch.approval_remind_sec', '승인 재알림 간격 (초)', 'number', '0 이면 다시 알리지 않는다'],
      ['launch.params', '기구 추가 값', 'json', '투척 기구가 받는 값(세기 · 각도 등)의 자리. 명령에 그대로 실려 간다'],
    ],
  },
  {
    header: '사건',
    items: [
      ['incident.responder_robot_id', '출동시킬 로봇', 'robot', '비워 두면 연결된 로봇 가운데 한가한 것을 고른다'],
      ['incident.merge_radius_m', '사건 묶음 거리 (m)', 'number', '열린 사건에서 이 거리 안의 감지는 새 사건을 만들지 않는다'],
      ['incident.monitor_interval_sec', '현장 감시 간격 (초)', 'number', '투척 뒤에도 열원이 남으면 대응 로봇이 그 자리에 머물며 이 간격으로 다시 찍어 본다'],
      ['incident.monitor_clear_count', '감시 종료 기준 (연속 정상 횟수)', 'number', '현장 감시 중 연속으로 이만큼 정상이면 열원이 사라진 것으로 보고 사건을 닫는다'],
      ['incident.reopen_grace_sec', '닫은 뒤 다시 여는 유예 (초)', 'number', '사건을 닫은 뒤 이 시간이 지나도 같은 감지가 계속 오면 새 사건으로 다시 연다. 닫는 것은 기록을 닫는 것이지 실제 상황의 종료가 아니다'],
    ],
  },
  {
    header: '판독',
    items: [
      ['detect.thermal', '열화상 기준', 'json', '도착 후 재판독에 쓰는 열화상 판독 설정(params)과 등급 기준(grading). 인쇄물의 색상표 · 열원 기준이 바뀌면 여기를 고친다'],
      ['camera.hfov_deg', '카메라 수평 화각 (°)', 'number', '사진 속 위치를 조준 각도로 바꿀 때 쓴다'],
    ],
  },
  {
    header: '화면',
    footer: '관제 화면(지도 모드)과 대시보드 지도에 함께 적용됩니다. 열려 있는 화면에는 10초 안에 반영됩니다.',
    items: [
      ['display.control_direction', '주행 경로 표시 (제어기 방향)', 'bool', '지도에 제어기가 지금 가려는 방향을 주황 실선과 화살촉으로 그린다. 점선(계획 경로)은 항상 보인다'],
    ],
  },
];
const ONOFF: ['on' | 'off', string][] = [['on', '표시'], ['off', '숨김']];
const MODES: [LaunchMode, string][] = [['APPROVAL', '사람 승인'], ['AUTO', '자동 투척']];

/** A7 설정: 키마다 따로 저장한다. */
export default function Settings() {
  const api = useApi();
  const settings = usePoll(() => api.settings(), 0);
  const robots = usePoll(() => api.adminRobots(), 0);
  const act = useAction();
  /** 고치는 중인 값(글자). 저장하면 서버 값으로 다시 맞춘다 */
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [saved, setSaved] = useState<string | null>(null);

  useEffect(() => {
    if (!settings.data) return;
    const d: Record<string, string> = {};
    Object.entries(settings.data).forEach(([k, v]) => {
      d[k] = v !== null && typeof v === 'object' ? JSON.stringify(v, null, 2) : v === null ? '' : String(v);
    });
    setDraft(d);
  }, [settings.data]);

  const save = (key: string, value: unknown, label: string) => act.run(async () => {
    setSaved(null);
    settings.setData(await api.saveSetting(key, value));
    setSaved(label);
  });
  const changed = (key: string) => {
    const v = settings.data?.[key];
    const cur = v !== null && typeof v === 'object' ? JSON.stringify(v, null, 2) : v === null || v === undefined ? '' : String(v);
    return draft[key] !== undefined && draft[key] !== cur;
  };

  return (
    <Page title="설정" width="narrow">
      <ErrorBox msg={settings.error || act.error} />
      {saved && <Notice tone="ok">"{saved}" 을(를) 저장했습니다.</Notice>}
      {settings.data && GROUPS.map((g) => (
        <Group key={g.header} header={g.header} footer={g.footer}>
          {g.items.filter(([key]) => key in settings.data!).map(([key, label, kind, hint]) => (
            <Field key={key} label={label} stack={kind === 'json'} hint={hint || undefined}>
              {kind === 'mode' ? (
                <Segmented value={(settings.data![key] as LaunchMode) ?? 'APPROVAL'} options={MODES}
                  onChange={(v) => { if (v !== settings.data![key]) save(key, v, label); }} />
              ) : kind === 'bool' ? (
                <Segmented value={settings.data![key] === true ? 'on' : 'off'} options={ONOFF}
                  onChange={(v) => { if ((v === 'on') !== (settings.data![key] === true)) save(key, v === 'on', label); }} />
              ) : kind === 'robot' ? (
                <Picker variant="field" label={label} value={settings.data![key] == null ? 0 : Number(settings.data![key])}
                  onChange={(v) => save(key, v === 0 ? null : v, label)}
                  options={[{ value: 0, label: '자동 선택' }, ...(robots.data ?? []).map((r) => ({ value: r.robotId, label: r.code, sub: r.name }))]} />
              ) : kind === 'json' ? (
                <span className="setting-json">
                  <textarea rows={Math.min(12, (draft[key] ?? '').split('\n').length + 1)} className="mono" spellCheck={false}
                    value={draft[key] ?? ''} onChange={(e) => setDraft({ ...draft, [key]: e.target.value })} />
                  <span className="setting-row">
                    <button type="button" disabled={act.busy || !changed(key)} onClick={() => {
                      let v: unknown;
                      try { v = JSON.parse(draft[key]); } catch { act.setError(`"${label}" 이(가) 올바른 JSON 이 아닙니다`); return; }
                      save(key, v, label);
                    }}>저장</button>
                  </span>
                </span>
              ) : (
                <span className="setting-row">
                  <input type="number" step="any" value={draft[key] ?? ''} onChange={(e) => setDraft({ ...draft, [key]: e.target.value })} />
                  <button type="button" disabled={act.busy || !changed(key) || draft[key].trim() === '' || isNaN(Number(draft[key]))}
                    onClick={() => save(key, Number(draft[key]), label)}>저장</button>
                </span>
              )}
            </Field>
          ))}
        </Group>
      ))}
    </Page>
  );
}
