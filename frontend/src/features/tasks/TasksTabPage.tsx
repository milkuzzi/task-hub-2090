import { useNavigate } from 'react-router-dom';
import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import type { TaskRole } from '@/shared/types';
import { api } from '@/shared/api/client';
import { errorMessage } from '@/shared/api/http';
import { STR } from '@/shared/strings';
import { saveBlob } from '@/shared/lib/download';
import { Spinner, EmptyState } from '@/shared/ui/Spinner';
import TasksTable from './TasksTable';
import { useTableSort, sortItems } from './useTableSort';

interface TasksTabPageProps {
  role: TaskRole;
}

export default function TasksTabPage({ role }: TasksTabPageProps) {
  const navigate = useNavigate();
  const { sort, toggle } = useTableSort();
  const [search, setSearch] = useState('');
  const [printError, setPrintError] = useState<string | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ['tasks', role],
    queryFn: () => api.listTasks({ role }),
  });

  // Выгрузка под печать требует авторизации (Bearer), поэтому грузим её через
  // axios (а не прямой ссылкой) и открываем готовый HTML из blob. Окно
  // открываем синхронно по клику, чтобы не сработал блокировщик всплывающих окон.
  const handlePrint = async () => {
    setPrintError(null);
    const win = window.open('', '_blank');
    try {
      const blob = await api.exportTasks(role);
      const url = URL.createObjectURL(blob);
      if (win) {
        win.location.href = url;
        setTimeout(() => URL.revokeObjectURL(url), 60_000);
      } else {
        saveBlob(blob, `tasks-${role}.html`);
        URL.revokeObjectURL(url);
      }
    } catch (err) {
      win?.close();
      setPrintError(errorMessage(err));
    }
  };

  const title =
    role === 'author' ? STR.tabAuthor : role === 'assignee' ? STR.tabAssignee : STR.tabObserver;
  const items = sortItems(data?.items ?? [], sort);

  // Клиентский фильтр по уже загруженному списку (page_size 500): совпадение по
  // названию (подстрока без учёта регистра) ИЛИ по ID — 6-значному коду (code)
  // или порядковому номеру (seqNo), если запрос содержит цифры.
  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return items;
    const digits = q.replace(/\D/g, '');
    return items.filter((t) => {
      if (t.title.toLowerCase().includes(q)) return true;
      if (digits && (t.code.includes(digits) || String(t.seqNo).includes(digits))) return true;
      return false;
    });
  }, [items, search]);

  return (
    <div className="panel">
      <div className="between">
        <h1>{title}</h1>
        <div className="row">
          {role === 'author' ? (
            <button className="btn primary" onClick={() => navigate('/tasks/new')}>
              {STR.addTask}
            </button>
          ) : null}
          <button className="btn" onClick={handlePrint}>
            {STR.print}
          </button>
        </div>
      </div>
      {printError && <div className="form-error">{printError}</div>}
      {isLoading ? (
        <Spinner />
      ) : (
        <>
          <div className="field tasks-search">
            <input
              id="tasks-search"
              type="search"
              aria-label={STR.searchPlaceholder}
              placeholder={STR.searchPlaceholder}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
          {filtered.length === 0 ? (
            <EmptyState text={search.trim() ? STR.nothingFound : STR.empty} />
          ) : (
            <TasksTable
              items={filtered}
              role={role}
              sort={sort}
              onToggle={toggle}
              onRowClick={(id) => navigate('/tasks/' + id)}
            />
          )}
        </>
      )}
    </div>
  );
}
