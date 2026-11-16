import { useEffect, useState } from 'react';
import { Navigate, NavLink, Outlet, Route, Routes, useNavigate } from 'react-router-dom';
import type { Me, Role } from './api/types';
import { AuthContext, ROLE_LABEL, useApi, useAuth } from './util';
import { Icon } from './Icon';
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

// [경로, 이름, 아이콘(SF Symbols 이름)]
const MENUS: Record<'admin' | 'user', [string, string, string][]> = {
  admin: [
    ['/admin/users', '사용자', 'person.2'], ['/admin/robots', '로봇', 'cpu'], ['/admin/points', '점검 지점', 'mappin.and.ellipse'],
    ['/admin/analysis', '분석 기준', 'slider.horizontal.3'], ['/admin/audit', '감사 로그', 'list.bullet.clipboard'],
    ['/admin/system', '시스템', 'server.rack'],
  ],
  user: [
    ['/app/monitor', '관제', 'video'], ['/app/request', '점검 요청', 'plus.circle'], ['/app/tasks', '작업 목록', 'checklist'],
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
          <button className="link" onClick={logout}><Icon name="rectangle.portrait.and.arrow.right" size={16} />로그아웃</button>
        </div>
      </aside>
      <main>
        <Outlet />
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
