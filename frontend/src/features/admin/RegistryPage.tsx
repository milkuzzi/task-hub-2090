import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/shared/api/client';
import { errorMessage } from '@/shared/api/http';
import { STR } from '@/shared/strings';
import { ConfirmDialog } from '@/shared/ui/Modal';
import { Spinner, EmptyState } from '@/shared/ui/Spinner';

type PendingAction =
  | { type: 'removeRegistry'; id: string }
  | { type: 'deleteUser'; userId: string };

export default function RegistryPage() {
  const qc = useQueryClient();

  const [email, setEmail] = useState('');
  const [fullName, setFullName] = useState('');
  const [maxContact, setMaxContact] = useState('');
  const [isAdmin, setIsAdmin] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [pending, setPending] = useState<PendingAction | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ['registry'],
    queryFn: () => api.listRegistry(),
  });

  const createMutation = useMutation({
    mutationFn: () =>
      api.createRegistry({
        email,
        fullName: fullName.trim() ? fullName.trim() : null,
        maxContact: maxContact.trim() ? maxContact.trim() : null,
        isAdmin,
      }),
    onSuccess: () => {
      setEmail('');
      setFullName('');
      setMaxContact('');
      setIsAdmin(false);
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

  const handleAdd = (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);
    createMutation.mutate();
  };

  const handleConfirm = () => {
    if (!pending) return;
    if (pending.type === 'removeRegistry') {
      removeRegistryMutation.mutate(pending.id);
    } else {
      deleteUserMutation.mutate(pending.userId);
    }
  };

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
        <div className="field">
          <label htmlFor="reg-max">MAX</label>
          <input
            id="reg-max"
            value={maxContact}
            onChange={(e) => setMaxContact(e.target.value)}
          />
        </div>
        <div className="field checkbox">
          <input
            id="reg-admin"
            type="checkbox"
            checked={isAdmin}
            onChange={(e) => setIsAdmin(e.target.checked)}
          />
          <span>Админ</span>
        </div>
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

      {pending && (
        <ConfirmDialog
          message={
            pending.type === 'removeRegistry'
              ? 'Убрать e-mail из реестра? Вход будет заблокирован.'
              : 'Удалить пользователя и весь его архив? Действие необратимо.'
          }
          confirmLabel={STR.confirm}
          danger={pending.type === 'deleteUser'}
          onConfirm={handleConfirm}
          onCancel={() => setPending(null)}
        />
      )}
    </div>
  );
}
