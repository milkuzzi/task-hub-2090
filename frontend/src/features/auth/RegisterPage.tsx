import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { api } from '@/shared/api/client';
import { errorMessage } from '@/shared/api/http';
import { useAuthStore } from '@/shared/auth/store';
import { STR } from '@/shared/strings';

export default function RegisterPage() {
  const setSession = useAuthStore((s) => s.setSession);
  const navigate = useNavigate();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const res = await api.register(email, password);
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
      <div className="panel auth-card">
        <div className="warn-banner">{STR.accessListWarning}</div>
        <h1>{STR.register}</h1>
        <form onSubmit={handleSubmit}>
          <div className="field">
            <label htmlFor="register-email">{STR.email}</label>
            <input
              id="register-email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>
          <div className="field">
            <label htmlFor="register-password">{STR.password}</label>
            <input
              id="register-password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>
          {error && <div className="form-error">{error}</div>}
          <button className="btn primary" type="submit" disabled={loading}>
            {loading ? STR.loading : STR.register}
          </button>
        </form>
        <div className="auth-links">
          <Link to="/login">{STR.login}</Link>
        </div>
      </div>
    </div>
  );
}
