import { STR } from '@/shared/strings';

export function Spinner() {
  return <div className="spinner">{STR.loading}</div>;
}

export function EmptyState({ text }: { text: string }) {
  return <div className="spinner">{text}</div>;
}
