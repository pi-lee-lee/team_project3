import { ErrorBox, useApi, usePoll } from '../../util';

const age = (v: number | null | undefined) => (v === null || v === undefined ? '수신 없음' : `${(v / 1000).toFixed(1)}s`);

/** A6 시스템 상태 */
export default function SystemStatus() {
  const api = useApi();
  const s = usePoll(() => api.system(), 5000);
  return (
    <section>
      <h2>시스템 상태 <span className="muted small">5초마다 새로고침</span></h2>
      <ErrorBox msg={s.error} />
      <div className="cards">
        {s.data?.services.map((x) => (
          <div key={x.name} className="card stat">
            <div className="muted">{x.name}</div>
            <div className={x.status === 'UP' ? 'big ok' : 'big bad'}>{x.status}</div>
          </div>
        ))}
      </div>
      <h3>로봇 연결과 데이터 갱신</h3>
      <table>
        <thead><tr><th>로봇</th><th>rosbridge</th><th>odom</th><th>scan</th><th>camera</th><th>battery</th><th>미전송 보고</th></tr></thead>
        <tbody>
          {s.data?.robots.map((r) => (
            <tr key={r.code} className={r.enabled ? '' : 'dim'}>
              <td>{r.code}</td>
              <td className={r.connected ? 'ok' : 'bad'}>{r.enabled ? (r.connected ? '연결' : '끊김') : '비활성'}</td>
              {['odom', 'scan', 'camera', 'battery'].map((k) => {
                const v = r.ageMs?.[k];
                return <td key={k} className={v === null || v === undefined ? 'muted' : v > 2000 ? 'warn-t' : 'ok'}>{age(v)}</td>;
              })}
              <td>{r.outboxPending}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="muted">갱신 = 마지막 수신 후 경과 시간. 2초를 넘으면 주황색으로 표시합니다. 서버 ↔ rosbridge 구간이 끊기면 rosbridge 칸이 "끊김"이 됩니다.</p>
    </section>
  );
}
