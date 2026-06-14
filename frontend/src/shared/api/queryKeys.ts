export const qk = {
  me: ['me'] as const,
  profile: ['profile'] as const,
  avatar: (userId: string) => ['avatar', userId] as const,
  tasks: (role: string, params: Record<string, string | undefined>) =>
    ['tasks', role, params] as const,
  task: (id: string) => ['task', id] as const,
  registry: (query: string) => ['registry', query] as const,
  messages: (taskId: string) => ['messages', taskId] as const,
  notifications: ['notifications'] as const,
  notificationsUnread: ['notifications', 'unread'] as const,
};
