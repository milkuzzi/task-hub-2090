import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '@/shared/api/client';
import { STR } from '@/shared/strings';
import { errorMessage } from '@/shared/api/http';
import { formatDeadline } from '@/shared/lib/date';
import { isVisuallyOverdue } from '@/shared/lib/overdue';
import { useAuthStore } from '@/shared/auth/store';
import type { CreateTaskInput, ReviewDecision, TaskStatus, UpdateTaskInput } from '@/shared/types';
import { StatusBadge, OverdueBadge, ReadyBadge, ReassignBadge } from '@/shared/ui/Badge';
import { ConfirmDialog } from '@/shared/ui/Modal';
import { Spinner, EmptyState } from '@/shared/ui/Spinner';
import { AttachmentLink } from '@/shared/ui/AttachmentLink';
import TaskForm from './TaskForm';
import DeadlineProgress from './DeadlineProgress';
import TaskChat from './TaskChat';

// Клиентский предел на размер вложения (бэкенд может иметь более строгий лимит).
const MAX_FILE_SIZE = 25 * 1024 * 1024;

function isClosed(status: TaskStatus): boolean {
  return status === 'done' || status === 'cancelled';
}

export default function TaskCardPage() {
  const { id } = useParams();
  const me = useAuthStore((s) => s.user);
  const qc = useQueryClient();
  const navigate = useNavigate();

  const [editing, setEditing] = useState(false);
  const [reportText, setReportText] = useState('');
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [confirmCancel, setConfirmCancel] = useState(false);
  const [actionError, setActionError] = useState('');

  const { data: task, isLoading, isError } = useQuery({
    queryKey: ['task', id],
    queryFn: () => api.getTask(id!),
  });

  // При открытии карточки помечаем связанные с задачей уведомления прочитанными
  // (явный вызов с фронта — чище, чем сайд-эффект в GET карточки на бэкенде).
  useEffect(() => {
    if (!id) return;
    api
      .markReadForTask(id)
      .then(() => {
        qc.invalidateQueries({ queryKey: ['notifications'] });
      })
      .catch(() => {
        /* не критично для отображения задачи */
      });
  }, [id, qc]);

  const invalidateTask = () => {
    qc.invalidateQueries({ queryKey: ['task', id] });
    qc.invalidateQueries({ queryKey: ['tasks'] });
  };

  const onError = (err: unknown) => setActionError(errorMessage(err));

  const updateMutation = useMutation({
    mutationFn: (input: UpdateTaskInput) => api.updateTask(id!, input),
    onSuccess: () => {
      setEditing(false);
      setActionError('');
      invalidateTask();
    },
    onError,
  });

  const statusMutation = useMutation({
    mutationFn: (status: TaskStatus) => api.changeStatus(id!, status),
    onSuccess: invalidateTask,
    onError,
  });

  const submitReviewMutation = useMutation({
    mutationFn: () => api.submitReview(id!),
    onSuccess: invalidateTask,
    onError,
  });

  const reviewMutation = useMutation({
    mutationFn: (decision: ReviewDecision) => api.reviewDecision(id!, decision),
    onSuccess: invalidateTask,
    onError,
  });

  const deleteMutation = useMutation({
    mutationFn: () => api.deleteTask(id!),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['tasks'] });
      navigate('/author');
    },
    onError,
  });

  const reportMutation = useMutation({
    mutationFn: (text: string) => api.addReport(id!, text),
    onSuccess: () => {
      setReportText('');
      invalidateTask();
    },
    onError,
  });

  const attachTaskMutation = useMutation({
    mutationFn: (file: File) => {
      const form = new FormData();
      form.append('file', file);
      return api.addAttachment(id!, 'task', form);
    },
    onSuccess: invalidateTask,
    onError,
  });

  const attachReportMutation = useMutation({
    mutationFn: (file: File) => {
      const form = new FormData();
      form.append('file', file);
      return api.addAttachment(id!, 'report', form);
    },
    onSuccess: invalidateTask,
    onError,
  });

  if (isLoading) return <Spinner />;
  if (isError || !task) return <EmptyState text={STR.taskUnavailable} />;

  const isAdmin = !!me?.isAdmin;
  const isAuthor = task.author.id === me?.id;
  const isAssignee = task.assignees.some((a) => a.id === me?.id);
  const isObserver = task.observers.some((o) => o.id === me?.id);
  const canManage = isAuthor || isAdmin; // правка/удаление/отмена/переоткрытие
  const canReview = isObserver || isAdmin; // приёмка
  const canSubmitReview = isAssignee && (task.status === 'in_progress' || task.status === 'rework');

  const handleFilePick = (file: File | undefined, mutate: (file: File) => void) => {
    if (!file) return;
    if (file.size > MAX_FILE_SIZE) {
      setActionError('Файл слишком большой. Максимальный размер — 25 МБ.');
      return;
    }
    setActionError('');
    mutate(file);
  };

  return (
    <div className="panel">
      <div className="between">
        <h1>
          Задача №{task.seqNo} · ID {task.code}
        </h1>
        <div className="row">
          <StatusBadge status={task.status} />
          {isVisuallyOverdue(task) && <OverdueBadge />}
          {task.needsReassignment && <ReassignBadge />}
        </div>
      </div>

      <div className="field">
        <label>{STR.fTitle}</label>
        <div className="field-value">{task.title}</div>
      </div>

      <div className="field">
        <label>{STR.fDescription}</label>
        <div className="field-value">{task.description || '—'}</div>
      </div>

      <div className="field">
        <label>{STR.fDeadline}</label>
        <div className="field-value">{formatDeadline(task.deadline, task.deadlineHasTime)}</div>
        <DeadlineProgress item={task} />
      </div>

      <div className="field">
        <label>{STR.fAssignees}</label>
        {task.assignees.length === 0 ? (
          <div className="field-value">—</div>
        ) : (
          <div className="chip-list">
            {task.assignees.map((a) => (
              <span className="chip" key={a.id}>
                {a.displayName}
                {a.isDeleted ? ' (удалён)' : ''}
              </span>
            ))}
          </div>
        )}
      </div>

      <div className="field">
        <label>{STR.fAuthor}</label>
        <div className="field-value">{task.author.displayName}</div>
      </div>

      <div className="field">
        <label>{STR.fObservers}</label>
        {task.observers.length === 0 ? (
          <div className="field-value">—</div>
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
          <ul className="attach-list">
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
          <div className="field-value">{task.report.text || '—'}</div>
          {task.report.ready && (
            <div>
              <ReadyBadge />
            </div>
          )}
          {task.report.attachments.length > 0 && (
            <ul className="attach-list">
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

      {/* Действия по статусу — зависят от роли и текущего статуса. */}
      <section className="task-action-section">
        <div className="task-action-header">
          {canSubmitReview && (
            <button
              className="btn primary"
              disabled={submitReviewMutation.isPending}
              onClick={() => submitReviewMutation.mutate()}
            >
              {STR.submitReview}
            </button>
          )}
          {canReview && task.status === 'under_review' && (
            <>
              <button
                className="btn primary"
                disabled={reviewMutation.isPending}
                onClick={() => reviewMutation.mutate('accept')}
              >
                {STR.reviewAccept}
              </button>
              <button
                className="btn"
                disabled={reviewMutation.isPending}
                onClick={() => reviewMutation.mutate('rework')}
              >
                {STR.reviewRework}
              </button>
            </>
          )}
          {canManage && !isClosed(task.status) && (
            <button
              className="btn danger"
              disabled={statusMutation.isPending}
              onClick={() => setConfirmCancel(true)}
            >
              {STR.cancelTask}
            </button>
          )}
          {canManage && isClosed(task.status) && (
            <button
              className="btn"
              disabled={statusMutation.isPending}
              onClick={() => statusMutation.mutate('in_progress')}
            >
              {STR.reopen}
            </button>
          )}
        </div>
      </section>

      {canManage && (
        <section className="task-action-section">
          <div className="task-action-header">
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
                assigneeIds: task.assignees.map((a) => a.id),
                observerIds: task.observers.map((o) => o.id),
              }}
              submitLabel={STR.save}
              onSubmit={(input: CreateTaskInput) => updateMutation.mutate(input)}
              busy={updateMutation.isPending}
              error={updateMutation.isError ? errorMessage(updateMutation.error) : ''}
              surface="plain"
            />
          )}

          <div className="field">
            <label htmlFor="task-attachment">Прикрепить файл</label>
            <input
              id="task-attachment"
              type="file"
              disabled={attachTaskMutation.isPending}
              onChange={(e) => {
                handleFilePick(e.target.files?.[0], attachTaskMutation.mutate);
                e.target.value = '';
              }}
            />
            {attachTaskMutation.isPending && <span className="muted">Загрузка файла…</span>}
          </div>
        </section>
      )}

      {isAssignee && (
        <section className="task-action-section">
          <div className="field">
            <label htmlFor="task-report-text">{STR.fReport}</label>
            <textarea
              id="task-report-text"
              value={reportText}
              onChange={(e) => setReportText(e.target.value)}
            />
          </div>
          <div className="form-actions">
            <button
              className="btn"
              disabled={reportMutation.isPending}
              onClick={() => reportMutation.mutate(reportText)}
            >
              {STR.addReport}
            </button>
          </div>
          <div className="field">
            <label htmlFor="report-attachment">Прикрепить файл к отчёту</label>
            <input
              id="report-attachment"
              type="file"
              disabled={attachReportMutation.isPending}
              onChange={(e) => {
                handleFilePick(e.target.files?.[0], attachReportMutation.mutate);
                e.target.value = '';
              }}
            />
            {attachReportMutation.isPending && <span className="muted">Загрузка файла…</span>}
          </div>
        </section>
      )}

      <TaskChat taskId={task.id} />

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

      {confirmCancel && (
        <ConfirmDialog
          message="Перевести задачу в статус «Отменена»?"
          confirmLabel={STR.confirm}
          danger
          onConfirm={() => {
            setConfirmCancel(false);
            statusMutation.mutate('cancelled');
          }}
          onCancel={() => setConfirmCancel(false)}
        />
      )}
    </div>
  );
}
