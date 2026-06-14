import { useState } from 'react';
import type { CreateTaskInput, DueMode } from '@/shared/types';
import { STR } from '@/shared/strings';
import { toInputValue, fromInputValue } from '@/shared/lib/date';
import { AssigneePicker } from './UserPicker';
import ObserversPicker from './UserPicker';

interface TaskFormProps {
  initial?: Partial<CreateTaskInput> & { title?: string };
  submitLabel: string;
  onSubmit: (input: CreateTaskInput) => void;
  busy?: boolean;
  error?: string;
  surface?: 'panel' | 'plain';
}

export default function TaskForm({
  initial,
  submitLabel,
  onSubmit,
  busy,
  error,
  surface = 'panel',
}: TaskFormProps) {
  const [title, setTitle] = useState<string>(initial?.title ?? '');
  const [description, setDescription] = useState<string>(initial?.description ?? '');
  const [dueMode, setDueMode] = useState<DueMode>(initial?.dueMode ?? 'datetime');
  const [deadline, setDeadline] = useState<string>(
    toInputValue(initial?.dueAt, (initial?.dueMode ?? 'datetime') === 'datetime'),
  );
  const [assigneeId, setAssigneeId] = useState<string>(initial?.assigneeId ?? '');
  const [observerIds, setObserverIds] = useState<string[]>(initial?.observerIds ?? []);
  const [links, setLinks] = useState<string[]>(initial?.links ?? []);
  const [localError, setLocalError] = useState<string>('');

  const changeMode = (mode: DueMode) => {
    setDueMode(mode);
    if (deadline) {
      // Re-normalize the existing input value to the new mode if possible.
      setDeadline(toInputValue(fromInputValue(deadline, dueMode === 'datetime'), mode === 'datetime'));
    }
  };

  const addLink = () => setLinks([...links, '']);
  const updateLink = (idx: number, val: string) => {
    const next = links.slice();
    next[idx] = val;
    setLinks(next);
  };
  const removeLink = (idx: number) => setLinks(links.filter((_, i) => i !== idx));

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) {
      setLocalError('Укажите название задачи');
      return;
    }
    if (!assigneeId) {
      setLocalError('Выберите исполнителя');
      return;
    }
    if (!deadline) {
      setLocalError('Укажите срок');
      return;
    }
    setLocalError('');
    const input: CreateTaskInput = {
      title: title.trim(),
      description: description || null,
      dueAt: fromInputValue(deadline, dueMode === 'datetime'),
      dueMode,
      assigneeId,
      observerIds,
      links: links.filter((l) => l.trim().length > 0),
    };
    onSubmit(input);
  };

  return (
    <form
      className={surface === 'panel' ? 'panel task-form' : 'task-form'}
      onSubmit={handleSubmit}
    >
      <div className="field">
        <label htmlFor="task-title">{STR.fTitle}</label>
        <input id="task-title" value={title} onChange={(e) => setTitle(e.target.value)} />
      </div>

      <div className="field">
        <label htmlFor="task-description">{STR.fDescription}</label>
        <textarea
          id="task-description"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
        />
      </div>

      <div className="field">
        <label htmlFor="task-due-mode">Режим срока</label>
        <select
          id="task-due-mode"
          value={dueMode}
          onChange={(e) => changeMode(e.target.value as DueMode)}
        >
          <option value="datetime">Дата и время</option>
          <option value="date">Только дата</option>
        </select>
      </div>

      <div className="field">
        <label htmlFor="task-deadline">{STR.fDeadline}</label>
        <input
          id="task-deadline"
          type={dueMode === 'datetime' ? 'datetime-local' : 'date'}
          value={deadline}
          onChange={(e) => setDeadline(e.target.value)}
        />
      </div>

      <div className="field">
        <label htmlFor="task-assignee">{STR.fAssignee}</label>
        <AssigneePicker id="task-assignee" value={assigneeId} onChange={setAssigneeId} />
      </div>

      <div className="field">
        <label id="task-observers-label">{STR.fObservers}</label>
        <ObserversPicker
          labelledBy="task-observers-label"
          value={observerIds}
          onChange={setObserverIds}
        />
      </div>

      <div className="field">
        <label htmlFor="task-links">Ссылки</label>
        {links.map((link, idx) => (
          <div className="form-row" key={idx}>
            <input
              id={idx === 0 ? 'task-links' : undefined}
              type="url"
              value={link}
              placeholder="https://"
              aria-label={`Ссылка ${idx + 1}`}
              onChange={(e) => updateLink(idx, e.target.value)}
            />
            <button type="button" className="btn" onClick={() => removeLink(idx)}>
              {STR.delete}
            </button>
          </div>
        ))}
        <button type="button" className="btn" onClick={addLink}>
          + ссылка
        </button>
      </div>

      {localError && <div className="form-error">{localError}</div>}
      {error && <div className="form-error">{error}</div>}

      <div className="form-actions">
        <button type="submit" className="btn primary" disabled={busy}>
          {submitLabel}
        </button>
      </div>
    </form>
  );
}
