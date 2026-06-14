import { useEffect, useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '@/shared/api/client';
import { qk } from '@/shared/api/queryKeys';
import { errorMessage } from '@/shared/api/http';
import { STR } from '@/shared/strings';
import { useAuthStore } from '@/shared/auth/store';
import { Avatar } from '@/shared/ui/Avatar';
import { Spinner } from '@/shared/ui/Spinner';
import type { Profile } from '@/shared/types';

export default function ProfilePage() {
  const qc = useQueryClient();
  const setUser = useAuthStore((s) => s.setUser);
  const authUser = useAuthStore((s) => s.user);

  const fileInput = useRef<HTMLInputElement>(null);
  const [displayName, setDisplayName] = useState('');
  const [maxContact, setMaxContact] = useState('');
  const [formError, setFormError] = useState<string | null>(null);
  const [savedMessage, setSavedMessage] = useState<string | null>(null);
  const [avatarError, setAvatarError] = useState<string | null>(null);
  // Локальный предпросмотр только что выбранного файла (object URL).
  const [preview, setPreview] = useState<string | null>(null);

  const { data: profile, isLoading } = useQuery({
    queryKey: qk.profile,
    queryFn: () => api.getMe(),
  });

  // Инициализируем поля формы значениями профиля при загрузке.
  useEffect(() => {
    if (profile) {
      setDisplayName(profile.displayName);
      setMaxContact(profile.maxContact ?? '');
    }
  }, [profile]);

  // Отзываем object URL предпросмотра на размонтировании/замене.
  useEffect(() => {
    return () => {
      if (preview) URL.revokeObjectURL(preview);
    };
  }, [preview]);

  // После изменения аватара обновляем кэш профиля и пере-загружаем видимые
  // аватары этого пользователя (инвалидируем blob-кэш per-userId).
  const refreshAfterAvatar = (next: Profile) => {
    qc.setQueryData(qk.profile, next);
    if (authUser) qc.invalidateQueries({ queryKey: qk.avatar(authUser.id) });
  };

  const saveMutation = useMutation({
    mutationFn: () =>
      api.updateMe({ displayName: displayName.trim(), maxContact: maxContact.trim() }),
    onSuccess: (next) => {
      setFormError(null);
      setSavedMessage(STR.profileSaved);
      qc.setQueryData(qk.profile, next);
      // Имя в шапке/сайдбаре берётся из auth-store — синхронизируем.
      if (authUser) setUser({ ...authUser, displayName: next.displayName });
    },
    onError: (err) => {
      setSavedMessage(null);
      setFormError(errorMessage(err));
    },
  });

  const uploadMutation = useMutation({
    mutationFn: (file: File) => api.uploadAvatar(file),
    onSuccess: (next) => {
      setAvatarError(null);
      refreshAfterAvatar(next);
    },
    onError: (err) => setAvatarError(errorMessage(err)),
  });

  const deleteMutation = useMutation({
    mutationFn: () => api.deleteAvatar(),
    onSuccess: (next) => {
      setAvatarError(null);
      setPreview(null);
      refreshAfterAvatar(next);
    },
    onError: (err) => setAvatarError(errorMessage(err)),
  });

  const onPickFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = ''; // позволяем выбрать тот же файл повторно
    if (!file) return;
    setPreview((prev) => {
      if (prev) URL.revokeObjectURL(prev);
      return URL.createObjectURL(file);
    });
    uploadMutation.mutate(file);
  };

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setSavedMessage(null);
    saveMutation.mutate();
  };

  if (isLoading || !profile) return <Spinner />;

  const hasAvatar = profile.hasAvatar;

  return (
    <section className="profile-page" aria-label={STR.profileTitle}>
      <h1>{STR.profileTitle}</h1>

      <div className="profile-avatar-block">
        <h2>{STR.avatar}</h2>
        <div className="profile-avatar-row">
          {/* Предпросмотр (object URL) приоритетнее; иначе грузим по userId. */}
          <Avatar
            name={profile.displayName}
            src={preview}
            userId={preview ? null : hasAvatar ? profile.id : null}
            size={96}
          />
          <div className="profile-avatar-actions">
            <input
              ref={fileInput}
              type="file"
              accept="image/png,image/jpeg,image/webp"
              style={{ display: 'none' }}
              onChange={onPickFile}
              data-testid="avatar-file-input"
            />
            <button
              type="button"
              className="btn"
              disabled={uploadMutation.isPending}
              onClick={() => fileInput.current?.click()}
            >
              {uploadMutation.isPending
                ? STR.avatarUploading
                : hasAvatar
                  ? STR.avatarReplace
                  : STR.avatarUpload}
            </button>
            {hasAvatar && (
              <button
                type="button"
                className="btn"
                disabled={deleteMutation.isPending}
                onClick={() => deleteMutation.mutate()}
              >
                {STR.avatarRemove}
              </button>
            )}
            <p className="muted">{STR.avatarHint}</p>
            {avatarError && <div className="form-error">{avatarError}</div>}
          </div>
        </div>
      </div>

      <form className="profile-form" onSubmit={onSubmit}>
        <label>
          {STR.email}
          <input type="email" value={profile.email} disabled readOnly />
        </label>

        <label>
          Отображаемое имя
          <input
            type="text"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            maxLength={120}
          />
        </label>

        <label>
          {STR.fMaxContact}
          <input
            type="text"
            value={maxContact}
            onChange={(e) => setMaxContact(e.target.value)}
            maxLength={100}
            placeholder={STR.fMaxContact}
          />
          <span className="muted">{STR.maxContactHint}</span>
        </label>

        {formError && <div className="form-error">{formError}</div>}
        {savedMessage && <div className="form-success">{savedMessage}</div>}

        <button type="submit" className="btn primary" disabled={saveMutation.isPending}>
          {STR.save}
        </button>
      </form>
    </section>
  );
}
