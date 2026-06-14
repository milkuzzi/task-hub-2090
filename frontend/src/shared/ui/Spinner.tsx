import { STR } from '@/shared/strings';

export function Spinner({ fullscreen = false }: { fullscreen?: boolean }) {
  const spinner = <div className="spinner">{STR.loading}</div>;
  if (fullscreen) {
    return <div className="spinner-fullscreen">{spinner}</div>;
  }
  return spinner;
}

export function EmptyState({ text }: { text: string }) {
  return <div className="empty-state">{text}</div>;
}
