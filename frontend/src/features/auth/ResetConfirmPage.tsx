import { useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { api } from '@/shared/api/client';
import { errorMessage } from '@/shared/api/http';
import { STR } from '@/shared/strings';

export default function ResetConfirmPage() {
  const [params] = useSearchParams();
  const token = params.get('token') ?? '';

  const [newPassword, setNewPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await api.resetConfirm(token, newPassword);
      setSuccess(true);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="auth-wrap">
      <div className="panel auth-card">
        <h1>Сброс пароля</h1>
        {!token ? (
          <div className="form-error">Ссылка недействительна или не содержит токен.</div>
        ) : success ? (
          <>
            <p className="muted">Пароль успешно изменён.</p>
            <div className="auth-links">
              <Link to="/login">{STR.login}</Link>
            </div>
          </>
        ) : (
          <>
            <form onSubmit={handleSubmit}>
              <div className="field">
                <label htmlFor="reset-new-password">{STR.newPassword}</label>
                <input
                  id="reset-new-password"
                  type="password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  minLength={8}
                  required
                />
              </div>
              {error && <div className="form-error">{error}</div>}
              <button className="btn primary" type="submit" disabled={loading}>
                {loading ? STR.loading : STR.save}
              </button>
            </form>
            <div className="auth-links">
              <Link to="/login">{STR.login}</Link>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
