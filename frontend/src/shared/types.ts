// Контракт API (camelCase) — зеркалит DTO бэкенда (§13.6.4).

export type TaskRole = 'author' | 'assignee' | 'observer';
export type TaskStatus = 'in_progress' | 'done' | 'cancelled';
export type DueMode = 'datetime' | 'date';
export type AttachKind = 'file' | 'url';

export interface UserRef {
  id: string;
  email: string;
  displayName: string;
  isDeleted: boolean;
}

export interface User {
  id: string;
  email: string;
  isAdmin: boolean;
  displayName: string;
}

export interface Attachment {
  id: string;
  kind: AttachKind;
  filename: string | null;
  size: number | null;
  contentType: string | null;
  url: string | null;
  downloadUrl: string | null;
}

export interface ReportOut {
  text: string | null;
  attachments: Attachment[];
  ready: boolean;
  readyAt: string | null;
  updatedAt: string | null;
}

export interface TaskListItem {
  id: string;
  seqNo: number;
  code: string;
  title: string;
  deadline: string;
  deadlineHasTime: boolean;
  status: TaskStatus;
  isOverdue: boolean;
  needsReassignment: boolean;
  assignee: UserRef;
  author: UserRef;
  observers: UserRef[];
  assigneeMarkedReady: boolean;
  createdAt: string;
}

export interface TaskDetail extends TaskListItem {
  description: string | null;
  attachments: Attachment[];
  report: ReportOut | null;
  updatedAt: string;
}

export interface TaskListResponse {
  items: TaskListItem[];
  total: number;
  page: number;
  pageSize: number;
}

export interface RegistryItem {
  id: string;
  email: string;
  fullName: string | null;
  maxContact: string | null;
  isAdmin: boolean;
  registered: boolean;
  userId: string | null;
}

export interface RegistryListResponse {
  items: RegistryItem[];
  total: number;
}

// Вход для создания/обновления записи реестра — без isAdmin: администратора
// нельзя выдать через реестр (только консоль и передача администрирования).
export interface RegistryInput {
  email: string;
  fullName?: string | null;
}

export interface TransferAdminResult {
  completed: boolean;
  email: string;
  emailSent?: boolean | null;
}

export interface TokenResponse {
  accessToken: string;
  tokenType: string;
  user: User;
}

export interface ApiErrorBody {
  error: { code: string; message: string; details?: { field: string; message: string }[] };
}

export interface CreateTaskInput {
  title: string;
  description?: string | null;
  dueAt: string;
  dueMode: DueMode;
  assigneeId: string;
  observerIds: string[];
  links?: string[];
}

export interface UpdateTaskInput {
  title?: string;
  description?: string | null;
  dueAt?: string;
  dueMode?: DueMode;
  assigneeId?: string;
  observerIds?: string[];
}
