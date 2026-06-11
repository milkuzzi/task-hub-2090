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
  search: 'Поиск по ID',
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

  // Прочее
  empty: 'Нет задач для отображения.',
  loading: 'Загрузка…',
  taskUnavailable: 'Задача недоступна.',
  daysToDeadline: 'Дней до ближайшего дедлайна',
  deadlinePassed: 'дедлайн прошёл',
} as const;

export const STATUS_LABEL: Record<string, string> = {
  in_progress: STR.status_in_progress,
  done: STR.status_done,
  cancelled: STR.status_cancelled,
};
