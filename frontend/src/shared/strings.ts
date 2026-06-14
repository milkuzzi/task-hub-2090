// Единый источник русских строк. Фраза отказа — дословная константа (§3, §13.6.3).

export const STR = {
  // Дословно из ТЗ — изменять нельзя (закреплено тестом backend и frontend).
  noAccess: 'Извините, у вас нет доступа к сервису.',
  accessListWarning: 'Регистрация возможна только для адресов из утверждённого списка.',

  appTitle: 'Поручения · школа № 2090',

  // Навигация
  tabAuthor: 'Я постановщик',
  tabAssignee: 'Я исполнитель',
  tabObserver: 'Я наблюдатель',
  admin: 'Администрирование',
  logout: 'Выйти',
  addTask: 'Добавить задачу',

  // Статусы
  status_in_progress: 'В работе',
  status_done: 'Выполнена',
  status_cancelled: 'Отменена',
  overdue: 'Просрочена',
  needsReassignment: 'Требуется переназначение исполнителя',
  markedReady: 'Готовность отмечена',

  // Поля
  fTitle: 'Название',
  fDescription: 'Описание',
  fDeadline: 'Срок',
  fAssignee: 'Исполнитель',
  fAuthor: 'Постановщик',
  fObservers: 'Наблюдатели',
  fStatus: 'Статус',
  fReady: 'Готовность',
  fReport: 'Информация о выполнении',

  // Действия
  save: 'Сохранить',
  cancel: 'Отмена',
  delete: 'Удалить',
  confirm: 'Подтвердить',
  print: 'Печать',
  edit: 'Изменить',
  addReport: 'Добавить отчёт',
  markReady: 'Отписаться о готовности',

  // Auth
  login: 'Вход',
  register: 'Регистрация',
  forgotPassword: 'Забыли пароль?',
  email: 'E-mail',
  password: 'Пароль',
  newPassword: 'Новый пароль',

  // Администрирование: приглашения и передача администрирования
  inviteHint: 'Пользователь получит письмо со ссылкой для установки пароля.',
  transferAdmin: 'Передать администрирование',
  transferAdminEmail: 'E-mail нового администратора',
  transferAdminHint:
    'Новый администратор получит права. После передачи вы станете обычным пользователем (данные сохранятся).',
  transferAdminConfirm:
    'Передать администрирование этому пользователю? Вы перестанете быть администратором.',
  transferDoneImmediate: 'Администрирование передано. Вы больше не администратор.',
  transferDoneDeferred:
    'Приглашение отправлено. Передача завершится после установки пароля новым администратором.',
  transferEmailNotSent:
    'Назначение выполнено, но письмо не отправилось. Попробуйте переотправить позже.',

  // Прочее
  empty: 'Нет задач для отображения.',
  loading: 'Загрузка…',
  taskUnavailable: 'Задача недоступна.',
  daysToDeadline: 'Дней до ближайшего дедлайна',
  timeToDeadline: 'До ближайшего дедлайна',
  goToNearestDeadline: 'Перейти к задаче',
  searchPlaceholder: 'Поиск по названию или ID…',
  nothingFound: 'Ничего не найдено.',
  deadlinePassed: 'дедлайн прошёл',
} as const;

export const STATUS_LABEL: Record<string, string> = {
  in_progress: STR.status_in_progress,
  done: STR.status_done,
  cancelled: STR.status_cancelled,
};
