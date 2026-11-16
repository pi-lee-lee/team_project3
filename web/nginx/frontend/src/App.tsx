import { useEffect, useState } from 'react';
import { Navigate, NavLink, Outlet, Route, Routes, useNavigate } from 'react-router-dom';
import type { Me, Role } from './api/types';
import { AuthContext, ROLE_LABEL, useApi, useAuth } from './util';
import Login from './pages/Login';
import Users from './pages/admin/Users';
import Robots from './pages/admin/Robots';
import Points from './pages/admin/Points';
import AnalysisCriteria from './pages/admin/AnalysisCriteria';
import Audit from './pages/admin/Audit';
import SystemStatus from './pages/admin/SystemStatus';
import Monitor from './pages/user/Monitor';
import RequestPage from './pages/user/Request';
import Tasks from './pages/user/Tasks';
import TaskDetail from './pages/user/TaskDetail';
import History from './pages/user/History';

const USER_ROLES: Role[] = ['SUPERVISOR', 'MANAGER', 'USER'];

export const homeOf = (role: Role) => (role === 'ADMIN' ? '/admin/users' : '/app/monitor');

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
        <Route element={<Shell area="admin" roles={['ADMIN']} />}>
          <Route path="/admin/users" element={<Users />} />
          <Route path="/admin/robots" element={<Robots />} />
          <Route path="/admin/points" element={<Points />} />
          <Route path="/admin/analysis" element={<AnalysisCriteria />} />
          <Route path="/admin/audit" element={<Audit />} />
          <Route path="/admin/system" element={<SystemStatus />} />
        </Route>
        <Route element={<Shell area="user" roles={USER_ROLES} />}>
          <Route path="/app/monitor" element={<Monitor />} />
          <Route path="/app/request" element={<RequestPage />} />
          <Route path="/app/tasks" element={<Tasks />} />
          <Route path="/app/tasks/:id" element={<TaskDetail />} />
          <Route path="/app/history" element={<History />} />
        </Route>
        <Route path="*" element={<Navigate to={me ? homeOf(me.role) : '/login'} replace />} />
      </Routes>
    </AuthContext.Provider>
  );
}

const MENUS = {
  admin: [
    ['/admin/users', '사용자'], ['/admin/robots', '로봇'], ['/admin/points', '점검 지점'],
    ['/admin/analysis', '분석 기준'], ['/admin/audit', '감사 로그'], ['/admin/system', '시스템'],
  ],
  user: [['/app/monitor', '관제'], ['/app/request', '점검 요청'], ['/app/tasks', '작업 목록'], ['/app/history', '지점 이력']],
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
      <header className="topbar">
        <span className="brand">{area === 'admin' ? '관리자' : '화재 점검'}</span>
        <nav>
          {MENUS[area].map(([to, label]) => (
            <NavLink key={to} to={to}>{label}</NavLink>
          ))}
        </nav>
        <span className="who">
          {me.loginId} ({ROLE_LABEL[me.role]}) <button className="link light" onClick={logout}>로그아웃</button>
        </span>
      </header>
      <main>
        <Outlet />
      </main>
    </div>
  );
}
