import { http } from './http';
import type {
  CreateTaskInput,
  RegistryItem,
  RegistryListResponse,
  TaskDetail,
  TaskListResponse,
  TaskStatus,
  TokenResponse,
  UpdateTaskInput,
  User,
  UserRef,
} from '@/shared/types';

// --- Auth ---
export const api = {
  register: (email: string, password: string) =>
    http.post<TokenResponse>('/auth/register', { email, password }).then((r) => r.data),
  login: (email: string, password: string) =>
    http.post<TokenResponse>('/auth/login', { email, password }).then((r) => r.data),
  logout: () => http.post('/auth/logout').then((r) => r.data),
  me: () => http.get<User>('/auth/me').then((r) => r.data),

  // --- Users (выбор исполнителя/наблюдателей) ---
  listUsers: (query?: string) =>
    http.get<UserRef[]>('/users', { params: { query } }).then((r) => r.data),
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
  }) => http.get<TaskListResponse>('/tasks', { params }).then((r) => r.data),
  getTask: (id: string) => http.get<TaskDetail>(`/tasks/${id}`).then((r) => r.data),
  createTask: (input: CreateTaskInput) =>
    http.post<TaskDetail>('/tasks', input).then((r) => r.data),
  updateTask: (id: string, input: UpdateTaskInput) =>
    http.put<TaskDetail>(`/tasks/${id}`, input).then((r) => r.data),
  deleteTask: (id: string) => http.delete(`/tasks/${id}`).then((r) => r.data),
  changeStatus: (id: string, status: TaskStatus) =>
    http.patch<TaskDetail>(`/tasks/${id}/status`, { status }).then((r) => r.data),
  addReport: (id: string, text: string) =>
    http.post<TaskDetail>(`/tasks/${id}/report`, { text }).then((r) => r.data),
  markReady: (id: string, text?: string) =>
    http.post(`/tasks/${id}/mark-ready`, { text }).then((r) => r.data),
  searchByCode: (code: string) =>
    http.get<TaskDetail>('/tasks/search', { params: { code } }).then((r) => r.data),
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
  exportUrl: (role: string, status?: string, sort?: string, order?: string) => {
    const p = new URLSearchParams({ role, format: 'print' });
    if (status) p.set('status', status);
    if (sort) p.set('sort', sort);
    if (order) p.set('order', order);
    return `/api/v1/tasks/export?${p.toString()}`;
  },

  // --- Admin ---
  listRegistry: (query?: string) =>
    http
      .get<RegistryListResponse>('/admin/registry', { params: { query, pageSize: 500 } })
      .then((r) => r.data),
  createRegistry: (body: Partial<RegistryItem>) =>
    http.post<RegistryItem>('/admin/registry', body).then((r) => r.data),
  updateRegistry: (id: string, body: Partial<RegistryItem>) =>
    http.put<RegistryItem>(`/admin/registry/${id}`, body).then((r) => r.data),
  deleteRegistry: (id: string) => http.delete(`/admin/registry/${id}`).then((r) => r.data),
  deleteUser: (id: string) =>
    http.delete(`/admin/users/${id}`, { params: { confirm: true } }).then((r) => r.data),
};
