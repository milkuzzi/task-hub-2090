import { describe, expect, it } from 'vitest';
import { QueryClient } from '@tanstack/react-query';
import { routeMessage } from '@/shared/realtime/useRealtime';
import { qk } from '@/shared/api/queryKeys';
import type { MessageListResponse, TaskMessage } from '@/shared/types';

function msg(id: string): TaskMessage {
  return {
    id,
    authorId: 'u1',
    authorName: 'Иван',
    body: `тело ${id}`,
    createdAt: '2026-06-14T10:00:00Z',
  };
}

describe('routeMessage (WS → react-query)', () => {
  it('chat: добавляет сообщение в кэш ленты задачи', () => {
    const qc = new QueryClient();
    const initial: MessageListResponse = { items: [msg('a')], nextAfter: null };
    qc.setQueryData(qk.messages('t1'), initial);

    routeMessage(qc, { type: 'chat', taskId: 't1', message: msg('b') });

    const after = qc.getQueryData<MessageListResponse>(qk.messages('t1'));
    expect(after?.items.map((m) => m.id)).toEqual(['a', 'b']);
  });

  it('chat: дубликат по id не добавляется', () => {
    const qc = new QueryClient();
    qc.setQueryData(qk.messages('t1'), { items: [msg('a')], nextAfter: null });

    routeMessage(qc, { type: 'chat', taskId: 't1', message: msg('a') });

    const after = qc.getQueryData<MessageListResponse>(qk.messages('t1'));
    expect(after?.items).toHaveLength(1);
  });

  it('chat: не трогает кэш другой задачи / отсутствующий кэш', () => {
    const qc = new QueryClient();
    routeMessage(qc, { type: 'chat', taskId: 'missing', message: msg('a') });
    expect(qc.getQueryData(qk.messages('missing'))).toBeUndefined();
  });

  it('notification: инвалидирует очереди уведомлений', () => {
    const qc = new QueryClient();
    let invalidated: unknown[] = [];
    qc.invalidateQueries = ((opts: { queryKey: unknown[] }) => {
      invalidated.push(opts.queryKey);
      return Promise.resolve();
    }) as typeof qc.invalidateQueries;

    routeMessage(qc, {
      type: 'notification',
      notification: {
        id: 'n1',
        kind: 'chat_message',
        text: 'привет',
        taskId: 't1',
        messageId: 'm1',
        isRead: false,
        createdAt: '2026-06-14T10:00:00Z',
      },
    });

    expect(invalidated).toContainEqual(qk.notifications);
    expect(invalidated).toContainEqual(qk.notificationsUnread);
  });
});
