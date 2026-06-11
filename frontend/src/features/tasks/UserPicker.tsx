import { useQuery } from '@tanstack/react-query';
import { api } from '@/shared/api/client';
import type { UserRef } from '@/shared/types';

const MAX_OBSERVERS = 5;

export function AssigneePicker({ value, onChange }: { value: string; onChange: (id: string) => void }) {
  const { data: users } = useQuery({ queryKey: ['users'], queryFn: () => api.listUsers() });

  return (
    <select
      className="field"
      value={value}
      onChange={(e) => onChange(e.target.value)}
    >
      <option value="">— выберите —</option>
      {(users ?? []).map((u: UserRef) => (
        <option key={u.id} value={u.id}>
          {u.displayName} ({u.email})
        </option>
      ))}
    </select>
  );
}

export default function ObserversPicker({ value, onChange }: { value: string[]; onChange: (ids: string[]) => void }) {
  const { data: users } = useQuery({ queryKey: ['users'], queryFn: () => api.listUsers() });

  const toggle = (id: string) => {
    if (value.includes(id)) {
      onChange(value.filter((v) => v !== id));
    } else {
      if (value.length >= MAX_OBSERVERS) return;
      onChange([...value, id]);
    }
  };

  return (
    <div>
      <div className="muted">Выбрано {value.length}/{MAX_OBSERVERS}</div>
      <div className="chip-list">
        {(users ?? []).map((u: UserRef) => {
          const checked = value.includes(u.id);
          const disabled = !checked && value.length >= MAX_OBSERVERS;
          return (
            <label key={u.id} className="chip">
              <input
                type="checkbox"
                checked={checked}
                disabled={disabled}
                onChange={() => toggle(u.id)}
              />
              {u.displayName} ({u.email})
            </label>
          );
        })}
      </div>
    </div>
  );
}
