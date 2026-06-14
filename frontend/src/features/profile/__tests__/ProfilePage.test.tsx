import { describe, expect, it, vi, beforeEach, type Mock } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import ProfilePage from '@/features/profile/ProfilePage';
import { useAuthStore } from '@/shared/auth/store';
import type { Profile } from '@/shared/types';

vi.mock('@/shared/api/client', () => ({
  api: {
    getMe: vi.fn(),
    updateMe: vi.fn(),
    uploadAvatar: vi.fn(),
    deleteAvatar: vi.fn(),
    fetchAvatarBlob: vi.fn(),
  },
}));

import { api } from '@/shared/api/client';

const PROFILE: Profile = {
  id: 'u1',
  email: 'me@s.ru',
  displayName: 'Иван Петров',
  isAdmin: false,
  maxContact: '@ivan',
  hasAvatar: false,
};

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <ProfilePage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('ProfilePage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    URL.createObjectURL = vi.fn(() => 'blob:preview');
    URL.revokeObjectURL = vi.fn();
    useAuthStore.setState({
      accessToken: 't',
      user: { id: 'u1', email: 'me@s.ru', isAdmin: false, displayName: 'Иван Петров' },
    });
    (api.getMe as Mock).mockResolvedValue(PROFILE);
  });

  it('загружает профиль и заполняет поля', async () => {
    renderPage();
    await waitFor(() => expect(screen.getByDisplayValue('Иван Петров')).toBeInTheDocument());
    expect(screen.getByDisplayValue('@ivan')).toBeInTheDocument();
    expect(screen.getByDisplayValue('me@s.ru')).toBeInTheDocument();
  });

  it('сохраняет изменения профиля (обрезает пробелы)', async () => {
    (api.updateMe as Mock).mockResolvedValue({ ...PROFILE, maxContact: '+79990001122' });
    renderPage();
    await waitFor(() => expect(screen.getByDisplayValue('@ivan')).toBeInTheDocument());

    const maxInput = screen.getByDisplayValue('@ivan');
    fireEvent.change(maxInput, { target: { value: '  +79990001122 ' } });
    fireEvent.click(screen.getByRole('button', { name: 'Сохранить' }));

    await waitFor(() =>
      expect(api.updateMe).toHaveBeenCalledWith({
        displayName: 'Иван Петров',
        maxContact: '+79990001122',
      }),
    );
  });

  it('загружает выбранный файл-аватар', async () => {
    (api.uploadAvatar as Mock).mockResolvedValue({ ...PROFILE, hasAvatar: true });
    renderPage();
    await waitFor(() => expect(screen.getByDisplayValue('@ivan')).toBeInTheDocument());

    const file = new File(['data'], 'a.png', { type: 'image/png' });
    const input = screen.getByTestId('avatar-file-input') as HTMLInputElement;
    fireEvent.change(input, { target: { files: [file] } });

    await waitFor(() => expect(api.uploadAvatar).toHaveBeenCalledWith(file));
  });

  it('показывает ошибку при отклонении аватара сервером', async () => {
    (api.uploadAvatar as Mock).mockRejectedValue({
      isAxiosError: true,
      response: { data: { error: { code: 'UNSUPPORTED_MEDIA_TYPE', message: 'Недопустимый тип файла.' } } },
    });
    renderPage();
    await waitFor(() => expect(screen.getByDisplayValue('@ivan')).toBeInTheDocument());

    const file = new File(['data'], 'evil.png', { type: 'image/png' });
    const input = screen.getByTestId('avatar-file-input') as HTMLInputElement;
    fireEvent.change(input, { target: { files: [file] } });

    await waitFor(() => expect(api.uploadAvatar).toHaveBeenCalled());
    // Ошибка отрисована (errorMessage достаёт message из тела axios-ошибки).
    await waitFor(() => expect(screen.getByText(/Недопустимый тип файла/)).toBeInTheDocument());
  });
});
