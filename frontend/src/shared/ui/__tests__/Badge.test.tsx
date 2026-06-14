import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { StatusBadge, OverdueBadge, ReassignBadge } from '@/shared/ui/Badge';

describe('Бейджи', () => {
  it('StatusBadge показывает русскую метку статуса', () => {
    render(<StatusBadge status="in_progress" />);
    expect(screen.getByText('В работе')).toBeInTheDocument();
  });

  it('StatusBadge для done', () => {
    render(<StatusBadge status="done" />);
    expect(screen.getByText('Выполнена')).toBeInTheDocument();
  });

  it('StatusBadge для under_review', () => {
    render(<StatusBadge status="under_review" />);
    expect(screen.getByText('На проверке')).toBeInTheDocument();
  });

  it('StatusBadge для rework', () => {
    render(<StatusBadge status="rework" />);
    expect(screen.getByText('На доработку')).toBeInTheDocument();
  });

  it('OverdueBadge показывает «Просрочена»', () => {
    render(<OverdueBadge />);
    expect(screen.getByText('Просрочена')).toBeInTheDocument();
  });

  it('ReassignBadge показывает требование переназначения', () => {
    render(<ReassignBadge />);
    expect(screen.getByText('Требуется переназначение исполнителя')).toBeInTheDocument();
  });
});
