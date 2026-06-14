import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { api } from '@/shared/api/client';
import { daysToDeadline, formatRemaining, DAY_MS } from '@/shared/lib/date';
import { STR } from '@/shared/strings';

/** «Дней до ближайшего дедлайна» по открытым задачам пользователя-исполнителя (§7 п.3). */
export function DeadlineCounter() {
  const { data } = useQuery({
    queryKey: ['tasks', 'assignee', { status: 'in_progress' }],
    queryFn: () => api.listTasks({ role: 'assignee', status: 'in_progress' }),
  });

  const items = (data?.items ?? []).filter((t) => t.status === 'in_progress');
  if (items.length === 0) return null;

  // Ближайшая по сроку задача (минимальный due_at) — её и описывает счётчик.
  const sorted = [...items].sort(
    (a, b) => new Date(a.deadline).getTime() - new Date(b.deadline).getTime(),
  );
  const nearest = sorted[0]!;
  const now = Date.now();
  const remainingMs = new Date(nearest.deadline).getTime() - now;
  const over = remainingMs < 0;
  // «Срочно»: до срока меньше суток — показываем часы/минуты и подсвечиваем красным.
  const urgent = !over && remainingMs < DAY_MS;

  // Кнопка перехода — к ближайшей ПРЕДСТОЯЩЕЙ задаче (с будущим сроком). Если
  // все сроки уже прошли — кнопку скрываем.
  const upcoming = sorted.find((t) => new Date(t.deadline).getTime() >= now) ?? null;

  let text: string;
  if (over) {
    text = `Ближайший ${STR.deadlinePassed} (просрочка ${-daysToDeadline(nearest.deadline)} дн.)`;
  } else if (urgent) {
    text = `${STR.timeToDeadline}: ${formatRemaining(remainingMs)}`;
  } else {
    text = `${STR.daysToDeadline}: ${daysToDeadline(nearest.deadline)}`;
  }

  return (
    <div className={`deadline-counter${over || urgent ? ' over' : ''}`}>
      <span>{text}</span>
      {upcoming && (
        <Link className="deadline-counter-link" to={`/tasks/${upcoming.id}`}>
          {STR.goToNearestDeadline}
        </Link>
      )}
    </div>
  );
}
