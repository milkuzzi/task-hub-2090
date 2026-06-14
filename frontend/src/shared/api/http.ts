import axios, { AxiosError, type InternalAxiosRequestConfig } from 'axios';
import { useAuthStore } from '@/shared/auth/store';
import type { ApiErrorBody, TokenResponse } from '@/shared/types';

// Относительный baseURL — фронт и API за одним origin (Caddy/прокси), §13.6.3.
export const http = axios.create({ baseURL: '/api/v1' });

// Отдельный инстанс без перехватчиков — чтобы /auth/refresh не зациклился.
const raw = axios.create({ baseURL: '/api/v1' });

http.interceptors.request.use((config) => {
  const token = useAuthStore.getState().accessToken;
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

let refreshing: Promise<string | null> | null = null;

async function tryRefresh(): Promise<string | null> {
  if (!refreshing) {
    refreshing = raw
      .post<TokenResponse>('/auth/refresh')
      .then((r) => {
        useAuthStore.getState().setSession(r.data.accessToken, r.data.user);
        return r.data.accessToken;
      })
      .catch(() => {
        useAuthStore.getState().clear();
        return null;
      })
      .finally(() => {
        refreshing = null;
      });
  }
  return refreshing;
}

http.interceptors.response.use(
  (r) => r,
  async (error: AxiosError<ApiErrorBody>) => {
    const original = error.config as InternalAxiosRequestConfig & { _retried?: boolean };
    const status = error.response?.status;
    const url = original?.url ?? '';
    const isAuthCall = url.startsWith('/auth/');

    if (status === 401 && !original._retried && !isAuthCall) {
      original._retried = true;
      const token = await tryRefresh();
      if (token) {
        original.headers.Authorization = `Bearer ${token}`;
        return http(original);
      }
    }
    return Promise.reject(error);
  },
);

/** Попытка восстановить сессию по refresh-cookie при старте приложения. */
export async function bootstrapSession(): Promise<boolean> {
  const token = await tryRefresh();
  return token !== null;
}

export function errorCode(error: unknown): string | undefined {
  if (axios.isAxiosError(error)) {
    return (error.response?.data as ApiErrorBody | undefined)?.error?.code;
  }
  return undefined;
}

export function errorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    // Нет ответа от сервера — это проблема связи, а не прикладная ошибка.
    if (!error.response) {
      return 'Нет связи с сервером. Проверьте подключение и повторите попытку.';
    }
    const body = error.response.data as ApiErrorBody | undefined;
    // Ошибки валидации (422) несут конкретику по полям в details — показываем
    // её, иначе верхнеуровневый текст всегда был бы общим «Проверьте поля…».
    const details = body?.error?.details;
    if (details && details.length > 0) {
      const msgs = details.map((d) => d.message).filter(Boolean);
      if (msgs.length > 0) return msgs.join('; ');
    }
    if (body?.error?.message) return body.error.message;
  }
  return 'Произошла ошибка. Повторите попытку.';
}
