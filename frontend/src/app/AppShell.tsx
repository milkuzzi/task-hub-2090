import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useAuthStore } from '@/shared/auth/store';
import { api } from '@/shared/api/client';
import { STR } from '@/shared/strings';
import { RealtimeProvider } from '@/shared/realtime/useRealtime';
import { Bell } from '@/features/notifications/Bell';
import { Avatar } from '@/shared/ui/Avatar';
import { DeadlineCounter } from './DeadlineCounter';

const TABS = [
  { to: '/author', label: STR.tabAuthor },
  { to: '/assignee', label: STR.tabAssignee },
  { to: '/observer', label: STR.tabObserver },
];

export function AppShell() {
  const user = useAuthStore((s) => s.user);
  const clear = useAuthStore((s) => s.clear);
  const navigate = useNavigate();

  const logout = async () => {
    try {
      await api.logout();
    } catch {
      /* ignore */
    }
    clear();
    navigate('/login', { replace: true });
  };

  return (
    <RealtimeProvider>
      <div className="shell">
        <a className="skip-link" href="#main-content">
          Перейти к содержимому
        </a>
        <nav className="sidebar">
          <div className="brand">
            <div className="brand-logo">2090</div>
            <div className="brand-name">
              <b>Поручения</b>
              <span>школа № 2090</span>
            </div>
          </div>
          {TABS.map((t) => (
            <NavLink key={t.to} to={t.to} className={({ isActive }) => (isActive ? 'active' : '')}>
              {t.label}
            </NavLink>
          ))}
          {user?.isAdmin && (
            <NavLink to="/admin" className={({ isActive }) => (isActive ? 'active' : '')}>
              {STR.admin}
            </NavLink>
          )}
          <div className="spacer" />
          <NavLink
            to="/profile"
            className={({ isActive }) => (isActive ? 'side-user active' : 'side-user')}
            title={user?.displayName}
          >
            <Avatar name={user?.displayName} userId={user?.id} size={32} />
            <div className="side-user-name">{user?.displayName}</div>
          </NavLink>
          <button className="navlink" onClick={logout}>
            {STR.logout}
          </button>
        </nav>

        <nav className="mobile-tabs">
          {TABS.map((t) => (
            <NavLink key={t.to} to={t.to} className={({ isActive }) => (isActive ? 'active' : '')}>
              {t.label}
            </NavLink>
          ))}
          {user?.isAdmin && <NavLink to="/admin">{STR.admin}</NavLink>}
          <NavLink to="/profile">{STR.profile}</NavLink>
          <button type="button" onClick={logout}>
            {STR.logout}
          </button>
        </nav>

        <main className="content" id="main-content" tabIndex={-1}>
          <div className="content-topbar">
            <Bell />
          </div>
          <DeadlineCounter />
          <Outlet />
        </main>
      </div>
    </RealtimeProvider>
  );
}
