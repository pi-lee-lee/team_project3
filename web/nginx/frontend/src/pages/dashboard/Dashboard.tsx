import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ROLE_LABEL, useApi, useAuth } from '../../util';
import { LAUNCH_MODE } from '../user/scenarioText';
import { Icon } from '../../Icon';
import { useDashData, type DashData, type Ref } from './data';
import { COLS, LAYOUT, ROWS } from './layout';
import { PANELS } from './panels';
import { DETAILS } from './details';
import { EmergencyDialog } from '../../EmergencyDialog';
import { LaunchDialog } from '../../LaunchDialog';
import './dashboard.css';

/** 설계 크기. 16:9 모니터 한 장을 가득 채우는 화면이고 반응형이 아니다 — 창 크기에 맞춰 통째로 확대·축소만 한다. */
const W = 1920, H = 1080;

/**
 * 관제 대시보드(전용 계정 DASHBOARD 의 첫 화면, 조회 전용).
 * 구성: data.ts(불러오기) → panels.tsx(패널) + layout.ts(배치) → details.tsx(누르면 뜨는 상세).
 */
export default function Dashboard() {
  const d = useDashData();
  const { me } = useAuth();
  // 상세 창은 쌓인다: 상세 안에서 다른 상세로 넘어가면 뒤로 돌아올 수 있다
  const [stack, setStack] = useState<Ref[]>([]);
  const open = (r: Ref) => setStack((s) => [...s, r]);
  const close = () => setStack([]);
  const back = () => setStack((s) => s.slice(0, -1));

  const [scale, setScale] = useState(1);
  useEffect(() => {
    const fit = () => setScale(Math.min(window.innerWidth / W, window.innerHeight / H));
    fit();
    window.addEventListener('resize', fit);
    return () => window.removeEventListener('resize', fit);
  }, []);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') back(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  const top = stack[stack.length - 1];
  return (
    <div className="dz-viewport">
      <div className="dz" style={{ width: W, height: H, transform: `translate(-50%, -50%) scale(${scale})` }}>
        <Header d={d} open={open} />
        <div className="dz-grid" style={{ gridTemplateColumns: `repeat(${COLS}, 1fr)`, gridTemplateRows: `repeat(${ROWS}, 1fr)` }}>
          {LAYOUT.map((s) => {
            const p = PANELS[s.panel];
            if (!p) return null;
            const style = { gridColumn: `${s.col} / span ${s.w}`, gridRow: `${s.row} / span ${s.h}` };
            if (p.bare) return <div key={s.panel} style={style}><p.Body d={d} open={open} /></div>;
            return (
              <section key={s.panel} className={`dz-panel p-${s.panel}`} style={style}>
                <header><Icon name={p.icon} size={18} /><h3>{p.title}</h3><span className="grow" />{p.extra?.(d)}</header>
                <div className="dz-body"><p.Body d={d} open={open} /></div>
              </section>
            );
          })}
        </div>
        {top && <Detail r={top} d={d} open={open} close={close} back={stack.length > 1 ? back : undefined} />}
      </div>
      {/* 투척 승인 팝업(비상 팝업보다 위). 대시보드 계정도 승인할 수 있다 — 조회 전용의 유일한 예외 */}
      <LaunchDialog canDismiss={!!me && ['ADMIN', 'SUPERVISOR', 'MANAGER', 'USER'].includes(me.role)}
        onOpen={(id) => open({ kind: 'incident', id })} />
      {/* 비상 등급 경고 팝업. 사용자 역할이면 확인을 서버에 남기고, 대시보드 전용 계정이면 이 화면에서만 닫는다 */}
      <EmergencyDialog canAck={!!me && ['ADMIN', 'SUPERVISOR', 'MANAGER', 'USER'].includes(me.role)} onOpen={(a) => open(
        a.ref_kind === 'incident' ? { kind: 'incident', id: a.ref_id }
          : a.ref_kind === 'observation' && a.task_id ? { kind: 'observation', id: a.ref_id, taskId: a.task_id }
            : a.task_id ? { kind: 'task', id: a.task_id } : { kind: 'system' })} />
    </div>
  );
}

function Detail({ r, d, open, close, back }: { r: Ref; d: DashData; open: (r: Ref) => void; close: () => void; back?: () => void }) {
  // Ref.kind 로 고른 상세 화면. 표(DETAILS)가 kind 별 타입을 맞춰 주므로 여기서는 한 번만 넓혀 쓴다.
  const def = DETAILS[r.kind] as { title: (r: Ref) => string; icon: string; Body: (p: { r: Ref; d: DashData; open: (r: Ref) => void }) => React.ReactNode };
  return (
    <div className="dz-scrim" onClick={close}>
      <div className="dz-modal" role="dialog" aria-modal="true" onClick={(e) => e.stopPropagation()}>
        <header>
          {back && <button className="dz-icon-btn" onClick={back} aria-label="뒤로"><Icon name="chevron.left" size={22} /></button>}
          <Icon name={def.icon} size={22} /><h2>{def.title(r)}</h2><span className="grow" />
          <button className="dz-icon-btn" onClick={close} aria-label="닫기"><Icon name="xmark" size={22} /></button>
        </header>
        <div className="dz-modal-body"><def.Body key={JSON.stringify(r)} r={r} d={d} open={open} /></div>
      </div>
    </div>
  );
}

function Header({ d, open }: { d: DashData; open: (r: Ref) => void }) {
  const { me, setMe } = useAuth();
  const api = useApi();
  const navigate = useNavigate();
  const [, tick] = useState(0);
  useEffect(() => {
    const h = setInterval(() => tick((n) => n + 1), 1000);
    return () => clearInterval(h);
  }, []);
  const now = new Date(Date.now() + (d.clock?.offsetMs ?? 0));
  const fmt = (o: Intl.DateTimeFormatOptions) => new Intl.DateTimeFormat('ko-KR', { timeZone: d.clock?.zone, ...o }).format(now);
  const logout = async () => {
    await api.logout().catch(() => {});
    setMe(null);
    navigate('/login');
  };
  const services = d.system?.services ?? [];
  const down = services.filter((s) => s.status !== 'UP').length;
  const critical = d.alerts.some((a) => a.severity === 'CRITICAL');
  return (
    <header className="dz-header">
      <div className="brand"><span className="logo"><Icon name="flame.fill" size={24} /></span>화재 점검 로봇 <b>통합 관제</b></div>
      <div className={`dz-state ${d.error ? 'red' : critical ? 'red' : d.alerts.length ? 'orange' : 'green'}`}>
        <i />{d.error ? `서버 응답 없음 · ${d.error}` : critical ? '비상 · 즉시 확인' : d.alerts.length ? `경고 ${d.alerts.length}건` : '정상 운용 중'}
      </div>
      {d.launchMode && (
        <div className={`dz-mode ${d.launchMode === 'AUTO' ? 'purple' : 'blue'}`} title="화재 대응 시 투척을 시작하는 방식">
          <Icon name="paperplane.fill" size={16} />투척 {LAUNCH_MODE[d.launchMode]}
        </div>
      )}
      <span className="grow" />
      <button className="dz-services" onClick={() => open({ kind: 'system' })} title="시스템 상태">
        <Icon name="server.rack" size={18} />
        {services.map((s) => <i key={s.name} className={s.status === 'UP' ? 'up' : 'down'} title={`${s.name} ${s.status}`} />)}
        <span>{services.length ? (down ? `서비스 ${down}개 중지` : `서비스 ${services.length}개 정상`) : '서비스 확인 중'}</span>
      </button>
      <div className="dz-clock">
        <b>{fmt({ hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })}</b>
        <span>{fmt({ year: 'numeric', month: 'long', day: 'numeric', weekday: 'short' })}</span>
      </div>
      <div className="dz-who">
        <b>{me?.name}</b><span>{me?.loginId} · {me ? ROLE_LABEL[me.role] : ''}</span>
      </div>
      {/* ADMIN 은 모든 화면에 들어갈 수 있다: 관리자 화면 · 사용자 화면으로 가는 단추 */}
      {me?.role === 'ADMIN' && (
        <>
          <button className="dz-icon-btn" title="관리자 화면" aria-label="관리자 화면" onClick={() => navigate('/admin/users')}><Icon name="gearshape" size={22} /></button>
          <button className="dz-icon-btn" title="사용자 화면" aria-label="사용자 화면" onClick={() => navigate('/app/monitor')}><Icon name="video" size={22} /></button>
        </>
      )}
      <button className="dz-icon-btn" title="전체 화면" aria-label="전체 화면"
        onClick={() => (document.fullscreenElement ? document.exitFullscreen() : document.documentElement.requestFullscreen().catch(() => {}))}>
        <Icon name="arrow.up.left.and.arrow.down.right" size={22} />
      </button>
      <button className="dz-icon-btn" title="로그아웃" aria-label="로그아웃" onClick={logout}><Icon name="rectangle.portrait.and.arrow.right" size={22} /></button>
    </header>
  );
}
