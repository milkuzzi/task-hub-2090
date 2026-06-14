import { describe, expect, it } from 'vitest';
import { formatRemaining, deadlineProgress } from '@/shared/lib/date';

describe('formatRemaining', () => {
  it('часы и минуты, когда больше часа', () => {
    expect(formatRemaining((5 * 60 + 30) * 60_000)).toBe('5 ч 30 мин');
  });

  it('только минуты, когда меньше часа', () => {
    expect(formatRemaining(30 * 60_000)).toBe('30 мин');
  });

  it('ровно час — 1 ч 0 мин', () => {
    expect(formatRemaining(60 * 60_000)).toBe('1 ч 0 мин');
  });

  it('нулевой/отрицательный остаток — 0 мин', () => {
    expect(formatRemaining(0)).toBe('0 мин');
    expect(formatRemaining(-1000)).toBe('0 мин');
  });
});

describe('deadlineProgress', () => {
  const created = '2024-01-01T00:00:00Z';
  const due = '2024-01-11T00:00:00Z'; // окно 10 суток

  it('середина окна → 0.5', () => {
    const now = new Date('2024-01-06T00:00:00Z').getTime();
    expect(deadlineProgress(created, due, now)).toBeCloseTo(0.5, 5);
  });

  it('до начала окна → 0 (clamp)', () => {
    const now = new Date('2023-12-31T00:00:00Z').getTime();
    expect(deadlineProgress(created, due, now)).toBe(0);
  });

  it('после срока → 1 (clamp)', () => {
    const now = new Date('2024-02-01T00:00:00Z').getTime();
    expect(deadlineProgress(created, due, now)).toBe(1);
  });

  it('некорректное окно (due ≤ created) → 1', () => {
    expect(deadlineProgress(due, created, new Date(created).getTime())).toBe(1);
  });
});
