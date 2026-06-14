import { format } from 'date-fns';

export function formatDeadline(iso: string, hasTime: boolean): string {
  const d = new Date(iso);
  return hasTime ? format(d, 'dd.MM.yyyy HH:mm') : format(d, 'dd.MM.yyyy');
}

export function formatDateTime(iso: string): string {
  return format(new Date(iso), 'dd.MM.yyyy HH:mm');
}

/** Целых дней до срока (может быть отрицательным, если срок прошёл). */
export function daysToDeadline(iso: string): number {
  const diff = new Date(iso).getTime() - Date.now();
  return Math.ceil(diff / 86_400_000);
}

/** Для <input type="datetime-local"> / "date" — локальное представление. */
export function toInputValue(iso: string | undefined, hasTime: boolean): string {
  const d = iso ? new Date(iso) : new Date();
  const pad = (n: number) => String(n).padStart(2, '0');
  const date = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
  return hasTime ? `${date}T${pad(d.getHours())}:${pad(d.getMinutes())}` : date;
}

/**
 * Значение из input → строка для отправки на сервер.
 * Отправляем НАИВНУЮ локальную дату/время (без TZ-суффикса): сервер трактует её
 * в таймзоне организации (Europe/Moscow). Так выбранная пользователем дата не
 * «съезжает» на соседние сутки из-за пересчёта в UTC (важно для режима «только дата»).
 */
export function fromInputValue(value: string, hasTime: boolean): string {
  return hasTime ? `${value}:00` : `${value}T23:59:59`;
}
