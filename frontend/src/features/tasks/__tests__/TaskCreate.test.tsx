import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';

// Picker подтягивает реестр пользователей — мокаем целиком клиент API.
vi.mock('@/shared/api/client', () => ({
  api: {
    createTask: vi.fn(() => Promise.resolve({ id: 'new-task-1' })),
    listUsers: vi.fn(() => Promise.resolve([])),
  },
}));

const navigateMock = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return { ...actual, useNavigate: () => navigateMock };
});

import { api } from '@/shared/api/client';
import TaskCreatePage from '@/features/tasks/TaskCreatePage';

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <TaskCreatePage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

// Заполняет минимально валидную форму, выбирая исполнителя через внутреннее
// состояние пикета напрямую невозможно — поэтому задаём исполнителя в обход
// через DOM был бы хрупким. Вместо этого тестируем форму с предзаполнением.
describe('TaskCreatePage — вложения при создании (§6)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('показывает поле вложений в режиме создания', () => {
    renderPage();
    expect(screen.getByLabelText('Вложения')).toBeInTheDocument();
  });

  it('прикреплённый файл можно удалить до отправки (Req 1.4)', () => {
    renderPage();
    const input = screen.getByLabelText('Вложения') as HTMLInputElement;
    const file = new File(['hello'], 'doc.txt', { type: 'text/plain' });
    fireEvent.change(input, { target: { files: [file] } });

    expect(screen.getByTestId('pending-files')).toHaveTextContent('doc.txt');

    fireEvent.click(screen.getByLabelText('Удалить вложение doc.txt'));
    expect(screen.queryByTestId('pending-files')).not.toBeInTheDocument();
  });

  it('валидация без исполнителя не вызывает создание', async () => {
    renderPage();
    fireEvent.change(screen.getByLabelText('Название'), { target: { value: 'Тест' } });
    fireEvent.click(screen.getByRole('button', { name: 'Сохранить' }));
    await waitFor(() =>
      expect(screen.getByText('Выберите хотя бы одного исполнителя')).toBeInTheDocument(),
    );
    expect(api.createTask).not.toHaveBeenCalled();
  });
});
