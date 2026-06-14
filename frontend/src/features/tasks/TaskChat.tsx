import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '@/shared/api/client';
import { qk } from '@/shared/api/queryKeys';
import { STR } from '@/shared/strings';
import { errorMessage } from '@/shared/api/http';
import { useRealtime } from '@/shared/realtime/useRealtime';
import { Avatar } from '@/shared/ui/Avatar';
import { Spinner } from '@/shared/ui/Spinner';
import type { MessageListResponse } from '@/shared/types';

function formatTime(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export default function TaskChat({ taskId }: { taskId: string }) {
  const qc = useQueryClient();
  const { connected } = useRealtime();
  const [text, setText] = useState('');
  const [sendError, setSendError] = useState('');

  const { data, isLoading, isError } = useQuery({
    queryKey: qk.messages(taskId),
    queryFn: () => api.listMessages(taskId),
    // Фоллбэк-поллинг, когда WS не подключён (деградация без потери чата).
    refetchInterval: connected ? false : 15_000,
  });

  const sendMutation = useMutation({
    mutationFn: (body: string) => api.postMessage(taskId, body),
    onSuccess: (msg) => {
      setText('');
      setSendError('');
      // Оптимистично кладём своё сообщение в кэш (WS-эхо отсеется по id).
      qc.setQueryData<MessageListResponse>(qk.messages(taskId), (prev) => {
        if (!prev) return { items: [msg], nextAfter: null };
        if (prev.items.some((m) => m.id === msg.id)) return prev;
        return { ...prev, items: [...prev.items, msg] };
      });
    },
    onError: (err) => setSendError(errorMessage(err)),
  });

  const loadMoreMutation = useMutation({
    mutationFn: (after: string) => api.listMessages(taskId, after),
    onSuccess: (next) => {
      qc.setQueryData<MessageListResponse>(qk.messages(taskId), (prev) => {
        if (!prev) return next;
        const known = new Set(prev.items.map((m) => m.id));
        const merged = [...prev.items, ...next.items.filter((m) => !known.has(m.id))];
        return { items: merged, nextAfter: next.nextAfter };
      });
    },
  });

  const submit = () => {
    const body = text.trim();
    if (!body || sendMutation.isPending) return;
    sendMutation.mutate(body);
  };

  return (
    <section className="task-chat" aria-label={STR.chatTitle}>
      <h2>{STR.chatTitle}</h2>

      {isLoading && <Spinner />}
      {isError && <div className="form-error">{STR.taskUnavailable}</div>}

      {data && (
        <>
          {data.nextAfter && (
            <button
              type="button"
              className="btn"
              disabled={loadMoreMutation.isPending}
              onClick={() => loadMoreMutation.mutate(data.nextAfter!)}
            >
              {STR.chatLoadEarlier}
            </button>
          )}
          {data.items.length === 0 ? (
            <p className="muted">{STR.chatEmpty}</p>
          ) : (
            <ul className="chat-list">
              {data.items.map((m) => (
                <li className="chat-item" key={m.id}>
                  <Avatar name={m.authorName} userId={m.authorId} size={32} />
                  <div className="chat-body">
                    <div className="chat-meta">
                      <span className="chat-author">{m.authorName}</span>
                      <span className="chat-time">{formatTime(m.createdAt)}</span>
                    </div>
                    {/* Тело рендерится как текст (React экранирует) */}
                    <div className="chat-text">{m.body}</div>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </>
      )}

      {sendError && <div className="form-error">{sendError}</div>}

      <div className="chat-input">
        <textarea
          aria-label={STR.chatPlaceholder}
          placeholder={STR.chatPlaceholder}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              submit();
            }
          }}
        />
        <button
          type="button"
          className="btn primary"
          disabled={!text.trim() || sendMutation.isPending}
          onClick={submit}
        >
          {STR.chatSend}
        </button>
      </div>
    </section>
  );
}
