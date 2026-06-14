// Аватар пользователя: инициалы из отображаемого имени (по умолчанию) либо
// картинка. Картинка задаётся одним из двух способов:
//   - `src` — прямой URL (например, object URL предпросмотра в профиле);
//   - `userId` — аватар грузится с аутентифицированного эндпойнта как blob через
//     useAvatarUrl (Bearer → object URL, кэш per-userId). На 404/ошибке — инициалы.
// Если ни src, ни userId не заданы (или картинка не загрузилась) — рисуем инициалы.

import { useAvatarUrl } from './useAvatarUrl';

export function initialsOf(name: string | null | undefined): string {
  return (name ?? '')
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0]!.toUpperCase())
    .join('');
}

interface AvatarViewProps {
  name: string | null | undefined;
  src?: string | null;
  size?: number;
  title?: string;
}

function AvatarView({ name, src, size = 32, title }: AvatarViewProps) {
  const initials = initialsOf(name) || '•';
  const style = { width: size, height: size, fontSize: Math.round(size * 0.4) };
  if (src) {
    return (
      <img
        className="avatar avatar-img"
        src={src}
        alt={name ?? ''}
        title={title ?? name ?? undefined}
        style={{ width: size, height: size }}
      />
    );
  }
  return (
    <span
      className="avatar avatar-initials"
      style={style}
      title={title ?? name ?? undefined}
      aria-hidden
    >
      {initials}
    </span>
  );
}

// Вынесено в отдельный компонент: хук useAvatarUrl (useQuery) вызывается только
// когда реально нужен сетевой аватар, поэтому Avatar без userId не требует
// QueryClientProvider.
function FetchedAvatar({ userId, name, size, title }: { userId: string } & AvatarViewProps) {
  const url = useAvatarUrl(userId);
  return <AvatarView name={name} src={url} size={size} title={title} />;
}

interface AvatarProps extends AvatarViewProps {
  // Если задан — аватар подгружается с эндпойнта (для чата задачи и т.п.).
  userId?: string | null;
}

export function Avatar({ name, src, userId, size = 32, title }: AvatarProps) {
  if (!src && userId) {
    return <FetchedAvatar userId={userId} name={name} size={size} title={title} />;
  }
  return <AvatarView name={name} src={src} size={size} title={title} />;
}
