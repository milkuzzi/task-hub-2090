# Tasks — Task Collaboration & Profiles (№6, №7, №8)

Реализация по дизайну `design.md`. Порядок отражает зависимости: данные/домен → бэкенд-логика →
real-time → №6 → №8 → фронтенд → тесты/деплой. Каждая задача завершается прогоном тестов.

- [ ] 1. Данные и доменный слой (фундамент)
  - [ ] 1.1 Миграция `0003_collaboration`: таблицы `task_assignees` (+backfill из `tasks.assignee_id`, затем drop столбца), `task_messages`, `notifications`; `ALTER TYPE task_status ADD VALUE 'under_review','rework'`; `users.avatar_path`. Предусмотреть `downgrade`.
  - [ ] 1.2 ORM-модели и `app/models/__init__.py`: `TaskAssignee`, `TaskMessage`, `Notification`, поле `User.avatar_path`; заменить связь `Task.assignee` на `Task.assignees` (selectin); обновить `observer`-логику где нужно.
  - [ ] 1.3 `domain/enums.py`: добавить статусы `under_review`,`rework` (+ RU-метки), новые `Action` (`SUBMIT_REVIEW`,`DECIDE_REVIEW`,`POST_MESSAGE`); `domain/status.py`: новая матрица переходов + `is_open`.
  - [ ] 1.4 `domain/roles.py`: `role_of(..., assignee_ids, observer_ids)`; `domain/permissions.py`: матрица под новые действия и `authorize(action, role, *, is_admin=False)` с admin-override.
  - [ ] 1.5 `domain/invariants.py`: валидация мультиисполнителей (≥1, без дублей, наблюдатель∉{исполнители,постановщик}); понятные доменные ошибки.
  - _Requirements: 2, 3, 5_

- [ ] 2. Бэкенд: репозитории и сервис задач под мультиисполнителей и новый статус-поток
  - [ ] 2.1 `tasks_repo`: чтение/запись исполнителей через `task_assignees`; фильтр «Я исполнитель» по членству; адаптировать `flag_foreign_for_reassignment`/`collect_*`/`get_full`/`list_tasks` (без N+1, selectin).
  - [ ] 2.2 `task_service`: создание/редактирование с набором исполнителей; `submit_review` (assignee→under_review), `review_decision` (observer/admin→done|rework); `change_status` оставить для cancel/reopen (author/admin); согласовать `report`/attachments.
  - [ ] 2.3 Презентеры/DTO (`schemas/tasks`, `presenters`): `assignees[]` вместо `assignee`; новые статусы; `is_open` в просрочке/overdue_sweep.
  - [ ] 2.4 Роутер `tasks.py`: эндпойнты `submit-review`, `review`; обновить create/update; коды ошибок.
  - _Requirements: 2, 3, 5_

- [ ] 3. Real-time: WebSocket + чат + on-site уведомления
  - [ ] 3.1 `app/realtime/manager.py` ConnectionManager (user_id→sockets, send_to_users) + `app/api/routers/ws.py` (`/ws`, auth первым сообщением, close 1008 при ошибке).
  - [ ] 3.2 Чат: модель доступа (POST_MESSAGE), `chat_service`, эндпойнты `GET/POST /tasks/{id}/messages`; рассылка по WS участникам.
  - [ ] 3.3 `notification_center`: создание `notifications` при сообщении (исполнителям, кроме автора) и при `rework`; WS-пуш; эндпойнты `GET /notifications`, `/notifications/unread-count`, `POST /notifications/read`; пометка прочитанным при открытии задачи.
  - [ ] 3.4 Caddy (edge + taskhub-web): явный проброс `/api/v1/ws` с увеличенными таймаутами; README-заметка.
  - _Requirements: 4, 6_

- [ ] 4. №6 — создание задачи с вложениями (атомарно)
  - [ ] 4.1 `POST /tasks` → multipart (`payload` JSON + `files[]`); сервис: задача+исполнители+наблюдатели+вложения в одной транзакции, компенсация (удаление файлов) при откате; переиспользовать лимиты `attachment_service`.
  - [ ] 4.2 Тесты атомарности (успех/сбой → нет осиротевших файлов/частичной задачи).
  - _Requirements: 1_

- [ ] 5. №8 — профиль и аватары
  - [ ] 5.1 `profile_service` + роутер `users.py`: `GET/PATCH /users/me` (maxContact/displayName, валидация MAX), `PUT/DELETE /users/me/avatar` (MIME по magic-bytes, лимит `MAX_AVATAR_MB`), `GET /users/{id}/avatar`.
  - [ ] 5.2 Хранилище аватаров через `app/storage`; конфиг `MAX_AVATAR_MB`, допустимые типы.
  - _Requirements: 7, 8_

- [ ] 6. Фронтенд
  - [ ] 6.1 `useRealtime()` (WS-хук: auth-сообщение, реконнект, маршрутизация в react-query) + поллинг-фоллбэк.
  - [ ] 6.2 `Avatar` компонент (картинка/инициалы); `Bell` (счётчик+список+переход+прочтение) в `AppShell`.
  - [ ] 6.3 `TaskForm`: мультивыбор исполнителей (`UserPicker`), прикрепление вложений в форме создания.
  - [ ] 6.4 Карточка задачи: чат (лента+ввод+аватары, live), кнопки статуса по роли (готово к проверке / принять / вернуть / отмена-переоткрытие).
  - [ ] 6.5 Страница `/profile`: аватар (загрузка/удаление), MAX, display_name; ссылка в шапке.
  - [ ] 6.6 `shared/api/client.ts`, `types.ts`, `strings.ts`, `router.tsx` — новые эндпойнты/типы/строки/маршруты.
  - _Requirements: 4, 5, 6, 7, 8_

- [ ] 7. Тесты, миграция и деплой
  - [ ] 7.1 Unit: роли (мультиисполнитель), статус-переходы, права (+admin), уведомления; PBT по correctness-properties дизайна.
  - [ ] 7.2 Integration (Postgres): мультипарт-создание (успех/откат), чат+права, submit/review/rework, уведомления (счётчик/прочтение/не-себе), профиль/аватар, backfill-миграция; WS через ASGI-клиент.
  - [ ] 7.3 Frontend-тесты (Avatar/Bell/useRealtime/TaskForm).
  - [ ] 7.4 Деплой: бэкап БД → pull → пересборка backend/web → миграция (alembic) → проброс WS в Caddy → проверка чата/уведомлений/профиля в проде.
  - _Requirements: 1–8_
