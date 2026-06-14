import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/shared/api/client';
import { qk } from '@/shared/api/queryKeys';

// Аватары отдаёт аутентифицированный эндпойнт (`GET /users/{id}/avatar`), поэтому
// обычный <img src> с Bearer-заголовком не работает. Грузим картинку как blob
// через axios-клиент (он добавляет Authorization), кэшируем blob per-userId в
// react-query и превращаем в object URL. На 404 (нет аватара) или любой ошибке
// возвращаем null — компонент рисует инициалы. Object URL отзывается на cleanup,
// чтобы не течь памятью.
export function useAvatarUrl(userId: string | null | undefined): string | null {
  const enabled = Boolean(userId);

  const { data: blob } = useQuery<Blob | null>({
    queryKey: qk.avatar(userId ?? ''),
    queryFn: async () => {
      try {
        return await api.fetchAvatarBlob(userId!);
      } catch {
        // 404 «нет аватара» и любые иные ошибки → заглушка-инициалы.
        return null;
      }
    },
    enabled,
    // Аватар меняется редко — держим в кэше, не дёргаем эндпойнт на каждый рендер.
    staleTime: 5 * 60_000,
    retry: false,
  });

  const [url, setUrl] = useState<string | null>(null);

  useEffect(() => {
    if (!blob || blob.size === 0) {
      setUrl(null);
      return;
    }
    const objectUrl = URL.createObjectURL(blob);
    setUrl(objectUrl);
    return () => URL.revokeObjectURL(objectUrl);
  }, [blob]);

  return url;
}
