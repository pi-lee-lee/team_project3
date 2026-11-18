import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import type { ScheduleInput, ScheduleKind } from '../../../api/types';
import { ErrorBox, useAction, useApi, usePoll } from '../../../util';
import { ActionBar, Field, Group, Page, Picker, Row, Segmented, Switch } from '../../../ui';
import { DAYS, KIND_LABEL } from './planText';

type Form = {
  name: string; robotId: number | null; order: number[]; note: string; kind: ScheduleKind;
  runAt: string; intervalMinutes: string; timeOfDay: string; days: number[]; useWindow: boolean;
  windowStart: string; windowEnd: string; enabled: boolean;
};
const empty: Form = {
  name: '', robotId: null, order: [], note: '', kind: 'MANUAL', runAt: '', intervalMinutes: '60', timeOfDay: '09:00',
  days: [1, 2, 3, 4, 5], useWindow: false, windowStart: '09:00', windowEnd: '18:00', enabled: true,
};

const KIND_HELP: Record<ScheduleKind, string> = {
  MANUAL: '정해 둔 시각 없이, 실행 버튼을 누를 때만 점검합니다.',
  ONCE: '정한 일시에 한 번 점검합니다.',
  INTERVAL: '정한 간격마다 점검합니다. 요일·시간대를 정하면 그 안에서만 실행합니다.',
  DAILY: '매일 정한 시각에 점검합니다.',
  WEEKLY: '고른 요일의 정한 시각에 점검합니다.',
};

/** 점검 (만들기·편집): 이름·로봇 → 점검 구간(방문 순서) → 실행 시각 */
export default function PlanForm() {
  const { id } = useParams();
  const editId = id ? Number(id) : null;
  const api = useApi();
  const navigate = useNavigate();
  const robots = usePoll(() => api.robots(), 0);
  const points = usePoll(() => api.points(), 0);
  const zone = usePoll(() => api.schedules().then((x) => x.zone), 0);
  const act = useAction();
  const [f, setF] = useState<Form>(empty);
  const [loaded, setLoaded] = useState(editId === null);
  const set = (patch: Partial<Form>) => setF((x) => ({ ...x, ...patch }));

  useEffect(() => {
    if (editId === null) return;
    act.run(async () => {
      const s = await api.schedule(editId);
      setF({
        name: s.name, robotId: s.robot_id, order: s.point_ids, note: s.note ?? '', kind: s.kind,
        runAt: s.run_at_local ?? '', intervalMinutes: String(s.interval_minutes ?? 60), timeOfDay: s.time_of_day ?? '09:00',
        days: s.days_of_week ?? [], useWindow: !!s.window_start, windowStart: s.window_start ?? '09:00',
        windowEnd: s.window_end ?? '18:00', enabled: s.kind === 'MANUAL' ? true : s.enabled,
      });
      setLoaded(true);
    });
  }, [editId]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (f.robotId === null && robots.data?.length) {
      const r = robots.data.find((x) => x.enabled && x.connected) ?? robots.data.find((x) => x.enabled);
      if (r) set({ robotId: r.robotId });
    }
  }, [robots.data, f.robotId]);

  const togglePoint = (pid: number) => set({ order: f.order.includes(pid) ? f.order.filter((x) => x !== pid) : [...f.order, pid] });
  const toggleDay = (d: number) => set({ days: f.days.includes(d) ? f.days.filter((x) => x !== d) : [...f.days, d].sort() });

  const body = (): ScheduleInput => {
    const k = f.kind;
    return {
      name: f.name.trim(), robotId: f.robotId!, pointIds: f.order, note: f.note, kind: k, enabled: f.enabled,
      runAt: k === 'ONCE' || k === 'INTERVAL' ? f.runAt || null : null,
      intervalMinutes: k === 'INTERVAL' ? Number(f.intervalMinutes) : null,
      timeOfDay: k === 'DAILY' || k === 'WEEKLY' ? f.timeOfDay : null,
      daysOfWeek: k === 'WEEKLY' || (k === 'INTERVAL' && f.days.length < 7) ? f.days : [],
      windowStart: k === 'INTERVAL' && f.useWindow ? f.windowStart : null,
      windowEnd: k === 'INTERVAL' && f.useWindow ? f.windowEnd : null,
    };
  };

  const save = (runAfter: boolean) => act.run(async () => {
    const s = await api.saveSchedule(body(), editId ?? undefined);
    if (!runAfter) {
      navigate(`/app/plans/${s.schedule_id}`, { replace: true });
      return;
    }
    const r = await api.runSchedule(s.schedule_id);
    if (r.outcome === 'CREATED' && r.taskId) navigate(`/app/tasks/${r.taskId}`, { replace: true });
    else navigate(`/app/plans/${s.schedule_id}`, {
      replace: true,
      state: { notice: r.outcome === 'QUEUED' ? `대기열에 담았습니다 — ${r.reason ?? '로봇이 비면'} · 끝나면 이어서 실행합니다` : `실행 실패: ${r.reason ?? r.outcome}` },
    });
  });

  const ready = !!f.name.trim() && !!f.robotId && f.order.length > 0;
  const back = editId ? { to: `/app/plans/${editId}`, label: f.name || '점검' } : { to: '/app/plans', label: '점검' };

  return (
    <Page title={editId ? '점검 편집' : '새 점검'} back={back} width="narrow">
      <ErrorBox msg={act.error} />
      {loaded && <>
        <Group>
          <Field label="이름"><input value={f.name} onChange={(e) => set({ name: e.target.value })} placeholder="예: 평일 아침 순회" /></Field>
          <Field label="로봇">
            <Picker variant="field" label="로봇" value={f.robotId} onChange={(v) => set({ robotId: v })}
              options={(robots.data ?? []).filter((r) => r.enabled).map((r) => ({
                value: r.robotId, label: `${r.code} · ${r.name}`, sub: r.connected ? (r.mission ? '작업 중' : '연결됨') : '연결 안 됨',
              }))} />
          </Field>
          <Field label="메모"><input value={f.note} onChange={(e) => set({ note: e.target.value })} placeholder="선택" /></Field>
        </Group>

        <Group header={<>점검 구간 · 고른 순서대로 방문{f.order.length > 0 && <button onClick={() => set({ order: [] })}>모두 해제</button>}</>}
          footer="지점을 누른 순서가 로봇이 방문하는 순서입니다. 다시 누르면 빠집니다.">
          {points.data?.map((p) => {
            const i = f.order.indexOf(p.point_id);
            return (
              <Row key={p.point_id} onClick={() => togglePoint(p.point_id)}
                title={<span className="row"><span className={`order-num ${i < 0 ? 'off' : ''}`}>{i >= 0 ? i + 1 : ''}</span>{p.code} {p.name}</span>}
                subtitle={p.description ?? undefined} />
            );
          })}
        </Group>

        <Group header="실행 시각" footer={<>{KIND_HELP[f.kind]} 시각은 {zone.data ?? 'Asia/Seoul'} 기준입니다.
          로봇이 다른 작업 중이면 건너뛰지 않고 기다렸다가 이어서 실행합니다.</>}>
          <div className="cell">
            <Segmented<ScheduleKind> full value={f.kind} onChange={(k) => set({ kind: k })}
              options={(Object.keys(KIND_LABEL) as ScheduleKind[]).map((k) => [k, KIND_LABEL[k]])} />
          </div>
          {f.kind === 'ONCE' && (
            <Field label="실행 일시"><input type="datetime-local" value={f.runAt} onChange={(e) => set({ runAt: e.target.value })} /></Field>
          )}
          {f.kind === 'INTERVAL' && <>
            <Field label="간격(분)" hint="5분 이상"><input type="number" min={5} step={5} value={f.intervalMinutes} onChange={(e) => set({ intervalMinutes: e.target.value })} /></Field>
            <Field label="첫 실행" hint="비우면 지금부터 간격 뒤"><input type="datetime-local" value={f.runAt} onChange={(e) => set({ runAt: e.target.value })} /></Field>
            <Field label="시간대 제한"><Switch label="시간대 제한" checked={f.useWindow} onChange={(v) => set({ useWindow: v })} /></Field>
            {f.useWindow && <>
              <Field label="부터"><input type="time" value={f.windowStart} onChange={(e) => set({ windowStart: e.target.value })} /></Field>
              <Field label="까지"><input type="time" value={f.windowEnd} onChange={(e) => set({ windowEnd: e.target.value })} /></Field>
            </>}
          </>}
          {(f.kind === 'DAILY' || f.kind === 'WEEKLY') && (
            <Field label="시각"><input type="time" value={f.timeOfDay} onChange={(e) => set({ timeOfDay: e.target.value })} /></Field>
          )}
          {(f.kind === 'WEEKLY' || f.kind === 'INTERVAL') && (
            <div className="cell field">
              <span className="field-label">요일</span>
              <span className="days">
                {DAYS.map((d, i) => (
                  <button key={d} type="button" className={f.days.includes(i + 1) ? 'on' : ''} onClick={() => toggleDay(i + 1)}>{d}</button>
                ))}
              </span>
            </div>
          )}
          {f.kind !== 'MANUAL' && (
            <Field label="자동 실행"><Switch label="자동 실행" checked={f.enabled} onChange={(v) => set({ enabled: v })} /></Field>
          )}
        </Group>

        <ActionBar>
          <button onClick={() => navigate(back.to)}>취소</button>
          <button className={editId ? 'primary' : ''} disabled={act.busy || !ready} onClick={() => save(false)}>저장</button>
          {!editId && <button className="primary" disabled={act.busy || !ready} onClick={() => save(true)}>저장하고 실행</button>}
        </ActionBar>
      </>}
    </Page>
  );
}
