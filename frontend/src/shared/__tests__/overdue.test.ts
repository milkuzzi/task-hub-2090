import { describe, expect, it } from 'vitest';
import { isVisuallyOverdue } from '@/shared/lib/overdue';

describe('isVisuallyOverdue', () => {
  const future = new Date(Date.now() + 86_400_000).toISOString();
  const past = new Date(Date.now() - 86_400_000).toISOString();

  it('доверяет серверному флагу', () => {
    expect(isVisuallyOverdue({ isOverdue: true, status: 'in_progress', deadline: future })).toBe(true);
  });

  it('открытая задача с прошедшим сроком — просрочена по факту', () => {
    expect(isVisuallyOverdue({ isOverdue: false, status: 'in_progress', deadline: past })).toBe(true);
  });

  it('открытая задача с будущим сроком — не просрочена', () => {
    expect(isVisuallyOverdue({ isOverdue: false, status: 'in_progress', deadline: future })).toBe(false);
  });

  it('закрытая задача без флага — не просрочена', () => {
    expect(isVisuallyOverdue({ isOverdue: false, status: 'done', deadline: past })).toBe(false);
  });
});
