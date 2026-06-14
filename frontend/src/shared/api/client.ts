import { http } from './http';
import type {
  CreateTaskInput,
  MarkReadResponse,
  MessageListResponse,
  NotificationListResponse,
  RegistryInput,
  RegistryItem,
  RegistryListResponse,
  ReviewDecision,
  TaskDetail,
  TaskListResponse,
  TaskMessage,
  TaskStatus,
  TokenResponse,
  TransferAdminResult,
  UnreadCountResponse,
  UpdateTaskInput,
  User,
  UserRef,
} from '@/shared/types';
import type { Profile, ProfileUpdateInput } from '@/shared/types';

// --- Auth ---
export const api = {
  login: (email: string, password: string) =>
    http.post<TokenResponse>('/auth/login', { email, password }).then((r) => r.data),
  logout: () => http.post('/auth/logout').then((r) => r.data),
  me: () => http.get<User>('/auth/me').then((r) => r.data),

  // --- Users (выбор исполнителя/наблюдателей) ---
  listUsers: (query?: string) =>
    http.get<UserRef[]>('/users', { params: { query } }).then((r) => r.data),

  // --- Профиль (§8) ---
  getMe: () => http.get<Profile>('/users/me').then((r) => r.data),
  updateMe: (input: ProfileUpdateInput) =>
    http.patch<Profile>('/users/me', input).then((r) => r.data),
  uploadAvatar: (file: File) => {
    const form = new FormData();
    form.append('file', file);
    return http.put<Profile>('/users/me/avatar', form).then((r) => r.data);
  },
  deleteAvatar: () => http.delete<Profile>('/users/me/avatar').then((r) => r.data),
  // Аватар отдаётся аутентифицированным эндпойнтом → грузим как blob через axios
  // (с Bearer), вызывающий код превращает его в object URL.
  fetchAvatarBlob: (userId: string) =>
    http
      .get<Blob>(`/users/${userId}/avatar`, { responseType: 'blob' })
      .then((r) => r.data),
  resetRequest: (email: string) =>
    http.post('/auth/password-reset/request', { email }).then((r) => r.data),
  resetConfirm: (token: string, newPassword: string) =>
    http.post('/auth/password-reset/confirm', { token, newPassword }).then((r) => r.data),

  // --- Tasks ---
  listTasks: (params: {
    role: string;
    status?: string;
    sort?: string;
    order?: string;
    pageSize?: number;
  }) => {
    const { pageSize, ...rest } = params;
    return http
      .get<TaskListResponse>('/tasks', { params: { ...rest, page_size: pageSize ?? 500 } })
      .then((r) => r.data);
  },
  getTask: (id: string) => http.get<TaskDetail>(`/tasks/${id}`).then((r) => r.data),
  createTask: (input: CreateTaskInput, files: File[] = []) => {
    // Контракт §6 (multipart/form-data): тело задачи JSON-строкой в поле
    // `payload` + ноль или более `files`. Работает и при нулевом числе файлов.
    const form = new FormData();
    form.append('payload', JSON.stringify(input));
    for (const file of files) form.append('files', file);
    return http.post<TaskDetail>('/tasks', form).then((r) => r.data);
  },
  updateTask: (id: string, input: UpdateTaskInput) =>
    http.put<TaskDetail>(`/tasks/${id}`, input).then((r) => r.data),
  deleteTask: (id: string) => http.delete(`/tasks/${id}`).then((r) => r.data),
  changeStatus: (id: string, status: TaskStatus) =>
    http.patch<TaskDetail>(`/tasks/${id}/status`, { status }).then((r) => r.data),
  submitReview: (id: string) =>
    http.post<TaskDetail>(`/tasks/${id}/submit-review`).then((r) => r.data),
  reviewDecision: (id: string, decision: ReviewDecision) =>
    http.post<TaskDetail>(`/tasks/${id}/review`, { decision }).then((r) => r.data),
  addReport: (id: string, text: string) =>
    http.post<TaskDetail>(`/tasks/${id}/report`, { text }).then((r) => r.data),
  markReady: (id: string, text?: string) =>
    http.post(`/tasks/${id}/mark-ready`, { text }).then((r) => r.data),
  addAttachment: (id: string, scope: 'task' | 'report', form: FormData) =>
    http
      .post(`/tasks/${id}/attachments`, form, { params: { scope } })
      .then((r) => r.data),
  deleteAttachment: (id: string, attId: string) =>
    http.delete(`/tasks/${id}/attachments/${attId}`).then((r) => r.data),
  downloadAttachment: (id: string, attId: string) =>
    http
      .get<Blob>(`/tasks/${id}/attachments/${attId}/download`, { responseType: 'blob' })
      .then((r) => r.data),
  exportTasks: (role: string, status?: string, sort?: string, order?: string) =>
    http
      .get('/tasks/export', {
        params: { role, format: 'print', status, sort, order },
        responseType: 'blob',
      })
      .then((r) => r.data as Blob),

  // --- Чат задачи (§4) ---
  listMessages: (taskId: string, after?: string) =>
    http
      .get<MessageListResponse>(`/tasks/${taskId}/messages`, { params: { after } })
      .then((r) => r.data),
  postMessage: (taskId: string, body: string) =>
    http.post<TaskMessage>(`/tasks/${taskId}/messages`, { body }).then((r) => r.data),

  // --- On-site уведомления (§6) ---
  listNotifications: (unread?: boolean) =>
    http
      .get<NotificationListResponse>('/notifications', { params: { unread } })
      .then((r) => r.data),
  unreadCount: () =>
    http.get<UnreadCountResponse>('/notifications/unread-count').then((r) => r.data),
  markRead: (ids?: string[]) =>
    http.post<MarkReadResponse>('/notifications/read', { ids }).then((r) => r.data),
  markReadForTask: (taskId: string) =>
    http.post<MarkReadResponse>('/notifications/read', { taskId }).then((r) => r.data),

  // --- Admin ---
  listRegistry: (query?: string) =>
    http
      .get<RegistryListResponse>('/admin/registry', { params: { query, page_size: 500 } })
      .then((r) => r.data),
  createRegistry: (body: RegistryInput) =>
    http.post<RegistryItem>('/admin/registry', body).then((r) => r.data),
  updateRegistry: (id: string, body: RegistryInput) =>
    http.put<RegistryItem>(`/admin/registry/${id}`, body).then((r) => r.data),
  deleteRegistry: (id: string) => http.delete(`/admin/registry/${id}`).then((r) => r.data),
  deleteUser: (id: string) =>
    http.delete(`/admin/users/${id}`, { params: { confirm: true } }).then((r) => r.data),
  transferAdmin: (email: string) =>
    http.post<TransferAdminResult>('/admin/transfer-admin', { email }).then((r) => r.data),
};
