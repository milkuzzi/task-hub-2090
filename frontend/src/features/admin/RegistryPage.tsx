import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/shared/api/client';
import { errorMessage } from '@/shared/api/http';
import { STR } from '@/shared/strings';
import { ConfirmDialog } from '@/shared/ui/Modal';
import { Spinner, EmptyState } from '@/shared/ui/Spinner';

type PendingAction =
  | { type: 'removeRegistry'; id: string }
  | { type: 'deleteUser'; userId: string }
  | { type: 'transferAdmin'; email: string };

export default function RegistryPage() {
  const qc = useQueryClient();

  const [email, setEmail] = useState('');
  const [fullName, setFullName] = useState('');
  const [formError, setFormError] = useState<string | null>(null);
  const [pending, setPending] = useState<PendingAction | null>(null);

  const [transferEmail, setTransferEmail] = useState('');
  const [transferError, setTransferError] = useState<string | null>(null);
  const [transferMessage, setTransferMessage] = useState<string | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ['registry'],
    queryFn: () => api.listRegistry(),
  });

  const createMutation = useMutation({
    mutationFn: () =>
      api.createRegistry({
        email,
        fullName: fullName.trim() ? fullName.trim() : null,
      }),
    onSuccess: () => {
      setEmail('');
      setFullName('');
      setFormError(null);
      qc.invalidateQueries({ queryKey: ['registry'] });
    },
    onError: (err) => {
      setFormError(errorMessage(err));
    },
  });

  const removeRegistryMutation = useMutation({
    mutationFn: (id: string) => api.deleteRegistry(id),
    onSuccess: () => {
      setPending(null);
      qc.invalidateQueries({ queryKey: ['registry'] });
    },
  });

  const deleteUserMutation = useMutation({
    mutationFn: (userId: string) => api.deleteUser(userId),
    onSuccess: () => {
      setPending(null);
      qc.invalidateQueries({ queryKey: ['registry'] });
    },
  });

  const transferMutation = useMutation({
    mutationFn: (targetEmail: string) => api.transferAdmin(targetEmail),
    onSuccess: (res) => {
      setPending(null);
      setTransferEmail('');
      setTransferError(null);
      if (res.completed) {
        setTransferMessage(STR.transferDoneImmediate);
      } else if (res.emailSent === false) {
        setTransferMessage(STR.transferEmailNotSent);
      } else {
        setTransferMessage(STR.transferDoneDeferred);
      }
      qc.invalidateQueries({ queryKey: ['registry'] });
    },
    onError: (err) => {
      setPending(null);
      setTransferMessage(null);
      setTransferError(errorMessage(err));
    },
  });

  const handleAdd = (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);
    createMutation.mutate();
  };

  const handleTransfer = (e: React.FormEvent) => {
    e.preventDefault();
    setTransferError(null);
    setTransferMessage(null);
    setPending({ type: 'transferAdmin', email: transferEmail.trim() });
  };

  const handleConfirm = () => {
    if (!pending) return;
    if (pending.type === 'removeRegistry') {
      removeRegistryMutation.mutate(pending.id);
    } else if (pending.type === 'deleteUser') {
      deleteUserMutation.mutate(pending.userId);
    } else {
      transferMutation.mutate(pending.email);
    }
  };

  const confirmMessage =
    pending?.type === 'removeRegistry'
      ? 'Убрать e-mail из реестра? Вход будет заблокирован.'
      : pending?.type === 'deleteUser'
        ? 'Удалить пользователя и весь его архив? Действие необратимо.'
        : STR.transferAdminConfirm;

  return (
    <div className="panel">
      <h1>{STR.admin}</h1>

      <form onSubmit={handleAdd}>
        <div className="field">
          <label htmlFor="reg-email">E-mail</label>
          <input
            id="reg-email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
        </div>
        <div className="field">
          <label htmlFor="reg-fullname">Имя</label>
          <input
            id="reg-fullname"
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
          />
        </div>
        <p className="muted">{STR.inviteHint}</p>
        {formError && <div className="form-error">{formError}</div>}
        <div className="form-actions">
          <button type="submit" className="btn primary" disabled={createMutation.isPending}>
            Добавить
          </button>
        </div>
      </form>

      <hr className="divider" />

      {isLoading ? (
        <Spinner />
      ) : !data || data.items.length === 0 ? (
        <EmptyState text={STR.empty} />
      ) : (
        <div className="table-scroll">
          <table className="table">
            <thead>
              <tr>
                <th>E-mail</th>
                <th>Имя</th>
                <th>MAX</th>
                <th>Админ</th>
                <th>Зарегистрирован</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((item) => (
                <tr key={item.id}>
                  <td data-label="E-mail">{item.email}</td>
                  <td data-label="Имя">{item.fullName ?? ''}</td>
                  <td data-label="MAX">{item.maxContact ?? ''}</td>
                  <td data-label="Админ">{item.isAdmin ? 'да' : 'нет'}</td>
                  <td data-label="Зарегистрирован">{item.registered ? 'да' : 'нет'}</td>
                  <td data-label="Действия">
                    <div className="form-actions">
                      <button
                        type="button"
                        className="btn"
                        onClick={() => setPending({ type: 'removeRegistry', id: item.id })}
                      >
                        Убрать из реестра
                      </button>
                      {item.userId && (
                        <button
                          type="button"
                          className="btn danger"
                          onClick={() =>
                            setPending({
                              type: 'deleteUser',
                              userId: item.userId as string,
                            })
                          }
                        >
                          Удалить пользователя и архив
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <hr className="divider" />

      <section>
        <h2>{STR.transferAdmin}</h2>
        <p className="muted">{STR.transferAdminHint}</p>
        <form onSubmit={handleTransfer}>
          <div className="field">
            <label htmlFor="transfer-email">{STR.transferAdminEmail}</label>
            <input
              id="transfer-email"
              type="email"
              value={transferEmail}
              onChange={(e) => setTransferEmail(e.target.value)}
              required
            />
          </div>
          {transferError && <div className="form-error">{transferError}</div>}
          {transferMessage && <div className="form-success">{transferMessage}</div>}
          <div className="form-actions">
            <button type="submit" className="btn primary" disabled={transferMutation.isPending}>
              {STR.transferAdmin}
            </button>
          </div>
        </form>
      </section>

      {pending && (
        <ConfirmDialog
          message={confirmMessage}
          confirmLabel={STR.confirm}
          danger={pending.type === 'deleteUser'}
          onConfirm={handleConfirm}
          onCancel={() => setPending(null)}
        />
      )}
    </div>
  );
}
