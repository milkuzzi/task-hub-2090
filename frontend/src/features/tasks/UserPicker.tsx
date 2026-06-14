import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/shared/api/client';
import type { UserRef } from '@/shared/types';

const MAX_OBSERVERS = 5;

function filterUsers(users: UserRef[], query: string): UserRef[] {
  const q = query.trim().toLowerCase();
  if (!q) return users;
  return users.filter(
    (u) => u.displayName.toLowerCase().includes(q) || u.email.toLowerCase().includes(q),
  );
}

export default function ObserversPicker({
  labelledBy,
  value,
  onChange,
}: {
  labelledBy?: string;
  value: string[];
  onChange: (ids: string[]) => void;
}) {
  const { data: users } = useQuery({ queryKey: ['users'], queryFn: () => api.listUsers() });
  const [query, setQuery] = useState('');

  const toggle = (id: string) => {
    if (value.includes(id)) {
      onChange(value.filter((v) => v !== id));
    } else {
      if (value.length >= MAX_OBSERVERS) return;
      onChange([...value, id]);
    }
  };

  const visible = filterUsers(users ?? [], query);

  return (
    <div className="user-picker">
      <div className="muted">
        Выбрано {value.length}/{MAX_OBSERVERS}
      </div>
      <input
        className="picker-search"
        type="search"
        placeholder="Поиск по имени или e-mail"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        aria-label="Поиск наблюдателей"
      />
      <div className="chip-list choice-list" role="group" aria-labelledby={labelledBy}>
        {visible.map((u: UserRef) => {
          const checked = value.includes(u.id);
          const disabled = !checked && value.length >= MAX_OBSERVERS;
          return (
            <label key={u.id} className={`chip choice-chip${disabled ? ' disabled' : ''}`}>
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

// Мультивыбор исполнителей (≥1 — проверяется в форме). Без верхнего лимита.
export function AssigneesPicker({
  labelledBy,
  value,
  onChange,
}: {
  labelledBy?: string;
  value: string[];
  onChange: (ids: string[]) => void;
}) {
  const { data: users } = useQuery({ queryKey: ['users'], queryFn: () => api.listUsers() });
  const [query, setQuery] = useState('');

  const toggle = (id: string) => {
    if (value.includes(id)) {
      onChange(value.filter((v) => v !== id));
    } else {
      onChange([...value, id]);
    }
  };

  const visible = filterUsers(users ?? [], query);

  return (
    <div className="user-picker">
      <div className="muted">Выбрано исполнителей: {value.length}</div>
      <input
        className="picker-search"
        type="search"
        placeholder="Поиск по имени или e-mail"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        aria-label="Поиск исполнителей"
      />
      <div className="chip-list choice-list" role="group" aria-labelledby={labelledBy}>
        {visible.map((u: UserRef) => {
          const checked = value.includes(u.id);
          return (
            <label key={u.id} className="chip choice-chip">
              <input type="checkbox" checked={checked} onChange={() => toggle(u.id)} />
              {u.displayName} ({u.email})
            </label>
          );
        })}
      </div>
    </div>
  );
}
