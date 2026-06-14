import { useState } from 'react';
import type { TaskListItem } from '@/shared/types';
import { STATUS_LABEL } from '@/shared/strings';

export type SortField = 'seqNo' | 'code' | 'title' | 'deadline' | 'status' | 'assignee' | 'author';

export interface SortState {
  field: SortField | null;
  order: 'asc' | 'desc';
}

export function useTableSort(): { sort: SortState; toggle: (f: SortField) => void } {
  const [sort, setSort] = useState<SortState>({ field: null, order: 'asc' });

  const toggle = (f: SortField): void => {
    setSort((prev) => {
      if (prev.field === f) {
        return { field: f, order: prev.order === 'asc' ? 'desc' : 'asc' };
      }
      return { field: f, order: 'asc' };
    });
  };

  return { sort, toggle };
}

function compareByField(a: TaskListItem, b: TaskListItem, field: SortField): number {
  switch (field) {
    case 'seqNo':
      return a.seqNo - b.seqNo;
    case 'code':
      return a.code.localeCompare(b.code, 'ru', { numeric: true });
    case 'title':
      return a.title.localeCompare(b.title, 'ru');
    case 'deadline':
      return new Date(a.deadline).getTime() - new Date(b.deadline).getTime();
    case 'status':
      return (STATUS_LABEL[a.status] ?? a.status).localeCompare(STATUS_LABEL[b.status] ?? b.status, 'ru');
    case 'assignee':
      return a.assignees
        .map((x) => x.displayName)
        .join(', ')
        .localeCompare(b.assignees.map((x) => x.displayName).join(', '), 'ru');
    case 'author':
      return a.author.displayName.localeCompare(b.author.displayName, 'ru');
    default:
      return 0;
  }
}

export function sortItems(items: TaskListItem[], sort: SortState): TaskListItem[] {
  const copy = items.slice();

  if (sort.field === null) {
    copy.sort((a, b) => {
      const aOpen = a.status === 'done' || a.status === 'cancelled' ? 1 : 0;
      const bOpen = b.status === 'done' || b.status === 'cancelled' ? 1 : 0;
      if (aOpen !== bOpen) {
        return aOpen - bOpen;
      }
      return new Date(a.deadline).getTime() - new Date(b.deadline).getTime();
    });
    return copy;
  }

  const field = sort.field;
  const dir = sort.order === 'asc' ? 1 : -1;
  copy.sort((a, b) => compareByField(a, b, field) * dir);
  return copy;
}
