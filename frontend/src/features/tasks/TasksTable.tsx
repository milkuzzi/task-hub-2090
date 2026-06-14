import type { TaskListItem, TaskRole } from '@/shared/types';
import { StatusBadge, OverdueBadge, ReadyBadge, ReassignBadge } from '@/shared/ui/Badge';
import { formatDeadline } from '@/shared/lib/date';
import { isVisuallyOverdue } from '@/shared/lib/overdue';
import DeadlineProgress from './DeadlineProgress';
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

function SortHeader({
  sort,
  field,
  label,
  className,
  onToggle,
}: {
  sort: SortState;
  field: SortField;
  label: string;
  className?: string;
  onToggle: (f: SortField) => void;
}) {
  return (
    <th className={className} aria-sort={ariaSort(sort, field)}>
      <button type="button" className="table-sort" onClick={() => onToggle(field)}>
        {label}
        {arrow(sort, field)}
      </button>
    </th>
  );
}

export default function TasksTable({ items, role, sort, onToggle, onRowClick }: TasksTableProps) {
  const showAuthorColumn = role === 'assignee';
  const personField: SortField = showAuthorColumn ? 'author' : 'assignee';
  const personLabel = showAuthorColumn ? 'Постановщик' : 'Исполнитель';
  const showReadiness = role === 'author';

  const openFromKeyboard = (event: React.KeyboardEvent<HTMLTableRowElement>, id: string) => {
    if (event.key !== 'Enter' && event.key !== ' ') {
      return;
    }
    event.preventDefault();
    onRowClick(id);
  };

  return (
    <div className="table-scroll">
      <table className="table">
        <thead>
          <tr>
            <SortHeader className="num" sort={sort} field="seqNo" label="№" onToggle={onToggle} />
            <SortHeader className="num" sort={sort} field="code" label="ID" onToggle={onToggle} />
            <SortHeader sort={sort} field="title" label="Название" onToggle={onToggle} />
            <SortHeader sort={sort} field={personField} label={personLabel} onToggle={onToggle} />
            <SortHeader
              className="num"
              sort={sort}
              field="deadline"
              label="Срок"
              onToggle={onToggle}
            />
            <th>До срока</th>
            <SortHeader sort={sort} field="status" label="Статус" onToggle={onToggle} />
            <th>Просрочка</th>
            {showReadiness ? <th>Готовность</th> : null}
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr
              key={item.id}
              className="clickable-row"
              tabIndex={0}
              role="button"
              onClick={() => onRowClick(item.id)}
              onKeyDown={(event) => openFromKeyboard(event, item.id)}
            >
              <td className="num" data-label="№">
                {item.seqNo}
              </td>
              <td className="num" data-label="ID">
                {item.code}
              </td>
              <td data-label="Название">
                <div className="cell-stack">
                  <span>{item.title}</span>
                  {item.needsReassignment ? <ReassignBadge /> : null}
                </div>
              </td>
              <td data-label={personLabel}>
                {showAuthorColumn ? item.author.displayName : item.assignee.displayName}
              </td>
              <td className="num" data-label="Срок">
                {formatDeadline(item.deadline, item.deadlineHasTime)}
              </td>
              <td data-label="До срока">
                <DeadlineProgress item={item} />
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
