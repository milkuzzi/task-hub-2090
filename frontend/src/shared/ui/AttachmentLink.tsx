import { api } from '@/shared/api/client';
import { saveBlob } from '@/shared/lib/download';
import type { Attachment } from '@/shared/types';

// Скачивание файла — через авторизованный запрос (Bearer), а не прямую ссылку:
// эндпойнт скачивания требует токен, которого нет у обычного <a href> (§13.5.6).
export function AttachmentLink({ taskId, att }: { taskId: string; att: Attachment }) {
  if (att.kind === 'url') {
    return (
      <a href={att.url ?? '#'} target="_blank" rel="noreferrer">
        {att.url}
      </a>
    );
  }
  const onClick = async (e: React.MouseEvent) => {
    e.preventDefault();
    const blob = await api.downloadAttachment(taskId, att.id);
    saveBlob(blob, att.filename ?? 'file');
  };
  return (
    <a href="#" onClick={onClick}>
      {att.filename}
    </a>
  );
}
