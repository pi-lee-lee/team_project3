import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { ErrorBox, useAction, useApi, usePoll } from '../../util';
import { ActionBar, Empty, Field, Group, Page, Picker, Switch } from '../../ui';
import { MapPicker } from '../../MapPicker';
import './admin.css';

type Form = { code: string; name: string; description: string; x: string; y: string; yawDeg: string; active: boolean };
// 새 지점은 위치를 비워 둔다(지도를 누르거나 숫자를 넣어야 저장할 수 있다)
const empty: Form = { code: '', name: '', description: '', x: '', y: '', yawDeg: '0', active: true };

/** A3 지점 추가 · A3-1 지점 수정 */
export default function PointForm() {
  const { id } = useParams<{ id: string }>();
  const pointId = id ? Number(id) : undefined;
  const api = useApi();
  const nav = useNavigate();
  const points = usePoll(() => api.adminPoints(), 0, [pointId]);
  const robots = usePoll(() => api.adminRobots(), 0);
  const [robotId, setRobotId] = useState<number | null>(null);
  useEffect(() => {
    if (robotId === null && robots.data?.length) {
      const r = robots.data.find((x) => x.enabled && x.connected) ?? robots.data.find((x) => x.enabled) ?? robots.data[0];
      setRobotId(r.robotId);
    }
  }, [robots.data, robotId]);
  const act = useAction();
  const [form, setForm] = useState<Form>(empty);
  const [loaded, setLoaded] = useState(!pointId);
  const set = (patch: Partial<Form>) => setForm((f) => ({ ...f, ...patch }));

  const point = pointId ? points.data?.find((p) => p.point_id === pointId) : undefined;
  useEffect(() => {
    if (!point || loaded) return;
    setForm({
      code: point.code, name: point.name, description: point.description ?? '',
      x: String(point.x), y: String(point.y), yawDeg: String(point.yaw_deg), active: point.active,
    });
    setLoaded(true);
  }, [point, loaded]);

  const back = { to: '/admin/points', label: '점검 지점' };
  // 지도에 그릴 현재 값(숫자 칸이 올바를 때만). 지도에서 고르면 숫자 칸이 바뀌고, 숫자 칸을 고치면 지도 표시가 따라온다
  const pick = [form.x, form.y, form.yawDeg].every((v) => v.trim() !== '' && !isNaN(Number(v)))
    ? { x: Number(form.x), y: Number(form.y), yawDeg: Number(form.yawDeg) } : null;
  const others = (points.data ?? []).filter((p) => p.point_id !== pointId);
  const title = pointId ? '지점 수정' : '지점 추가';
  const nums = [form.x, form.y, form.yawDeg];
  const valid = !!form.code && !!form.name && nums.every((v) => v.trim() !== '' && !isNaN(Number(v)));

  const save = () => act.run(async () => {
    await api.savePoint({
      point_id: pointId, code: form.code, name: form.name, description: form.description || null,
      x: Number(form.x), y: Number(form.y), yawDeg: Number(form.yawDeg), active: form.active,
    });
    nav('/admin/points');
  });

  if (pointId && !loaded) {
    return (
      <Page title={title} width="narrow" back={back}>
        <ErrorBox msg={points.error} />
        {points.data && !point && <Empty icon="mappin.and.ellipse" title="지점을 찾을 수 없습니다" />}
      </Page>
    );
  }

  return (
    <Page title={title} sub={pointId ? `${form.code}` : undefined} width="normal" back={back}>
      <Group>
        <Field label="코드"><input value={form.code} disabled={!!pointId} placeholder="P4" autoComplete="off"
          onChange={(e) => set({ code: e.target.value })} /></Field>
        <Field label="이름"><input value={form.name} placeholder="필수" onChange={(e) => set({ name: e.target.value })} /></Field>
        <Field label="설명"><input value={form.description} placeholder="선택" onChange={(e) => set({ description: e.target.value })} /></Field>
      </Group>

      <Group header={<>지도에서 고르기
          {(robots.data?.length ?? 0) > 1 && (
            <Picker label="지도" icon="cpu" value={robotId} onChange={setRobotId}
              options={(robots.data ?? []).map((r) => ({ value: r.robotId, label: r.code, sub: r.connected ? '연결됨' : '연결 안 됨' }))} />
          )}</>}
        footer={<>지도를 누르면 그 자리가 지점 위치, 누른 채 끌면 끈 방향이 로봇이 촬영할 때 바라볼 방향입니다.
          보라색이 지금 지점, 청록색은 다른 지점, 파란 점은 로봇의 현재 위치입니다. 좌표는 관제 지도와 같은 변환식(지도 칸 기준)을 씁니다.</>}>
        <div className="cell map-cell">
          {robotId !== null
            ? <MapPicker robotId={robotId} value={pick} code={form.code || undefined} others={others}
                onChange={(v) => set({ x: v.x.toFixed(2), y: v.y.toFixed(2), yawDeg: String(v.yawDeg) })} />
            : <span className="muted">등록된 로봇이 없어 지도를 표시할 수 없습니다</span>}
        </div>
      </Group>

      <Group header="위치 · 방향"
        footer="좌표는 로봇 지도 기준(m), 방향은 오른쪽(+x)이 0°, 반시계 방향이 + 입니다. 비활성 지점은 새 점검에서 숨기고 지난 기록은 그대로 둡니다.">
        <Field label="x (m)"><input value={form.x} placeholder="지도에서 고르기" onChange={(e) => set({ x: e.target.value })} /></Field>
        <Field label="y (m)"><input value={form.y} placeholder="지도에서 고르기" onChange={(e) => set({ y: e.target.value })} /></Field>
        <Field label="방향 (도)"><input value={form.yawDeg} onChange={(e) => set({ yawDeg: e.target.value })} /></Field>
        {pointId && (
          <Field label="사용"><Switch label="사용" checked={form.active} onChange={(v) => set({ active: v })} /></Field>
        )}
      </Group>

      <ErrorBox msg={act.error} />
      <ActionBar>
        <button type="button" onClick={() => nav('/admin/points')}>취소</button>
        <button type="button" className="primary" disabled={act.busy || !valid} onClick={save}>{pointId ? '저장' : '추가'}</button>
      </ActionBar>
    </Page>
  );
}
