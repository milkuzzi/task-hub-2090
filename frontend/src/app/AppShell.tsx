import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useAuthStore } from '@/shared/auth/store';
import { api } from '@/shared/api/client';
import { STR } from '@/shared/strings';
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

  const initials = (user?.displayName ?? '')
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0]!.toUpperCase())
    .join('');

  return (
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
        <div className="side-user" title={user?.displayName}>
          <div className="side-avatar">{initials || '•'}</div>
          <div className="side-user-name">{user?.displayName}</div>
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
        <button type="button" onClick={logout}>
          {STR.logout}
        </button>
      </nav>

      <main className="content" id="main-content" tabIndex={-1}>
        <DeadlineCounter />
        <Outlet />
      </main>
    </div>
  );
}
