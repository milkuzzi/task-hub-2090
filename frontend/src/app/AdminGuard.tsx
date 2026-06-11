import { Navigate, Outlet } from 'react-router-dom';
import { useAuthStore } from '@/shared/auth/store';

export function AdminGuard() {
  const user = useAuthStore((s) => s.user);
  if (!user?.isAdmin) return <Navigate to="/author" replace />;
  return <Outlet />;
}
