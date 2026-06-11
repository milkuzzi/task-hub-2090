export const qk = {
  me: ['me'] as const,
  tasks: (role: string, params: Record<string, string | undefined>) =>
    ['tasks', role, params] as const,
  task: (id: string) => ['task', id] as const,
  registry: (query: string) => ['registry', query] as const,
};
