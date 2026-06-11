import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import type { TaskRole } from '@/shared/types';
import { api } from '@/shared/api/client';
import { STR } from '@/shared/strings';
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

  const title =
    role === 'author' ? STR.tabAuthor : role === 'assignee' ? STR.tabAssignee : STR.tabObserver;
  const items = sortItems(data?.items ?? [], sort);

  return (
    <div className="panel">
      <div className="between">
        <h2>{title}</h2>
        <div className="row">
          {role === 'author' ? (
            <button className="btn primary" onClick={() => navigate('/tasks/new')}>
              {STR.addTask}
            </button>
          ) : null}
          <button className="btn" onClick={() => window.open(api.exportUrl(role), '_blank')}>
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
