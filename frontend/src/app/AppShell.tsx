import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useAuthStore } from '@/shared/auth/store';
import { api } from '@/shared/api/client';
import { STR } from '@/shared/strings';
import { DeadlineCounter } from './DeadlineCounter';

const TABS = [
  { to: '/author', label: STR.tabAuthor },
  { to: '/assignee', label: STR.tabAssignee },
  { to: '/observer', label: STR.tabObserver },
  { to: '/search', label: STR.search },
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
    <div className="shell">
      <nav className="sidebar">
        <h1>{STR.appTitle}</h1>
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
        <div className="muted" style={{ fontSize: 13, padding: '0 12px' }}>
          {user?.displayName}
        </div>
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
        <a onClick={logout} style={{ cursor: 'pointer' }}>
          {STR.logout}
        </a>
      </nav>

      <main className="content">
        <DeadlineCounter />
        <Outlet />
      </main>
    </div>
  );
}
