import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMutation } from '@tanstack/react-query';
import { api } from '@/shared/api/client';
import { STR } from '@/shared/strings';

export default function SearchPage() {
  const navigate = useNavigate();
  const [code, setCode] = useState('');
  const [validationError, setValidationError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: (value: string) => api.searchByCode(value),
    onSuccess: (task) => {
      navigate('/tasks/' + task.id);
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setValidationError(null);
    if (!/^\d{6}$/.test(code)) {
      setValidationError('Введите ровно 6 цифр.');
      return;
    }
    mutation.mutate(code);
  };

  return (
    <div className="panel">
      <h2>{STR.search}</h2>
      <form onSubmit={handleSubmit}>
        <div className="field">
          <label htmlFor="search-code">{STR.search}</label>
          <input
            id="search-code"
            value={code}
            inputMode="numeric"
            maxLength={6}
            onChange={(e) => setCode(e.target.value)}
          />
        </div>
        {validationError && <div className="form-error">{validationError}</div>}
        <div className="row">
          <button type="submit" className="btn primary" disabled={mutation.isPending}>
            Найти
          </button>
        </div>
      </form>
      {mutation.isError && (
        <div className="form-error">Задача не найдена или недоступна.</div>
      )}
    </div>
  );
}
