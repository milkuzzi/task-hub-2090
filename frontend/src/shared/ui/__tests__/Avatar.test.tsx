import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Avatar, initialsOf } from '@/shared/ui/Avatar';

describe('Avatar', () => {
  it('initialsOf берёт до двух первых букв', () => {
    expect(initialsOf('Иван Петров')).toBe('ИП');
    expect(initialsOf('Анна')).toBe('А');
    expect(initialsOf('')).toBe('');
    expect(initialsOf(null)).toBe('');
  });

  it('рисует инициалы по имени', () => {
    render(<Avatar name="Иван Петров" />);
    expect(screen.getByText('ИП')).toBeInTheDocument();
  });

  it('заглушка «•» для пустого имени', () => {
    render(<Avatar name="" />);
    expect(screen.getByText('•')).toBeInTheDocument();
  });

  it('рисует картинку, когда задан src', () => {
    render(<Avatar name="Иван" src="/api/v1/users/1/avatar" />);
    const img = screen.getByRole('img');
    expect(img).toHaveAttribute('src', '/api/v1/users/1/avatar');
  });
});
