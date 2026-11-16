import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ErrorBox, useAction, useApi, usePoll } from '../../util';
import { Icon } from '../../Icon';

/** U2 점검 요청 */
export default function RequestPage() {
  const api = useApi();
  const navigate = useNavigate();
  const robots = usePoll(() => api.robots(), 3000);
  const points = usePoll(() => api.points(), 0);
  const [robotId, setRobotId] = useState<number | null>(null);
  const [order, setOrder] = useState<number[]>([]);
  const [note, setNote] = useState('');
  const act = useAction();

  useEffect(() => {
    if (robotId === null) {
      const r = robots.data?.find((x) => x.enabled && x.connected);
      if (r) setRobotId(r.robotId);
    }
  }, [robots.data, robotId]);

  const toggle = (id: number) => setOrder((o) => (o.includes(id) ? o.filter((x) => x !== id) : [...o, id]));
  const robot = robots.data?.find((r) => r.robotId === robotId);

  return (
    <section className="narrow">
      <h2>점검 요청</h2>
      <label>로봇
        <select value={robotId ?? ''} onChange={(e) => setRobotId(Number(e.target.value))}>
          <option value="" disabled>로봇 선택</option>
          {robots.data?.filter((r) => r.enabled).map((r) => (
            <option key={r.robotId} value={r.robotId} disabled={!r.connected}>
              {r.code} · {r.name} {r.connected ? (r.mission ? '(작업 중)' : '(연결됨)') : '(연결 안 됨)'}
            </option>
          ))}
        </select>
      </label>
      <div className="label">점검 지점 (고른 순서대로 방문)</div>
      <div className="checklist">
        {points.data?.map((p) => {
          const i = order.indexOf(p.point_id);
          return (
            <button key={p.point_id} className={i >= 0 ? 'on' : ''} onClick={() => toggle(p.point_id)}>
              <span className="num">{i >= 0 ? i + 1 : ''}</span> {p.code} {p.name}
              <span className="muted"> ({p.x}, {p.y})</span>
            </button>
          );
        })}
      </div>
      <label>메모<input value={note} onChange={(e) => setNote(e.target.value)} /></label>
      <ErrorBox msg={act.error} />
      {robot?.mission && <div className="warn-t">이 로봇은 작업 #{robot.mission.missionId} 를 수행 중입니다.</div>}
      <button className="primary block" disabled={act.busy || !robotId || order.length === 0}
        onClick={() => act.run(async () => {
          const t = await api.createTask(robotId!, order, note);
          navigate(`/app/tasks/${t.task_id}`);
        })}>
        <Icon name="plus.circle" size={18} />점검 요청
      </button>
      <p className="muted">요청하면 작업 상세 화면으로 이동합니다. 로봇은 출발 전에 연결·위치·카메라를 검사하고, 실패하면 사유를 남깁니다.</p>
    </section>
  );
}
