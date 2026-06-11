import type { TaskListItem, TaskRole } from '@/shared/types';
import { StatusBadge, OverdueBadge, ReadyBadge, ReassignBadge } from '@/shared/ui/Badge';
import { formatDeadline } from '@/shared/lib/date';
import { isVisuallyOverdue } from '@/shared/lib/overdue';
import type { SortField, SortState } from './useTableSort';

interface TasksTableProps {
  items: TaskListItem[];
  role: TaskRole;
  sort: SortState;
  onToggle: (f: SortField) => void;
  onRowClick: (id: string) => void;
}

function ariaSort(sort: SortState, field: SortField): 'ascending' | 'descending' | undefined {
  if (sort.field !== field) {
    return undefined;
  }
  return sort.order === 'asc' ? 'ascending' : 'descending';
}

function arrow(sort: SortState, field: SortField): string {
  if (sort.field !== field) {
    return '';
  }
  return sort.order === 'asc' ? ' ▲' : ' ▼';
}

export default function TasksTable({ items, role, sort, onToggle, onRowClick }: TasksTableProps) {
  const showAuthorColumn = role === 'assignee';
  const personField: SortField = showAuthorColumn ? 'author' : 'assignee';
  const personLabel = showAuthorColumn ? 'Постановщик' : 'Исполнитель';
  const showReadiness = role === 'author';

  return (
    <div className="table-scroll">
    <table className="table">
      <thead>
        <tr>
          <th
            className="num"
            aria-sort={ariaSort(sort, 'seqNo')}
            onClick={() => onToggle('seqNo')}
          >
            №{arrow(sort, 'seqNo')}
          </th>
          <th
            className="num"
            aria-sort={ariaSort(sort, 'code')}
            onClick={() => onToggle('code')}
          >
            ID{arrow(sort, 'code')}
          </th>
          <th aria-sort={ariaSort(sort, 'title')} onClick={() => onToggle('title')}>
            Название{arrow(sort, 'title')}
          </th>
          <th aria-sort={ariaSort(sort, personField)} onClick={() => onToggle(personField)}>
            {personLabel}
            {arrow(sort, personField)}
          </th>
          <th
            className="num"
            aria-sort={ariaSort(sort, 'deadline')}
            onClick={() => onToggle('deadline')}
          >
            Срок{arrow(sort, 'deadline')}
          </th>
          <th aria-sort={ariaSort(sort, 'status')} onClick={() => onToggle('status')}>
            Статус{arrow(sort, 'status')}
          </th>
          <th>Просрочка</th>
          {showReadiness ? <th>Готовность</th> : null}
        </tr>
      </thead>
      <tbody>
        {items.map((item) => (
          <tr key={item.id} onClick={() => onRowClick(item.id)}>
            <td className="num" data-label="№">
              {item.seqNo}
            </td>
            <td className="num" data-label="ID">
              {item.code}
            </td>
            <td data-label="Название">
              {item.title}
              {item.needsReassignment ? <ReassignBadge /> : null}
            </td>
            <td data-label={personLabel}>
              {showAuthorColumn ? item.author.displayName : item.assignee.displayName}
            </td>
            <td className="num" data-label="Срок">
              {formatDeadline(item.deadline, item.deadlineHasTime)}
            </td>
            <td data-label="Статус">
              <StatusBadge status={item.status} />
            </td>
            <td data-label="Просрочка">
              {isVisuallyOverdue(item) ? <OverdueBadge /> : <span className="muted">—</span>}
            </td>
            {showReadiness ? (
              <td data-label="Готовность">{item.assigneeMarkedReady ? <ReadyBadge /> : '—'}</td>
            ) : null}
          </tr>
        ))}
      </tbody>
    </table>
    </div>
  );
}
