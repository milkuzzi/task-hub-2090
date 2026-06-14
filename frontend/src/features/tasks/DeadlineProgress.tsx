import type { TaskListItem } from '@/shared/types';
import { deadlineProgress } from '@/shared/lib/date';

/**
 * Тонкий индикатор «сколько времени окна задачи прошло» (от создания до срока).
 * Чем заполненнее — тем ближе дедлайн. Цвет: норма → янтарь (≥70%) → красный
 * (≥90% или просрочка). Для завершённых/отменённых задач не показываем.
 */
export default function DeadlineProgress({
  item,
}: {
  item: Pick<TaskListItem, 'status' | 'createdAt' | 'deadline'>;
}) {
  if (item.status !== 'in_progress') return null;

  const pct = Math.round(deadlineProgress(item.createdAt, item.deadline) * 100);
  const level = pct >= 90 ? 'danger' : pct >= 70 ? 'warn' : 'ok';

  return (
    <div
      className="deadline-progress"
      role="progressbar"
      aria-valuenow={pct}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-label="Прошло времени до срока"
    >
      <span className={`deadline-progress-fill ${level}`} style={{ width: `${pct}%` }} />
    </div>
  );
}
