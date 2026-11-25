import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { ErrorBox, useAction, useApi, usePoll } from '../../util';
import { ActionBar, Empty, Field, Group, Page, Picker, Switch } from '../../ui';
import { MapPicker } from '../../MapPicker';
import './admin.css';

type Form = { code: string; name: string; description: string; x: string; y: string; yawDeg: string; active: boolean; exitZone: string };
// 새 지점은 위치를 비워 둔다(지도를 누르거나 숫자를 넣어야 저장할 수 있다)
const empty: Form = { code: '', name: '', description: '', x: '', y: '', yawDeg: '0', active: true, exitZone: '' };

/** 비상구 앞 구역 칸: "x1, y1, x2, y2" → 숫자 네 개. 비우면 null(일반 지점), 모양이 틀리면 undefined */
function parseZone(text: string): number[] | null | undefined {
  const t = text.replace(/[\[\]]/g, '').trim();
  if (!t) return null;
  const v = t.split(/[\s,]+/).map(Number);
  return v.length === 4 && v.every((n) => !isNaN(n)) ? v : undefined;
}

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
      exitZone: (point.exit_zone ?? '').replace(/[\[\]]/g, ''),
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
  const zone = parseZone(form.exitZone);
  const valid = !!form.code && !!form.name && nums.every((v) => v.trim() !== '' && !isNaN(Number(v))) && zone !== undefined;

  const save = () => act.run(async () => {
    await api.savePoint({
      point_id: pointId, code: form.code, name: form.name, description: form.description || null,
      x: Number(form.x), y: Number(form.y), yawDeg: Number(form.yawDeg), active: form.active, exitZone: zone ?? null,
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

      <Group header="비상구 점검"
        footer={<>비상구 앞 통로를 점검하는 지점이면 그 통로 구역을 지도 좌표로 넣습니다(왼쪽 아래 x1, y1 · 오른쪽 위 x2, y2, m).
          이 지점으로 가는 로봇이 구역 안에서 막히면 돌아가지 않고 바로 '통로 막힘 · 진입 불가'로 끝내고 그 쪽 사진을 올립니다.
          구역 밖에서 막히면 평소처럼 돌아갑니다. 비우면 일반 지점입니다.</>}>
        <Field label="비상구 앞 구역"><input value={form.exitZone} placeholder="비움 = 일반 지점 · 예: 7.15, 3.6, 8.2, 7.2"
          onChange={(e) => set({ exitZone: e.target.value })} /></Field>
        {zone === undefined && <span className="cell muted">숫자 네 개(x1, y1, x2, y2)를 쉼표로 나눠 넣으세요</span>}
      </Group>

      <ErrorBox msg={act.error} />
      <ActionBar>
        <button type="button" onClick={() => nav('/admin/points')}>취소</button>
        <button type="button" className="primary" disabled={act.busy || !valid} onClick={save}>{pointId ? '저장' : '추가'}</button>
      </ActionBar>
    </Page>
  );
}
