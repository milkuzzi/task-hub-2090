import { useState } from 'react';
import { AuthBrand } from '@/shared/ui/AuthBrand';
import { Link, Navigate, useNavigate } from 'react-router-dom';
import { api } from '@/shared/api/client';
import { errorMessage } from '@/shared/api/http';
import { useAuthStore } from '@/shared/auth/store';
import { STR } from '@/shared/strings';

export default function LoginPage() {
  const accessToken = useAuthStore((s) => s.accessToken);
  const setSession = useAuthStore((s) => s.setSession);
  const navigate = useNavigate();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  if (accessToken) {
    return <Navigate to="/author" replace />;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const res = await api.login(email, password);
      setSession(res.accessToken, res.user);
      navigate('/author');
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="auth-wrap">
      <AuthBrand />
      <div className="panel auth-card">
        <h1>{STR.login}</h1>
        <form onSubmit={handleSubmit}>
          <div className="field">
            <label htmlFor="login-email">{STR.email}</label>
            <input
              id="login-email"
              type="email"
              autoComplete="username"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>
          <div className="field">
            <label htmlFor="login-password">{STR.password}</label>
            <input
              id="login-password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>
          {error && <div className="form-error">{error}</div>}
          <button className="btn primary" type="submit" disabled={loading}>
            {loading ? STR.loading : STR.login}
          </button>
        </form>
        <div className="auth-links">
          <Link to="/register">{STR.register}</Link>
          <Link to="/reset">{STR.forgotPassword}</Link>
        </div>
      </div>
    </div>
  );
}
