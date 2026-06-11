import { describe, expect, it } from 'vitest';
import { STR } from '@/shared/strings';

// §13.7.3 Ж: фраза отказа должна совпадать дословно с константой бэкенда.
describe('фраза отказа в доступе', () => {
  it('совпадает дословно (регистр и точка)', () => {
    expect(STR.noAccess).toBe('Извините, у вас нет доступа к сервису.');
  });
});
