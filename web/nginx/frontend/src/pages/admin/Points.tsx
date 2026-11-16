import { useState } from 'react';
import type { Point } from '../../api/types';
import { ErrorBox, useAction, useApi, usePoll } from '../../util';

type Form = { point_id?: number; code: string; name: string; description: string; x: string; y: string; yawDeg: string; active: boolean };
const empty: Form = { code: '', name: '', description: '', x: '0', y: '0', yawDeg: '0', active: true };

/** A3 점검 지점 (+ A3-1 지점 수정) */
export default function Points() {
  const api = useApi();
  const points = usePoll(() => api.adminPoints(), 0);
  const act = useAction();
  const [form, setForm] = useState<Form>(empty);

  const edit = (p: Point) => setForm({
    point_id: p.point_id, code: p.code, name: p.name, description: p.description ?? '',
    x: String(p.x), y: String(p.y), yawDeg: String(p.yaw_deg), active: p.active,
  });
  const save = () => act.run(async () => {
    await api.savePoint({
      point_id: form.point_id, code: form.code, name: form.name, description: form.description || null,
      x: Number(form.x), y: Number(form.y), yawDeg: Number(form.yawDeg), active: form.active,
    });
    setForm(empty);
    await points.reload();
  });

  return (
    <section>
      <h2>점검 지점</h2>
      <ErrorBox msg={act.error || points.error} />
      <table>
        <thead><tr><th>코드</th><th>이름</th><th>설명</th><th>x</th><th>y</th><th>방향</th><th>상태</th><th /></tr></thead>
        <tbody>
          {points.data?.map((p) => (
            <tr key={p.point_id} className={p.active ? '' : 'dim'}>
              <td>{p.code}</td><td>{p.name}</td><td className="muted">{p.description}</td>
              <td>{p.x}</td><td>{p.y}</td><td>{p.yaw_deg}°</td>
              <td>{p.active ? '사용' : '비활성'}</td>
              <td><button className="link" onClick={() => edit(p)}>수정</button></td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="card">
        <h3>{form.point_id ? `지점 수정 · ${form.code}` : '지점 추가'}</h3>
        <div className="row wrap">
          <label>코드<input value={form.code} disabled={!!form.point_id} onChange={(e) => setForm({ ...form, code: e.target.value })} size={6} /></label>
          <label>이름<input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></label>
          <label>설명<input value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></label>
          <label>x<input value={form.x} onChange={(e) => setForm({ ...form, x: e.target.value })} size={5} /></label>
          <label>y<input value={form.y} onChange={(e) => setForm({ ...form, y: e.target.value })} size={5} /></label>
          <label>방향(도)<input value={form.yawDeg} onChange={(e) => setForm({ ...form, yawDeg: e.target.value })} size={5} /></label>
          {form.point_id && (
            <label>상태
              <select value={form.active ? '1' : '0'} onChange={(e) => setForm({ ...form, active: e.target.value === '1' })}>
                <option value="1">사용</option><option value="0">비활성</option>
              </select>
            </label>
          )}
        </div>
        <div className="row end">
          {form.point_id && <button onClick={() => setForm(empty)}>취소</button>}
          <button className="primary" disabled={act.busy || !form.code || !form.name} onClick={save}>{form.point_id ? '저장' : '추가'}</button>
        </div>
        <p className="muted">좌표는 로봇 지도 기준(m), 방향은 로봇이 촬영할 때 바라볼 방향(도)입니다. 비활성 지점은 새 요청에서 숨기고 지난 기록은 그대로 둡니다.</p>
      </div>
    </section>
  );
}
