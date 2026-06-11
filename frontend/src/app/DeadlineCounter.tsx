import { useQuery } from '@tanstack/react-query';
import { api } from '@/shared/api/client';
import { daysToDeadline } from '@/shared/lib/date';
import { STR } from '@/shared/strings';

/** «Дней до ближайшего дедлайна» по открытым задачам пользователя-исполнителя (§7 п.3). */
export function DeadlineCounter() {
  const { data } = useQuery({
    queryKey: ['tasks', 'assignee', { status: 'in_progress' }],
    queryFn: () => api.listTasks({ role: 'assignee', status: 'in_progress' }),
  });

  const items = data?.items ?? [];
  if (items.length === 0) return null;

  const nearest = Math.min(...items.map((t) => daysToDeadline(t.deadline)));
  const over = nearest < 0;

  return (
    <div className={`deadline-counter${over ? ' over' : ''}`}>
      {over
        ? `Ближайший ${STR.deadlinePassed} (просрочка ${-nearest} дн.)`
        : `${STR.daysToDeadline}: ${nearest}`}
    </div>
  );
}
