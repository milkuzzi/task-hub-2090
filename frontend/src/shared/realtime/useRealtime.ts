import {
  createContext,
  createElement,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import { useQueryClient, type QueryClient } from '@tanstack/react-query';
import { useAuthStore } from '@/shared/auth/store';
import { qk } from '@/shared/api/queryKeys';
import type { MessageListResponse, RealtimeMessage } from '@/shared/types';

// Канал реального времени (§транспорт). Подключается к /api/v1/ws на том же
// origin, авторизуется ПЕРВЫМ сообщением (токен не уходит в URL/логи), при обрыве
// переподключается с экспоненциальной паузой. Доставленные события кладутся в
// react-query кэш; при недоступности WS компоненты деградируют на поллинг.

interface RealtimeState {
  connected: boolean;
}

const RealtimeContext = createContext<RealtimeState>({ connected: false });

export function useRealtime(): RealtimeState {
  return useContext(RealtimeContext);
}

function wsUrl(): string {
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${proto}//${window.location.host}/api/v1/ws`;
}

/** Применяет входящее WS-событие к кэшу react-query. */
export function routeMessage(qc: QueryClient, data: RealtimeMessage): void {
  if (data.type === 'chat') {
    qc.setQueryData<MessageListResponse>(qk.messages(data.taskId), (prev) => {
      if (!prev) return prev;
      if (prev.items.some((m) => m.id === data.message.id)) return prev; // дубль
      return { ...prev, items: [...prev.items, data.message] };
    });
  } else if (data.type === 'notification') {
    qc.invalidateQueries({ queryKey: qk.notifications });
    qc.invalidateQueries({ queryKey: qk.notificationsUnread });
  }
}

const MAX_BACKOFF_MS = 30_000;
const BASE_BACKOFF_MS = 1_000;

export function RealtimeProvider({ children }: { children: ReactNode }) {
  const token = useAuthStore((s) => s.accessToken);
  const qc = useQueryClient();
  const [connected, setConnected] = useState(false);

  const wsRef = useRef<WebSocket | null>(null);
  const retryRef = useRef(0);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const closedRef = useRef(false);

  useEffect(() => {
    if (!token) return;
    if (typeof WebSocket === 'undefined') return; // среда без WS (тесты/SSR)
    closedRef.current = false;

    const connect = () => {
      if (closedRef.current) return;
      let ws: WebSocket;
      try {
        ws = new WebSocket(wsUrl());
      } catch {
        scheduleReconnect();
        return;
      }
      wsRef.current = ws;

      ws.onopen = () => {
        // Аутентификация первым сообщением.
        ws.send(JSON.stringify({ type: 'auth', token }));
      };
      ws.onmessage = (ev) => {
        try {
          const data = JSON.parse(ev.data) as RealtimeMessage;
          if (data.type === 'ready') {
            retryRef.current = 0;
            setConnected(true);
            return;
          }
          routeMessage(qc, data);
        } catch {
          /* игнорируем неразборчивый кадр */
        }
      };
      ws.onclose = () => {
        setConnected(false);
        wsRef.current = null;
        scheduleReconnect();
      };
      ws.onerror = () => {
        // onclose последует автоматически; ничего не делаем здесь.
      };
    };

    const scheduleReconnect = () => {
      if (closedRef.current) return;
      const delay = Math.min(BASE_BACKOFF_MS * 2 ** retryRef.current, MAX_BACKOFF_MS);
      retryRef.current += 1;
      timerRef.current = setTimeout(connect, delay);
    };

    connect();

    return () => {
      closedRef.current = true;
      if (timerRef.current) clearTimeout(timerRef.current);
      const ws = wsRef.current;
      wsRef.current = null;
      if (ws) {
        ws.onclose = null;
        ws.onmessage = null;
        ws.onopen = null;
        ws.onerror = null;
        try {
          ws.close();
        } catch {
          /* noop */
        }
      }
      setConnected(false);
    };
  }, [token, qc]);

  return createElement(RealtimeContext.Provider, { value: { connected } }, children);
}
