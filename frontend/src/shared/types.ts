// Контракт API (camelCase) — зеркалит DTO бэкенда (§13.6.4).

export type TaskRole = 'author' | 'assignee' | 'observer';
export type TaskStatus = 'in_progress' | 'under_review' | 'rework' | 'done' | 'cancelled';
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

// --- Профиль пользователя (§8) ---
export interface Profile {
  id: string;
  email: string;
  displayName: string;
  isAdmin: boolean;
  maxContact: string | null;
  hasAvatar: boolean;
}

export interface ProfileUpdateInput {
  displayName?: string;
  maxContact?: string;
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
  assignees: UserRef[];
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
  assigneeIds: string[];
  observerIds: string[];
  links?: string[];
}

export interface UpdateTaskInput {
  title?: string;
  description?: string | null;
  dueAt?: string;
  dueMode?: DueMode;
  assigneeIds?: string[];
  observerIds?: string[];
}

export type ReviewDecision = 'accept' | 'rework';

// --- Чат задачи (§4) ---
export interface TaskMessage {
  id: string;
  authorId: string;
  authorName: string;
  body: string;
  createdAt: string;
}

export interface MessageListResponse {
  items: TaskMessage[];
  nextAfter: string | null;
}

// --- On-site уведомления (§6) ---
export type NotificationKind = 'chat_message' | 'task_rework';

export interface Notification {
  id: string;
  kind: NotificationKind | string;
  text: string;
  taskId: string | null;
  messageId: string | null;
  isRead: boolean;
  createdAt: string;
}

export interface NotificationListResponse {
  items: Notification[];
  unread: number;
}

export interface UnreadCountResponse {
  unread: number;
}

export interface MarkReadResponse {
  marked: number;
  unread: number;
}

// --- WebSocket: серверные сообщения ---
export type RealtimeMessage =
  | { type: 'ready' }
  | { type: 'chat'; taskId: string; message: TaskMessage }
  | { type: 'notification'; notification: Notification };
