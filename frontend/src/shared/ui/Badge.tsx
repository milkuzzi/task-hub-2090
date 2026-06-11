import type { TaskStatus } from '@/shared/types';
import { STATUS_LABEL, STR } from '@/shared/strings';

export function StatusBadge({ status }: { status: TaskStatus }) {
  return <span className={`badge status-${status}`}>{STATUS_LABEL[status]}</span>;
}

export function OverdueBadge() {
  return <span className="badge overdue">{STR.overdue}</span>;
}

export function ReadyBadge() {
  return <span className="badge ready">{STR.markedReady}</span>;
}

export function ReassignBadge() {
  return <span className="badge reassign">{STR.needsReassignment}</span>;
}
