import { useEffect, useState } from 'react';
import { Navigate, NavLink, Outlet, Route, Routes, useNavigate } from 'react-router-dom';
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

const USER_ROLES: Role[] = ['SUPERVISOR', 'MANAGER', 'USER'];

export const homeOf = (role: Role) => (role === 'ADMIN' ? '/admin/users' : role === 'DASHBOARD' ? '/dashboard' : '/app/monitor');

export default function App() {
  const api = useApi();
  const [me, setMe] = useState<Me | null>(null);
  const [checked, setChecked] = useState(false);
  const navigate = useNavigate();

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
        <Route path="/dashboard" element={me ? <Dashboard /> : <Navigate to="/login" replace />} />
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
          <Route path="/admin/analysis" element={<AnalysisCriteria />} />
          <Route path="/admin/audit" element={<Audit />} />
          <Route path="/admin/system" element={<SystemStatus />} />
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
    ['/admin/system', '시스템', 'server.rack'],
  ],
  user: [
    ['/app/monitor', '관제', 'video'], ['/app/plans', '점검', 'calendar.badge.clock'], ['/app/tasks', '작업', 'checklist'],
    ['/app/history', '지점 이력', 'clock.arrow.circlepath'],
  ],
};

/** 역할 확인 + 상단 메뉴. 화면에서 막는 것은 편의이고, 실제 권한은 게이트웨이가 확인한다. */
function Shell({ area, roles }: { area: 'admin' | 'user'; roles: Role[] }) {
  const { me, setMe } = useAuth();
  const api = useApi();
  const navigate = useNavigate();
  if (!me) return <Navigate to="/login" replace />;
  if (!roles.includes(me.role)) return <Navigate to={homeOf(me.role)} replace />;
  const logout = async () => {
    await api.logout().catch(() => {});
    setMe(null);
    navigate('/login');
  };
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
        <div className="who">
          <b>{me.name}</b>
          <span>{me.loginId} · {ROLE_LABEL[me.role]}</span>
          <ServerClock />
          <button className="link" onClick={logout}><Icon name="rectangle.portrait.and.arrow.right" size={16} />로그아웃</button>
        </div>
      </aside>
      <main>
        {area === 'user' && <DelayBanner />}
        <Outlet />
        {/* 스마트폰: 사이드바가 없으므로 사용자 영역(이름·서버 시간)을 화면 맨 아래에 둔다 */}
        <div className="mobile-who">
          <div><b>{me.name}</b> <span className="muted small">{me.loginId} · {ROLE_LABEL[me.role]}</span></div>
          <ServerClock />
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
