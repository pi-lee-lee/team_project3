import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { Navigate, NavLink, Outlet, Route, Routes, useLocation, useNavigate } from 'react-router-dom';
import type { Me, Role } from './api/types';
import { AuthContext, ROLE_LABEL, useApi, useAuth } from './util';
import { Icon } from './Icon';
import { ServerClock } from './ServerClock';
import Login from './pages/Login';
import Users from './pages/admin/Users';
import UserDetail from './pages/admin/UserDetail';
import UserForm from './pages/admin/UserForm';
import Robots from './pages/admin/Robots';
import RobotDetail from './pages/admin/RobotDetail';
import RobotForm from './pages/admin/RobotForm';
import Points from './pages/admin/Points';
import PointForm from './pages/admin/PointForm';
import AnalysisCriteria from './pages/admin/AnalysisCriteria';
import Audit from './pages/admin/Audit';
import SystemStatus from './pages/admin/SystemStatus';
import Monitor from './pages/user/Monitor';
import Tasks from './pages/user/Tasks';
import TaskDetail from './pages/user/TaskDetail';
import ObservationDetail from './pages/user/ObservationDetail';
import History from './pages/user/History';
import PointHistory from './pages/user/PointHistory';
import PlanList from './pages/user/plans/PlanList';
import PlanDetail from './pages/user/plans/PlanDetail';
import PlanForm from './pages/user/plans/PlanForm';
import DelayBanner from './pages/user/DelayBanner';
import Dashboard from './pages/dashboard/Dashboard';
import Rules from './pages/admin/Rules';
import RuleForm from './pages/admin/RuleForm';
import Settings from './pages/admin/Settings';
import Alerts from './pages/user/Alerts';
import Incidents from './pages/user/Incidents';
import IncidentDetail from './pages/user/IncidentDetail';
import IncidentBanner from './pages/user/IncidentBanner';
import { EmergencyDialog } from './EmergencyDialog';
import Demo from './pages/admin/Demo';
import { LaunchDialog } from './LaunchDialog';
import { getTheme, ThemeToggle, useTheme } from './theme';
import Duel from './pages/dashboard/Duel';
import { playTransition } from './PixelFx';

// 사용자 화면에 들어올 수 있는 역할. ADMIN 은 모든 화면에 들어갈 수 있다(사이드바의 "화면 이동" 링크)
const USER_ROLES: Role[] = ['ADMIN', 'SUPERVISOR', 'MANAGER', 'USER'];

/** ADMIN 에게만 보이는 화면 이동 링크: 역할마다 다른 세 화면을 로그아웃 없이 오간다. [경로, 이름, 아이콘, 영역] */
export const AREA_LINKS: [string, string, string, 'admin' | 'user' | 'dashboard'][] = [
  ['/admin/users', '관리자 화면', 'gearshape', 'admin'],
  ['/app/monitor', '사용자 화면', 'video', 'user'],
  ['/dashboard', '관제 대시보드', 'server.rack', 'dashboard'],
];

export const homeOf = (role: Role) => (role === 'ADMIN' ? '/admin/users' : role === 'DASHBOARD' ? '/dashboard' : '/app/monitor');

export default function App() {
  const api = useApi();
  const [me, setMe] = useState<Me | null>(null);
  const [checked, setChecked] = useState(false);
  const navigate = useNavigate();

  // 픽셀 모드: 메뉴(주소 앞 두 마디)가 바뀌면 덮인 화면이 걷히는 전환 연출을 낸다. 목록 → 상세 같은 메뉴 안 이동에는 내지 않는다
  const { pathname } = useLocation();
  const menu = pathname.split('/').slice(1, 3).join('/');
  const prevMenu = useRef(menu);
  useLayoutEffect(() => {
    if (prevMenu.current === menu) return;
    prevMenu.current = menu;
    if (getTheme() === 'pixel') playTransition({ reveal: true, speed: 1.8 });
  }, [menu]);
  const pixel = useTheme() === 'pixel';

  useEffect(() => {
    api.me().then(setMe, () => setMe(null)).finally(() => setChecked(true));
    const onExpired = () => {
      setMe(null);
      navigate('/login');
    };
    window.addEventListener('auth:expired', onExpired);
    return () => window.removeEventListener('auth:expired', onExpired);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (!checked) return <div className="center muted">불러오는 중…</div>;

  return (
    <AuthContext.Provider value={{ me, setMe }}>
      <Routes>
        <Route path="/login" element={<Login />} />
        {/* 관제 대시보드: 메뉴 틀(Shell) 없이 화면 전체를 쓴다. 전용 계정(DASHBOARD)의 첫 화면이고, 다른 역할도 주소로 열 수 있다 */}
        {/* 픽셀 모드(이스터 에그)에서는 대시보드 자리에 포격전이 뜬다 */}
        <Route path="/dashboard" element={me ? (pixel ? <Duel /> : <Dashboard />) : <Navigate to="/login" replace />} />
        <Route element={<Shell area="admin" roles={['ADMIN']} />}>
          {/* 일 단위 화면: 목록 → 상세 → 폼 */}
          <Route path="/admin/users" element={<Users />} />
          <Route path="/admin/users/new" element={<UserForm />} />
          <Route path="/admin/users/:id" element={<UserDetail />} />
          <Route path="/admin/robots" element={<Robots />} />
          <Route path="/admin/robots/new" element={<RobotForm />} />
          <Route path="/admin/robots/:id" element={<RobotDetail />} />
          <Route path="/admin/robots/:id/edit" element={<RobotForm />} />
          <Route path="/admin/points" element={<Points />} />
          <Route path="/admin/points/new" element={<PointForm />} />
          <Route path="/admin/points/:id/edit" element={<PointForm />} />
          {/* 점검 규칙: 지점마다 판독기 종류 · 설정 · 등급 기준 */}
          <Route path="/admin/points/:id/rules" element={<Rules />} />
          <Route path="/admin/points/:id/rules/new" element={<RuleForm />} />
          <Route path="/admin/points/:id/rules/:ruleId/edit" element={<RuleForm />} />
          <Route path="/admin/settings" element={<Settings />} />
          <Route path="/admin/analysis" element={<AnalysisCriteria />} />
          <Route path="/admin/audit" element={<Audit />} />
          <Route path="/admin/system" element={<SystemStatus />} />
          <Route path="/admin/demo" element={<Demo />} />
        </Route>
        <Route element={<Shell area="user" roles={USER_ROLES} />}>
          <Route path="/app/monitor" element={<Monitor />} />
          {/* 점검 = 점검 요청 + 예약 점검 (점검 계획). 실행 버튼이 예전의 점검 요청 */}
          <Route path="/app/plans" element={<PlanList />} />
          <Route path="/app/plans/new" element={<PlanForm />} />
          <Route path="/app/plans/:id" element={<PlanDetail />} />
          <Route path="/app/plans/:id/edit" element={<PlanForm />} />
          <Route path="/app/request" element={<Navigate to="/app/plans/new" replace />} />
          <Route path="/app/schedules" element={<Navigate to="/app/plans" replace />} />
          <Route path="/app/tasks" element={<Tasks />} />
          <Route path="/app/tasks/:id" element={<TaskDetail />} />
          <Route path="/app/tasks/:id/observations/:obsId" element={<ObservationDetail />} />
          <Route path="/app/alerts" element={<Alerts />} />
          <Route path="/app/incidents" element={<Incidents />} />
          <Route path="/app/incidents/:id" element={<IncidentDetail />} />
          <Route path="/app/history" element={<History />} />
          <Route path="/app/history/:pointId" element={<PointHistory />} />
        </Route>
        <Route path="*" element={<Navigate to={me ? homeOf(me.role) : '/login'} replace />} />
      </Routes>
    </AuthContext.Provider>
  );
}

// [경로, 이름, 아이콘(SF Symbols 이름)]
const MENUS: Record<'admin' | 'user', [string, string, string][]> = {
  admin: [
    ['/admin/users', '사용자', 'person.2'], ['/admin/robots', '로봇', 'cpu'], ['/admin/points', '점검 지점', 'mappin.and.ellipse'],
    ['/admin/analysis', '분석 기준', 'slider.horizontal.3'], ['/admin/audit', '감사 로그', 'list.bullet.clipboard'],
    ['/admin/demo', '시연', 'play.fill'], ['/admin/settings', '설정', 'gearshape'], ['/admin/system', '시스템', 'server.rack'],
  ],
  user: [
    ['/app/monitor', '관제', 'video'], ['/app/plans', '점검', 'calendar.badge.clock'], ['/app/tasks', '작업', 'checklist'],
    ['/app/alerts', '경고', 'bell.fill'], ['/app/incidents', '사건', 'flame.fill'],
    ['/app/history', '지점 이력', 'clock.arrow.circlepath'],
  ],
};

/** 역할 확인 + 상단 메뉴. 화면에서 막는 것은 편의이고, 실제 권한은 게이트웨이가 확인한다. */
function Shell({ area, roles }: { area: 'admin' | 'user'; roles: Role[] }) {
  const { me, setMe } = useAuth();
  const api = useApi();
  const navigate = useNavigate();
  const pixel = useTheme() === 'pixel';
  if (!me) return <Navigate to="/login" replace />;
  if (!roles.includes(me.role)) return <Navigate to={homeOf(me.role)} replace />;
  const logout = async () => {
    await api.logout().catch(() => {});
    setMe(null);
    navigate('/login');
  };
  // 화면 이동 링크: ADMIN 은 세 화면 모두, 픽셀 모드에서는 누구에게나 대시보드(포격전) 하나를 보인다
  const areaLinks = AREA_LINKS.filter(([, , , a]) => a !== area && (me.role === 'ADMIN' || (pixel && a === 'dashboard')));
  return (
    <div className={`shell ${area}`}>
      {/* 사이드바(넓은 화면) */}
      <aside className="sidebar">
        <div className="brand">
          <Icon name="checkmark.shield.fill" size={22} />
          화재 점검 <span className="badge-area">{area === 'admin' ? '관리자' : '사용자'}</span>
        </div>
        <nav>
          {MENUS[area].map(([to, label, icon]) => (
            <NavLink key={to} to={to}><Icon name={icon} />{label}</NavLink>
          ))}
        </nav>
        {areaLinks.length > 0 && (
          <div className="area-links">
            <span className="area-title">화면 이동</span>
            {areaLinks.map(([to, label, icon, a]) => (a === 'dashboard' && !pixel
              // 관제 대시보드는 상황실 모니터용 전체 화면이라 새 창으로 띄운다(하던 화면은 그대로 둔다). 픽셀 모드는 창마다 따로라 같은 창에서 연다
              ? <a key={to} href={to} target="_blank" rel="noopener"><Icon name={icon} size={18} />{label}<Icon name="arrow.up.right.square" size={14} /></a>
              : <NavLink key={to} to={to}><Icon name={icon} size={18} />{label}<Icon name="chevron.right" size={14} /></NavLink>
            ))}
          </div>
        )}
        <div className="who">
          <b>{me.name}</b>
          <span>{me.loginId} · {ROLE_LABEL[me.role]}</span>
          <ServerClock />
          {pixel && <ThemeToggle />}
          <button className="link" onClick={logout}><Icon name="rectangle.portrait.and.arrow.right" size={16} />로그아웃</button>
        </div>
      </aside>
      <main>
        {/* 비상 등급 경고는 어느 화면에 있든 큰 팝업으로 띄운다 */}
        {area === 'user' && (
          <EmergencyDialog canAck onOpen={(a) => navigate(
            a.ref_kind === 'incident' ? `/app/incidents/${a.ref_id}`
              : a.ref_kind === 'observation' && a.task_id ? `/app/tasks/${a.task_id}/observations/${a.ref_id}`
                : '/app/alerts')} />
        )}
        {/* 투척 승인 팝업: 로봇이 투척 위치에 도착해 승인을 기다리면 카메라 화면과 함께 띄운다(비상 팝업보다 위) */}
        {area === 'user' && <LaunchDialog canDismiss onOpen={(id) => navigate(`/app/incidents/${id}`)} />}
        {area === 'user' && <IncidentBanner />}
        {area === 'user' && <DelayBanner />}
        <Outlet />
        {/* 스마트폰: 사이드바가 없으므로 사용자 영역(이름·서버 시간)을 화면 맨 아래에 둔다 */}
        <div className="mobile-who">
          <div><b>{me.name}</b> <span className="muted small">{me.loginId} · {ROLE_LABEL[me.role]}</span></div>
          {areaLinks.length > 0 && (
            <div className="area-links row wrap">
              {areaLinks.map(([to, label, icon, a]) => (a === 'dashboard' && !pixel
                ? <a key={to} href={to} target="_blank" rel="noopener"><Icon name={icon} size={16} />{label}</a>
                : <NavLink key={to} to={to}><Icon name={icon} size={16} />{label}</NavLink>
              ))}
            </div>
          )}
          <ServerClock />
          {pixel && <ThemeToggle />}
        </div>
      </main>
      {/* 하단 탭 바(좁은 화면) */}
      <nav className="tabbar">
        {MENUS[area].map(([to, label, icon]) => (
          <NavLink key={to} to={to}><Icon name={icon} size={22} />{label}</NavLink>
        ))}
        <a href="#" onClick={(e) => { e.preventDefault(); logout(); }}><Icon name="rectangle.portrait.and.arrow.right" size={22} />로그아웃</a>
      </nav>
    </div>
  );
}
