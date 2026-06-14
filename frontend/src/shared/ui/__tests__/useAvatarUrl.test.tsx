import { describe, expect, it, vi, beforeEach, type Mock } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Avatar } from '@/shared/ui/Avatar';

// Эндпойнт аватара аутентифицирован → грузим как blob через axios-клиент.
vi.mock('@/shared/api/client', () => ({
  api: { fetchAvatarBlob: vi.fn() },
}));

import { api } from '@/shared/api/client';

function renderWithClient(ui: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

describe('Avatar c userId (useAvatarUrl)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // jsdom не реализует object URL — подставляем заглушки.
    URL.createObjectURL = vi.fn(() => 'blob:mock-url');
    URL.revokeObjectURL = vi.fn();
  });

  it('грузит аватар как blob (Bearer) и рисует картинку из object URL', async () => {
    (api.fetchAvatarBlob as Mock).mockResolvedValue(new Blob(['x'], { type: 'image/png' }));
    renderWithClient(<Avatar name="Иван Петров" userId="u1" />);
    await waitFor(() =>
      expect(screen.getByRole('img')).toHaveAttribute('src', 'blob:mock-url'),
    );
    expect(api.fetchAvatarBlob).toHaveBeenCalledWith('u1');
    expect(URL.createObjectURL).toHaveBeenCalled();
  });

  it('на 404/ошибке возвращает инициалы (фоллбэк)', async () => {
    (api.fetchAvatarBlob as Mock).mockRejectedValue(new Error('404'));
    renderWithClient(<Avatar name="Иван Петров" userId="u1" />);
    await waitFor(() => expect(api.fetchAvatarBlob).toHaveBeenCalled());
    expect(screen.getByText('ИП')).toBeInTheDocument();
    expect(screen.queryByRole('img')).not.toBeInTheDocument();
  });

  it('без userId не обращается к сети', async () => {
    renderWithClient(<Avatar name="Анна" />);
    expect(screen.getByText('А')).toBeInTheDocument();
    expect(api.fetchAvatarBlob).not.toHaveBeenCalled();
  });
});
