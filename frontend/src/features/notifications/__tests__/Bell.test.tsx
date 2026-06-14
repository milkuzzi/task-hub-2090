import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { Bell } from '@/features/notifications/Bell';

vi.mock('@/shared/api/client', () => ({
  api: {
    unreadCount: vi.fn(),
    listNotifications: vi.fn(),
    markRead: vi.fn(() => Promise.resolve({ marked: 1, unread: 0 })),
  },
}));

import { api } from '@/shared/api/client';

function renderBell() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <Bell />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('Bell', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('показывает бейдж с числом непрочитанных', async () => {
    (api.unreadCount as ReturnType<typeof vi.fn>).mockResolvedValue({ unread: 3 });
    (api.listNotifications as ReturnType<typeof vi.fn>).mockResolvedValue({ items: [], unread: 3 });
    renderBell();
    await waitFor(() => expect(screen.getByTestId('bell-badge')).toHaveTextContent('3'));
  });

  it('без непрочитанных бейдж не отображается', async () => {
    (api.unreadCount as ReturnType<typeof vi.fn>).mockResolvedValue({ unread: 0 });
    (api.listNotifications as ReturnType<typeof vi.fn>).mockResolvedValue({ items: [], unread: 0 });
    renderBell();
    await waitFor(() => expect(api.unreadCount).toHaveBeenCalled());
    expect(screen.queryByTestId('bell-badge')).not.toBeInTheDocument();
  });

  it('открывает список и показывает уведомления', async () => {
    (api.unreadCount as ReturnType<typeof vi.fn>).mockResolvedValue({ unread: 1 });
    (api.listNotifications as ReturnType<typeof vi.fn>).mockResolvedValue({
      items: [
        {
          id: 'n1',
          kind: 'chat_message',
          text: 'Новое сообщение',
          taskId: 't1',
          messageId: 'm1',
          isRead: false,
          createdAt: '2026-06-14T10:00:00Z',
        },
      ],
      unread: 1,
    });
    renderBell();
    await waitFor(() => expect(api.unreadCount).toHaveBeenCalled());
    fireEvent.click(screen.getByLabelText('Уведомления'));
    await waitFor(() => expect(screen.getByText('Новое сообщение')).toBeInTheDocument());
  });
});
