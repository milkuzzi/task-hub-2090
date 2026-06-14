import type { TaskListItem } from '@/shared/types';

/**
 * Визуальная просрочка: материализованный флаг сервера ИЛИ «по факту» для
 * открытой задачи (на случай устаревшего кэша). Авторитетен сервер (§13.6.2).
 */
export function isVisuallyOverdue(item: Pick<TaskListItem, 'isOverdue' | 'status' | 'deadline'>): boolean {
  if (item.isOverdue) return true;
  if (item.status === 'done' || item.status === 'cancelled') return false;
  return Date.now() >= new Date(item.deadline).getTime();
}
