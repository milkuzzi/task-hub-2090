import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '@/shared/api/client';
import { qk } from '@/shared/api/queryKeys';
import { STR } from '@/shared/strings';
import { useRealtime } from '@/shared/realtime/useRealtime';
import type { Notification } from '@/shared/types';

export function Bell() {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const { connected } = useRealtime();
  const [open, setOpen] = useState(false);

  // Счётчик непрочитанных — живёт по WS; при отсутствии WS поллим.
  const { data: count } = useQuery({
    queryKey: qk.notificationsUnread,
    queryFn: () => api.unreadCount(),
    refetchInterval: connected ? false : 30_000,
  });

  const { data: list } = useQuery({
    queryKey: qk.notifications,
    queryFn: () => api.listNotifications(),
    enabled: open,
  });

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: qk.notifications });
    qc.invalidateQueries({ queryKey: qk.notificationsUnread });
  };

  const markAll = useMutation({
    mutationFn: () => api.markRead(),
    onSuccess: invalidate,
  });

  const markOne = useMutation({
    mutationFn: (id: string) => api.markRead([id]),
    onSuccess: invalidate,
  });

  const unread = count?.unread ?? 0;

  const onClickNotification = (n: Notification) => {
    setOpen(false);
    markOne.mutate(n.id);
    if (n.taskId) navigate(`/tasks/${n.taskId}`);
  };

  return (
    <div className="bell">
      <button
        type="button"
        className="bell-button"
        aria-label={STR.bellAriaLabel}
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        <span aria-hidden>🔔</span>
        {unread > 0 && (
          <span className="bell-badge" data-testid="bell-badge">
            {unread > 99 ? '99+' : unread}
          </span>
        )}
      </button>

      {open && (
        <div className="bell-dropdown" role="menu">
          <div className="bell-header">
            <span>{STR.notifications}</span>
            <button type="button" className="btn" onClick={() => markAll.mutate()}>
              {STR.notificationsMarkAll}
            </button>
          </div>
          {!list || list.items.length === 0 ? (
            <p className="muted bell-empty">{STR.notificationsEmpty}</p>
          ) : (
            <ul className="bell-list">
              {list.items.map((n) => (
                <li key={n.id} className={n.isRead ? 'bell-row read' : 'bell-row'}>
                  <button
                    type="button"
                    className="bell-row-button"
                    onClick={() => onClickNotification(n)}
                  >
                    {n.text}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
