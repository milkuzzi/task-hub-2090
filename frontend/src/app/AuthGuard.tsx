import { useEffect, useState } from 'react';
import { Navigate } from 'react-router-dom';
import { useAuthStore } from '@/shared/auth/store';
import { bootstrapSession } from '@/shared/api/http';
import { Spinner } from '@/shared/ui/Spinner';
import { AppShell } from './AppShell';

export function AuthGuard() {
  const token = useAuthStore((s) => s.accessToken);
  const [state, setState] = useState<'loading' | 'in' | 'out'>(token ? 'in' : 'loading');

  useEffect(() => {
    if (token) {
      setState('in');
      return;
    }
    let active = true;
    bootstrapSession().then((ok) => {
      if (active) setState(ok ? 'in' : 'out');
    });
    return () => {
      active = false;
    };
  }, [token]);

  if (state === 'loading') return <Spinner />;
  if (state === 'out') return <Navigate to="/login" replace />;
  return <AppShell />;
}
