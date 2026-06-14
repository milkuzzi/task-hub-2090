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

/** Порог «меньше суток» (мс) — ниже него остаток показываем в часах/минутах. */
export const DAY_MS = 86_400_000;

/**
 * Остаток времени до срока в формате «часы/минуты» для дедлайнов ближе суток.
 * Чистая функция от миллисекунд остатка (удобно тестировать):
 * «5 ч 30 мин», «30 мин» (<1 ч), «0 мин» (срок наступил).
 */
export function formatRemaining(ms: number): string {
  if (ms <= 0) return '0 мин';
  const totalMinutes = Math.floor(ms / 60_000);
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;
  return hours > 0 ? `${hours} ч ${minutes} мин` : `${minutes} мин`;
}

/**
 * Доля прошедшего времени окна задачи в диапазоне [0..1]:
 * (now - created) / (due - created). Чем ближе к 1 — тем ближе дедлайн.
 * Некорректное/нулевое окно (due ≤ created) считаем заполненным (1).
 */
export function deadlineProgress(
  createdAtIso: string,
  dueAtIso: string,
  nowMs: number = Date.now(),
): number {
  const start = new Date(createdAtIso).getTime();
  const end = new Date(dueAtIso).getTime();
  if (!(end > start)) return 1;
  const frac = (nowMs - start) / (end - start);
  return Math.min(1, Math.max(0, frac));
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
