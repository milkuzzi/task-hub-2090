import { useState } from 'react';
import { AuthBrand } from '@/shared/ui/AuthBrand';
import { Link } from 'react-router-dom';
import { api } from '@/shared/api/client';
import { errorMessage } from '@/shared/api/http';
import { STR } from '@/shared/strings';

export default function ResetRequestPage() {
  const [email, setEmail] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState(false);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await api.resetRequest(email);
      setSubmitted(true);
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
        <h1>{STR.forgotPassword}</h1>
        {submitted ? (
          <p className="muted">
            Если адрес зарегистрирован, мы отправили письмо со ссылкой для сброса пароля.
          </p>
        ) : (
          <form onSubmit={handleSubmit}>
            <div className="field">
              <label htmlFor="reset-email">{STR.email}</label>
              <input
                id="reset-email"
                type="email"
                autoComplete="username"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>
            {error && <div className="form-error">{error}</div>}
            <button className="btn primary" type="submit" disabled={loading}>
              {loading ? STR.loading : STR.forgotPassword}
            </button>
          </form>
        )}
        <div className="auth-links">
          <Link to="/login">{STR.login}</Link>
        </div>
      </div>
    </div>
  );
}
