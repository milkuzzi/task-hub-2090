import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import type { TaskRole } from '@/shared/types';
import { api } from '@/shared/api/client';
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

  const { data, isLoading } = useQuery({
    queryKey: ['tasks', role],
    queryFn: () => api.listTasks({ role }),
  });

  // Выгрузка под печать требует авторизации (Bearer), поэтому грузим её через
  // axios (а не прямой ссылкой) и открываем готовый HTML из blob. Окно
  // открываем синхронно по клику, чтобы не сработал блокировщик всплывающих окон.
  const handlePrint = async () => {
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
    } catch {
      win?.close();
    }
  };

  const title =
    role === 'author' ? STR.tabAuthor : role === 'assignee' ? STR.tabAssignee : STR.tabObserver;
  const items = sortItems(data?.items ?? [], sort);

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
      {isLoading ? (
        <Spinner />
      ) : items.length === 0 ? (
        <EmptyState text={STR.empty} />
      ) : (
        <TasksTable
          items={items}
          role={role}
          sort={sort}
          onToggle={toggle}
          onRowClick={(id) => navigate('/tasks/' + id)}
        />
      )}
    </div>
  );
}
