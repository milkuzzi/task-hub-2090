import { useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '@/shared/api/client';
import { STR, STATUS_LABEL } from '@/shared/strings';
import { errorMessage } from '@/shared/api/http';
import { formatDeadline } from '@/shared/lib/date';
import { isVisuallyOverdue } from '@/shared/lib/overdue';
import { useAuthStore } from '@/shared/auth/store';
import type { CreateTaskInput, TaskStatus, UpdateTaskInput } from '@/shared/types';
import { StatusBadge, OverdueBadge, ReadyBadge, ReassignBadge } from '@/shared/ui/Badge';
import { ConfirmDialog } from '@/shared/ui/Modal';
import { Spinner, EmptyState } from '@/shared/ui/Spinner';
import { AttachmentLink } from '@/shared/ui/AttachmentLink';
import TaskForm from './TaskForm';

const STATUSES: TaskStatus[] = ['in_progress', 'done', 'cancelled'];

export default function TaskCardPage() {
  const { id } = useParams();
  const me = useAuthStore((s) => s.user);
  const qc = useQueryClient();
  const navigate = useNavigate();

  const [editing, setEditing] = useState(false);
  const [reportText, setReportText] = useState('');
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [actionError, setActionError] = useState('');

  const { data: task, isLoading, isError } = useQuery({
    queryKey: ['task', id],
    queryFn: () => api.getTask(id!),
  });

  const invalidateTask = () => {
    qc.invalidateQueries({ queryKey: ['task', id] });
    qc.invalidateQueries({ queryKey: ['tasks'] });
  };

  const updateMutation = useMutation({
    mutationFn: (input: UpdateTaskInput) => api.updateTask(id!, input),
    onSuccess: () => {
      setEditing(false);
      setActionError('');
      invalidateTask();
    },
    onError: (err) => setActionError(errorMessage(err)),
  });

  const statusMutation = useMutation({
    mutationFn: (status: TaskStatus) => api.changeStatus(id!, status),
    onSuccess: invalidateTask,
    onError: (err) => setActionError(errorMessage(err)),
  });

  const deleteMutation = useMutation({
    mutationFn: () => api.deleteTask(id!),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['tasks'] });
      navigate('/author');
    },
    onError: (err) => setActionError(errorMessage(err)),
  });

  const reportMutation = useMutation({
    mutationFn: (text: string) => api.addReport(id!, text),
    onSuccess: () => {
      setReportText('');
      invalidateTask();
    },
    onError: (err) => setActionError(errorMessage(err)),
  });

  const readyMutation = useMutation({
    mutationFn: () => api.markReady(id!),
    onSuccess: invalidateTask,
    onError: (err) => setActionError(errorMessage(err)),
  });

  const attachTaskMutation = useMutation({
    mutationFn: (file: File) => {
      const form = new FormData();
      form.append('file', file);
      return api.addAttachment(id!, 'task', form);
    },
    onSuccess: invalidateTask,
    onError: (err) => setActionError(errorMessage(err)),
  });

  const attachReportMutation = useMutation({
    mutationFn: (file: File) => {
      const form = new FormData();
      form.append('file', file);
      return api.addAttachment(id!, 'report', form);
    },
    onSuccess: invalidateTask,
    onError: (err) => setActionError(errorMessage(err)),
  });

  if (isLoading) return <Spinner />;
  if (isError || !task) return <EmptyState text={STR.taskUnavailable} />;

  const role =
    task.author.id === me?.id ? 'author' : task.assignee.id === me?.id ? 'assignee' : 'observer';

  return (
    <div className="panel">
      <div className="row between">
        <h2>
          Задача №{task.seqNo} · ID {task.code}
        </h2>
        <div className="row">
          <StatusBadge status={task.status} />
          {isVisuallyOverdue(task) && <OverdueBadge />}
          {task.needsReassignment && <ReassignBadge />}
        </div>
      </div>

      <div className="field">
        <label>{STR.fTitle}</label>
        <div>{task.title}</div>
      </div>

      <div className="field">
        <label>{STR.fDescription}</label>
        <div>{task.description || '—'}</div>
      </div>

      <div className="field">
        <label>{STR.fDeadline}</label>
        <div>{formatDeadline(task.deadline, task.deadlineHasTime)}</div>
      </div>

      <div className="field">
        <label>{STR.fAssignee}</label>
        <div>
          {task.assignee.displayName}
          {task.assignee.isDeleted ? ' (удалён)' : ''}
        </div>
      </div>

      <div className="field">
        <label>{STR.fAuthor}</label>
        <div>{task.author.displayName}</div>
      </div>

      <div className="field">
        <label>{STR.fObservers}</label>
        {task.observers.length === 0 ? (
          <div>—</div>
        ) : (
          <div className="chip-list">
            {task.observers.map((o) => (
              <span className="chip" key={o.id}>
                {o.displayName}
                {o.isDeleted ? ' (удалён)' : ''}
              </span>
            ))}
          </div>
        )}
      </div>

      {task.attachments.length > 0 && (
        <div className="field">
          <label>Вложения</label>
          <ul>
            {task.attachments.map((a) => (
              <li key={a.id}>
                <AttachmentLink taskId={task.id} att={a} />
              </li>
            ))}
          </ul>
        </div>
      )}

      {task.report && (
        <div className="field">
          <label>{STR.fReport}</label>
          <div>{task.report.text || '—'}</div>
          {task.report.ready && <ReadyBadge />}
          {task.report.attachments.length > 0 && (
            <ul>
              {task.report.attachments.map((a) => (
                <li key={a.id}>
                  <AttachmentLink taskId={task.id} att={a} />
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {actionError && <div className="form-error">{actionError}</div>}

      {role === 'author' && (
        <div className="panel">
          <div className="row between">
            <button className="btn" onClick={() => setEditing((v) => !v)}>
              {editing ? STR.cancel : STR.edit}
            </button>
            <button className="btn danger" onClick={() => setConfirmDelete(true)}>
              {STR.delete}
            </button>
          </div>

          {editing && (
            <TaskForm
              initial={{
                title: task.title,
                description: task.description,
                dueAt: task.deadline,
                dueMode: task.deadlineHasTime ? 'datetime' : 'date',
                assigneeId: task.assignee.id,
                observerIds: task.observers.map((o) => o.id),
              }}
              submitLabel={STR.save}
              onSubmit={(input: CreateTaskInput) => updateMutation.mutate(input)}
              busy={updateMutation.isPending}
              error={updateMutation.isError ? errorMessage(updateMutation.error) : ''}
            />
          )}

          <div className="field">
            <label>{STR.fStatus}</label>
            <select
              value={task.status}
              onChange={(e) => statusMutation.mutate(e.target.value as TaskStatus)}
            >
              {STATUSES.map((s) => (
                <option key={s} value={s}>
                  {STATUS_LABEL[s] ?? s}
                </option>
              ))}
            </select>
          </div>

          <div className="field">
            <label>Прикрепить файл</label>
            <input
              type="file"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) attachTaskMutation.mutate(file);
              }}
            />
          </div>
        </div>
      )}

      {role === 'assignee' && (
        <div className="panel">
          <div className="field">
            <label>{STR.fReport}</label>
            <textarea value={reportText} onChange={(e) => setReportText(e.target.value)} />
          </div>
          <div className="row">
            <button
              className="btn"
              disabled={reportMutation.isPending}
              onClick={() => reportMutation.mutate(reportText)}
            >
              {STR.addReport}
            </button>
            <button
              className="btn primary"
              disabled={readyMutation.isPending}
              onClick={() => readyMutation.mutate()}
            >
              {STR.markReady}
            </button>
          </div>
          <div className="field">
            <label>Прикрепить файл к отчёту</label>
            <input
              type="file"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) attachReportMutation.mutate(file);
              }}
            />
          </div>
        </div>
      )}

      {confirmDelete && (
        <ConfirmDialog
          message="Удалить задачу?"
          confirmLabel={STR.delete}
          danger
          onConfirm={() => {
            setConfirmDelete(false);
            deleteMutation.mutate();
          }}
          onCancel={() => setConfirmDelete(false)}
        />
      )}
    </div>
  );
}
